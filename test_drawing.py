import datetime
import io
import cairo

# Gebruik de exact dezelfde logica uit app.py
def test_pdf_logic():
    MM_TO_PT = 72 / 25.4
    jaar = 2026
    # Mock vakantie van 16 t/m 22 februari (Krokus)
    v_ranges = [{'start': datetime.date(2026, 2, 16), 'end': datetime.date(2026, 2, 22), 'name': 'Krokusvakantie'}]
    
    # We simuleren de loop voor februari
    fday = datetime.date(2026, 2, 1); fwd = fday.weekday() # Maandag=0
    
    drawn_days = []
    labels_drawn = []
    
    for k in range(42):
        cdate = fday + datetime.timedelta(days=k - fwd)
        active = [r for r in v_ranges if r['start'] <= cdate <= r['end']]
        
        if active:
            drawn_days.append(cdate.isoformat())
            for r in active:
                if cdate == r['start']:
                    labels_drawn.append((cdate.isoformat(), r['name']))
                    
    print(f"Lijn getekend voor {len(drawn_days)} dagen: {drawn_days}")
    print(f"Label getekend op: {labels_drawn}")
    
    if len(drawn_days) == 7:
        print("✅ VERIFIED: Lijn wordt over het volledige bereik van 7 dagen getekend.")
    else:
        print("❌ FOUT: Lijn wordt niet voor alle dagen getekend!")

test_pdf_logic()
