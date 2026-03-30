-- bdays[maand][dag] = {naam1, naam2, ...}
bdays = {}

local file = io.open("verjaardagen.txt", "r")
if file then
    for line in file:lines() do
        local d, m, n = line:match("^(%d+)/(%d+)%s*(.*)$")
        if d and m and n then
            d, m = tonumber(d), tonumber(m)
            if not bdays[m] then bdays[m] = {} end
            if not bdays[m][d] then bdays[m][d] = {} end
            if n ~= "" then
                table.insert(bdays[m][d], n)
            end
        end
    end
    file:close()
end

function get_bdays(d, m)
    d, m = tonumber(d), tonumber(m)
    if bdays[m] and bdays[m][d] then
        return table.concat(bdays[m][d], "\\\\ ")
    else
        return ""
    end
end

-- Functie om het weeknummer op te halen
function get_week_num(y, m, d)
    local t = os.time{year=y, month=m, day=d}
    return os.date("%V", t)
end

-- Functie om de grijze vakjes (vorige/volgende maand) te berekenen
function fill_gaps(year, month, breedte, hoogte)
    local t_first = os.time{year=year, month=month, day=1}
    local d_first = os.date("*t", t_first)
    local first_wd = (d_first.wday + 5) % 7 -- 0=ma, ..., 6=zo

    -- Aantal dagen in huidige maand
    local t_last = os.time{year=year, month=month+1, day=0}
    local d_last_obj = os.date("*t", t_last)
    local total_days = d_last_obj.day

    -- We vullen een grid van 6 rijen en 7 kolommen (42 vakjes totaal)
    for k = 0, 41 do
        -- Alleen invullen als het buiten het bereik van de huidige maand valt
        if k < first_wd or k >= (first_wd + total_days) then
            local offset = k - first_wd
            local t = os.time{year=year, month=month, day=1 + offset}
            local d = os.date("*t", t)
            
            local col = k % 7
            local row = math.floor(k / 7)
            local x = col * breedte
            local y = -row * hoogte
            
            -- Teken het dagnummer in lichtgrijs (gray!40)
            tex.sprint(string.format("\\node[anchor=north east, xshift=-0.2cm, yshift=-0.2cm, font=\\huge\\bfseries, text=gray!40] at (%f, %f) {%d};", x + breedte, y, d.day))

            -- Weeknummer op maandag (col == 0)
            if col == 0 then
                local week_num = os.date("%V", t)
                tex.sprint(string.format("\\node[anchor=north west, xshift=0.2cm, yshift=-0.2cm, font=\\small\\bfseries, text=gray!40] at (%f, %f) {W%s};", x, y, week_num))
            end
        end
    end
end
