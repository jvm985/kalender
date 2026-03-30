import cairo
import datetime
import calendar
import argparse
import json
import os
import requests
import re

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
    print(f"Online data ophalen voor {jaar}...")
    day_events = {}
    v_ranges = []
    
    # 1. Publieke feestdagen België (via Nager.Date API - betrouwbaar en gratis)
    try:
        r = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{jaar}/BE")
        if r.status_code == 200:
            for h in r.json():
                date_obj = datetime.date.fromisoformat(h['date'])
                m, d = date_obj.month, date_obj.day
                name = h['localName']
                if m not in day_events: day_events[m] = {}
                if d not in day_events[m]: day_events[m][d] = []
                day_events[m][d].append(name)
    except Exception as e:
        print(f"Fout bij ophalen feestdagen: {e}")

    # 2. Vlaamse Schoolvakanties (Scraping van onderwijs.vlaanderen.be)
    # Opmerking: Dit is een vereenvoudigde scraper. 
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get("https://onderwijs.vlaanderen.be/nl/schoolvakanties", headers=headers)
        if r.status_code == 200:
            # We zoeken naar datums in de tekst voor het gevraagde jaar
            # Dit is een heuristiek: we zoeken naar patronen zoals "maandag 27 oktober tot en met zondag 2 november 2025"
            content = r.text
            # We zoeken specifiek naar de vakantieblokken
            # Voorbeeld: "Herfstvakantie: van maandag 27 oktober tot en met zondag 2 november 2025"
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
                        start_date = datetime.date(jaar, m1, int(d1))
                        end_date = datetime.date(jaar, m2, int(d2))
                        v_ranges.append({'start': start_date.isoformat(), 'end': end_date.isoformat(), 'name': v_name})
    except Exception as e:
        print(f"Fout bij ophalen schoolvakanties: {e}")

    return {"events": day_events, "ranges": v_ranges}

def load_data(jaar):
    # Check cache
    if os.path.exists(CACHE_FILE):
        mtime = os.path.getmtime(CACHE_FILE)
        last_mod = datetime.datetime.fromtimestamp(mtime)
        # Als de cache minder dan 30 dagen oud is, gebruik deze
        if (datetime.datetime.now() - last_mod).days < 30:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                if str(jaar) in cache:
                    print("Data geladen uit cache.")
                    return cache[str(jaar)]
    
    # Anders: ophalen
    online_data = fetch_online_data(jaar)
    
    # Cache bijwerken
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
        except: pass
    
    cache[str(jaar)] = online_data
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)
    
    return online_data

def read_local_birthdays(filename):
    # Alleen voor persoonlijke verjaardagen uit verjaardagen.txt
    bdays = {}
    if not os.path.exists(filename): return bdays
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split(maxsplit=1)
            if len(parts) < 2: continue
            date_part, name = parts
            if '-' in date_part: continue # We laten reeksen nu aan de online data over
            try:
                d, m = map(int, date_part.split('/'))
                if m not in bdays: bdays[m] = {}
                if d not in bdays[m]: bdays[m][d] = []
                bdays[m][d].append(name)
            except: continue
    return bdays

def draw_calendar(jaar):
    online_data = load_data(jaar)
    day_events = online_data['events'] # { "maand": { "dag": ["naam"] } }
    # JSON keys zijn strings, even omzetten naar ints
    day_events = {int(m): {int(d): names for d, names in days.items()} for m, days in day_events.items()}
    
    v_ranges = []
    for r in online_data['ranges']:
        v_ranges.append({
            'start': datetime.date.fromisoformat(r['start']),
            'end': datetime.date.fromisoformat(r['end']),
            'name': r['name']
        })
        
    # Lokale verjaardagen toevoegen
    local_bdays = read_local_birthdays("verjaardagen.txt")
    for m, days in local_bdays.items():
        if m not in day_events: day_events[m] = {}
        for d, names in days.items():
            if d not in day_events[m]: day_events[m][d] = []
            for n in names:
                if n not in day_events[m][d]: day_events[m][d].append(n)

    surface = cairo.PDFSurface("kalender.pdf", PAGE_WIDTH, PAGE_HEIGHT)
    ctx = cairo.Context(surface)
    
    for month in range(1, 13):
        ctx.set_source_rgb(1, 1, 1); ctx.paint()
        grid_width, grid_height = 7 * BREEDTE_PT, 6 * HOOGTE_PT
        start_x, start_y = (PAGE_WIDTH - grid_width) / 2, 100
        
        # Grid
        ctx.set_source_rgb(0, 0, 0); ctx.set_line_width(1.0)
        for r in range(6):
            for c in range(7):
                ctx.rectangle(start_x + c * BREEDTE_PT, start_y + r * HOOGTE_PT, BREEDTE_PT, HOOGTE_PT)
        ctx.stroke()
        
        # Maandnaam
        ctx.select_font_face("LM Sans 10", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(24)
        txt = f"{MONTH_NAMES[month]} {jaar}"
        xb, yb, w, h, _, _ = ctx.text_extents(txt)
        ctx.move_to(start_x + grid_width/2 - w/2, start_y - 10 * MM_TO_PT); ctx.show_text(txt)
        
        # Dagnamen
        ctx.set_font_size(17.28)
        for i, dn in enumerate(DAY_NAMES):
            xb, yb, w, h, _, _ = ctx.text_extents(dn)
            ctx.move_to(start_x + i * BREEDTE_PT + BREEDTE_PT/2 - w/2, start_y - 5 * MM_TO_PT); ctx.show_text(dn)
            
        first_day = datetime.date(jaar, month, 1)
        first_wd = first_day.weekday()
        
        for k in range(42):
            col, row = k % 7, k // 7
            x, y = start_x + col * BREEDTE_PT, start_y + row * HOOGTE_PT
            curr_date = first_day + datetime.timedelta(days=k - first_wd)
            
            # Markeerstift (Vakanties)
            active = [r for r in v_ranges if r['start'] <= curr_date <= r['end']]
            for ridx, r in enumerate(active):
                ctx.set_source_rgba(0.2, 0.6, 0.8, 0.3); ctx.set_line_width(20.0)
                ly = y + 15 + (ridx * 22)
                ctx.move_to(x, ly); ctx.line_to(x + BREEDTE_PT, ly); ctx.stroke()
                if curr_date == r['start']:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(8)
                    ctx.move_to(x + 5, ly + 4); ctx.show_text(r['name'])

            # Dagnummer
            ctx.set_font_size(20.74); ctx.set_source_rgb(0,0,0) if curr_date.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
            dn_txt = str(curr_date.day)
            xb, yb, w, h, _, _ = ctx.text_extents(dn_txt)
            ctx.move_to(x + BREEDTE_PT - 2*MM_TO_PT - w, y + 2*MM_TO_PT - yb); ctx.show_text(dn_txt)
            
            # Weeknummer
            if col == 0:
                ctx.set_font_size(9); ctx.set_source_rgb(0.4,0.4,0.4) if curr_date.month == month else ctx.set_source_rgb(0.6,0.6,0.6)
                wn_txt = f"W{get_week_num(curr_date.year, curr_date.month, curr_date.day)}"
                xb, yb, w, h, _, _ = ctx.text_extents(wn_txt)
                ctx.move_to(x + 2*MM_TO_PT, y + 2*MM_TO_PT - yb); ctx.show_text(wn_txt)
            
            # Events
            if curr_date.month == month:
                evs = day_events.get(curr_date.month, {}).get(curr_date.day, [])
                if evs:
                    ctx.set_source_rgb(0,0,0); ctx.set_font_size(10)
                    for idx, name in enumerate(evs):
                        ctx.move_to(x + 3*MM_TO_PT, y + 7*MM_TO_PT + idx * 11); ctx.show_text(name)

        ctx.show_page()
    ctx.show_page()
    surface.finish()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-y", "--year", type=int, default=datetime.date.today().year)
    args = parser.parse_args()
    draw_calendar(args.year)
