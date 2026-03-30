from flask import Flask, render_template, request, send_file, io
import cairo
import datetime
import calendar
import json
import os
import requests
import re

app = Flask(__name__)

# Instellingen
DPI = 72
MM_TO_PT = 72 / 25.4
A3_BREEDTE_MM = 420
A3_HOOGTE_MM = 297
PAGE_WIDTH = A3_BREEDTE_MM * MM_TO_PT
PAGE_HEIGHT = A3_HOOGTE_MM * MM_TO_PT
BREEDTE_CM = 5.5
HOOGTE_CM = 4.3
BREEDTE_PT = BREEDTE_CM * 10 * MM_TO_PT
HOOGTE_PT = HOOGTE_CM * 10 * MM_TO_PT

MONTH_NAMES = ["", "Januari", "Februari", "Maart", "April", "Mei", "Juni", "Juli", "Augustus", "September", "Oktober", "November", "December"]
DAY_NAMES = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
CACHE_FILE = "kalender_cache.json"

def get_week_num(y, m, d):
    return datetime.date(y, m, d).isocalendar()[1]

def fetch_online_data(jaar):
    day_events = {}
    v_ranges = []
    try:
        r = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{jaar}/BE")
        if r.status_code == 200:
            for h in r.json():
                date_obj = datetime.date.fromisoformat(h['date'])
                m, d = date_obj.month, date_obj.day
                if m not in day_events: day_events[m] = {}
                if d not in day_events[m]: day_events[m][d] = []
                day_events[m][d].append(h['localName'])
    except: pass

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get("https://onderwijs.vlaanderen.be/nl/schoolvakanties", headers=headers)
        if r.status_code == 200:
            content = r.text
            patterns = [
                (r"Herfstvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Herfstvakantie"),
                (r"Kerstvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Kerstvakantie"),
                (r"Krokusvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Krokusvakantie"),
                (r"Paasvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Paasvakantie"),
                (r"Zomervakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Zomervakantie")
            ]
            maanden = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
            for p_raw, v_name in patterns:
                p = p_raw.format(jaar=jaar)
                matches = re.finditer(p, content, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    d1, m1_str, d2, m2_str, _ = m.groups()
                    m1, m2 = maanden.get(m1_str.lower()), maanden.get(m2_str.lower())
                    if m1 and m2:
                        v_ranges.append({'start': datetime.date(jaar, m1, int(d1)).isoformat(), 
                                         'end': datetime.date(jaar, m2, int(d2)).isoformat(), 
                                         'name': v_name})
    except: pass
    return {"events": day_events, "ranges": v_ranges}

def load_data(jaar):
    if os.path.exists(CACHE_FILE):
        if (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))).days < 30:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                if str(jaar) in cache: return cache[str(jaar)]
    data = fetch_online_data(jaar)
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f: cache = json.load(f)
        except: pass
    cache[str(jaar)] = data
    with open(CACHE_FILE, 'w') as f: json.dump(cache, f)
    return data

def read_local_birthdays():
    bdays = {}
    if os.path.exists("verjaardagen.txt"):
        with open("verjaardagen.txt", 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = line.split(maxsplit=1)
                if len(parts) < 2: continue
                try:
                    d, m = map(int, parts[0].split('/'))
                    if m not in bdays: bdays[m] = {}
                    if d not in bdays[m]: bdays[m][d] = []
                    bdays[m][d].append(parts[1])
                except: continue
    return bdays

def generate_pdf(jaar):
    online_data = load_data(jaar)
    day_events = {int(m): {int(d): v for d, v in days.items()} for m, days in online_data['events'].items()}
    v_ranges = [{'start': datetime.date.fromisoformat(r['start']), 'end': datetime.date.fromisoformat(r['end']), 'name': r['name']} for r in online_data['ranges']]
    
    local_bdays = read_local_birthdays()
    for m, days in local_bdays.items():
        if m not in day_events: day_events[m] = {}
        for d, names in days.items():
            if d not in day_events[m]: day_events[m][d] = []
            for n in names:
                if n not in day_events[m][d]: day_events[m][d].append(n)

    output = io.BytesIO()
    surface = cairo.PDFSurface(output, PAGE_WIDTH, PAGE_HEIGHT)
    ctx = cairo.Context(surface)
    
    for month in range(1, 13):
        ctx.set_source_rgb(1, 1, 1); ctx.paint()
        gw, gh = 7 * BREEDTE_PT, 6 * HOOGTE_PT
        sx, sy = (PAGE_WIDTH - gw) / 2, 100
        
        ctx.set_source_rgb(0, 0, 0); ctx.set_line_width(1.0)
        for r in range(6):
            for c in range(7):
                ctx.rectangle(sx + c * BREEDTE_PT, sy + r * HOOGTE_PT, BREEDTE_PT, HOOGTE_PT)
        ctx.stroke()
        
        ctx.select_font_face("LM Sans 10", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(24)
        txt = f"{MONTH_NAMES[month]} {jaar}"
        xb, yb, w, h, _, _ = ctx.text_extents(txt)
        ctx.move_to(sx + gw/2 - w/2, sy - 10 * MM_TO_PT); ctx.show_text(txt)
        
        ctx.set_font_size(17.28)
        for i, dn in enumerate(DAY_NAMES):
            xb, yb, w, h, _, _ = ctx.text_extents(dn)
            ctx.move_to(sx + i * BREEDTE_PT + BREEDTE_PT/2 - w/2, sy - 5 * MM_TO_PT); ctx.show_text(dn)
            
        fday = datetime.date(jaar, month, 1)
        fwd = fday.weekday()
        
        for k in range(42):
            col, row = k % 7, k // 7
            x, y = sx + col * BREEDTE_PT, sy + row * HOOGTE_PT
            cdate = fday + datetime.timedelta(days=k - fwd)
            
            # Markeerstift
            active = [r for r in v_ranges if r['start'] <= cdate <= r['end']]
            for ridx, r in enumerate(active):
                ctx.set_source_rgba(0.2, 0.6, 0.8, 0.3); ctx.set_line_width(20.0)
                ly = y + 15 + (ridx * 22)
                ctx.move_to(x, ly); ctx.line_to(x + BREEDTE_PT, ly); ctx.stroke()
                if cdate == r['start']:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(8)
                    ctx.move_to(x + 5, ly + 4); ctx.show_text(r['name'])

            ctx.set_font_size(20.74); ctx.set_source_rgb(0,0,0) if cdate.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
            dn_txt = str(cdate.day)
            xb, yb, w, h, _, _ = ctx.text_extents(dn_txt)
            ctx.move_to(x + BREEDTE_PT - 2*MM_TO_PT - w, y + 2*MM_TO_PT - yb); ctx.show_text(dn_txt)
            
            if col == 0:
                ctx.set_font_size(9); ctx.set_source_rgb(0.4,0.4,0.4) if cdate.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
                wn_txt = f"W{get_week_num(cdate.year, cdate.month, cdate.day)}"
                xb, yb, w, h, _, _ = ctx.text_extents(wn_txt)
                ctx.move_to(x + 2*MM_TO_PT, y + 2*MM_TO_PT - yb); ctx.show_text(wn_txt)
            
            if cdate.month == month:
                evs = day_events.get(cdate.month, {}).get(cdate.day, [])
                if evs:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(10)
                    for idx, name in enumerate(evs):
                        ctx.move_to(x + 3*MM_TO_PT, y + 7*MM_TO_PT + idx * 11); ctx.show_text(name)
        ctx.show_page()
    ctx.show_page()
    surface.finish()
    output.seek(0)
    return output

@app.route('/')
def index():
    return render_template('index.html', year=datetime.date.today().year)

@app.route('/generate', methods=['POST'])
def generate():
    jaar = int(request.form.get('year', datetime.date.today().year))
    pdf = generate_pdf(jaar)
    return send_file(pdf, download_name=f"kalender_{jaar}.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
