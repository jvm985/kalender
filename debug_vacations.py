import requests
import re
import datetime

jaar = 2026
headers = {'User-Agent': 'Mozilla/5.0'}
url = "https://onderwijs.vlaanderen.be/nl/schoolvakanties"

print(f"Fetching {url}...")
r = requests.get(url, headers=headers, timeout=10)
if r.status_code == 200:
    content = r.text
    print(f"Content length: {len(content)}")
    
    patterns = [
        (r"Herfstvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Herfstvakantie"),
        (r"Kerstvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Kerstvakantie"),
        (r"Krokusvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Krokusvakantie"),
        (r"Paasvakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Paasvakantie"),
        (r"Zomervakantie.*?(\d+)\s+(\w+).*?(\d+)\s+(\w+)\s+({jaar})", "Zomervakantie")
    ]
    
    maanden = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    
    v_ranges = []
    for p_raw, v_name in patterns:
        p = p_raw.format(jaar=jaar)
        print(f"Testing pattern for {v_name}: {p}")
        matches = list(re.finditer(p, content, re.IGNORECASE | re.DOTALL))
        print(f"Found {len(matches)} matches")
        for m in matches:
            groups = m.groups()
            print(f"Match groups: {groups}")
            d1, m1_str, d2, m2_str, _ = groups
            m1, m2 = maanden.get(m1_str.lower()), maanden.get(m2_str.lower())
            if m1 and m2:
                v_ranges.append({'start': datetime.date(jaar, m1, int(d1)).isoformat(), 'end': datetime.date(jaar, m2, int(d2)).isoformat(), 'name': v_name})
    
    print("\nResulting v_ranges:")
    for v in v_ranges:
        print(v)
else:
    print(f"Failed to fetch: {r.status_code}")
