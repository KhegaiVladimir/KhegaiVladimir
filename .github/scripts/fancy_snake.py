"""Redraw the Platane/snk snake as a detailed reptile.

Keeps snk's grid and movement path (the `s0` keyframes), removes the four
block segments and draws instead: a smooth tapered body made of overlapping
scales, a head that turns toward the direction of travel, eyes with slit
pupils and a flicking forked tongue.

Usage: python fancy_snake.py <in.svg> <out.svg> dark|light
"""
import math
import re
import sys

PALETTES = {
    "dark": {
        "neck": (196, 181, 253), "tail": (91, 33, 182),
        "edge": "#1E0B4B", "band": "#3B0F8C", "shine": "#F5F3FF",
        "belly": "#DDD6FE", "eye": "#FDE047", "tongue": "#FB7185",
    },
    "light": {
        "neck": (139, 92, 246), "tail": (59, 7, 100),
        "edge": "#2E1065", "band": "#2E1065", "shine": "#FFFFFF",
        "belly": "#EDE9FE", "eye": "#FACC15", "tongue": "#E11D48",
    },
}

CELL = 16
BODY_CELLS = 6          # body length in grid cells
PER_CELL = 5            # scales per cell
STEP_MS = 100           # snk moves one cell every 100ms


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
    return duration, frames


def pos(frames, pct):
    pct %= 100
    for (p0, x0, y0), (p1, x1, y1) in zip(frames, frames[1:]):
        if p0 <= pct <= p1:
            f = 0 if p1 == p0 else (pct - p0) / (p1 - p0)
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    return frames[-1][1], frames[-1][2]


def head_rotation(frames, duration):
    """Keyframes for the head angle, turning smoothly around each corner."""
    steps = round(duration / STEP_MS)
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
            keys.append((t - 0.4 * step_pct, unwrapped[i - 1]))
            keys.append((t + 0.4 * step_pct, unwrapped[i]))
    keys.append((100.0, unwrapped[-1]))
    return "".join(
        f"{max(0, min(100, t)):.3f}%{{transform:translate(8px,8px) rotate({a:.1f}deg)}}"
        for t, a in keys
    )


def mix(c0, c1, f):
    return "#%02X%02X%02X" % tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))


def build(duration, frames, pal):
    n = BODY_CELLS * PER_CELL
    css = [
        f".fs{{animation:s0 {duration}ms linear infinite}}",
        f"@keyframes fh{{{head_rotation(frames, duration)}}}",
        f".fh{{animation:fh {duration}ms linear infinite}}",
        "@keyframes ft{0%,62%,100%{transform:scaleX(0)}66%,74%{transform:scaleX(1)}"
        "70%{transform:scaleX(.75)}}",
        ".ft{animation:ft 1.6s ease-in-out infinite}",
    ]
    body = []
    for k in range(n, 0, -1):  # tail first so the neck sits on top
        lag = k / PER_CELL * STEP_MS
        f = k / n
        r = 6.4 - 4.6 * f ** 1.4
        fill = mix(pal["neck"], pal["tail"], f)
        delay = -(duration - lag)
        stripe = k % PER_CELL == 0
        body.append(
            f'<g class="fs" style="animation-delay:{delay:.0f}ms">'
            f'<circle cx="8" cy="8" r="{r:.2f}" fill="{pal["band"] if stripe else fill}" '
            f'stroke="{pal["edge"]}" stroke-width=".7"/>'
            # alternate dark dorsal spots with pale scale centres
            + (f'<circle cx="8" cy="8" r="{r * .38:.2f}" fill="{pal["band"]}" opacity=".8"/>'
               if k % 2 else
               f'<circle cx="8" cy="8" r="{r * .45:.2f}" fill="{pal["belly"]}" opacity=".35"/>')
            + f'<circle cx="{8 - r * .35:.2f}" cy="{8 - r * .4:.2f}" r="{r * .22:.2f}" '
            f'fill="{pal["shine"]}" opacity=".55"/></g>'
        )
    neck = mix(pal["neck"], pal["tail"], 0)
    head = (
        '<g class="fs"><g class="fh">'
        # forked tongue, flicking out of the snout
        f'<g transform="translate(7.2 0)"><g class="ft">'
        f'<path d="M0 0H4.2L6 -1.6M4.2 0L6 1.6" fill="none" stroke="{pal["tongue"]}" '
        'stroke-width=".9" stroke-linecap="round" stroke-linejoin="round"/></g></g>'
        # skull: wide at the back, tapering to a rounded snout
        f'<path d="M-6 -5.6C-1 -7.4 5.5 -5.2 8 -1.6C8.8 -.6 8.8 .6 8 1.6'
        f'C5.5 5.2 -1 7.4 -6 5.6C-8 4 -8 -4 -6 -5.6Z" fill="{neck}" '
        f'stroke="{pal["edge"]}" stroke-width=".8"/>'
        # head plate pattern
        f'<path d="M-4.5 0C-2 -2.6 2 -2.6 4.5 0C2 2.6 -2 2.6 -4.5 0Z" '
        f'fill="{pal["band"]}" opacity=".55"/>'
        f'<ellipse cx="-1.5" cy="-3.4" rx="2.6" ry="1" fill="{pal["shine"]}" opacity=".45"/>'
        # eyes with vertical slit pupils
        f'<circle cx="2.4" cy="-3.3" r="1.7" fill="{pal["eye"]}" stroke="{pal["edge"]}" stroke-width=".5"/>'
        f'<circle cx="2.4" cy="3.3" r="1.7" fill="{pal["eye"]}" stroke="{pal["edge"]}" stroke-width=".5"/>'
        '<ellipse cx="2.6" cy="-3.3" rx=".45" ry="1.3" fill="#0B0B0F"/>'
        '<ellipse cx="2.6" cy="3.3" rx=".45" ry="1.3" fill="#0B0B0F"/>'
        '<circle cx="2" cy="-3.8" r=".4" fill="#fff"/><circle cx="2" cy="2.8" r=".4" fill="#fff"/>'
        # nostrils
        f'<circle cx="7" cy="-.9" r=".35" fill="{pal["edge"]}"/>'
        f'<circle cx="7" cy=".9" r=".35" fill="{pal["edge"]}"/>'
        "</g></g>"
    )
    return f'<style>{"".join(css)}</style><g>{"".join(body)}{head}</g>'


def main(src, dst, theme):
    svg = open(src, encoding="utf-8").read()
    duration, frames = parse(svg)
    svg = re.sub(r'<rect class="s s\d+"[^>]*/>', "", svg)
    svg = svg.replace("</svg>", build(duration, frames, PALETTES[theme]) + "</svg>")
    open(dst, "w", encoding="utf-8").write(svg)


if __name__ == "__main__":
    main(*sys.argv[1:4])
