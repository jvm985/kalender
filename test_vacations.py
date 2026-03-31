import os
import json
import datetime
import requests
import re

# Mock DATA_DIR
DATA_DIR = "."
CACHE_FILE = os.path.join(DATA_DIR, "kalender_cache.json")

def load_data(jaar):
    # Verwijder cache voor test
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        
    day_events = {}; v_ranges = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        url = "https://www.vlaanderen.be/onderwijs-en-vorming/wat-mag-en-moet-op-school/schoolvakanties-vrije-dagen-en-afwezigheden/schoolvakanties"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content = r.text
            print(f"DEBUG: Content length: {len(content)}")
            
            patterns = [
                (r"Herfstvakantie:.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+(\d{4})", "Herfstvakantie"),
                (r"Kerstvakantie:.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+(\d{4})", "Kerstvakantie"),
                (r"Krokusvakantie:.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+(\d{4})", "Krokusvakantie"),
                (r"Paasvakantie:.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+(\d{4})", "Paasvakantie"),
                (r"Zomervakantie:.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+(\d{4})", "Zomervakantie")
            ]
            maanden = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
            
            for p_raw, v_name in patterns:
                matches = list(re.finditer(p_raw, content, re.IGNORECASE | re.DOTALL))
                print(f"DEBUG: Pattern {v_name} found {len(matches)} matches")
                for m in matches:
                    d1, m1_str, d2, m2_str, end_year = m.groups()
                    m1, m2 = maanden.get(m1_str.lower()), maanden.get(m2_str.lower())
                    ey = int(end_year)
                    if m1 and m2:
                        sy = ey
                        if m1 > m2: sy = ey - 1
                        if sy == jaar or ey == jaar:
                            v_ranges.append({'start': f"{sy}-{m1:02d}-{int(d1):02d}", 'end': f"{ey}-{m2:02d}-{int(d2):02d}", 'name': v_name})
                            print(f"DEBUG: Added {v_name}: {sy}-{m1}-{d1} tot {ey}-{m2}-{d2}")
        else:
            print(f"DEBUG: Status code {r.status_code}")
    except Exception as e:
        print(f"DEBUG: Error: {e}")
    
    return v_ranges

jaar = 2026
print(f"--- Test voor jaar {jaar} ---")
vacations = load_data(jaar)
print(f"\nUiteindelijke vakanties ({len(vacations)}):")
for v in vacations:
    print(v)
