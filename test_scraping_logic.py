import re
import datetime

def test_logic():
    content = """
    <ul>
    <li>Herfstvakantie: van maandag 27 oktober tot en met zondag 2 november 2025</li>
    <li>Wapenstilstand: dinsdag 11 november 2025</li>
    <li>Kerstvakantie: van maandag 22 december 2025 tot en met zondag 4 januari 2026</li>
    <li>Krokusvakantie: van maandag 16 tot en met zondag 22 februari 2026</li>
    <li>Paasvakantie: van maandag 6 tot en met zondag 19 april 2026 (paasmaandag: 6 april)</li>
    <li>Dag van de Arbeid: vrijdag 1 mei 2026</li>
    <li>Hemelvaart: donderdag 14 en vrijdag 15 mei 2026 (deeltijds kunstonderwijs: alleen 14 mei, in het deeltijds kunstonderwijs en in het volwassenenonderwijs kan er in het weekend na Hemelvaart wel les zijn)</li>
    <li>Pinkstermaandag: 25 mei 2026</li>
    <li>Zomervakantie: van woensdag 1 juli tot en met maandag 31 augustus 2026</li>
    </ul>
    """
    
    maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    
    items = re.findall(r'<li>(.*?)</li>', content, re.DOTALL)
    results = []
    
    for item in items:
        clean_item = re.sub(r'<.*?>', '', item).strip()
        print(f"Analyzing: {clean_item}")
        
        # Verbeterde Range Regex: zoekt naar twee getallen en een jaar
        # Groep 1: Naam, 2: Dag1, 3: Maand1 (optioneel), 4: Dag2, 5: Maand2, 6: Jaar
        range_match = re.search(r'^(.*?):\s*(?:van\s+)?.*?\b(\d+)\s+([a-z]+)?.*?\b(\d+)\s+([a-z]+)\s+(\d{4})', clean_item, re.IGNORECASE)
        if range_match:
            name, d1, m1_str, d2, m2_str, ey_str = range_match.groups()
            ey = int(ey_str)
            m2 = maanden_dict.get(m2_str.lower())
            m1 = maanden_dict.get(m1_str.lower()) if (m1_str and m1_str.lower() in maanden_dict) else m2
            if m1 and m2:
                sy = ey
                if m1 > m2: sy = ey - 1
                results.append(f"RANGE: {name} | {sy}-{m1}-{d1} tot {ey}-{m2}-{d2}")
                continue

        # Verbeterde Dag Regex: zoekt naar een getal, maand en jaar
        day_match = re.search(r'^(.*?):\s*.*?\b(\d+)\s+([a-z]+)\s+(\d{4})', clean_item, re.IGNORECASE)
        if day_match:
            name, d, m_str, y_str = day_match.groups()
            m = maanden_dict.get(m_str.lower())
            if m:
                results.append(f"DAY: {name} | {y_str}-{m}-{d}")

    print("\n--- RESULTS ---")
    for r in results: print(r)

test_logic()
