"""Management Preview -- the campus as one dark "office intelligence" screen.

27 Nov 2026 night, Shamroze, with ChatGPT's "EnergyCam: Office
Intelligence" brief and its three mock-ups: "Management Preview ka column
pehle add karo, password wahi, aur andar exact aisa dashboard chahiye ...
3D dekho kitne pyar se bana hai, hamara nakli lagta hai".

What it shows, in the mock-ups' order: a header (campus switch, date,
live), five KPI cards with their day's line, the Office Digital Twin (3D,
every room of the campus coloured as the cameras see it now), the team's
work pattern, the AC's money by the hour today against yesterday, how much
of the AC's running was in rooms with people, the discoveries (explainable
rules, each with its evidence, method and confidence), the rooms' status,
the savings tracker, the data's coverage, and the quick actions.

The brief's rules are kept: every number is a real one the other pages
already work out (the mock-ups' figures are fiction and are not copied);
what the building cannot measure -- room temperature -- says so instead of
a number; estimates say they are estimates and how; work patterns are
team-level (no individual ranking); never a camera picture (the hosted
page shows none). The 3D twin is a schematic: the rooms are this campus's
own, placed by the system on their floors -- not the architect's plan.

No Streamlit and no database here: plain values in, HTML out, so the tests
can draw every part.
"""
import html
import json
import math

INK, MUTED = "#e6f0ff", "#8ea3c7"
C = {"cyan": "#22d3ee", "green": "#22c55e", "red": "#ef4444",
     "amber": "#f59e0b", "purple": "#a78bfa", "blue": "#3b82f6",
     "grey": "#64748b", "slate": "#334155"}

# room colours in the twin and on the legend
STATUS = {
    "occupied": ("#22c55e", "Occupied"),
    "empty": ("#94a3b8", "Empty"),
    "waste": ("#ef4444", "Empty + AC on"),
    "low": ("#f59e0b", "Few people"),
    "unknown": ("#334155", "Not answering"),
    "private": ("#1e293b", "Private hours"),
}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def _fmt(n, digits=0):
    if n is None:
        return "&ndash;"
    if digits:
        return ("%." + str(digits) + "f") % n
    return format(int(round(n)), ",")


# ------------------------------------------------------------------- icons
# Line icons drawn here (no icon font): stroke paths on a 24-unit box.
ICONS = {
    "people": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.6 2.7-6 6-6s6 '
              '2.4 6 6"/><circle cx="17" cy="9" r="2.6"/><path d="M15.5 14.2c3'
              ' .2 5.5 2.3 5.5 5.8"/>',
    "desk": '<path d="M3 10h18M5 10v9M19 10v9M8 10V6h8v4M9 14h6"/>',
    "snow": '<path d="M12 2v20M4 7l16 10M20 7L4 17M9 3.5 12 6l3-2.5M9 20.5 '
            '12 18l3 2.5"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "coins": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v5c0 1.7 3.1 '
             '3 7 3s7-1.3 7-3V6M5 11v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/>',
    "home": '<path d="M3 11 12 4l9 7M5 10v10h14V10"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "cube": '<path d="M12 2 21 7v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 '
             '18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
    "doc": '<path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h8M9 17h8"/>',
    "gear": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3'
            'M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    "leaf": '<path d="M5 19C5 9 11 4 20 4c0 9-5 15-15 15z"/><path d="M5 19 '
            '13 11"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.6 2.6L16 9.5"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 10v4.5M12 17.5v.5"/>',
    "bulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.8.6 1.1 1.4 '
            '1.1 2.2h5c0-.8.3-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>',
    "trophy": '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a4 4 0 0 0 4 4M16 6h4v1'
              'a4 4 0 0 1-4 4M12 13v4M8 21h8M10 17h4v4h-4z"/>',
    "camera": '<path d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" '
              'r="4"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 '
                '10h18M8 3v4M16 3v4"/>',
    "pulse": '<path d="M2 12h4l3-7 4 14 3-7h6"/>',
    "shield": '<path d="M12 2 4 6v6c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V6z"/>',
}


def icon(name, colour=C["cyan"], size=22, stroke=1.8):
    return ('<svg width="%d" height="%d" viewBox="0 0 24 24" fill="none" '
            'stroke="%s" stroke-width="%s" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true">%s</svg>'
            % (size, size, colour, stroke, ICONS.get(name, "")))


# -------------------------------------------------------------------- CSS
def css():
    """The page's dark navy look. One <style> block of its own (two on one
    line in st.markdown leave the second open -- productivity_view)."""
    return """<style>
.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:
radial-gradient(1200px 600px at 20% -10%,#0f2a55 0%,rgba(5,13,31,0) 60%),
radial-gradient(900px 500px at 100% 0%,#0b2447 0%,rgba(5,13,31,0) 55%),
#050d1f !important}
[data-testid="stAppViewContainer"] .main .block-container{max-width:1480px}
.mp{font-family:Inter,"Segoe UI",Roboto,Arial,sans-serif;color:#e6f0ff}
.mp *{box-sizing:border-box}
.mp a{color:inherit;text-decoration:none}
.mp-top{display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px;
justify-content:space-between;margin:2px 0 14px}
.mp-title{font-size:30px;font-weight:800;letter-spacing:-.01em;line-height:1.1}
.mp-title span{background:linear-gradient(90deg,#38bdf8,#22d3ee 45%,#34d399);
-webkit-background-clip:text;background-clip:text;color:transparent}
.mp-sub{color:#7dd3fc;font-size:15px;margin-top:4px;letter-spacing:.02em}
.mp-sub i{color:#3b82f6;font-style:normal;margin:0 8px}
.mp-right{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.mp-camp{padding:10px 20px;border-radius:999px;border:1px solid #23406e;
background:rgba(15,30,60,.7);color:#cfe1ff;font-weight:650;font-size:14.5px}
.mp-camp.on{background:linear-gradient(90deg,#1d4ed8,#2563eb);border-color:#3b82f6;
color:#fff;box-shadow:0 0 18px rgba(37,99,235,.45)}
.mp-when{display:flex;align-items:center;gap:10px;padding:6px 14px;
border-left:1px solid #23406e;color:#dbe8ff;font-size:14px;line-height:1.35}
.mp-live{color:#22c55e;font-weight:700}
.mp-live i{display:inline-block;width:8px;height:8px;border-radius:50%;
background:#22c55e;margin-right:6px;box-shadow:0 0 10px #22c55e}
.mp-live.off{color:#f87171}.mp-live.off i{background:#f87171;box-shadow:0 0 10px #f87171}
.mp-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;
margin-bottom:14px}
.mp-card{background:linear-gradient(180deg,rgba(16,33,66,.92),rgba(8,20,43,.92));
border:1px solid #1c3866;border-radius:16px;box-shadow:0 0 0 1px rgba(56,189,248,.04),
0 10px 30px rgba(0,0,0,.35),inset 0 1px 0 rgba(148,197,255,.06);padding:16px 18px;
position:relative;overflow:hidden}
.mp-kpi{display:grid;grid-template-columns:52px 1fr;gap:4px 12px;align-items:center;
min-height:128px}
.mp-kpi .ic{grid-row:1/3;width:48px;height:48px;border-radius:14px;display:flex;
align-items:center;justify-content:center;background:rgba(34,211,238,.08)}
.mp-kpi .k{font-size:14.5px;font-weight:650;color:#e2ecff;line-height:1.25}
.mp-kpi .v{font-size:30px;font-weight:800;letter-spacing:-.01em;line-height:1.05;
font-variant-numeric:tabular-nums}
.mp-kpi .v small{font-size:15px;font-weight:650;color:#9fb4d8;margin-left:4px}
.mp-kpi .d{font-size:13px;font-weight:700;margin-left:8px}
.mp-kpi .d.up{color:#22c55e}.mp-kpi .d.down{color:#f87171}.mp-kpi .d.flat{color:#94a3b8}
.mp-kpi .n{grid-column:1/3;font-size:11.5px;color:#8ea3c7;margin-top:2px}
.mp-kpi svg.sp{grid-column:1/3;width:100%;height:34px;margin-top:2px}
.mp-h{display:flex;align-items:center;justify-content:space-between;gap:10px;
margin-bottom:12px}
.mp-h .t{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:750}
.mp-h .s{font-size:12px;color:#8ea3c7}
.mp-pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;
padding:5px 11px;border-radius:999px;border:1px solid #23406e;
background:rgba(15,30,60,.7);color:#cfe1ff}
.mp-legend{display:flex;flex-wrap:wrap;gap:8px 14px;font-size:12.5px;color:#cbd5e1}
.mp-legend i{display:inline-block;width:10px;height:10px;border-radius:50%;
margin-right:6px;vertical-align:-1px}
.mp-grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;
margin-top:14px}
.mp-grid3{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:14px;margin-top:14px}
.mp-donut{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.mp-rows{display:flex;flex-direction:column;gap:9px;flex:1;min-width:150px}
.mp-row{display:flex;justify-content:space-between;gap:10px;font-size:14px}
.mp-row b{font-variant-numeric:tabular-nums}
.mp-row span i{display:inline-block;width:11px;height:11px;border-radius:50%;
margin-right:9px;vertical-align:-1px}
.mp-note{font-size:11.5px;color:#8ea3c7;line-height:1.45;margin-top:10px}
.mp-ok{display:flex;gap:10px;align-items:center;margin-top:10px;padding:10px 12px;
border-radius:12px;border:1px solid rgba(34,197,94,.35);background:rgba(34,197,94,.08);
font-size:13.5px}
.mp-disc{border:1.5px solid #f59e0b;border-radius:14px;padding:13px 14px;
background:linear-gradient(180deg,rgba(245,158,11,.08),rgba(245,158,11,.02))}
.mp-disc .tt{display:flex;justify-content:space-between;gap:8px;align-items:center}
.mp-disc .tt b{color:#fbbf24;font-size:15px}
.mp-tag{font-size:11px;font-weight:750;padding:3px 9px;border-radius:999px;
background:rgba(245,158,11,.18);color:#fcd34d;white-space:nowrap}
.mp-tag.med{background:rgba(59,130,246,.18);color:#93c5fd}
.mp-tag.low{background:rgba(148,163,184,.16);color:#cbd5e1}
.mp-disc p{margin:8px 0 0;font-size:13.5px;line-height:1.45;color:#e2e8f0}
.mp-disc .sg{color:#fbbf24;font-weight:700;margin-top:8px;font-size:13px}
.mp-disc .ev{font-size:11.5px;color:#9fb4d8;margin-top:6px;line-height:1.4}
.mp-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;
padding:10px 14px;border-radius:12px;font-weight:750;font-size:14px;
background:linear-gradient(90deg,#f59e0b,#fbbf24);color:#1f1300 !important;
margin-top:10px;width:100%}
.mp-btn.ghost{background:transparent;border:1px solid #2b4a7c;color:#cfe1ff !important}
.mp-more{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.mp-mini{display:flex;gap:10px;align-items:flex-start;font-size:13px;
padding:9px 10px;border-radius:11px;background:rgba(15,30,60,.6);
border:1px solid #1c3866}
.mp-mini b{display:block;font-size:13px}
.mp-bar{height:7px;border-radius:99px;background:#1e3358;overflow:hidden;
margin-top:6px}
.mp-bar i{display:block;height:100%;border-radius:99px;
background:linear-gradient(90deg,#10b981,#22d3ee)}
.mp-team{display:grid;grid-template-columns:22px 1fr auto;gap:2px 10px;
align-items:center;padding:6px 0;font-size:14px}
.mp-team .r{color:#8ea3c7;font-weight:700}
.mp-team .bar{grid-column:2/4}
.mp-tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.mp-tbl th{color:#9fb4d8;font-weight:650;text-align:left;padding:7px 8px;
border-bottom:1px solid #1c3866;font-size:12.5px}
.mp-tbl td{padding:8px;border-bottom:1px solid rgba(28,56,102,.55)}
.mp-tbl tr.w td{background:rgba(239,68,68,.10)}
.mp-st{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:650}
.mp-acts{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:14px}
.mp-acts .lbl{display:flex;align-items:center;gap:8px;font-weight:750;font-size:16px;
margin-right:6px}
.mp-act{display:inline-flex;align-items:center;gap:9px;padding:11px 16px;
border-radius:12px;border:1px solid #2b4a7c;background:rgba(15,30,60,.75);
font-size:14px;font-weight:650}
.mp-act:hover{border-color:#38bdf8;box-shadow:0 0 14px rgba(56,189,248,.25)}
.mp-health{display:flex;align-items:center;gap:12px;padding:12px 16px;
border-radius:14px;border:1px solid rgba(34,197,94,.45);
background:rgba(34,197,94,.08);margin-left:auto}
.mp-health.bad{border-color:rgba(248,113,113,.5);background:rgba(248,113,113,.08)}
.mp-health b{display:block;color:#4ade80;font-size:15px}
.mp-health.bad b{color:#f87171}
.mp-health span{font-size:12px;color:#a7b8d6}
.mp-nav{display:flex;flex-direction:column;gap:6px}
.mp-logo{display:flex;flex-direction:column;align-items:flex-start;gap:4px;
margin:0 0 16px 4px}
.mp-logo b{font-size:24px;font-weight:800}
.mp-logo b span{color:#34d399}
.mp-logo small{font-size:11.5px;color:#7dd3fc}
.mp-nv{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:12px;
font-size:15px;color:#dbe8ff}
.mp-nv.on{background:linear-gradient(90deg,#1d4ed8,#2563eb);color:#fff;
box-shadow:0 0 18px rgba(37,99,235,.35)}
.mp-nv:hover{background:rgba(37,99,235,.18)}
.mp-green{margin-top:16px;border-radius:16px;padding:14px;
background:linear-gradient(180deg,rgba(22,101,52,.55),rgba(5,46,22,.65));
border:1px solid rgba(74,222,128,.35)}
.mp-green .v{font-size:28px;font-weight:800;margin-top:6px}
.mp-green .k{font-size:14px;font-weight:650}
.mp-twin-h{margin-bottom:6px}
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"]{display:none !important}
.st-key-mgmt_campus{margin:-4px 0 14px}
.st-key-mgmt_campus [data-testid="stButtonGroup"]{gap:10px}
div.st-key-mgmt_campus div[data-testid="stButtonGroup"] button{
border-radius:999px !important;padding:9px 20px !important;min-height:0 !important;
font-weight:650 !important;background:rgba(15,30,60,.7) !important;
border:1px solid #23406e !important;color:#cfe1ff !important}
div.st-key-mgmt_campus div[data-testid="stButtonGroup"] button p{
font-size:14.5px !important;font-weight:650 !important}
div.st-key-mgmt_campus div[data-testid="stButtonGroup"] button[aria-checked="true"]{
background:linear-gradient(90deg,#1d4ed8,#2563eb) !important;
border-color:#3b82f6 !important;color:#fff !important;
box-shadow:0 0 18px rgba(37,99,235,.45) !important}
@media (max-width:1100px){.mp-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}
.mp-grid4{grid-template-columns:repeat(2,minmax(0,1fr))}
.mp-grid3{grid-template-columns:1fr}}
@media (max-width:640px){.mp-kpis{grid-template-columns:repeat(2,minmax(0,1fr));
gap:10px}.mp-kpi{min-height:112px;grid-template-columns:40px 1fr}
.mp-kpi .ic{width:38px;height:38px}.mp-kpi .v{font-size:24px}
.mp-title{font-size:23px}.mp-grid4{grid-template-columns:1fr}
.mp-health{margin-left:0;width:100%}.mp-hide-sm{display:none}}
</style>"""


# ------------------------------------------------------------- tiny charts
def sparkline(values, colour, w=220, h=34):
    vals = [float(v) for v in values or [] if v is not None]
    if len(vals) < 2:
        return ('<svg class="sp" viewBox="0 0 %d %d" preserveAspectRatio="none">'
                '</svg>' % (w, h))
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pts = []
    for i, v in enumerate(vals):
        x = i * (w - 2) / (len(vals) - 1) + 1
        y = h - 3 - (v - lo) / span * (h - 8)
        pts.append("%.1f,%.1f" % (x, y))
    gid = "g%x" % (abs(hash((colour, tuple(vals)))) % 0xFFFFFF)
    area = "1,%d %s %d,%d" % (h, " ".join(pts), w - 1, h)
    return ('<svg class="sp" viewBox="0 0 %d %d" preserveAspectRatio="none">'
            '<defs><linearGradient id="%s" x1="0" x2="0" y1="0" y2="1">'
            '<stop offset="0" stop-color="%s" stop-opacity=".35"/>'
            '<stop offset="1" stop-color="%s" stop-opacity="0"/></linearGradient>'
            '</defs><polygon points="%s" fill="url(#%s)"/><polyline points="%s"'
            ' fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
            '</svg>' % (w, h, gid, colour, colour, area, gid, " ".join(pts),
                        colour))


def donut(parts, size=150, width=16, centre="", sub=""):
    """parts: [(value, colour)]; the centre text in the middle."""
    total = sum(max(0.0, float(v)) for v, _ in parts) or 1.0
    r = (size - width) / 2.0
    circ = 2 * math.pi * r
    off = 0.0
    arcs = []
    for v, col in parts:
        frac = max(0.0, float(v)) / total
        if frac <= 0:
            continue
        arcs.append('<circle cx="%s" cy="%s" r="%.1f" fill="none" stroke="%s" '
                    'stroke-width="%d" stroke-dasharray="%.2f %.2f" '
                    'stroke-dashoffset="%.2f" transform="rotate(-90 %s %s)"/>'
                    % (size / 2, size / 2, r, col, width,
                       max(0.0, frac * circ - 2), circ, -off, size / 2,
                       size / 2))
        off += frac * circ
    return ('<svg width="%d" height="%d" viewBox="0 0 %d %d" role="img">'
            '<circle cx="%s" cy="%s" r="%.1f" fill="none" stroke="#13284a" '
            'stroke-width="%d"/>%s<text x="50%%" y="48%%" text-anchor="middle" '
            'fill="#fff" font-size="30" font-weight="800" dominant-baseline='
            '"middle">%s</text><text x="50%%" y="66%%" text-anchor="middle" '
            'fill="#9fb4d8" font-size="11.5">%s</text></svg>'
            % (size, size, size, size, size / 2, size / 2, r, width,
               "".join(arcs), esc(centre), esc(sub)))


def ring(pct, colour="#22d3ee", size=118, width=12, centre="", sub=""):
    p = max(0.0, min(100.0, float(pct or 0)))
    return donut([(p, colour), (100 - p, "#13284a")], size, width, centre, sub)


def line_chart(series, labels, w=420, h=170, unit="", now_i=None):
    """series: [(values, colour, dashed, name)]; a few y gridlines."""
    vals = [v for s in series for v in s[0] if v is not None]
    hi = max(vals) if vals else 1.0
    hi = hi if hi > 0 else 1.0
    top = _nice(hi)
    pl, pb, pt = 44, 22, 8
    iw, ih = w - pl - 6, h - pb - pt
    n = max(len(s[0]) for s in series) if series else 0
    g = []
    for k in range(4):
        y = pt + ih - ih * k / 3.0
        g.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#1c3866" '
                 'stroke-width="1"/><text x="%d" y="%.1f" fill="#8ea3c7" '
                 'font-size="10.5" text-anchor="end">%s%s</text>'
                 % (pl, w - 6, y, y, pl - 6, y + 3.5,
                    _short_num(top * k / 3.0), unit))
    lines = []
    for vals_, col, dashed, _ in series:
        pts = ["%.1f,%.1f" % (pl + i * iw / max(n - 1, 1),
                              pt + ih - (v / top) * ih)
               for i, v in enumerate(vals_) if v is not None]
        if len(pts) > 1:
            lines.append('<polyline points="%s" fill="none" stroke="%s" '
                         'stroke-width="2.4" %s stroke-linejoin="round"/>'
                         % (" ".join(pts), col,
                            'stroke-dasharray="5 4"' if dashed else ""))
    xl = []
    for i, lab in labels:
        x = pl + i * iw / max(n - 1, 1)
        xl.append('<text x="%.1f" y="%d" fill="#8ea3c7" font-size="10.5" '
                  'text-anchor="middle">%s</text>' % (x, h - 5, esc(lab)))
    if now_i is not None and n > 1:
        x = pl + now_i * iw / (n - 1)
        xl.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="#38bdf8" '
                  'stroke-opacity=".35" stroke-dasharray="3 3"/>'
                  % (x, x, pt, pt + ih))
    return ('<svg viewBox="0 0 %d %d" width="100%%" role="img">%s%s%s</svg>'
            % (w, h, "".join(g), "".join(lines), "".join(xl)))


def _nice(x):
    if x <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(x))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * e >= x:
            return m * e
    return 10 * e


def _short_num(v):
    if v >= 1000:
        return ("%.1fk" % (v / 1000.0)).replace(".0k", "k")
    return "%d" % round(v)


# ------------------------------------------------------------------ the page
def header(p, pills=True):
    """pills=False: the campus switch is drawn by the page itself (a
    Streamlit control, so switching keeps the session -- a link reloads
    the page and asks for the password again)."""
    camps = "".join(
        '<a class="mp-camp%s" href="%s" target="_self">Campus %s</a>'
        % (" on" if c["on"] else "", esc(c["url"]), esc(c["name"]))
        for c in p["campuses"]) if pills else ""
    return ('<div class="mp"><div class="mp-top"><div><div class="mp-title">'
            'EnergyCam &ndash; <span>Office Intelligence Dashboard</span></div>'
            '<div class="mp-sub">Observe<i>&bull;</i>Understand<i>&bull;</i>'
            'Optimize</div></div><div class="mp-right">%s<div class="mp-when">'
            '%s<div>%s<br><span class="mp-live%s"><i></i>%s</span></div></div>'
            '</div></div></div>'
            % (camps, icon("calendar", "#cfe1ff", 22),
               "<br>".join(esc(x) for x in str(p["when"]).split("\n")),
               "" if p["live"] else " off",
               "Live" if p["live"] else esc(p["live_text"])))


def kpis(p):
    cards = []
    for k in p["kpis"]:
        cards.append(
            '<div class="mp-card mp-kpi"><div class="ic" style="background:%s">'
            '%s</div><div class="k">%s</div><div class="v">%s<small>%s</small>'
            '<span class="d %s">%s</span></div>%s<div class="n">%s</div></div>'
            % (k.get("bg", "rgba(34,211,238,.08)"),
               icon(k["icon"], k["colour"], 26), esc(k["label"]), k["value"],
               esc(k.get("unit", "")), k.get("dir", "flat"),
               k.get("delta", ""), sparkline(k.get("spark"), k["colour"]),
               k.get("note", "")))
    return '<div class="mp"><div class="mp-kpis">%s</div></div>' % "".join(cards)


def nav(p):
    items = "".join(
        '<a class="mp-nv%s" href="%s" target="_self">%s%s</a>'
        % (" on" if n["on"] else "", esc(n["url"]),
           icon(n["icon"], "#fff" if n["on"] else "#9fc3ff", 20), esc(n["label"]))
        for n in p["nav"])
    g = p.get("green") or {}
    green = ""
    if g:
        green = ('<div class="mp-green">%s<div class="k">%s</div><div class="v">'
                 '%s</div><div class="mp-note" style="color:#bbf7d0">%s</div>'
                 '</div>' % (icon("leaf", "#4ade80", 26), esc(g["label"]),
                             g["value"], g["note"]))
    return ('<div class="mp"><div class="mp-logo"><b>Energy<span>Cam</span></b>'
            '<small>Smart Office. Smarter Decisions.</small></div>'
            '<div class="mp-nav">%s</div>%s</div>' % (items, green))


def twin_head(p):
    leg = "".join('<span><i style="background:%s"></i>%s</span>' % (c, esc(t))
                  for k, (c, t) in STATUS.items() if k in p["twin"]["used"])
    return ('<div class="mp"><div class="mp-h mp-twin-h"><div class="t">%s'
            'Office Digital Twin &ndash; Live View</div><div class="mp-legend">'
            '%s</div></div><div class="mp-note" style="margin:-4px 0 8px">%s'
            '</div></div>' % (icon("cube", C["cyan"], 24), leg,
                              esc(p["twin"]["note"])))


def work(p):
    w = p.get("work")
    if not w:
        return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
                'class="t">%sWork Pattern Overview</div></div><div '
                'class="mp-note">The desk cameras have not read this campus\'s '
                'desks for today yet.</div></div></div>' % icon("chart"))
    rows = "".join('<div class="mp-row"><span><i style="background:%s"></i>'
                   '%s</span><b>%d%%</b></div>' % (col, esc(lab), round(v))
                   for lab, v, col in w["shares"])
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sWork Pattern Overview</div><span class="mp-pill">%s'
            '</span></div><div class="mp-donut">%s<div class="mp-rows">%s</div>'
            '</div>%s<div class="mp-note">%s</div></div></div>'
            % (icon("chart", C["cyan"], 22), esc(w["day_label"]),
               donut([(v, col) for _, v, col in w["shares"]], 150, 16,
                     "%d%%" % round(w["at_desk"]), "at own desk"),
               rows, line_chart([(w["curve"], C["cyan"], False, "people")],
                                w["curve_labels"], 420, 150),
               w["note"]))


def energy(p):
    e = p["energy"]
    labels = [(i, "%d%s" % ((i % 12) or 12, "am" if i < 12 else "pm"))
              for i in range(0, 24, 6)] + [(23, "12am")]
    better = e.get("vs_yday")
    banner = ""
    if better is not None:
        good = better <= 0
        banner = ('<div class="mp-ok" style="%s">%s<div>%s<br><span style="'
                  'color:#9fb4d8;font-size:12px">AC spend so far today against '
                  'yesterday by this hour (estimated)</span></div></div>'
                  % ("" if good else "border-color:rgba(248,113,113,.4);"
                     "background:rgba(248,113,113,.08)",
                     icon("check" if good else "alert",
                          "#4ade80" if good else "#f87171", 26),
                     "<b>%d%% %s than yesterday</b> &asymp; Rs %s" % (
                         abs(round(better)), "less" if good else "more",
                         _fmt(abs(e["diff_rs"])))))
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sEnergy Insights</div><span class="s">AC, Rs by hour'
            '</span></div><div class="mp-legend" style="margin-bottom:6px">'
            '<span><i style="background:%s"></i>Today</span><span><i style='
            '"background:#94a3b8"></i>Yesterday</span></div>%s%s<div '
            'class="mp-note">%s</div></div></div>'
            % (icon("bolt", C["amber"], 22), C["cyan"],
               line_chart([(e["today"], C["cyan"], False, "today"),
                           (e["yday"], "#94a3b8", True, "yesterday")],
                          labels, 420, 170, "", e.get("now_hour")),
               banner, e["note"]))


def ac_panel(p):
    a = p["ac"]
    rows = [("Running now (read by a camera)", "%s of %s" % (a["on"],
                                                           a["readable"])),
            ("Rooms with nobody in and AC on", "%d" % a["waste_rooms"]),
            ("Units a camera can read", "%s of %s" % (a["readable"],
                                                    a["all_units"]))]
    body = "".join('<div class="mp-row"><span>%s</span><b>%s</b></div>' % r
                   for r in rows)
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sAC Performance</div></div><div class="mp-donut">%s'
            '<div class="mp-rows">%s</div></div><div class="mp-mini" style='
            '"margin-top:12px">%s<div><b>Room temperature: not measured</b>'
            'No sensor or camera reads it yet. A few low-cost room sensors '
            'would let comfort be set beside energy.</div></div><div '
            'class="mp-note">%s</div></div></div>'
            % (icon("snow", C["cyan"], 22),
               ring(a["efficient"], C["green"], 118, 12,
                    "%d%%" % round(a["efficient"]) if a["efficient"] is not None
                    else "&ndash;", "with people in"),
               body, icon("alert", "#fbbf24", 20), a["note"]))


def discoveries(p):
    ds = p["discoveries"]
    if not ds:
        return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
                'class="t">%sSmart Insights</div></div><div class="mp-note">'
                'Nothing stands out right now: no room is cooled empty, every '
                'camera answers.</div></div></div>' % icon("bulb", "#fbbf24"))
    d = ds[0]
    tag = {"High": "", "Medium": " med", "Low": " low"}[d["impact"]]
    first = ('<div class="mp-disc"><div class="tt"><b>%s Discovery #%03d</b>'
             '<span class="mp-tag%s">%s Impact</span></div><p>%s</p>'
             '<div class="sg">Suggestion:</div><p style="margin-top:2px">%s</p>'
             '<div class="ev">Evidence: %s &middot; confidence %s</div>'
             '<a class="mp-btn" href="%s" target="_self">Inspect Evidence '
             '&rarr;</a></div>'
             % (icon("bulb", "#fbbf24", 18), d["n"], tag, d["impact"],
                d["text"], d["action"], d["evidence"], d["confidence"],
                esc(d["url"])))
    more = "".join(
        '<a class="mp-mini" href="%s" target="_self">%s<div><b>%s</b>%s</div>'
        '</a>' % (esc(x["url"]), icon(x.get("icon", "spark"), "#a78bfa", 18),
                  esc(x["title"]), x["short"]) for x in ds[1:4])
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sSmart Insights</div><span class="s">%d today</span>'
            '</div>%s<div class="mp-more">%s</div></div></div>'
            % (icon("bulb", "#fbbf24", 22), len(ds), first, more))


def teams(p):
    t = p.get("teams") or []
    if not t:
        body = ('<div class="mp-note">Department figures come from the desk '
                'cameras; none for this campus yet.</div>')
    else:
        body = "".join(
            '<div class="mp-team"><span class="r">%d</span><span>%s <small '
            'style="color:#8ea3c7">(%d)</small></span><b>%d%%</b><div class='
            '"mp-bar bar"><i style="width:%d%%"></i></div></div>'
            % (i, esc(n), k, round(v), round(v)) for i, (n, v, k)
            in enumerate(t[:5], 1))
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sTeams at their desks</div></div>%s<div class="mp-note">'
            'Time at their own desk as a share of time in the building, the '
            'last five working days, by department (5+ measured). Team-level '
            'only: no one person is ranked.</div></div></div>'
            % (icon("trophy", "#fbbf24", 22), body))


def rooms_table(p):
    rows = []
    for r in p["rooms_table"]:
        col, lab = {"waste": (C["red"], "Wasted cooling"),
                    "ok": (C["green"], "OK"),
                    "check": (C["amber"], "Check needed"),
                    "unknown": ("#94a3b8", "Not answering")}[r["kind"]]
        rows.append('<tr class="%s"><td><a href="%s" target="_self">%s</a></td>'
                    '<td>%s</td><td>%s</td><td><span class="mp-st" style="color:'
                    '%s">&#9679; %s</span></td></tr>'
                    % ("w" if r["kind"] == "waste" else "", esc(r["url"]),
                       esc(r["room"]), r["occ"], r["ac"], col, lab))
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sRoom-wise Status</div><span class="s">%d rooms with '
            'a unit or people</span></div><div style="max-height:330px;'
            'overflow:auto"><table class="mp-tbl"><tr><th>Room</th><th>People'
            '</th><th>AC</th><th>Status</th></tr>%s</table></div></div></div>'
            % (icon("home", C["cyan"], 22), len(p["rooms_table"]),
               "".join(rows)))


def savings(p):
    s = p["savings"]
    bars = []
    for lab, before, after in s["pairs"]:
        hi = max(before or 0, after or 0, 1)
        bars.append(
            '<div style="flex:1;min-width:120px"><div style="display:flex;gap:10px;'
            'align-items:flex-end;height:120px">%s%s</div><div style="text-align:'
            'center;font-size:12.5px;color:#cbd5e1;margin-top:6px">%s</div></div>'
            % (_bar(before, hi, "#94a3b8"), _bar(after, hi, "#22c55e"),
               esc(lab)))
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sCooling-empty Tracker</div><div class="mp-legend">'
            '<span><i style="background:#94a3b8"></i>Before</span><span><i '
            'style="background:#22c55e"></i>Now</span></div></div><div style='
            '"display:flex;gap:16px">%s</div><div class="mp-note">%s</div>'
            '</div></div>' % (icon("leaf", C["green"], 22), "".join(bars),
                              s["note"]))


def _bar(v, hi, col):
    h = 0 if not v else max(4, int(100 * v / hi))
    return ('<div style="flex:1;text-align:center"><div style="font-size:11.5px;'
            'color:#e2e8f0;margin-bottom:3px">%s</div><div style="height:%dpx;'
            'background:%s;border-radius:6px 6px 0 0"></div></div>'
            % ("Rs " + _fmt(v) if v else "&ndash;", h, col))


def trust(p):
    rows = "".join(
        '<div class="mp-row"><span>%s %s</span><b style="font-weight:600;'
        'color:#cbd5e1;font-size:12.5px;text-align:right">%s</b></div>'
        % (icon("check" if ok else "alert", "#4ade80" if ok else (
            "#fbbf24" if ok is None else "#f87171"), 16), esc(k), v)
        for ok, k, v in p["trust"])
    return ('<div class="mp"><div class="mp-card"><div class="mp-h"><div '
            'class="t">%sEvidence &amp; Trust</div></div><div class="mp-rows">'
            '%s</div><div class="mp-note">Counts are what the cameras see; '
            'unknown stays unknown. Estimates say so. No camera picture leaves '
            'the building.</div></div></div>' % (icon("shield", C["cyan"], 22),
                                                 rows))


def actions(p):
    acts = "".join('<a class="mp-act" href="%s" target="_self">%s%s</a>'
                   % (esc(a["url"]), icon(a["icon"], a["colour"], 20),
                      esc(a["label"])) for a in p["actions"])
    ok = p["live"] and not p.get("silent")
    return ('<div class="mp"><div class="mp-card"><div class="mp-acts"><span '
            'class="lbl">%sQuick Actions:</span>%s<div class="mp-health%s">%s'
            '<div><b>%s</b><span>%s</span></div></div></div></div></div>'
            % (icon("bolt", "#fbbf24", 22), acts, "" if ok else " bad",
               icon("pulse", "#4ade80" if ok else "#f87171", 30),
               "System Healthy" if ok else "Needs a look",
               esc(p["health_text"])))


# ------------------------------------------------------- data -> the panels
# Zones that are not rooms: the twin draws the building, not the car park.
OUTDOOR = ("outside", "perimeter", "parking")
FLOOR_ORDER = ("basement", "ground", "first", "second", "third", "fourth",
               "cafe", "main building", "not placed")


def floor_key(name):
    t = str(name or "").lower()
    for i, w in enumerate(FLOOR_ORDER):
        if w in t:
            return (i, t)
    return (len(FLOOR_ORDER), t)


def room_state(r):
    """occupied / empty / waste / unknown / private for one room row."""
    if r.get("private"):
        return "private"
    if r.get("waste"):
        return "waste"
    st = r.get("status")
    if st == "occupied":
        return "occupied"
    if st == "empty":
        return "empty"
    return "unknown"


def twin_payload(rooms, start=None, floor_w=46.0):
    """rooms: [{name, short, floor, zone, status, people, waste, ac_state,
    units, private, desks, q, since}] -> the twin's data: floors of laid-out
    rooms, the states used, the floor to open on."""
    shown, used = [], set()
    for r in rooms:
        if any(w in str(r.get("zone") or "").lower() for w in OUTDOOR):
            continue
        kind = kind_of(r["name"], r.get("zone"))
        w, d = room_size(kind, r.get("desks"))
        state = room_state(r)
        used.add(state)
        people = int(r.get("people") or 0)
        ac = {"on": "AC on", "off": "AC off"}.get(r.get("ac_state"),
                                                   "AC not read" if r.get(
                                                       "units") else "no AC")
        line = "%s &middot; %s &middot; %s" % (
            "nobody in" if state in ("empty", "waste") else
            ("%d %s" % (people, "person" if people == 1 else "people"))
            if state == "occupied" else STATUS[state][1].lower(),
            ac, STATUS[state][1])
        call = None
        if state == "waste":
            call = {"title": "AC ON", "good": False,
                    "text": "%s<br>empty%s" % (esc(r.get("short") or r["name"]),
                                               (" " + esc(r["since"]))
                                               if r.get("since") else "")}
        shown.append({"name": esc(r["name"]), "floor": r.get("floor") or
                      "Not placed yet", "kind": kind, "w": w, "d": d,
                      "status": state, "colour": STATUS[state][0],
                      "desks": int(r.get("desks") or 0),
                      "busy": min(people, int(r.get("desks") or 0)),
                      "line": line, "q": r.get("q") or "", "call": call})
    # the three busiest rooms get a green callout with their people, as in
    # the mock-ups ("Engineering (12 people)")
    people_of = {esc(r["name"]): int(r.get("people") or 0) for r in rooms}
    busy = sorted([s for s in shown if s["status"] == "occupied"
                   and not s["call"]],
                  key=lambda s: -people_of.get(s["name"], 0))
    for s in busy[:3]:
        n = people_of.get(s["name"], 0)
        if n >= 2:
            s["call"] = {"title": s["name"].replace("140-H ", "").replace(
                "141 ", ""), "good": True, "text": "%d people" % n}
    placed, depth = layout(shown, floor_w)
    floors = []
    for fl in sorted(placed, key=floor_key):
        rs = placed[fl]
        w = max([r["x"] + r["w"] for r in rs] or [floor_w])
        floors.append({"name": fl, "rooms": rs, "w": round(w, 1),
                       "d": round(depth[fl], 1)})
    names = [f["name"] for f in floors]
    if start not in names:
        # the floor with the most to see: AC-on-empty first, then people
        def score(f):
            return (sum(1 for r in f["rooms"] if r["status"] == "waste"),
                    sum(r["busy"] for r in f["rooms"]))
        start = max(floors, key=score)["name"] if floors else "All"
    return {"floors": floors, "used": sorted(used), "start": start,
            "note": "Schematic: this campus's own rooms placed on their floors "
                    "by the system, sized by their desks -- not the architect's"
                    " plan. Colours are the cameras' latest pass."}


def desks_by_room(spaces, campus):
    """{room: desks} from seating.yaml's spaces (HR's sheet, counts only),
    a space's seats shared among the rooms whose cameras see it."""
    out = {}
    for s in spaces or []:
        if campus and s.get("campus") and s.get("campus") != campus:
            continue
        rooms = s.get("rooms") or []
        seats = s.get("override", {}).get("seats") if isinstance(
            s.get("override"), dict) else None
        seats = seats or s.get("seats") or 0
        for r in rooms:
            out[r] = out.get(r, 0) + int(round(float(seats) / len(rooms)))
    return out


def desk_occupancy(rooms):
    """(share 0-100, desks) -- people at desk rooms over those desks."""
    desks = sum(int(r.get("desks") or 0) for r in rooms)
    if not desks:
        return None, 0
    busy = sum(min(int(r.get("people") or 0), int(r.get("desks") or 0))
               for r in rooms if r.get("status") == "occupied")
    return 100.0 * busy / desks, desks


def discover(live, ledger_today, hourly_today, silent, rate, room_url,
             read_rooms, now_label=""):
    """The day's discoveries -- explainable rules, each with its evidence,
    method and confidence, strongest first:
      1. a camera reads a unit running in a room with nobody in, now;
      2. a room cooled while empty today (the ledger: the hours times the
         unit's rating times the tariff);
      3. the hours of the day the empty cooling gathers in;
      4. cameras not answering (a gap in the evidence itself)."""
    out = []
    for r in [x for x in live if x.get("waste")][:3]:
        rs_h = r["kw"] * rate
        out.append({
            "kind": "waste_now", "impact": "High", "icon": "alert",
            "title": "AC on, nobody in: %s" % r["room"],
            "text": "In <b>%s</b> the camera reads %s running and nobody in "
                    "the room%s." % (esc(r["room"]), "the AC" if r["counted"]
                                     <= 1 else "%d units" % r["counted"],
                                     (" " + esc(r["since"])) if r.get("since")
                                     else ""),
            "action": "Switch it off. The next pass (about 10 min) shows "
                      "whether it went off; &asymp; Rs %s an hour while it "
                      "runs." % _fmt(rs_h),
            "evidence": "the unit's display/louvre and the room's people, "
                        "this pass",
            "confidence": "high (both read by a camera)",
            "short": "&asymp; Rs %s an hour now" % _fmt(rs_h),
            "url": room_url(r["room"]), "score": 3.0 + rs_h / 100.0})
    for r in sorted(ledger_today or [], key=lambda x: -x.get("waste_rs", 0)):
        if r.get("waste_rs", 0) < 100 or len(out) >= 6:
            continue
        read = bool(read_rooms.get(r.get("room")))
        h = r.get("empty_on_h") or 0.0
        out.append({
            "kind": "waste_today", "impact": "High" if r["waste_rs"] >= 500
            else "Medium", "icon": "coins",
            "title": "Cooled empty today: %s" % r.get("room", ""),
            "text": "<b>%s</b> was cooled with nobody in for about %.1f h so "
                    "far today &asymp; Rs %s." % (esc(r.get("room", "")), h,
                                                  _fmt(r["waste_rs"])),
            "action": "Look at who switches it on and when; a set time to "
                      "switch off after the room empties would test it.",
            "evidence": "empty hours from the cameras &times; the unit's "
                        "rating &times; the tariff (estimated)",
            "confidence": "high (unit read by a camera)" if read else
                          "low (unit not read: assumed running while empty)",
            "short": "&asymp; Rs %s, %.1f h empty" % (_fmt(r["waste_rs"]), h),
            "url": room_url(r.get("room", "")),
            "score": (2.0 if read else 1.0) + r["waste_rs"] / 1000.0})
    spans = _waste_spans(hourly_today)
    if spans:
        a, b, rs = spans[0]
        out.append({
            "kind": "hours", "impact": "Medium", "icon": "calendar",
            "title": "Empty cooling gathers %s-%s" % (_h(a), _h(b)),
            "text": "Most of today's cooling with nobody in falls between "
                    "<b>%s and %s</b> &asymp; Rs %s." % (_h(a), _h(b),
                                                         _fmt(rs)),
            "action": "Check the rooms empty in that window (lunch, end of "
                      "day) before setting a schedule.",
            "evidence": "the AC ledger by hour, today",
            "confidence": "medium (estimated rupees, measured hours)",
            "short": "&asymp; Rs %s in that window" % _fmt(rs),
            "url": "", "score": 1.5})
    if silent:
        out.append({
            "kind": "gap", "impact": "Low", "icon": "camera",
            "title": "%d room%s not answering" % (len(silent),
                                                 "" if len(silent) == 1
                                                 else "s"),
            "text": "No picture from <b>%s</b>%s this pass: their people and "
                    "AC are unknown, not zero." % (
                        esc(", ".join(silent[:3])),
                        " and %d more" % (len(silent) - 3)
                        if len(silent) > 3 else ""),
            "action": "Camera health shows when each last answered.",
            "evidence": "the loop's last pass", "confidence": "certain",
            "short": "unknown, not zero", "url": "", "score": 0.5})
    out.sort(key=lambda d: -d["score"])
    for i, d in enumerate(out, 1):
        d["n"] = i
    return out


def _h(hour):
    hour = int(hour) % 24
    return "%d %s" % ((hour % 12) or 12, "am" if hour < 12 else "pm")


def _waste_spans(hours, least=1.0, share=1 / 3.0):
    """[(from hour, to hour, rupees)] -- hours whose AC money went mostly
    to empty rooms, joined into stretches, the costliest first (the same
    rule as energy_rooms.waste_stretches)."""
    runs, cur = [], None
    for h, pair in enumerate(hours or []):
        spent, waste = (float(pair[0]), float(pair[1])) if pair else (0.0,
                                                                       0.0)
        if waste >= least and waste >= share * spent:
            if cur and cur[1] == h:
                cur = (cur[0], h + 1, cur[2] + waste)
            else:
                if cur:
                    runs.append(cur)
                cur = (h, h + 1, waste)
        elif cur:
            runs.append(cur)
            cur = None
    if cur:
        runs.append(cur)
    return sorted(runs, key=lambda r: -r[2])


def room_rows(rooms, room_url):
    """The room table: rooms with a unit or people, wasted cooling first."""
    out = []
    for r in rooms:
        if not (r.get("units") or r.get("people")) or r.get("private"):
            continue
        st = room_state(r)
        people = int(r.get("people") or 0)
        occ = ("&ndash;" if st == "unknown" else "%d" % people)
        ac = {"on": "ON", "off": "OFF"}.get(r.get("ac_state"),
                                             "?" if r.get("units") else "&ndash;")
        if st == "waste":
            kind = "waste"
        elif st == "unknown":
            kind = "unknown"
        elif r.get("units") and r.get("ac_state") is None and people:
            kind = "check"
        else:
            kind = "ok"
        out.append({"room": r["name"], "occ": occ, "ac": ac, "kind": kind,
                    "url": room_url(r["name"])})
    rank = {"waste": 0, "check": 1, "ok": 2, "unknown": 3}
    return sorted(out, key=lambda x: (rank[x["kind"]], x["room"]))


def work_payload(people, day=None, min_people=3):
    """Team-level shares of time in the building, from the desk cameras'
    days (the board's history): at the desk on the computer / phone /
    talking / desk (not read) / away from the desk. The latest day at
    least `min_people` were read on (or `day`). None when there is none."""
    by_day = {}
    for p in people or []:
        for r in p.get("history") or []:
            d = str(r.get("day"))[:10]
            if (r.get("in_min") or 0) > 30:
                by_day.setdefault(d, []).append(r)
    days = sorted(d for d, rs in by_day.items() if len(rs) >= min_people)
    if day not in days:
        day = days[-1] if days else None
    if not day:
        return None
    rs = by_day[day]
    tot = sum(float(r["in_min"]) for r in rs)
    desk = sum(min(float(r.get("desk_min") or 0), float(r["in_min"]))
               for r in rs)
    read = [r for r in rs if r.get("computer_min") is not None]
    comp = sum(float(r.get("computer_min") or 0) for r in read)
    phone = sum(float(r.get("phone_min") or 0) for r in read)
    talk = sum(float(r.get("talking_min") or 0) for r in read)
    unread = max(0.0, desk - comp - phone - talk)
    away = max(0.0, tot - desk)
    shares = [("At desk, on the computer", comp, C["green"]),
              ("At desk, on the phone", phone, C["blue"]),
              ("At desk, talking", talk, C["amber"]),
              ("At desk, not read", unread, C["cyan"]),
              ("Away from the desk", away, C["purple"])]
    total = sum(v for _, v, _ in shares) or 1.0
    return {"day": day, "people": len(rs),
            "shares": [(lab, 100.0 * v / total, col) for lab, v, col in shares
                       if v > 0],
            "at_desk": 100.0 * desk / (tot or 1.0)}


def team_rows(people, days=5, least=5):
    """[(department, at-desk %, people)] -- time at their own desk over
    time in the building, the last `days` days each, departments with
    `least`+ measured. Team-level only."""
    by = {}
    for p in people or []:
        # the roster's department (the board's own "department" is the
        # room), else the role's "designation, department"
        role = [x.strip() for x in str(p.get("role") or "").split(",")]
        dept = p.get("dept") or (role[1] if len(role) > 1 and role[1]
                                 else None)
        if not dept:
            continue
        rs = [r for r in (p.get("history") or [])
              if (r.get("in_min") or 0) > 30][-days:]
        if not rs:
            continue
        d = by.setdefault(dept, [0.0, 0.0, 0])
        d[0] += sum(min(float(r.get("desk_min") or 0), float(r["in_min"]))
                    for r in rs)
        d[1] += sum(float(r["in_min"]) for r in rs)
        d[2] += 1
    rows = [(k, 100.0 * v[0] / v[1], v[2]) for k, v in by.items()
            if v[2] >= least and v[1] > 0]
    return sorted(rows, key=lambda r: -r[1])


# -------------------------------------------------------------- the 3D twin
def layout(rooms, floor_w=46.0, gap=1.4):
    """Each floor's rooms packed into rows (a schematic, not the plan):
    bigger rooms first, rooms sized by their desks (or their kind), rows
    filled to floor_w. Returns {floor: [room + x, z, w, d]} and each
    floor's depth."""
    floors = {}
    for r in rooms:
        floors.setdefault(r["floor"], []).append(r)
    out, depth = {}, {}
    for fl, rs in floors.items():
        rs = sorted(rs, key=lambda r: -(r["w"] * r["d"]))
        x, z, row_d, placed = 0.0, 0.0, 0.0, []
        for r in rs:
            if x > 0 and x + r["w"] > floor_w:
                x, z = 0.0, z + row_d + gap
                row_d = 0.0
            placed.append(dict(r, x=x, z=z))
            x += r["w"] + gap
            row_d = max(row_d, r["d"])
        out[fl] = placed
        depth[fl] = z + row_d
    return out, depth


def room_size(kind, desks):
    """(w, d) in the schematic's units: offices by their desks."""
    if desks:
        n = max(4, min(int(desks), 60))
        w = 4.0 + 1.1 * math.sqrt(n) * 2.0
        return round(min(w, 18.0), 1), round(min(3.5 + 0.9 * math.sqrt(n) * 1.6,
                                                  12.0), 1)
    return {"meeting": (7.0, 5.0), "cafe": (11.0, 7.5), "server": (4.0, 3.5),
            "lobby": (8.0, 5.5), "outside": (9.0, 6.0)}.get(kind, (6.0, 4.5))


def kind_of(name, zone):
    t = ("%s %s" % (name, zone)).lower()
    for word, kind in (("server", "server"), ("cafe", "cafe"),
                       ("cafeteria", "cafe"), ("meeting", "meeting"),
                       ("conference", "meeting"), ("board", "meeting"),
                       ("reception", "lobby"), ("lobby", "lobby"),
                       ("entrance", "lobby"), ("parking", "outside"),
                       ("outside", "outside"), ("roof", "outside")):
        if word in t:
            return kind
    return "office"


def twin_doc(p, height=520):
    """The 3D twin as a document of its own (components.html): three.js
    r128 (cdnjs) and its OrbitControls (jsDelivr), the payload inline."""
    data = json.dumps(p["twin"], separators=(",", ":"))
    return TWIN_HTML.replace("__DATA__", data).replace("__H__", str(height))


TWIN_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;height:100%;background:transparent;overflow:hidden;
font-family:Inter,"Segoe UI",Roboto,Arial,sans-serif}
#wrap{position:relative;width:100%;height:__H__px;border-radius:16px;overflow:hidden;
background:radial-gradient(800px 420px at 50% 30%,#10284e 0%,#071226 70%);
border:1px solid #1c3866;box-shadow:inset 0 0 60px rgba(34,211,238,.06)}
#c{position:absolute;inset:0;width:100%;height:100%;display:block}
.bar{position:absolute;top:12px;left:12px;right:12px;display:flex;gap:8px;
flex-wrap:nowrap;overflow-x:auto;align-items:center;z-index:3;
scrollbar-width:none;padding-bottom:2px}
.bar::-webkit-scrollbar{display:none}
.btn{background:rgba(15,30,60,.85);border:1px solid #2b4a7c;color:#dbe8ff;
border-radius:10px;padding:7px 12px;font-size:12.5px;cursor:pointer;
font-weight:650;white-space:nowrap;flex:0 0 auto}
.btn.on{background:#2563eb;border-color:#3b82f6;color:#fff}
.sp{flex:1}
.call{position:absolute;z-index:2;pointer-events:none;transform:translate(-50%,-100%);
background:rgba(20,8,12,.88);border:1.5px solid #ef4444;color:#fff;border-radius:10px;
padding:6px 10px;font-size:12px;line-height:1.35;white-space:nowrap;
box-shadow:0 0 14px rgba(239,68,68,.45)}
.call b{color:#fca5a5}
.call.g{border-color:#22c55e;box-shadow:0 0 14px rgba(34,197,94,.35);
background:rgba(6,24,14,.88)}
.call.g b{color:#86efac}
#tip{position:absolute;z-index:4;display:none;background:rgba(8,18,38,.95);
border:1px solid #38bdf8;color:#e6f0ff;border-radius:10px;padding:9px 12px;
font-size:12.5px;line-height:1.45;max-width:240px;pointer-events:none}
#tip b{font-size:13.5px}
.note{position:absolute;bottom:8px;left:12px;right:12px;z-index:3;font-size:11px;
color:#8ea3c7;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
</style></head><body><div id="wrap"><canvas id="c"></canvas>
<div class="bar" id="bar"></div><div id="tip"></div>
<div class="note"><span></span><span>tap a room &middot; "Explore 3D" to turn
and zoom</span></div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const D=__DATA__;
const wrap=document.getElementById('wrap'),canvas=document.getElementById('c');
const tip=document.getElementById('tip');
const R=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
R.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
const S=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(36,1,0.5,900);
const ctl=new THREE.OrbitControls(cam,canvas);
ctl.enableDamping=true;ctl.dampingFactor=0.08;ctl.maxPolarAngle=Math.PI*0.47;
ctl.minDistance=12;ctl.maxDistance=260;
// still until "Explore 3D": the page scrolls over it (a phone's finger, a
// mouse wheel), taps still open a room
ctl.enabled=false;canvas.style.touchAction='pan-y';
S.add(new THREE.HemisphereLight(0xcfe6ff,0x0a1830,0.95));
const sun=new THREE.DirectionalLight(0xffffff,0.75);sun.position.set(30,60,25);S.add(sun);
const ROOT=new THREE.Group();S.add(ROOT);
const pick=[],calls=[];
const mat=(c,o)=>new THREE.MeshStandardMaterial(Object.assign({color:c,roughness:.75,metalness:.05},o||{}));
const WALL=mat(0xe8eef7,{roughness:.55}),GLASS=mat(0x9fd8ff,{transparent:true,opacity:.28,roughness:.1});
const DESK=mat(0xd9c3a3,{roughness:.6}),DESK2=mat(0x6b7f99),CHAIR=mat(0x1f2937);
const FLOORM=mat(0x1a2b47,{roughness:.9}),SLAB=mat(0x0f1d36,{roughness:.95});
const WH=1.25,WT=0.14;
let floorsShown=[];
function box(w,h,d,m,x,y,z,g){const o=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m);
o.position.set(x,y,z);(g||ROOT).add(o);return o}
function build(sel){
 while(ROOT.children.length)ROOT.remove(ROOT.children[0]);pick.length=0;
 calls.forEach(c=>c.el.remove());calls.length=0;
 const fls=D.floors.filter(f=>sel==='All'||f.name===sel);floorsShown=fls;
 let y=0,maxW=0,maxD=0;
 fls.forEach((f,fi)=>{
  const g=new THREE.Group();g.position.y=y;ROOT.add(g);
  maxW=Math.max(maxW,f.w);maxD=Math.max(maxD,f.d);
  box(f.w+3,0.5,f.d+3,SLAB,f.w/2,-0.3,f.d/2,g);
  f.rooms.forEach(r=>{
   const col=new THREE.Color(r.colour);
   const glow=mat(col,{emissive:col,emissiveIntensity:r.status==='waste'?0.75:0.35,roughness:.6});
   const fl=box(r.w,0.08,r.d,glow,r.x+r.w/2,0.02,r.z+r.d/2,g);fl.userData=r;pick.push(fl);
   const wm=r.kind==='meeting'?GLASS:WALL;
   box(r.w,WH,WT,wm,r.x+r.w/2,WH/2,r.z,g);
   box(r.w,WH*.55,WT,GLASS,r.x+r.w/2,WH*.55/2,r.z+r.d,g);
   box(WT,WH,r.d,wm,r.x,WH/2,r.z+r.d/2,g);
   box(WT,WH,r.d,WALL,r.x+r.w,WH/2,r.z+r.d/2,g);
   furnish(r,g);
   if(r.call){const el=document.createElement('div');el.className='call'+(r.call.good?' g':'');
    el.innerHTML='<b>'+r.call.title+'</b><br>'+r.call.text;wrap.appendChild(el);
    calls.push({el,p:new THREE.Vector3(r.x+r.w/2,y+WH+0.6,r.z+r.d/2)});}
  });
  const lab=document.createElement('div');lab.className='call g';lab.style.background='rgba(8,18,38,.8)';
  lab.style.borderColor='#2b4a7c';lab.style.boxShadow='none';lab.innerHTML='<b style="color:#7dd3fc">'+f.name+'</b>';
  wrap.appendChild(lab);calls.push({el:lab,p:new THREE.Vector3(f.w/2,y+0.5,-2.2)});
  y+=sel==='All'?9:0;
 });
 view={w:maxW,d:maxD,y:y,all:sel==='All'};frame();
}
let view={w:40,d:30,y:0,all:false};
function frame(){
 // the whole floor in view: further back on a narrow (phone) screen
 const aspect=Math.max(0.45,Math.min(2.2,(wrap.clientWidth||400)/(wrap.clientHeight||500)));
 const cx=view.w/2,cz=view.d/2;
 const span=(Math.max(view.w,view.d)+(view.all?view.y*0.9:0))*(1.55/Math.min(1.35,Math.sqrt(aspect)))*(aspect<1?Math.pow(1/aspect,0.6)*0.82:1);
 ctl.target.set(cx,(view.all?view.y/2-4:0),cz);
 cam.position.set(cx-span*0.55,span*0.72+8,cz+span*0.92);ctl.update();
}
function furnish(r,g){
 if(r.kind==='office'&&r.desks>0){
  const n=Math.min(r.desks,48),cols=Math.max(2,Math.round(Math.sqrt(n*r.w/r.d)));
  const rows=Math.ceil(n/cols),sx=(r.w-1.4)/cols,sz=(r.d-1.4)/rows;
  for(let i=0;i<n;i++){const c=i%cols,rr=Math.floor(i/cols);
   const x=r.x+0.7+sx*(c+0.5),z=r.z+0.7+sz*(rr+0.5);
   box(Math.min(1.1,sx*.8),0.5,Math.min(0.6,sz*.5),i<r.busy?DESK:DESK2,x,0.3,z,g);
   if(i<r.busy){const p=new THREE.Mesh(new THREE.CylinderGeometry(.16,.16,.55,10),mat(0x22c55e,{emissive:0x0b5d2a,emissiveIntensity:.6}));
    p.position.set(x,0.5,z+Math.min(0.55,sz*.42));g.add(p);}
   else box(.32,.3,.32,CHAIR,x,0.2,z+Math.min(0.55,sz*.42),g);}
 }else if(r.kind==='meeting'){
  box(r.w*.55,.45,r.d*.38,mat(0x8b5a2b),r.x+r.w/2,.28,r.z+r.d/2,g);
 }else if(r.kind==='cafe'){
  for(let i=0;i<6;i++)box(1,.4,1,DESK,r.x+1.5+(i%3)*(r.w-3)/2,.25,r.z+1.5+Math.floor(i/3)*(r.d-3),g);
 }else if(r.kind==='server'){
  for(let i=0;i<3;i++)box(.6,1.1,.5,mat(0x334155),r.x+.9+i*1.0,.55,r.z+r.d/2,g);
 }
}
const bar=document.getElementById('bar');
let current=D.start;
function buttons(){bar.innerHTML='';
 ['All'].concat(D.floors.map(f=>f.name)).forEach(n=>{const b=document.createElement('button');
  b.className='btn'+(n===current?' on':'');
  b.textContent=n==='All'?'All floors':(/not placed/i.test(n)?'Not placed yet':n);
  b.onclick=()=>{current=n;buttons();build(n)};bar.appendChild(b)});
 const s=document.createElement('span');s.className='sp';bar.appendChild(s);
 const x=document.createElement('button');x.className='btn'+(ctl.enabled?' on':'');
 x.textContent=ctl.enabled?'Done':'Explore 3D';
 x.onclick=()=>{ctl.enabled=!ctl.enabled;canvas.style.touchAction=ctl.enabled?'none':'pan-y';buttons()};
 bar.appendChild(x);
 const t=document.createElement('button');t.className='btn';t.textContent='Top view';
 t.onclick=()=>{const v=ctl.target;cam.position.set(v.x,Math.max(60,cam.position.distanceTo(v)),v.z+0.01);ctl.update()};
 bar.appendChild(t);}
buttons();build(current);
const ray=new THREE.Raycaster(),m2=new THREE.Vector2();
function hit(ev){const b=canvas.getBoundingClientRect();
 m2.x=((ev.clientX-b.left)/b.width)*2-1;m2.y=-((ev.clientY-b.top)/b.height)*2+1;
 ray.setFromCamera(m2,cam);const h=ray.intersectObjects(pick)[0];return h?h.object.userData:null}
canvas.addEventListener('pointermove',ev=>{const r=hit(ev);
 if(!r){tip.style.display='none';return}
 tip.innerHTML='<b>'+r.name+'</b><br>'+r.line+'<br><span style="color:#8ea3c7">'+r.floor+' &middot; tap to open</span>';
 const b=wrap.getBoundingClientRect();tip.style.display='block';
 tip.style.left=Math.min(ev.clientX-b.left+14,b.width-250)+'px';tip.style.top=(ev.clientY-b.top+14)+'px'});
canvas.addEventListener('click',ev=>{const r=hit(ev);if(!r||!r.q)return;
 try{window.top.location.search=r.q}catch(e){window.open('?'+r.q.replace(/^\?/,''),'_blank')}});
function size(){const w=wrap.clientWidth,h=wrap.clientHeight;R.setSize(w,h,false);
 cam.aspect=w/h;cam.updateProjectionMatrix();if(!ctl.enabled)frame()}
window.addEventListener('resize',size);size();
const v=new THREE.Vector3();
// drawn only when something changed, or while exploring: a still twin
// costs a phone nothing
let dirty=3;
['pointerdown','pointermove','wheel','touchstart'].forEach(e=>canvas.addEventListener(e,()=>{dirty=Math.max(dirty,2)},{passive:true}));
window.addEventListener('resize',()=>{dirty=3});
bar.addEventListener('click',()=>{dirty=3});
(function loop(){requestAnimationFrame(loop);
 if(!(ctl.enabled||dirty>0))return;dirty=Math.max(0,dirty-1);
 ctl.update();R.render(S,cam);
 const w=wrap.clientWidth,h=wrap.clientHeight;
 calls.forEach(c=>{v.copy(c.p).project(cam);
  if(v.z>1){c.el.style.display='none';return}
  c.el.style.display='block';c.el.style.left=((v.x+1)/2*w)+'px';c.el.style.top=((1-v.y)/2*h)+'px'})})();
</script></body></html>"""
