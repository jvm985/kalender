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
    SESSION_COOKIE_SAMESITE='Lax',
)

# Zorg dat Flask HTTPS begrijpt achter Nginx en Docker
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Database Setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/kalender.db'
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
CACHE_FILE = "/data/kalender_cache.json"

def get_week_num(y, m, d):
    return datetime.date(y, m, d).isocalendar()[1]

def load_data(jaar):
    if os.path.exists(CACHE_FILE):
        if (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))).days < 30:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                if str(jaar) in cache: return cache[str(jaar)]
    
    day_events = {}; v_ranges = []
    try:
        r = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{jaar}/BE", timeout=5)
        if r.status_code == 200:
            for h in r.json():
                date_obj = datetime.date.fromisoformat(h['date'])
                if date_obj.month not in day_events: day_events[date_obj.month] = {}
                if date_obj.day not in day_events[date_obj.month]: day_events[date_obj.month][date_obj.day] = []
                day_events[date_obj.month][date_obj.day].append(h['localName'])
    except: pass
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get("https://onderwijs.vlaanderen.be/nl/schoolvakanties", headers=headers, timeout=5)
        if r.status_code == 200:
            content = r.text
            patterns = [(r"Herfstvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Herfstvakantie"), (r"Kerstvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Kerstvakantie"), (r"Krokusvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Krokusvakantie"), (r"Paasvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Paasvakantie"), (r"Zomervakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Zomervakantie")]
            maanden = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
            for p_raw, v_name in patterns:
                p = p_raw.format(jaar=jaar)
                matches = re.finditer(p, content, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    d1, m1_str, d2, m2_str, _ = m.groups()
                    m1, m2 = maanden.get(m1_str.lower()), maanden.get(m2_str.lower())
                    if m1 and m2:
                        v_ranges.append({'start': datetime.date(jaar, m1, int(d1)).isoformat(), 'end': datetime.date(jaar, m2, int(d2)).isoformat(), 'name': v_name})
    except: pass
    
    data = {"events": day_events, "ranges": v_ranges}
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f: cache = json.load(f)
        except: pass
    cache[str(jaar)] = data
    with open(CACHE_FILE, 'w') as f: json.dump(cache, f)
    return data

def generate_pdf(jaar, paper_size='A3', orientation='landscape', show_birthdays=True, show_holidays=True, show_vacations=True):
    online_data = load_data(jaar)
    day_events = {}
    if show_holidays:
        day_events = {int(m): {int(d): v for d, v in days.items()} for m, days in online_data['events'].items()}
    v_ranges = []
    if show_vacations:
        v_ranges = [{'start': datetime.date.fromisoformat(r['start']), 'end': datetime.date.fromisoformat(r['end']), 'name': r['name']} for r in online_data['ranges']]
    
    if show_birthdays and current_user.is_authenticated:
        for b in Birthday.query.filter_by(user_id=current_user.id).all():
            if b.month not in day_events: day_events[b.month] = {}
            if b.day not in day_events[b.month]: day_events[b.month][b.day] = []
            day_events[b.month][b.day].append(b.name)

    pw_mm, ph_mm = (420, 297) if paper_size == 'A3' else (297, 210)
    if orientation == 'portrait': pw_mm, ph_mm = ph_mm, pw_mm
    pw_pt, ph_pt = pw_mm * MM_TO_PT, ph_mm * MM_TO_PT
    margin_mm = 15
    grid_w_mm, grid_h_mm = pw_mm - 2 * margin_mm, ph_mm - 2 * margin_mm - 30
    cell_w_pt, cell_h_pt = (grid_w_mm / 7) * MM_TO_PT, (grid_h_mm / 6) * MM_TO_PT
    
    output = io.BytesIO()
    surface = cairo.PDFSurface(output, pw_pt, ph_pt)
    ctx = cairo.Context(surface)
    for month in range(1, 13):
        ctx.set_source_rgb(1, 1, 1); ctx.paint()
        sx, sy = margin_mm * MM_TO_PT, margin_mm * MM_TO_PT + 25 * MM_TO_PT
        ctx.set_source_rgb(0, 0, 0); ctx.set_line_width(1.0)
        for r in range(6):
            for c in range(7): ctx.rectangle(sx + c * cell_w_pt, sy + r * cell_h_pt, cell_w_pt, cell_h_pt)
        ctx.stroke()
        ctx.select_font_face("LM Sans 10", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(24 if paper_size == 'A3' else 18)
        txt = f"{MONTH_NAMES[month]} {jaar}"
        _, _, w, _, _, _ = ctx.text_extents(txt)
        ctx.move_to(sx + (7*cell_w_pt)/2 - w/2, sy - 10 * MM_TO_PT); ctx.show_text(txt)
        ctx.set_font_size(14 if paper_size == 'A3' else 10)
        for i, dn in enumerate(DAY_NAMES):
            _, _, w, _, _, _ = ctx.text_extents(dn); ctx.move_to(sx + i * cell_w_pt + cell_w_pt/2 - w/2, sy - 4 * MM_TO_PT); ctx.show_text(dn)
        fday = datetime.date(jaar, month, 1); fwd = fday.weekday()
        for k in range(42):
            col, row = k % 7, k // 7; x, y = sx + col * cell_w_pt, sy + row * cell_h_pt; cdate = fday + datetime.timedelta(days=k - fwd)
            active = [r for r in v_ranges if r['start'] <= cdate <= r['end']]
            for ridx, r in enumerate(active):
                ctx.set_source_rgba(0.2, 0.6, 0.8, 0.3); ctx.set_line_width(18.0 if paper_size == 'A3' else 12.0)
                ly = y + (12 if paper_size == 'A3' else 8) + (ridx * (20 if paper_size == 'A3' else 14))
                ctx.move_to(x, ly); ctx.line_to(x + cell_w_pt, ly); ctx.stroke()
                if cdate == r['start']:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(8 if paper_size == 'A3' else 6); ctx.move_to(x + 5, ly + 3); ctx.show_text(r['name'])
            ctx.set_font_size(18 if paper_size == 'A3' else 12); ctx.set_source_rgb(0,0,0) if cdate.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
            dn_txt = str(cdate.day); _, yb, w, h, _, _ = ctx.text_extents(dn_txt); ctx.move_to(x + cell_w_pt - 2*MM_TO_PT - w, y + 2*MM_TO_PT - yb); ctx.show_text(dn_txt)
            if col == 0:
                ctx.set_font_size(8 if paper_size == 'A3' else 6); ctx.set_source_rgb(0.4,0.4,0.4) if cdate.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
                wn_txt = f"W{get_week_num(cdate.year, cdate.month, cdate.day)}"; _, yb, w, h, _, _ = ctx.text_extents(wn_txt); ctx.move_to(x + 2*MM_TO_PT, y + 2*MM_TO_PT - yb); ctx.show_text(wn_txt)
            if cdate.month == month:
                evs = day_events.get(cdate.month, {}).get(cdate.day, [])
                if evs:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(9 if paper_size == 'A3' else 7)
                    for idx, name in enumerate(evs): ctx.move_to(x + 3*MM_TO_PT, y + 6*MM_TO_PT + idx * (11 if paper_size == 'A3' else 8)); ctx.show_text(name)
        ctx.show_page()
    ctx.show_page(); surface.finish(); output.seek(0)
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
    pdf = generate_pdf(int(request.args.get('year', 2026)), request.args.get('paper_size', 'A3'), request.args.get('orientation', 'landscape'), request.args.get('show_birthdays') == 'true', request.args.get('show_holidays') == 'true', request.args.get('show_vacations') == 'true')
    return send_file(pdf, mimetype='application/pdf')

@app.route('/generate', methods=['POST'])
def generate():
    pdf = generate_pdf(int(request.form.get('year', 2026)), request.form.get('paper_size', 'A3'), request.form.get('orientation', 'landscape'), 'show_birthdays' in request.form, 'show_holidays' in request.form, 'show_vacations' in request.form)
    return send_file(pdf, download_name=f"kalender.pdf", as_attachment=True)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)
