import re
import datetime
import json

def test():
    with open("vlaanderen.html", "r") as f:
        content = f.read()
    
    maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    
    # split_regex = r'<(?:h[234]|span)[^>]*>(?:\s*Schooljaar\s*|Schoolvakanties\s*)?(\d{4}-\d{4}).*?</(?:h[234]|span)>'
    # Verbeterde split regex: minder streng op tags, pakt ook data-attributes
    split_regex = r'(?:Schooljaar|Schoolvakanties)\s*(\d{4}-\d{4})'
    
    sections = re.split(split_regex, content, flags=re.IGNORECASE)
    print(f"Aantal secties gevonden: {len(sections)}")
    
    data = {"events": [], "ranges": []}
    
    for i in range(1, len(sections), 2):
        label = sections[i]
        text = sections[i+1]
        print(f"\n--- Sectie {label} (lengte {len(text)}) ---")
        
        # We zoeken alleen tot de volgende mogelijke kop om te voorkomen dat we te ver doorlopen
        # als de split niet alles pakt (bijv. intro tekst van volgende jaren)
        # Maar re.split doet dit al voor ons.
        
        items = re.findall(r'<li>(.*?)</li>', text, re.DOTALL)
        print(f"Aantal <li> gevonden: {len(items)}")
        
        for item in items:
            clean_item = re.sub(r'<.*?>', '', item).strip()
            if not clean_item: continue
            
            range_match = re.search(r'^(.*?):\s*(?:van\s+)?.*?\b(\d+)\s+([a-z]+)?.*?\b(\d+)\s+([a-z]+)\s+(\d{4})', clean_item, re.IGNORECASE)
            if range_match:
                name, d1, m1_str, d2, m2_str, ey_str = range_match.groups()
                ey = int(ey_str)
                m2 = maanden_dict.get(m2_str.lower())
                m1 = maanden_dict.get(m1_str.lower()) if (m1_str and m1_str.lower() in maanden_dict) else m2
                if m1 and m2:
                    sy = ey
                    if m1 > m2: sy = ey - 1
                    print(f"  MATCH RANGE: {name} | {sy}-{m1}-{d1} tot {ey}-{m2}-{d2}")
                    data["ranges"].append({"start": f"{sy}-{m1:02d}-{int(d1):02d}", "end": f"{ey}-{m2:02d}-{int(d2):02d}", "name": name.strip()})
                continue

            day_match = re.search(r'^(.*?):\s*.*?\b(\d+)\s+([a-z]+)\s+(\d{4})', clean_item, re.IGNORECASE)
            if day_match:
                name, d, m_str, y_str = day_match.groups()
                m = maanden_dict.get(m_str.lower())
                if m:
                    print(f"  MATCH DAY: {name} | {y_str}-{m}-{d}")
                    data["events"].append({"date": f"{int(y_str)}-{m:02d}-{int(d):02d}", "name": name.strip()})

test()
