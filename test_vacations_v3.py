import re
import datetime

def load_data(jaar):
    content = """
    <ul><li>Herfstvakantie: van maandag 27 oktober tot en met zondag 2 november 2025</li>
    <li>Kerstvakantie: van maandag 22 december 2025 tot en met zondag 4 januari 2026</li>
    <li>Krokusvakantie: van maandag 16 tot en met zondag 22 februari 2026</li>
    <li>Paasvakantie: van maandag 6 tot en met zondag 19 april 2026 (paasmaandag: 6 april)</li>
    <li>Zomervakantie: van woensdag 1 juli tot en met maandag 31 augustus 2026</li></ul>
    """
    
    maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    maanden_regex = "|".join(maanden_dict.keys())
    v_ranges = []
    
    # Verbeterde regex met expliciete maandenlijst
    pattern = rf"(Herfstvakantie|Kerstvakantie|Krokus|Paas|Zomervakantie):.*?\b(\d+)\s+({maanden_regex})?\b.*?\b(\d+)\s+({maanden_regex})\s+(\d{{4}})"
    
    matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
    for m in matches:
        name, d1, m1_str, d2, m2_str, end_year = m.groups()
        ey = int(end_year)
        m2 = maanden_dict.get(m2_str.lower())
        m1 = maanden_dict.get(m1_str.lower()) if m1_str else m2
        
        if m1 and m2:
            sy = ey
            if m1 > m2: sy = ey - 1
            if sy == jaar or ey == jaar:
                v_ranges.append({'start': f"{sy}-{m1:02d}-{int(d1):02d}", 'end': f"{ey}-{m2:02d}-{int(d2):02d}", 'name': name})
    return v_ranges

print("Resultaat voor 2026:")
for v in load_data(2026): print(v)
