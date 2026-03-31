import io
import os
import re
import json
import datetime
import calendar
import requests
import cairo
from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = Flask(__name__)
# Gebruik een vaste secret key voor sessie-persistentie na herstart
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'kalender-secret-123')

# Sessie instellingen voor HTTPS en Iframe support
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',  # Nodig voor cross-site context in iframes
)

# Zorg dat Flask HTTPS begrijpt achter Nginx en Docker
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

@app.after_request
def add_cookie_headers(response):
    # Voeg 'Partitioned' toe aan Set-Cookie headers voor iframe support (CHIPS)
    cookies = response.headers.getlist('Set-Cookie')
    response.headers.remove('Set-Cookie')
    for cookie in cookies:
        if 'Partitioned' not in cookie:
            cookie += '; Partitioned'
        response.headers.add('Set-Cookie', cookie)
    return response

# Database Setup
DATA_DIR = '/data'
if not os.path.exists(DATA_DIR) or not os.access(DATA_DIR, os.W_OK):
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(DATA_DIR, 'kalender.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# OAuth Setup
oauth = OAuth(app)
GOOGLE_CLIENT_ID = '339058057860-i6ne31mqs27mqm2ulac7al9vi26pmgo1.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'GOCSPX-missing-secret')

google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    birthdays = db.relationship('Birthday', backref='user', lazy=True)

class Birthday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Kalender Logica ---
MM_TO_PT = 72 / 25.4
MONTH_NAMES = ["", "Januari", "Februari", "Maart", "April", "Mei", "Juni", "Juli", "Augustus", "September", "Oktober", "November", "December"]
DAY_NAMES = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
CACHE_FILE = os.path.join(DATA_DIR, "kalender_cache_v2.json")

def get_week_num(y, m, d):
    return datetime.date(y, m, d).isocalendar()[1]

def load_all_vlaanderen_data():
    """Scraapt alle beschikbare schooljaren en feestdagen van Vlaanderen.be"""
    if os.path.exists(CACHE_FILE):
        # Cache voor 7 dagen
        if (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))).days < 7:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)

    url = "https://www.vlaanderen.be/onderwijs-en-vorming/wat-mag-en-moet-op-school/schoolvakanties-vrije-dagen-en-afwezigheden/schoolvakanties"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    data = {"events": [], "ranges": []}
    maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content = r.text
            # Stap 1: Vind alle secties per schooljaar (bijv. 2025-2026)
            # We splitsen op de koppen
            sections = re.split(r'<(?:h[234]|span)[^>]*>(?:\s*Schooljaar\s*|Schoolvakanties\s*)?(\d{4}-\d{4}).*?</(?:h[234]|span)>', content, flags=re.IGNORECASE)
            
            # sections[0] is de intro tekst
            # daarna hebben we paren: [ "2025-2026", "sectie content", "2026-2027", "sectie content" ]
            for i in range(1, len(sections), 2):
                sj_label = sections[i]
                sj_content = sections[i+1]
                
                # Zoek alle <li> elementen in deze sectie
                items = re.findall(r'<li>(.*?)</li>', sj_content, re.DOTALL)
                for item in items:
                    # Strip HTML tags
                    clean_item = re.sub(r'<.*?>', '', item).strip()
                    if not clean_item: continue
                    
                    # Match bereik: "Naam: van 27 oktober tot en met 2 november 2025"
                    # Regex groepen: 1=Naam, 2=d1, 3=m1, 4=d2, 5=m2, 6=jaar
                    range_match = re.search(r'^(.*?):\s*van\s+.*?\b(\d+)\s+([a-z]+)?.*?\b(\d+)\s+([a-z]+)\s+(\d{4})', clean_item, re.IGNORECASE)
                    if range_match:
                        name, d1, m1_str, d2, m2_str, ey_str = range_match.groups()
                        ey = int(ey_str)
                        m2 = maanden_dict.get(m2_str.lower())
                        m1 = maanden_dict.get(m1_str.lower()) if (m1_str and m1_str.lower() in maanden_dict) else m2
                        if m1 and m2:
                            sy = ey
                            if m1 > m2: sy = ey - 1
                            data["ranges"].append({
                                "start": datetime.date(sy, m1, int(d1)).isoformat(),
                                "end": datetime.date(ey, m2, int(d2)).isoformat(),
                                "name": name.strip()
                            })
                        continue

                    # Match losse dag: "Wapenstilstand: dinsdag 11 november 2025"
                    # Of: "Pinkstermaandag: 25 mei 2026"
                    day_match = re.search(r'^(.*?):\s*.*?\b(\d+)\s+([a-z]+)\s+(\d{4})', clean_item, re.IGNORECASE)
                    if day_match:
                        name, d, m_str, y_str = day_match.groups()
                        m = maanden_dict.get(m_str.lower())
                        if m:
                            data["events"].append({
                                "date": datetime.date(int(y_str), m, int(d)).isoformat(),
                                "name": name.strip()
                            })

            with open(CACHE_FILE, 'w') as f:
                json.dump(data, f)
    except Exception as e:
        print(f"Scraping error: {e}")
        
    return data

def generate_pdf(jaar, paper_size='A3', orientation='landscape', show_birthdays=True, show_holidays=True, show_vacations=True, is_schoolyear=False):
    all_data = load_all_vlaanderen_data()
    
    day_events = {} # {year: {month: {day: [names]}}}
    holiday_dates = set() # {(year, month, day)}
    v_ranges = []
    
    target_years = [jaar, jaar + 1] if is_schoolyear else [jaar]
    
    # Verwerk vakantie-bereiken
    if show_vacations:
        for r in all_data["ranges"]:
            s_date = datetime.date.fromisoformat(r['start'])
            e_date = datetime.date.fromisoformat(r['end'])
            # Alleen bereiken die overlap hebben met onze target jaren
            if s_date.year in target_years or e_date.year in target_years:
                v_ranges.append({'start': s_date, 'end': e_date, 'name': r['name']})

    # Verwerk losse feestdagen
    if show_holidays:
        for e in all_data["events"]:
            d_obj = datetime.date.fromisoformat(e['date'])
            if d_obj.year in target_years:
                y, m, d = d_obj.year, d_obj.month, d_obj.day
                if y not in day_events: day_events[y] = {}
                if m not in day_events[y]: day_events[y][m] = {}
                if d not in day_events[y][m]: day_events[y][m][d] = []
                day_events[y][m][d].append(e['name'])
                holiday_dates.add((y, m, d))

    # Verjaardagen (vallen elk jaar op dezelfde dag)
    if show_birthdays and current_user.is_authenticated:
        all_birthdays = Birthday.query.filter_by(user_id=current_user.id).all()
        for y in target_years:
            if y not in day_events: day_events[y] = {}
            for b in all_birthdays:
                if b.month not in day_events[y]: day_events[y][b.month] = {}
                if b.day not in day_events[y][b.month]: day_events[y][b.month][b.day] = []
                day_events[y][b.month][b.day].append(b.name)

    pw_mm, ph_mm = (420, 297) if paper_size == 'A3' else (297, 210)
    if orientation == 'portrait': pw_mm, ph_mm = ph_mm, pw_mm
    pw_pt, ph_pt = pw_mm * MM_TO_PT, ph_mm * MM_TO_PT
    margin_mm = 15
    grid_w_mm, grid_h_mm = pw_mm - 2 * margin_mm, ph_mm - 2 * margin_mm - 30
    cell_w_pt, cell_h_pt = (grid_w_mm / 7) * MM_TO_PT, (grid_h_mm / 6) * MM_TO_PT
    
    output = io.BytesIO()
    surface = cairo.PDFSurface(output, pw_pt, ph_pt)
    ctx = cairo.Context(surface)
    
    months_to_draw = []
    if is_schoolyear:
        for m in range(9, 13): months_to_draw.append((jaar, m))
        for m in range(1, 9): months_to_draw.append((jaar + 1, m))
    else:
        for m in range(1, 13): months_to_draw.append((jaar, m))

    for cur_year, month in months_to_draw:
        ctx.set_source_rgb(1, 1, 1); ctx.paint()
        sx, sy = margin_mm * MM_TO_PT, margin_mm * MM_TO_PT + 25 * MM_TO_PT
        ctx.set_source_rgb(0, 0, 0); ctx.set_line_width(1.0)
        for r in range(6):
            for c in range(7): ctx.rectangle(sx + c * cell_w_pt, sy + r * cell_h_pt, cell_w_pt, cell_h_pt)
        ctx.stroke()
        ctx.select_font_face("LM Sans 10", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(24 if paper_size == 'A3' else 18)
        txt = f"{MONTH_NAMES[month]} {cur_year}"
        _, _, w, _, _, _ = ctx.text_extents(txt)
        ctx.move_to(sx + (7*cell_w_pt)/2 - w/2, sy - 10 * MM_TO_PT); ctx.show_text(txt)
        ctx.set_font_size(14 if paper_size == 'A3' else 10)
        for i, dn in enumerate(DAY_NAMES):
            _, _, w, _, _, _ = ctx.text_extents(dn); ctx.move_to(sx + i * cell_w_pt + cell_w_pt/2 - w/2, sy - 4 * MM_TO_PT); ctx.show_text(dn)
        
        fday = datetime.date(cur_year, month, 1); fwd = fday.weekday()
        for k in range(42):
            col, row = k % 7, k // 7; x, y = sx + col * cell_w_pt, sy + row * cell_h_pt; cdate = fday + datetime.timedelta(days=k - fwd)
            is_holiday = show_holidays and (cur_year, cdate.month, cdate.day) in holiday_dates
            active_vacations = [r for r in v_ranges if r['start'] <= cdate <= r['end']]
            has_line = len(active_vacations) > 0 or is_holiday
            
            if has_line:
                ctx.set_source_rgba(0.2, 0.6, 0.8, 0.3)
                bar_height = (8 if paper_size == 'A3' else 6)
                ctx.rectangle(x, y, cell_w_pt, bar_height)
                ctx.fill()
                
                for r in active_vacations:
                    if cdate == r['start']:
                        ctx.set_source_rgb(0,0,0); ctx.set_font_size(8 if paper_size == 'A3' else 6)
                        ctx.move_to(x + 3*MM_TO_PT, y + bar_height + 6); ctx.show_text(r['name'])

            ctx.set_font_size(18 if paper_size == 'A3' else 12); ctx.set_source_rgb(0,0,0) if cdate.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
            dn_txt = str(cdate.day); _, yb, w, h, _, _ = ctx.text_extents(dn_txt); ctx.move_to(x + cell_w_pt - 2*MM_TO_PT - w, y + 2*MM_TO_PT - yb); ctx.show_text(dn_txt)
            
            if col == 0:
                ctx.set_font_size(8 if paper_size == 'A3' else 6); ctx.set_source_rgb(0.5, 0.5, 0.5)
                wn_txt = f"W{get_week_num(cdate.year, cdate.month, cdate.day)}"; _, yb, w, h, _, _ = ctx.text_extents(wn_txt)
                ctx.move_to(sx - w - 4*MM_TO_PT, y + 4*MM_TO_PT - yb); ctx.show_text(wn_txt)

            if cdate.month == month:
                evs = day_events.get(cur_year, {}).get(cdate.month, {}).get(cdate.day, [])
                if evs:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(9 if paper_size == 'A3' else 7)
                    y_offset = 7*MM_TO_PT
                    for idx, name in enumerate(evs): 
                        ctx.move_to(x + 3*MM_TO_PT, y + y_offset + idx * (11 if paper_size == 'A3' else 8))
                        ctx.show_text(name)
        ctx.show_page()
    surface.finish(); output.seek(0)
    return output

# --- Google Auth (Robuuste methode met ID Token) ---
@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    try:
        data = request.get_json()
        token = data.get('token')
        if not token:
            return {"error": "Geen token ontvangen"}, 400
        
        # Verifieer de ID Token (geen client_secret nodig!)
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        
        # Gebruiker identificeren
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', email)

        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User(google_id=google_id, email=email, name=name)
            db.session.add(user); db.session.commit()
        
        login_user(user)
        return {"success": True, "name": name}
    except Exception as e:
        return {"error": f"Google verificatie mislukt: {str(e)}"}, 401

@app.route('/')
def index():
    user_birthdays = Birthday.query.filter_by(user_id=current_user.id).order_by(Birthday.month, Birthday.day).all() if current_user.is_authenticated else []
    return render_template('index.html', year=datetime.date.today().year, user_birthdays=user_birthdays)

@app.route('/login')
def login():
    # Forceer HTTPS redirect
    redirect_uri = url_for('authorize', _external=True, _scheme='https')
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo') or google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()
        user = User.query.filter_by(google_id=user_info['sub']).first()
        if not user:
            user = User(google_id=user_info['sub'], email=user_info['email'], name=user_info['name'])
            db.session.add(user); db.session.commit()
        login_user(user); return redirect('/')
    except Exception as e:
        flash(f"Login mislukt: {e}"); return redirect('/')

@app.route('/logout')
def logout(): logout_user(); return redirect('/')

@app.route('/birthday/add', methods=['POST'])
@login_required
def add_birthday():
    db.session.add(Birthday(user_id=current_user.id, name=request.form.get('name'), day=int(request.form.get('day')), month=int(request.form.get('month')))); db.session.commit()
    return redirect('/')

@app.route('/birthday/delete/<int:id>')
@login_required
def delete_birthday(id):
    b = Birthday.query.get(id)
    if b and b.user_id == current_user.id: db.session.delete(b); db.session.commit()
    return redirect('/')

@app.route('/pdf_preview')
def pdf_preview():
    pdf = generate_pdf(int(request.args.get('year', 2026)), request.args.get('paper_size', 'A3'), request.args.get('orientation', 'landscape'), request.args.get('show_birthdays') == 'true', request.args.get('show_holidays') == 'true', request.args.get('show_vacations') == 'true', request.args.get('is_schoolyear') == 'true')
    
    response = make_response(send_file(pdf, mimetype='application/pdf'))
    # Geef expliciet toestemming voor inbedden en voorkom MIME-sniffing
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Forceer dat de browser het als een apart document behandelt in de iframe context
    response.headers['Content-Disposition'] = 'inline; filename="preview.pdf"'
    
    return response

@app.route('/generate', methods=['POST'])
def generate():
    pdf = generate_pdf(int(request.form.get('year', 2026)), request.form.get('paper_size', 'A3'), request.form.get('orientation', 'landscape'), 'show_birthdays' in request.form, 'show_holidays' in request.form, 'show_vacations' in request.form, 'is_schoolyear' in request.form)
    return send_file(pdf, download_name=f"kalender.pdf", as_attachment=True)

# Initialize database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
