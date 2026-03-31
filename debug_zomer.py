import re
import datetime

def debug():
    item = "Zomervakantie: van woensdag 1 juli tot en met maandag 31 augustus 2026"
    maanden_dict = {"januari":1, "februari":2, "maart":3, "april":4, "mei":5, "juni":6, "juli":7, "augustus":8, "september":9, "oktober":10, "november":11, "december":12}
    
    # Huidige regex
    pattern = r'^(.*?):\s*(?:van\s+)?.*?\b(\d+)\s+([a-z]+)?.*?\b(\d+)\s+([a-z]+)\s+(\d{4})'
    match = re.search(pattern, item, re.IGNORECASE)
    
    if match:
        print("MATCH GEVONDEN!")
        groups = match.groups()
        print(f"Groups: {groups}")
        name, d1, m1_str, d2, m2_str, ey_str = groups
        print(f"Name: {name}, D1: {d1}, M1: {m1_str}, D2: {d2}, M2: {m2_str}, Jaar: {ey_str}")
    else:
        print("GEEN MATCH!")
        # Probeer te achterhalen waar het misgaat
        print(f"Item: {item}")

debug()
