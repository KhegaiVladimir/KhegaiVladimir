"""Redraw the Platane/snk snake as a detailed, living reptile.

snk decides the route and which cells get eaten; this script keeps that
(the `s0` keyframes and the cell animations) and replaces the four block
segments with:

  * a tapered body of overlapping segments, each one turned along the path,
    shaded like a cylinder, textured with scales and python-style saddles
  * lateral undulation: a sine wave travelling from head to tail
  * a soft blurred shadow under the whole snake
  * a gulp bulge that runs down the body after every eaten cell
  * a burst ring and sparks on every eaten cell
  * a head with brow plates, glowing slit-pupil eyes and a slight sway
  * a forked tongue that flicks in bursts, its tips fluttering

Everything is plain SVG + CSS keyframes, so it animates inside GitHub's <img>.

Usage: python fancy_snake.py <in.svg> <out.svg> dark|light
"""
import math
import re
import sys

PALETTES = {
    "dark": {
        "body": [(221, 214, 254), (167, 139, 250), (124, 58, 237), (59, 7, 100)],
        "edge": "#1E0B4B", "saddle": "#2E1065", "saddle_rim": "#E9D5FF",
        "shine": "#FFFFFF", "eye": ("#FEF08A", "#F59E0B"), "eye_glow": "#FDE047",
        "tongue": "#FB7185", "shadow": ".55", "burst": "#C4B5FD",
    },
    "light": {
        "body": [(167, 139, 250), (124, 58, 237), (91, 33, 182), (46, 16, 101)],
        "edge": "#2E1065", "saddle": "#3B0764", "saddle_rim": "#F5F3FF",
        "shine": "#FFFFFF", "eye": ("#FDE047", "#D97706"), "eye_glow": "#FACC15",
        "tongue": "#E11D48", "shadow": ".28", "burst": "#7C3AED",
    },
}

STEP_MS = 100           # snk moves one cell every 100ms
BODY_CELLS = 6          # body length in grid cells
PER_CELL = 6            # body segments per cell
WAVE_MS = 1100          # half period of the slither wave
WAVELENGTH = 13         # segments per full wave
GULP_STEPS = 1.6        # how long the bulge takes to pass one point, in steps


def parse(svg):
    duration = int(re.search(r"\.s\{[^}]*?(\d+)ms", svg).group(1))
    block = re.search(r"@keyframes s0\{(.*?\})\}", svg).group(1)
    frames = []
    for pcts, x, y in re.findall(
        r"([\d.,%]+)\{transform:translate\((-?[\d.]+)px,(-?[\d.]+)px\)\}", block
    ):
        for p in pcts.split(","):
            frames.append((float(p.rstrip("%")), float(x), float(y)))
    frames.sort()
    if frames[-1][0] < 100:
        # snk leaves 100% implicit: it equals the element's base transform (the 0% frame)
        frames.append((100.0, frames[0][1], frames[0][2]))
    eaten_at = {
        name: float(pct)
        for name, pct in re.findall(r"@keyframes (c\w+)\{([\d.]+)%", svg)
    }
    cells = [
        (eaten_at[name], float(x) + 6, float(y) + 6)
        for name, x, y in re.findall(r'<rect class="c (c\w+)" x="([\d.]+)" y="([\d.]+)"', svg)
        if name in eaten_at
    ]
    return duration, frames, sorted(cells)


def pos(frames, pct):
    pct %= 100
    for (p0, x0, y0), (p1, x1, y1) in zip(frames, frames[1:]):
        if p0 <= pct <= p1:
            f = 0 if p1 == p0 else (pct - p0) / (p1 - p0)
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    return frames[-1][1], frames[-1][2]


def pct(t):
    return f"{max(0.0, min(100.0, t)):.3f}".rstrip("0").rstrip(".") + "%"


def rotation_keyframes(frames, steps):
    """Translate to the cell centre and face the direction of travel,
    easing through each corner instead of snapping."""
    step_pct = 100 / steps
    angles = []
    for i in range(steps):
        x0, y0 = pos(frames, i * step_pct)
        x1, y1 = pos(frames, (i + 1) * step_pct)
        angles.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    # unwrap so a corner is always a 90° turn, never a spin the long way round
    unwrapped = [angles[0]]
    for a in angles[1:]:
        prev = unwrapped[-1]
        unwrapped.append(prev + ((a - prev + 180) % 360 - 180))
    keys = [(0.0, unwrapped[0])]
    for i in range(1, steps):
        if abs(unwrapped[i] - unwrapped[i - 1]) > 1e-6:
            t = i * step_pct
            keys.append((t - 0.45 * step_pct, unwrapped[i - 1]))
            keys.append((t + 0.45 * step_pct, unwrapped[i]))
    keys.append((100.0, unwrapped[-1]))
    return "".join(
        f"{pct(t)}{{transform:translate(8px,8px) rotate({a:.1f}deg)}}" for t, a in keys
    )


def gulp_keyframes(cells, steps):
    """Scale envelope that swells right after the head swallows a cell."""
    step_pct = 100 / steps
    width = GULP_STEPS * step_pct
    sub = 4  # samples per step
    times = sorted({round((p + d / sub * step_pct) * 1000) / 1000
                    for p, _, _ in cells for d in range(-1, int(GULP_STEPS * sub) + 2)})

    def bulge(t):
        b = 0.0
        for p, _, _ in cells:
            x = (t - p) / width
            if 0 < x < 1:
                b = max(b, math.sin(math.pi * x))
        return b

    keys = ["0%{transform:scale(1)}"]
    for t in times:
        if 0 < t < 100:
            keys.append(f"{pct(t)}{{transform:scale({1 + 0.2 * bulge(t):.3f})}}")
    keys.append("100%{transform:scale(1)}")
    return "".join(keys)


def mix(stops, f):
    f = min(max(f, 0), 1) * (len(stops) - 1)
    i = min(int(f), len(stops) - 2)
    t = f - i
    return "#%02X%02X%02X" % tuple(round(a + (b - a) * t) for a, b in zip(stops[i], stops[i + 1]))


def radius(f):
    """Body profile: slim neck, thick first third, long tapering tail."""
    if f < 0.22:
        return 4.3 + 1.2 * math.sin(f / 0.22 * math.pi / 2)
    g = (f - 0.22) / 0.78
    return 1.4 + 4.1 * (1 - g ** 1.5)


def build(duration, frames, cells, pal):
    steps = round(duration / STEP_MS)
    n = BODY_CELLS * PER_CELL
    D = f"{duration}ms"

    def lag_delay(k):
        lag = k / PER_CELL * STEP_MS
        return f"{-(duration - lag) % duration:.0f}ms" if k else "0ms"

    def amp(k):
        # quiet head, full wave mid-body, settling toward the tip
        a = min(1.0, k / 9) * (1.7 - 0.5 * k / n)
        return round(a * 5) / 5

    amps = sorted({amp(k) for k in range(n + 1)})
    wave_css = "".join(
        f"@keyframes w{i}{{from{{transform:translateY({-a}px)}}to{{transform:translateY({a}px)}}}}"
        for i, a in enumerate(amps)
    )

    def segment(k, inner, shadow=False, gulp=True):
        """Wrap content drawn in the segment's own frame (x = forward)."""
        d = lag_delay(k)
        wd = f"{-((2 * WAVE_MS) - (k / WAVELENGTH * 2 * WAVE_MS) % (2 * WAVE_MS)):.0f}ms"
        wave = amps.index(amp(k))
        body = (f'<g class="g" style="animation-delay:{d}">{inner}</g>' if gulp else inner)
        rot = (f'<g class="r" style="animation-delay:{d}">'
               f'<g class="w" style="animation-name:w{wave};animation-delay:{wd}">{body}</g></g>')
        if shadow:
            rot = f'<g transform="translate(1.3 2.2)">{rot}</g>'
        return f'<g class="m" style="animation-delay:{d}">{rot}</g>'

    css = (
        f".m{{animation:s0 {D} linear infinite}}"
        f".r{{animation:fr {D} linear infinite}}"
        f".g{{animation:fg {D} linear infinite}}"
        f".w{{animation:w0 {WAVE_MS}ms ease-in-out infinite alternate}}"
        f"@keyframes fr{{{rotation_keyframes(frames, steps)}}}"
        f"@keyframes fg{{{gulp_keyframes(cells, steps)}}}"
        + wave_css
        # head sway
        + "@keyframes hs{0%{transform:rotate(-6deg)}100%{transform:rotate(6deg)}}"
        ".hs{animation:hs 1.7s ease-in-out infinite alternate}"
        # tongue: rest, shoot out, three quick flicks, pull back
        "@keyframes tg{0%,38%{transform:scaleX(0)}44%{transform:scaleX(1.08)}"
        "48%{transform:scaleX(.72)}52%{transform:scaleX(1.05)}56%{transform:scaleX(.7)}"
        "60%{transform:scaleX(1)}66%,100%{transform:scaleX(0)}}"
        ".tg{animation:tg 2.6s cubic-bezier(.3,0,.3,1) infinite}"
        "@keyframes tw{0%{transform:rotate(-9deg)}100%{transform:rotate(9deg)}}"
        ".tw{animation:tw .13s ease-in-out infinite alternate}"
        "@keyframes tu{0%{transform:rotate(-14deg)}100%{transform:rotate(16deg)}}"
        ".tu{animation:tu .09s linear infinite alternate}"
        ".td{animation:tu .09s linear infinite alternate-reverse}"
        # eyes: slow glow pulse
        "@keyframes eg{0%,100%{opacity:.15}50%{opacity:.55}}"
        ".eg{animation:eg 2.2s ease-in-out infinite}"
    )

    defs = (
        "<defs>"
        # cylinder shading across the body (y is sideways in the segment frame)
        '<linearGradient id="fT" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#000" stop-opacity=".55"/>'
        '<stop offset=".22" stop-color="#fff" stop-opacity=".05"/>'
        '<stop offset=".36" stop-color="#fff" stop-opacity=".42"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity=".05"/>'
        '<stop offset=".8" stop-color="#000" stop-opacity=".2"/>'
        '<stop offset="1" stop-color="#000" stop-opacity=".6"/></linearGradient>'
        # overlapping scale texture, tied to each segment's frame
        '<pattern id="fP" width="2.4" height="2" patternUnits="userSpaceOnUse">'
        f'<path d="M2.4 0A1.4 1.4 0 0 0 2.4 2M1.2 -1A1.4 1.4 0 0 0 1.2 1M1.2 1A1.4 1.4 0 0 0 1.2 3" '
        f'fill="none" stroke="{pal["edge"]}" stroke-width=".28" opacity=".55"/></pattern>'
        f'<radialGradient id="fE" cx=".35" cy=".35" r=".75">'
        f'<stop offset="0" stop-color="{pal["eye"][0]}"/>'
        f'<stop offset="1" stop-color="{pal["eye"][1]}"/></radialGradient>'
        '<filter id="fB" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="1.3"/></filter>'
        "</defs>"
    )

    # ── eating bursts, synced to snk's cell timings ─────────────────
    step_pct = 100 / steps
    bursts, burst_css = [], []
    for i, (p, cx, cy) in enumerate(cells):
        end = p + 4.5 * step_pct
        burst_css.append(
            f"@keyframes b{i}{{0%,{pct(p - 0.01)}{{transform:scale(.2);opacity:0}}"
            f"{pct(p)}{{transform:scale(.35);opacity:.95}}"
            f"{pct(end)},100%{{transform:scale(1.5);opacity:0}}}}"
            f"@keyframes p{i}{{0%,{pct(p - 0.01)}{{transform:translateX(2px);opacity:0}}"
            f"{pct(p)}{{transform:translateX(3px);opacity:1}}"
            f"{pct(end)},100%{{transform:translateX(11px);opacity:0}}}}"
        )
        sparks = "".join(
            f'<g transform="rotate({a})"><circle r=".9" fill="{pal["burst"]}" '
            f'style="animation:p{i} {D} ease-out infinite"/></g>'
            for a in (20, 110, 200, 290)
        )
        bursts.append(
            f'<g transform="translate({cx:g} {cy:g})">'
            f'<circle r="6" fill="none" stroke="{pal["burst"]}" stroke-width="1.2" '
            f'style="animation:b{i} {D} ease-out infinite"/>{sparks}</g>'
        )

    # ── shadow, body, markings ───────────────────────────────────────
    order = range(n, 0, -1)  # tail first so segments nearer the head sit on top
    shadows = [segment(k, f'<circle r="{radius(k / n):.2f}" fill="#000"/>', shadow=True)
               for k in order]
    shadows.append(segment(0, '<ellipse cx="1" rx="8" ry="6.6" fill="#000"/>',
                           shadow=True, gulp=False))

    outline = [segment(k, f'<circle r="{radius(k / n) + .65:.2f}" fill="{pal["edge"]}"/>')
               for k in order]
    body = []
    for k in order:
        f, r = k / n, radius(k / n)
        body.append(segment(k, (
            f'<circle r="{r:.2f}" fill="{mix(pal["body"], f)}"/>'
            f'<circle r="{r:.2f}" fill="url(#fP)"/>'
            f'<circle r="{r:.2f}" fill="url(#fT)"/>'
        )))

    marks = []
    for k in order:
        r = radius(k / n)
        if k % PER_CELL == 2 and r > 2:
            # diamondback pattern along the spine
            dx, dy = r * 1.15, r * .62
            diamond = f"M{dx:.2f} 0L0 {-dy:.2f}L{-dx:.2f} 0L0 {dy:.2f}Z"
            marks.append(segment(k, (
                f'<path d="{diamond}" fill="{pal["saddle"]}" opacity=".7" '
                f'stroke="{pal["saddle_rim"]}" stroke-width=".35" stroke-opacity=".5"/>'
            )))
        elif k % PER_CELL == 0 and r > 1.5:
            marks.append(segment(k, (
                f'<circle r="{r * .22:.2f}" fill="{pal["saddle_rim"]}" opacity=".55"/>'
            )))

    # ── head (drawn facing +x, centred on the path) ──────────────────
    neck = mix(pal["body"], 0)
    edge, eye_glow = pal["edge"], pal["eye_glow"]
    eye = (
        lambda y: f'<circle cy="{y}" cx="2.6" r="2.9" fill="{eye_glow}" class="eg"/>'
        f'<circle cx="2.6" cy="{y}" r="1.95" fill="url(#fE)" stroke="{edge}" stroke-width=".5"/>'
        f'<ellipse cx="2.75" cy="{y}" rx="1.45" ry=".42" fill="#0B0B0F"/>'
        f'<circle cx="2.05" cy="{y - .65}" r=".45" fill="#fff"/>'
        f'<circle cx="3.3" cy="{y + .6}" r=".2" fill="#fff" opacity=".7"/>'
    )
    tongue = (
        f'<g transform="translate(7.6 0)"><g class="tg"><g class="tw">'
        f'<path d="M0 0H4.6" stroke="{pal["tongue"]}" stroke-width="1" stroke-linecap="round"/>'
        f'<g transform="translate(4.6 0)">'
        f'<g class="tu"><path d="M0 0L2.2 -1.4" stroke="{pal["tongue"]}" stroke-width=".75" '
        'stroke-linecap="round"/></g>'
        f'<g class="td"><path d="M0 0L2.2 1.4" stroke="{pal["tongue"]}" stroke-width=".75" '
        'stroke-linecap="round"/></g>'
        "</g></g></g></g>"
    )
    skull = (
        "M-6.5 -5.9C-1.5 -7.8 5.2 -5.8 8 -2C8.9 -.8 8.9 .8 8 2"
        "C5.2 5.8 -1.5 7.8 -6.5 5.9C-8.6 4.2 -8.6 -4.2 -6.5 -5.9Z"
    )
    head = segment(0, (
        '<g class="hs">'
        + tongue
        + f'<path d="{skull}" fill="{neck}" stroke="{edge}" stroke-width=".7"/>'
        f'<path d="{skull}" fill="url(#fP)"/>'
        f'<path d="{skull}" fill="url(#fT)"/>'
        # arrowhead marking down the crown
        f'<path d="M5 0L-1 -3.2L-6.6 -1.6L-3.6 0L-6.6 1.6L-1 3.2Z" fill="{pal["saddle"]}" '
        f'stroke="{pal["saddle_rim"]}" stroke-width=".4" stroke-opacity=".6" opacity=".8"/>'
        # brow plates over the eyes
        f'<path d="M.3 -4.4Q2.8 -6.3 5 -4.2" fill="none" stroke="{edge}" stroke-width="1.1" '
        'stroke-linecap="round"/>'
        f'<path d="M.3 4.4Q2.8 6.3 5 4.2" fill="none" stroke="{edge}" stroke-width="1.1" '
        'stroke-linecap="round"/>'
        + eye(-3.6) + eye(3.6)
        # snout scales and nostrils
        + f'<path d="M6.4 -1.8Q7.6 0 6.4 1.8" fill="none" stroke="{edge}" stroke-width=".35" opacity=".7"/>'
        f'<ellipse cx="7.3" cy="-1" rx=".45" ry=".3" fill="{edge}"/>'
        f'<ellipse cx="7.3" cy="1" rx=".45" ry=".3" fill="{edge}"/>'
        f'<ellipse cx="-2" cy="-3.6" rx="2.8" ry=".8" fill="{pal["shine"]}" opacity=".35"/>'
        "</g>"
    ), gulp=False)

    return (
        '<g id="fancy-snake">'
        f"<style>{css}{''.join(burst_css)}</style>{defs}"
        f"<g>{''.join(bursts)}</g>"
        f'<g filter="url(#fB)" opacity="{pal["shadow"]}">{"".join(shadows)}</g>'
        f"<g>{''.join(outline)}</g><g>{''.join(body)}</g><g>{''.join(marks)}</g>{head}"
        "</g>"
    )


def main(src, dst, theme):
    svg = open(src, encoding="utf-8").read()
    svg = re.sub(r'<g id="fancy-snake">.*?</g>(?=</svg>)', "", svg, flags=re.S)
    duration, frames, cells = parse(svg)
    svg = re.sub(r'<rect class="s s\d+"[^>]*/>', "", svg)
    svg = svg.replace("</svg>", build(duration, frames, cells, PALETTES[theme]) + "</svg>")
    open(dst, "w", encoding="utf-8").write(svg)


if __name__ == "__main__":
    main(*sys.argv[1:4])
