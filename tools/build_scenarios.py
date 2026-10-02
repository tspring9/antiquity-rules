"""Build the scenario setup sheets from the game's own data files.

    python tools/build_scenarios.py [path/to/antiquity/data]

Reads data/scenarios/*.json, territories.json and factions.json from the
Godot project (default D:/antiquity/data) and writes scenario-1p.html ...
scenario-5p.html next to index.html. It also rewrites the "Scenarios" list
on each faction sheet so the two never disagree. Re-run it whenever a
scenario file changes.
"""
import html
import json
import math
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/antiquity/data")

# Scenario files in play order, with the sheet's file name and display name.
SCENARIOS = [
    ("1p_ad117", "scenario-1p.html", 1, "Holding the Empire", "AD 117"),
    ("2p", "scenario-2p.html", 2, "First Punic War", "264 BC"),
    ("3p", "scenario-3p.html", 3, "Three Powers", "Rome, Carthage and the Seleucids"),
    ("4p", "scenario-4p.html", 4, "Four Powers", "Rome, Carthage, Macedon and Egypt"),
    ("5p", "scenario-5p.html", 5, "Five Powers", "The whole Mediterranean at war"),
]
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}

# Game faction id -> (CSS faction key, faction sheet or None)
FKEY = {
    "rome": ("rome", "faction-rome.html"),
    "carthage": ("carthage", "faction-carthage.html"),
    "ptolemy": ("ptolemaic", "faction-ptolemaic.html"),
    "seleucid": ("seleucid", "faction-seleucid.html"),
    "achaea": ("greek", "faction-greek.html"),
    "macedon": ("macedon", None),
    "usurper": ("usurper", None),
    "barbarian": ("barb", None),
}
HEAVY = ("legion", "hoplite", "heavy_infantry")
UNIT_NAME = {
    "legion": "Legion", "hoplite": "Hoplite", "heavy_infantry": "Heavy Infantry",
    "levy": "Levy", "cavalry": "Cavalry", "general": "General",
    "attack_boat": "Attack Boat", "transport": "Transport",
}
COLS = [("general", "General"), ("heavy", None), ("levy", "Levy"),
        ("cavalry", "Cav."), ("attack_boat", "Attack Boat"), ("transport", "Transport")]

esc = html.escape


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf8"))


TERR = {t["id"]: t for t in load("territories.json")}
FACT = {f["id"]: f for f in load("factions.json")}


def tname(i):
    return TERR[i]["name"] if i in TERR else i.replace("_", " ").title()


def is_sea(i):
    return TERR.get(i, {}).get("kind") == "sea"


def units_text(u):
    order = ["general", *HEAVY, "levy", "cavalry", "attack_boat", "transport"]
    return ", ".join(f"{u[k]} {UNIT_NAME[k]}" for k in order if u.get(k))


def join_names(ids):
    names = [tname(i) for i in ids]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


# ------------------------------------------------------------------ emblems

def faction_emblems():
    """The coin emblems, lifted from the faction sheets' switcher bar."""
    src = (SITE / "faction-rome.html").read_text(encoding="utf8")
    out = {}
    for key in ("rome", "carthage", "ptolemaic", "seleucid", "greek"):
        m = re.search(r'data-f="%s"[^>]*>(<svg class="emblem".*?</svg>)' % key, src, re.S)
        out[key] = m.group(1)
    rays = []
    for k in range(16):  # Vergina sun for Macedon
        a = math.radians(k * 22.5)
        tip = (50 + 34 * math.sin(a), 50 - 34 * math.cos(a))
        l = (50 + 13 * math.sin(a - 0.13), 50 - 13 * math.cos(a - 0.13))
        r = (50 + 13 * math.sin(a + 0.13), 50 - 13 * math.cos(a + 0.13))
        rays.append("M%.1f %.1f L%.1f %.1f L%.1f %.1f Z" % (l + tip + r))
    out["macedon"] = (
        '<svg class="emblem" viewBox="0 0 100 100" role="img" aria-hidden="true">'
        '<circle cx="50" cy="50" r="48" fill="var(--f-soft)" stroke="var(--f)" stroke-width="2.5"/>'
        '<circle cx="50" cy="50" r="43" fill="none" stroke="var(--f)" stroke-width="1.2" stroke-dasharray="1.5 3"/>'
        '<g fill="var(--f)"><path d="%s"/><circle cx="50" cy="50" r="10"/></g></svg>' % " ".join(rays))
    return out


EMB = faction_emblems()


def coin(n):
    return (
        '<svg class="coin" viewBox="0 0 100 100" role="img" aria-label="%d player%s">'
        '<circle cx="50" cy="50" r="48" fill="var(--gold-soft)" stroke="var(--gold)" stroke-width="2.5"/>'
        '<circle cx="50" cy="50" r="42" fill="none" stroke="var(--gold)" stroke-width="1.2" stroke-dasharray="1.5 3"/>'
        '<text x="50" y="%d" text-anchor="middle" font-family="Marcellus SC, Georgia, serif" font-size="%d" '
        'fill="var(--gold)" letter-spacing="1">%s</text>'
        '<text x="50" y="76" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="8.5" '
        'fill="var(--gold)" letter-spacing="2">%s</text></svg>'
        % (n, "" if n == 1 else "s", 58 if n < 4 else 57, 34 if len(ROMAN[n]) < 3 else 28, ROMAN[n],
           "PLAYER" if n == 1 else "PLAYERS"))


# ---------------------------------------------------------------------- map

def simplify(pts, tol=1.4):
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1
        best, idx = 0, None
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / n
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def path_d(t):
    polys = t.get("polygons") or [t.get("polygon") or []]
    parts = []
    for poly in polys:
        pts = simplify([(p["x"], p["y"]) for p in poly])
        if len(pts) < 3:
            continue
        parts.append("M" + "L".join("%d,%d" % (round(x), round(y)) for x, y in pts) + "Z")
    return "".join(parts)


PATHS = {i: path_d(t) for i, t in TERR.items()}
# Crop to the land, with a margin.
_xs = [p["x"] for t in TERR.values() for poly in (t.get("polygons") or [t.get("polygon") or []]) for p in poly]
_ys = [p["y"] for t in TERR.values() for poly in (t.get("polygons") or [t.get("polygon") or []]) for p in poly]
VB = (max(0, min(_xs) - 10), max(0, min(_ys) - 10), min(2000, max(_xs) + 10), min(1220, max(_ys) + 10))


def star(cx, cy, r):
    pts = []
    for k in range(10):
        a = math.radians(-90 + k * 36)
        rr = r if k % 2 == 0 else r * 0.45
        pts.append("%.1f,%.1f" % (cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return "M" + "L".join(pts) + "Z"


def map_svg(sc, owners, capitals, spawns):
    x0, y0, x1, y1 = VB
    out = ['<svg class="map" viewBox="%d %d %d %d" role="img" aria-label="Starting map: provinces coloured by owner">'
           % (x0, y0, x1 - x0, y1 - y0)]
    out.append('<defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="7" height="7" '
               'patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--barb-s)"/>'
               '<line x1="0" y1="0" x2="0" y2="7" stroke="var(--barb)" stroke-width="2.2"/></pattern></defs>')
    out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="var(--sea)"/>' % (x0, y0, x1 - x0, y1 - y0))
    for i, t in TERR.items():
        if t["kind"] == "sea":
            out.append('<path d="%s" fill="var(--sea)" stroke="var(--sea-line)" stroke-width="1.2"/>' % PATHS[i])
    for i, t in TERR.items():
        if t["kind"] == "sea":
            continue
        o = owners.get(i)
        if o == "barbarian":
            fill, cls = "url(#hatch)", ""
        elif o and o in FKEY:
            fill, cls = "var(--f)", ' class="own" data-f="%s"' % FKEY[o][0]
        else:
            fill, cls = "var(--land)", ""
        out.append('<path%s d="%s" fill="%s" stroke="var(--surface)" stroke-width="2" stroke-linejoin="round"><title>%s</title></path>'
                   % (cls, PATHS[i], fill, esc(t["name"])))
    # Markers: spawn ring, unit-count disc, capital star.
    for i in spawns:
        p = TERR[i]["position"]
        out.append('<circle cx="%d" cy="%d" r="30" fill="none" stroke="var(--barb)" stroke-width="5" stroke-dasharray="7 5"/>'
                   % (p["x"], p["y"]))
    for i, v in sc["territories"].items():
        n = sum(v.get("units", {}).values())
        if not n or i not in TERR:
            continue
        p = TERR[i]["position"]
        f = FKEY.get(v["owner"], ("barb", None))[0]
        out.append('<g data-f="%s"><circle cx="%d" cy="%d" r="21" fill="var(--f)" stroke="var(--surface)" stroke-width="2.5"/>'
                   '<text x="%d" y="%d" text-anchor="middle" class="mn">%d</text></g>'
                   % (f, p["x"], p["y"], p["x"], p["y"] + 8, n))
    for fid, cap in capitals.items():
        p = TERR[cap]["position"]
        out.append('<path d="%s" data-f="%s" fill="var(--f)" stroke="var(--surface)" stroke-width="2.5" stroke-linejoin="round"/>'
                   % (star(p["x"] + 22, p["y"] - 20, 16), FKEY[fid][0]))
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------- tables

def setup_table(fid, rows, heavy_label):
    head = "".join('<th class="n">%s</th>' % (heavy_label if k == "heavy" else lab) for k, lab in COLS)
    body, tot = [], {k: 0 for k, _ in COLS}
    for tid, u in rows:
        cells = []
        for k, _ in COLS:
            v = sum(u.get(h, 0) for h in HEAVY) if k == "heavy" else u.get(k, 0)
            tot[k] += v
            cells.append('<td class="n">%s</td>' % (v if v else '<span class="z">·</span>'))
        sea = ' class="sea"' if is_sea(tid) else ""
        body.append('<tr%s><td class="t">%s</td>%s</tr>' % (sea, esc(tname(tid)), "".join(cells)))
    foot = "".join('<td class="n">%s</td>' % (tot[k] or '<span class="z">·</span>') for k, _ in COLS)
    return ('<div class="tw"><table class="setup"><thead><tr><th>Place</th>%s</tr></thead>'
            '<tbody>%s</tbody><tfoot><tr><td>Total</td>%s</tr></tfoot></table></div>'
            % (head, "".join(body), foot))


def power_block(sc, fid, capital):
    f = FACT[fid]
    key, sheet = FKEY[fid]
    held = [(i, v.get("units", {})) for i, v in sc["territories"].items() if v.get("owner") == fid]
    land = [i for i, _ in held if not is_sea(i)]
    income = sum(TERR[i].get("income", 1) for i in land)
    with_units = [(i, u) for i, u in held if u]
    with_units.sort(key=lambda r: (is_sea(r[0]), r[0] != capital, -sum(r[1].values())))
    empty = sorted(i for i, u in held if not u and not is_sea(i))
    heavy = next((r for r in f["roster"] if r in HEAVY), "heavy_infantry")
    name = f["name"]
    title = '<a href="%s">%s</a>' % (sheet, esc(name)) if sheet else esc(name)
    extra = ""
    if empty:
        extra = '<p class="also"><b>Also held, no units:</b> %s.</p>' % esc(join_names(empty))
    return (
        '<section class="power" data-f="%s">'
        '<header class="ph">%s<div><h3>%s</h3>'
        '<p class="pm"><span><svg class="st" viewBox="0 0 24 24" aria-hidden="true"><path d="%s"/></svg>Capital <b>%s</b></span>'
        '<span><b>%d</b> provinces</span><span>Income <b class="gold">%d gold</b></span></p></div></header>'
        '%s%s</section>'
        % (key, EMB.get(key, ""), title, star(12, 12.5, 10), esc(tname(capital)), len(land), income,
           setup_table(fid, with_units, UNIT_NAME[heavy]), extra))


def barbarian_block(sc, spawns):
    rows = [(i, v["units"]) for i, v in sc["territories"].items()
            if v.get("owner") == "barbarian" and v.get("units")]
    rows.sort(key=lambda r: -sum(r[1].values()))
    lines = "".join('<li><span class="t">%s</span><span class="u">%s</span></li>'
                    % (esc(tname(i)), esc(units_text(u))) for i, u in rows)
    quiet = sorted(i for i, v in sc["territories"].items()
                   if v.get("owner") == "barbarian" and not v.get("units"))
    owned = [i for i in TERR if not is_sea(i)]
    neutral = sorted(i for i in owned if i not in sc["territories"])
    sp = "".join('<li>%s</li>' % esc(tname(i)) for i in spawns)
    out = ['<section class="barb" data-f="barb"><h3>Barbarians</h3>',
           '<div class="bcols"><div><p class="lab">Garrisons</p><ul class="garr">%s</ul>' % lines]
    if quiet:
        out.append('<p class="also"><b>Barbarian-held, no units:</b> %s.</p>' % esc(join_names(quiet)))
    if neutral:
        out.append('<p class="also"><b>Unclaimed and empty:</b> %s. Anyone may march in and take them.</p>'
                   % esc(join_names(neutral)))
    out.append('</div><div><p class="lab">Spawn provinces</p><ul class="spawn">%s</ul>'
               '<p class="note">Each Barbarian phase, roll a d12 for each one. On 1–4 a barbarian Levy appears, '
               'or on 1–8 if you hold it without heavy infantry (§14).</p></div></div></section>' % sp)
    return "".join(out)


# ------------------------------------------------------------- solo extras

def event_effect(e):
    k = e["kind"]
    if k == "spawn_override":
        return "Every successful spawn this round raises %s instead of one Levy." % units_text(e["units"])
    if k == "revolt":
        return ("%s rise in each of %d random provinces you hold without heavy infantry."
                % (units_text(e["units"]), e.get("count", 1)))
    if k == "storm":
        return "Every ship on the map has a %d%% chance to sink, with everything aboard." % e["percent"]
    if k == "plague":
        return "Every land unit except Generals has a %d%% chance to die." % e["percent"]
    if k == "boon":
        if e.get("gold"):
            return "Rome gains %d gold." % e["gold"]
        return "Rome gains %s in one of %s, if Rome holds it." % (units_text(e["units"]), join_names(e["one_of"]))
    if k == "uprising":
        if e.get("forces"):
            where = "; ".join("%s in %s" % (units_text(u), tname(t)) for t, u in e["forces"].items())
            s = "%s." % where
        else:
            s = "%s rise in one of %s." % (units_text(e["force"]), join_names(e["one_of"]))
        return s + " Rebel provinces raise Levies on 1–%d and attack neighbours in the revolt that lack heavy infantry, until you retake them." % e.get("unrest_chance", 8)
    return ""


def event_when(e):
    r = e.get("requires", {})
    bits = []
    if r.get("min_turn"):
        bits.append("From round %d" % r["min_turn"])
    for t, o in r.get("owner", {}).items():
        bits.append("Rome holds %s" % tname(t))
    for o, ts in r.get("any_owner", {}).items():
        bits.append("Rome holds %s" % (tname(ts[0]) if len(ts) == 1 else "any of " + join_names(ts).replace(" and ", " or ")))
    if e.get("once"):
        bits.append("Once per game")
    return "; ".join(bits) or "Any round"


def solo_extras(sc):
    out = []
    boss = sc.get("boss")
    if boss:
        lo, hi = boss.get("turn_window", [4, 8])
        out.append(
            '<section class="boss" data-f="usurper"><p class="lab">Named enemy</p><h3>%s</h3>'
            '<p>On a random round from <b>%d to %d</b>, a usurper rises in one of %s with <b>%s</b>, '
            'and takes the province. Each round after that, the usurper collects income from what it holds, '
            'spends it all on Cavalry, then Heavy Infantry, then Levies, and marches its whole army one step '
            'into the neighbouring province with the fewest heavy infantry. It leaves nothing behind, so '
            'ground it passes through can be walked straight back into.</p></section>'
            % (esc(boss.get("name", "The Usurper")), lo, hi, esc(join_names(boss["one_of"])), esc(units_text(boss["force"]))))
    inc = sc.get("incursions", [])
    if inc:
        li = "".join('<li>%s <span aria-hidden="true">→</span><span class="vh">to</span> %s</li>'
                     % (esc(tname(i["from"])), esc(tname(i["to"]))) for i in inc)
        out.append(
            '<section class="routes"><h3>Incursion routes</h3><p>At the end of each Barbarian phase, the whole '
            'barbarian stack on the left of a route attacks the province on the right, if that province '
            'is not barbarian-held and has <b>no heavy infantry</b> in it.</p><ol class="rt">%s</ol></section>' % li)
    ev = sc.get("events", [])
    if ev:
        total = sum(e.get("weight", 1) for e in ev)
        rows = "".join(
            '<tr><td class="ev">%s</td><td class="n">%d</td><td>%s</td><td class="when">%s</td></tr>'
            % (esc(e["name"].split(" — ")[0]), e.get("weight", 1), esc(event_effect(e)), esc(event_when(e)))
            for e in ev)
        out.append(
            '<section class="events"><h3>Events</h3><p>Exactly one event happens every Barbarian phase, '
            'before the spawn rolls. Draw it from the table by weight (out of %d). If an event\'s condition '
            'isn\'t met, draw again.</p><div class="tw"><table class="evt"><thead><tr><th>Event</th>'
            '<th class="n">Weight</th><th>Effect</th><th>Only when</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (total, rows))
    return "".join(out)


# ------------------------------------------------------------------ victory

def victory_html(sc, order, start_held):
    v = sc.get("victory", {})
    items = []
    if v.get("tiers"):
        lim = v.get("turn_limit")
        rows = "".join('<tr><td class="n">%s</td><td><b>%s</b></td><td>%s</td></tr>'
                       % ("%d" % t["min_held"] if t["min_held"] else "fewer", esc(t["title"].title()), esc(t["headline"]))
                       for t in v["tiers"])
        items.append('<p>Rome must hold its <b>%d starting provinces</b> through the end of round <b>%d</b>. '
                     'Losing ground mid-game is not a loss. Only the count at the end matters, and Rome '
                     'loses at once if it is destroyed.</p><table class="tiers"><thead><tr><th class="n">Held</th>'
                     '<th>Result</th><th></th></tr></thead><tbody>%s</tbody></table>' % (start_held, lim, rows))
    for g in v.get("hold_to_win", []):
        items.append('<p><b>%s</b> wins by taking <b>%s</b> and still holding it at the end of %d rounds in a row.</p>'
                     % (esc(FACT[g["faction"]]["name"]), esc(tname(g["territory"])), v.get("turns", 2)))
    if len(order) > 1:
        items.append('<p>Any player who outlasts every other player wins.</p>')
    if len(order) > 1 and not v:
        items.append('<p class="tbd">The game data sets no capital or turn-limit objective for this scenario yet.</p>')
    return "".join(items)


# --------------------------------------------------------------------- page

def page(idx, all_sc, faction_css):
    file, fname, n, title, epi = SCENARIOS[idx]
    sc = all_sc[file]
    order = sc["turn_order"]
    capitals = {f: FACT[f]["capital"] for f in order if FACT[f].get("capital")}
    capitals.update(sc.get("capitals", {}))
    owners = {i: v.get("owner") for i, v in sc["territories"].items()}
    spawns = [i for i in sc.get("barbarian_territories", []) if i in TERR]
    rome_start = sum(1 for i, o in owners.items() if o == order[0] and not is_sea(i))

    nav = ['<nav class="bar" aria-label="Antiquity"><a class="back" href="index.html">&larr; Rules of Play</a><div class="jump">']
    for j, (_, f2, n2, t2, _) in enumerate(SCENARIOS):
        cur = ' aria-current="page"' if j == idx else ""
        nav.append('<a href="%s"%s><span class="pc">%dP</span>%s</a>' % (f2, cur, n2, esc(t2)))
    nav.append("</div></nav>")

    turn = "".join('<li data-f="%s">%s<span>%s</span></li>' % (FKEY[f][0], EMB.get(FKEY[f][0], ""), esc(FACT[f]["name"]))
                   for f in order)
    caps = " · ".join('%s <b>%s</b>' % (esc(FACT[f]["name"]), esc(tname(c))) for f, c in capitals.items())

    legend = ['<ul class="legend">']
    for f in order:
        legend.append('<li data-f="%s"><i class="sw"></i>%s</li>' % (FKEY[f][0], esc(FACT[f]["name"])))
    legend.append('<li data-f="barb"><i class="sw hatch"></i>Barbarian</li>'
                  '<li><i class="sw land"></i>Unclaimed</li>'
                  '<li><i class="sw dot">3</i>Units at start</li>'
                  '<li><i class="sw ring"></i>Spawn province</li>'
                  '<li><svg class="sw-st" viewBox="0 0 24 24" aria-hidden="true"><path d="%s"/></svg>Capital</li></ul>'
                  % star(12, 12.5, 10))

    powers = "".join(power_block(sc, f, capitals.get(f, "")) for f in order)
    desc = sc.get("description", "")

    body = f"""<div class="wrap">{''.join(nav)}
<article class="sheet scen">
  <header class="sh">
    {coin(n)}
    <div class="sh-t">
      <p class="eyebrow">Antiquity · Scenario sheet · {n} player{'s' if n > 1 else ''}</p>
      <h2>{esc(title)}</h2>
      <p class="epi">{esc(epi)}</p>
    </div>
  </header>
  <p class="desc">{esc(desc)}</p>
  <div class="facts">
    <div class="fact"><p class="lab">Turn order</p><ol class="turn">{turn}</ol><p class="after">Then the barbarians act, and the round ends.</p></div>
    <div class="fact"><p class="lab">Capitals</p><p>{caps}</p><p class="lab l2">Starting gold</p><p>None. Income is collected at the start of each turn.</p></div>
  </div>
  <figure class="mapfig"><div class="mapscroll">{map_svg(sc, owners, capitals, spawns)}</div>{''.join(legend)}</figure>
  <h3 class="sec">Setup</h3>
  <p class="hint">Place these units before the first round. Ships go in the sea zones shown.</p>
  <div class="powers">{powers}</div>
  {barbarian_block(sc, spawns)}
  {solo_extras(sc)}
  <section class="victory"><h3>Victory</h3>{victory_html(sc, order, rome_start)}</section>
  <section class="tbd-box"><p class="lab">Not set in the game data yet</p><p><b>Strongholds.</b> The scenario file names no strongholds, so for now only capitals should be treated as walled (§3.5).</p></section>
  <p class="foot">Generated from the game's scenario file data/scenarios/{file}.json · where this sheet and the rulebook disagree, this sheet wins</p>
</article></div>"""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{esc(title)} Setup</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Marcellus+SC&family=Alegreya+Sans:ital,wght@0,400;0,500;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap"><style>{faction_css}{SCEN_CSS}</style></head><body>{body}</body></html>"""


SCEN_CSS = """
/* Scenario sheets: the faction-sheet system, plus map and setup-grid tokens. */
:root{--gold-soft:#f6eed8;--land:#e7e6dc;--sea:#dde7e8;--sea-line:#c9d6d8;
 --macedon:#a3541c;--macedon-s:#f6e6d9;--usurper:#a3245e;--usurper-s:#f6e0ea;--barb:#5f6b38;--barb-s:#ebeedd}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--gold-soft:#352c16;--land:#262d2c;--sea:#121b1f;--sea-line:#1f2b30;
 --macedon:#e39a62;--macedon-s:#3a2618;--usurper:#e083ad;--usurper-s:#3a1f2c;--barb:#a8b878;--barb-s:#252a1a}}
:root[data-theme="dark"]{--gold-soft:#352c16;--land:#262d2c;--sea:#121b1f;--sea-line:#1f2b30;
 --macedon:#e39a62;--macedon-s:#3a2618;--usurper:#e083ad;--usurper-s:#3a1f2c;--barb:#a8b878;--barb-s:#252a1a}
[data-f="macedon"]{--f:var(--macedon);--f-soft:var(--macedon-s)}
[data-f="usurper"]{--f:var(--usurper);--f-soft:var(--usurper-s)}
[data-f="barb"]{--f:var(--barb);--f-soft:var(--barb-s)}
.scen{border-top-color:var(--gold)}
.coin{width:104px;height:104px;flex:none}
.sh h2{color:var(--ink)}
.desc{margin:0;max-width:68ch;font-size:16.5px}
.facts{display:grid;grid-template-columns:1.3fr 1fr;gap:14px}
.fact{border:1px solid var(--rule);border-radius:6px;padding:14px 18px;display:grid;gap:6px;align-content:start}
.fact p{margin:0}
.fact .lab{color:var(--muted)}
.fact .l2{margin-top:8px}
.turn{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px;counter-reset:t}
.turn li{counter-increment:t;display:inline-flex;align-items:center;gap:7px;padding:4px 12px 4px 4px;border:1px solid var(--f);background:var(--f-soft);border-radius:999px;font-weight:500}
.turn li::before{content:counter(t);font-family:var(--mono);font-size:11px;color:var(--f);width:16px;text-align:center}
.turn .emblem{width:24px;height:24px}
.after{font-size:14px;color:var(--muted)}
.mapfig{margin:0;display:grid;gap:10px}
.mapscroll{overflow-x:auto;border:1px solid var(--rule);border-radius:6px;background:var(--sea)}
.map{display:block;width:100%;min-width:640px;height:auto}
.map .own{fill-opacity:.42}
.map .mn{font-family:var(--mono);font-size:24px;font-weight:500;fill:var(--surface)}
.legend{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13.5px;color:var(--muted)}
.legend li{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px;background:var(--f);opacity:.75}
.sw.hatch{background:repeating-linear-gradient(45deg,var(--barb) 0 2px,var(--barb-s) 2px 5px);opacity:1}
.sw.land{background:var(--land);border:1px solid var(--rule);opacity:1}
.sw.dot{border-radius:50%;width:18px;height:18px;background:var(--ink);color:var(--surface);font:500 10px/18px var(--mono);text-align:center;font-style:normal;opacity:1}
.sw.ring{border-radius:50%;width:16px;height:16px;background:none;border:2px dashed var(--barb);opacity:1}
.sw-st{width:16px;height:16px;fill:var(--gold)}
h3.sec{margin:6px 0 -10px;font-size:26px}
.hint{margin:0;color:var(--muted);font-size:15px}
.powers{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:16px}
.power{border:1px solid var(--rule);border-top:4px solid var(--f);border-radius:6px;padding:14px 16px 12px;display:grid;gap:10px;align-content:start}
.ph{display:flex;gap:12px;align-items:center}
.ph .emblem{width:48px;height:48px;flex:none}
.ph h3{margin:0;color:var(--f);font-size:22px}
.ph h3 a{color:inherit;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px}
.pm{margin:2px 0 0;display:flex;flex-wrap:wrap;gap:2px 14px;font-size:14px;color:var(--muted)}
.pm b{color:var(--ink);font-weight:700}
.pm .gold{color:var(--gold)}
.pm span{display:inline-flex;align-items:center;gap:4px}
.st{width:14px;height:14px;fill:var(--f)}
.power .tw,.events .tw{margin:0}
table.setup{min-width:0;font-size:14.5px}
table.setup th.n,table.setup td.n{width:auto;min-width:38px}
table.setup th{font-size:9.5px;letter-spacing:.06em;vertical-align:bottom}
table.setup td.t{font-weight:500}
table.setup tr.sea td.t{font-style:italic;color:var(--muted)}
table.setup tfoot td{border-bottom:0;border-top:1px solid var(--ink);font-family:var(--mono);font-size:12px;color:var(--muted)}
table.setup tfoot td.n{color:var(--ink);font-weight:500}
.z{color:var(--rule)}
.also{margin:0;font-size:13.5px;color:var(--muted)}
.also b{color:var(--ink);font-weight:500}
.barb{border:1px solid var(--rule);border-top:4px solid var(--barb);border-radius:6px;padding:14px 16px;display:grid;gap:10px}
.barb h3{margin:0;color:var(--barb);font-size:22px}
.bcols{display:grid;grid-template-columns:1.5fr 1fr;gap:20px}
.bcols>div{display:grid;gap:8px;align-content:start}
.lab{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0}
.garr{list-style:none;margin:0;padding:0;font-size:14.5px;columns:2 220px;column-gap:20px}
.garr li{break-inside:avoid;display:grid;padding:3px 0;border-bottom:1px solid var(--rule)}
.garr .t{font-weight:500}
.garr .u{color:var(--muted);font-size:13.5px}
.spawn{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.spawn li{font-size:14px;padding:2px 10px;border:1.5px dashed var(--barb);border-radius:999px}
.note{margin:0;font-size:13.5px;color:var(--muted)}
.boss{background:var(--f-soft);border:1.5px solid var(--f);border-radius:6px;padding:14px 18px;display:grid;gap:4px}
.boss .lab{color:var(--f)}
.boss h3{margin:0;color:var(--f);font-size:24px}
.boss p{margin:0;max-width:72ch}
.routes,.events,.victory{display:grid;gap:8px}
.routes h3,.events h3,.victory h3{margin:0;font-size:22px}
.routes p,.events>p,.victory p{margin:0;max-width:72ch}
.rt{margin:0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:4px 16px;font-size:14.5px}
.rt li{padding:3px 0;border-bottom:1px solid var(--rule)}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
table.evt{min-width:640px;font-size:14px}
table.evt td.ev{font-weight:700;white-space:nowrap;padding-right:12px}
table.evt td.when{color:var(--muted);font-size:13px}
table.tiers{min-width:0;max-width:460px;font-size:15px}
.tbd{color:var(--muted);font-style:italic}
.tbd-box{border:1px dashed var(--rule);border-radius:6px;padding:12px 16px;display:grid;gap:4px}
.tbd-box p{margin:0;font-size:14.5px}
.jump .pc{font-family:var(--mono);font-size:11px;color:var(--gold);border:1px solid var(--gold);border-radius:3px;padding:0 4px;margin-left:6px}
.jump a[aria-current="page"]{border-color:var(--gold);background:var(--gold-soft)}
.jump a{padding:5px 12px 5px 5px}
@media (max-width:700px){.coin{width:72px;height:72px}.facts,.bcols{grid-template-columns:1fr}}
@media print{.mapscroll{overflow:visible}.map{min-width:0}.power,.barb{break-inside:avoid}}
"""


def faction_css():
    src = (SITE / "faction-rome.html").read_text(encoding="utf8")
    return re.search(r"<style>(.*?)</style>", src, re.S).group(1)


# --------------------------------------------- faction sheets' scenario lists

def scenario_lists(all_sc):
    """Rewrite each faction sheet's Scenarios list from the real data."""
    by_key = {}
    for file, fname, n, title, _ in SCENARIOS:
        for f in all_sc[file]["turn_order"]:
            by_key.setdefault(FKEY[f][0], []).append((n, fname, title))
    for path in [SITE / "factions.html", *SITE.glob("faction-*.html")]:
        s = path.read_text(encoding="utf8")

        def repl(m):
            key = m.group(1)
            items = by_key.get(key, [])
            if items:
                lis = "".join('<li><span class="pc">%dP</span><a href="%s">%s</a></li>' % it for it in items)
            else:
                lis = '<li class="none">Not in a scenario yet.</li>'
            return m.group(0)[: m.start(2) - m.start(0)] + lis + m.group(0)[m.end(2) - m.start(0):]

        s2 = re.sub(r'<article class="sheet" id="[^"]*" data-f="(\w+)">.*?<ul class="sc">(.*?)</ul>', repl, s, flags=re.S)
        if ".sc a{" not in s2:
            s2 = s2.replace("</style>", ".sc a{color:var(--ink);text-decoration-color:var(--f);text-underline-offset:3px}"
                                        ".sc a:hover{color:var(--f)}.sc li.none{color:var(--muted);font-style:italic}</style>", 1)
        path.write_text(s2, encoding="utf8")


def main():
    all_sc = {f: json.loads((DATA / "scenarios" / (f + ".json")).read_text(encoding="utf8")) for f, *_ in SCENARIOS}
    css = faction_css()
    for i, (_, fname, *_r) in enumerate(SCENARIOS):
        (SITE / fname).write_text(page(i, all_sc, css), encoding="utf8")
        print("wrote", fname)
    scenario_lists(all_sc)
    print("updated faction sheet scenario lists")


if __name__ == "__main__":
    main()
