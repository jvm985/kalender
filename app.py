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
CACHE_FILE = os.path.join(DATA_DIR, "kalender_cache.json")

def get_week_num(y, m, d):
    return datetime.date(y, m, d).isocalendar()[1]

def load_data(jaar):
    if os.path.exists(CACHE_FILE):
        if (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))).days < 30:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                if str(jaar) in cache: return cache[str(jaar)]
    
    day_events = {}; v_ranges = []
    
    # Vertalingen voor veelvoorkomende Engelstalige feestdagen van de API
    translations = {
        "New Year's Day": "Nieuwjaar",
        "Easter Monday": "Paasmaandag",
        "Labour Day": "Dag van de Arbeid",
        "Ascension Day": "O.L.H. Hemelvaart",
        "Whit Monday": "Pinkstermaandag",
        "Belgian National Day": "Nationale feestdag",
        "Assumption of Mary": "O.L.V. Hemelvaart",
        "All Saints' Day": "Allerheiligen",
        "Armistice Day": "Wapenstilstand",
        "Christmas Day": "Kerstmis",
        "St. Stephen's Day": "Tweede Kerstdag"
    }

    try:
        r = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{jaar}/BE", timeout=5)
        if r.status_code == 200:
            for h in r.json():
                date_obj = datetime.date.fromisoformat(h['date'])
                if date_obj.month not in day_events: day_events[date_obj.month] = {}
                if date_obj.day not in day_events[date_obj.month]: day_events[date_obj.month][date_obj.day] = []
                
                name = h.get('localName') or h.get('name')
                # Forceer Nederlands als we een vertaling hebben
                name = translations.get(h.get('name'), name)
                day_events[date_obj.month][date_obj.day].append(name)
    except: pass
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://www.vlaanderen.be/onderwijs-en-vorming/wat-mag-en-moet-op-school/schoolvakanties-vrije-dagen-en-afwezigheden/schoolvakanties"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            content = r.text
            maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
            
            seen = set()
            for v_name in ["Herfstvakantie", "Kerstvakantie", "Krokusvakantie", "Paasvakantie", "Zomervakantie"]:
                # Verbeterde regex: flexibel voor één of twee maandnamen
                pattern = rf"{v_name}:.*?(\d+)(?:\s+([a-z]+))?.*?(\d+)\s+([a-z]+)\s+(\d{{4}})"
                matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    d1, m1_str, d2, m2_str, ey_str = m.groups()
                    ey = int(ey_str)
                    m2 = maanden_dict.get(m2_str.lower())
                    # Als de eerste maand ontbreekt, gebruik de tweede
                    m1 = maanden_dict.get(m1_str.lower()) if (m1_str and m1_str.lower() in maanden_dict) else m2
                    
                    if m1 and m2:
                        sy = ey
                        if m1 > m2: sy = ey - 1
                        
                        if sy == jaar or ey == jaar:
                            v_range = {
                                'start': datetime.date(sy, m1, int(d1)).isoformat(), 
                                'end': datetime.date(ey, m2, int(d2)).isoformat(), 
                                'name': v_name
                            }
                            # Vermijd duplicaten
                            v_key = (v_range['start'], v_range['end'], v_range['name'])
                            if v_key not in seen:
                                v_ranges.append(v_range)
                                seen.add(v_key)
    except Exception as e:
        print(f"Scraping error: {e}")
    
    data = {"events": day_events, "ranges": v_ranges}
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f: cache = json.load(f)
        except: pass
    cache[str(jaar)] = data
    with open(CACHE_FILE, 'w') as f: json.dump(cache, f)
    return data

def generate_pdf(jaar, paper_size='A3', orientation='landscape', show_birthdays=True, show_holidays=True, show_vacations=True, is_schoolyear=False):
    # Als het een schooljaar is, hebben we data nodig van jaar en jaar+1
    years_to_load = [jaar, jaar + 1] if is_schoolyear else [jaar]
    
    day_events = {} # format: {year: {month: {day: [events]}}}
    holiday_dates = set() # format: (year, month, day)
    v_ranges = []
    
    for y in years_to_load:
        online_data = load_data(y)
        if show_holidays:
            for m_str, days in online_data['events'].items():
                m = int(m_str)
                if y not in day_events: day_events[y] = {}
                if m not in day_events[y]: day_events[y][m] = {}
                for d_str, v in days.items():
                    d = int(d_str)
                    day_events[y][m][d] = v
                    holiday_dates.add((y, m, d))
        
        if show_vacations:
            for r in online_data['ranges']:
                s_date = datetime.date.fromisoformat(r['start'])
                e_date = datetime.date.fromisoformat(r['end'])
                v_ranges.append({'start': s_date, 'end': e_date, 'name': r['name']})

    if show_birthdays and current_user.is_authenticated:
        all_birthdays = Birthday.query.filter_by(user_id=current_user.id).all()
        for y in years_to_load:
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
    
    # Bepaal de maanden en jaren die we gaan tekenen
    months_to_draw = []
    if is_schoolyear:
        # Sept t/m Dec van jaar, Jan t/m Aug van jaar+1
        for m in range(9, 13): months_to_draw.append((jaar, m))
        for m in range(1, 9): months_to_draw.append((jaar + 1, m))
    else:
        # Jan t/m Dec van jaar
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
            
            # Check of het een vakantie of feestdag is voor de markeerstift
            is_holiday = show_holidays and (cur_year, cdate.month, cdate.day) in holiday_dates
            
            active_vacations = [r for r in v_ranges if r['start'] <= cdate <= r['end']]
            has_line = len(active_vacations) > 0 or is_holiday
            
            if has_line:
                # Blauwe lijn, doorzichtig, bovenaan het vak
                ctx.set_source_rgba(0.2, 0.6, 0.8, 0.3)
                bar_height = (8 if paper_size == 'A3' else 6) # ~1/3 van hoogte dagnummers
                ctx.rectangle(x, y, cell_w_pt, bar_height)
                ctx.fill()
                
                for r in active_vacations:
                    if cdate == r['start']:
                        ctx.set_source_rgb(0,0,0)
                        ctx.set_font_size(8 if paper_size == 'A3' else 6)
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
                    # Terug van bovenaan starten
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
