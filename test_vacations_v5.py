import requests
import re
import datetime

def load_data(jaar):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "https://www.vlaanderen.be/onderwijs-en-vorming/wat-mag-en-moet-op-school/schoolvakanties-vrije-dagen-en-afwezigheden/schoolvakanties"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200: return []
    content = r.text
    
    maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    v_ranges = []
    
    for v_name in ["Herfstvakantie", "Kerstvakantie", "Krokusvakantie", "Paasvakantie", "Zomervakantie"]:
        pattern = rf"{v_name}:.*?(\d+)(?:\s+([a-z]+))?.*?(\d+)\s+([a-z]+)\s+(\d{{4}})"
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for m in matches:
            d1, m1_str, d2, m2_str, ey_str = m.groups()
            ey = int(ey_str)
            m2 = maanden_dict.get(m2_str.lower())
            m1 = maanden_dict.get(m1_str.lower()) if (m1_str and m1_str.lower() in maanden_dict) else m2
            
            if m1 and m2:
                sy = ey
                if m1 > m2: sy = ey - 1
                if sy == jaar or ey == jaar:
                    v_ranges.append({'start': f"{sy}-{m1:02d}-{int(d1):02d}", 'end': f"{ey}-{m2:02d}-{int(d2):02d}", 'name': v_name})
                    
    return v_ranges

for v in load_data(2026): print(v)
