#!/usr/bin/env python3
"""Regression check for a rendered poster against the reference design metrics.

Measures the concrete style properties that were reverse-engineered from the
hand-made reference poster and flags any that drift outside tolerance, plus a
self-consistency check that each row's movement triangle, movement number and
position number share a vertical centre. Run after rendering, before sending,
so misalignments/size/colour regressions are caught by measurement rather than
by eye.

Usage: verify_poster.py <poster.png>
Exit code 0 if all checks pass, 1 otherwise.
"""
import sys
from collections import Counter

from PIL import Image

# Expected values measured from the reference poster (1190x1683).
EXPECT = {
    "size": (1190, 1683),
    "content_right": (995, 1020),      # right-most inked column
    "banner_width": (240, 252),        # grey border column
    "title_band": (70, 90),            # title cap-height band (px)
    "green": (48, 111, 29),
    "red": (166, 43, 23),
    "deck_max_sum": 60,                # deck text should be near-black
    "align_tol": 3,                    # px tolerance for row element centres
    "row1_name_top": (150, 168),       # 'H' of the row-1 name cap-top (baseline on cy)
}


def approx(v, lo, hi):
    return lo <= v <= hi


def color_close(c, target, tol=45):
    return all(abs(a - b) <= tol for a, b in zip(c, target))


def check(path):
    im = Image.open(path).convert("RGB")
    px = im.load()
    w, h = im.size
    results = []

    results.append(("canvas size", (w, h) == EXPECT["size"], f"{w}x{h}"))

    # content right edge / margin
    xs = [x for x in range(w) if any(sum(px[x, y]) < 720 for y in range(0, h, 4))]
    results.append(("content right edge", approx(xs[-1], *EXPECT["content_right"]),
                    f"x={xs[-1]} (margin {w-1-xs[-1]}px)"))

    # banner width via grey border at mid height
    y = h // 2
    border = next((x for x in range(200, 300)
                   if 150 < px[x, y][0] < 210 and px[x, y][2] > 180
                   and sum(px[x + 3, y]) > 720), None)
    results.append(("banner width+border", border is not None and approx(border, *EXPECT["banner_width"]),
                    f"x={border}"))

    # title cap band width
    txs = [x for x in range(15, 240) for yy in range(300, 1400, 7) if sum(px[x, yy]) > 720]
    band = (max(txs) - min(txs)) if txs else 0
    results.append(("title band width", approx(band, *EXPECT["title_band"]), f"{band}px"))

    # arrow colours (most common strong green / red anywhere)
    greens, reds = Counter(), Counter()
    for yy in range(0, h, 2):
        for x in range(320, 420, 1):
            r, g, b = px[x, yy]
            if g > 80 and g - r > 20 and g - b > 20:
                greens[(r, g, b)] += 1
            if r > 110 and r - g > 45 and r - b > 45:
                reds[(r, g, b)] += 1
    gc = greens.most_common(1)[0][0] if greens else (0, 0, 0)
    rc = reds.most_common(1)[0][0] if reds else (0, 0, 0)
    results.append(("green arrow colour", color_close(gc, EXPECT["green"]), str(gc)))
    results.append(("red arrow colour", color_close(rc, EXPECT["red"]), str(rc)))

    # deck near-black: darkest pixel in a deck strip under row 1 name
    deck_min = min(sum(px[x, yy]) for yy in range(205, 235) for x in range(575, 760))
    results.append(("deck near-black", deck_min <= EXPECT["deck_max_sum"], f"min_sum={deck_min}"))

    # row-1 name vertical placement (cap-top of the first name's 'H')
    name_top = next((yy for yy in range(150, 205)
                     if any(sum(px[x, yy]) < 200 for x in range(575, 600))), None)
    results.append(("row1 name cap-top", name_top is not None and approx(name_top, *EXPECT["row1_name_top"]),
                    f"y={name_top}"))

    # row alignment: for each arrow row, triangle centre vs movement-number centre
    def band_center(x0, x1, y0, y1, cond):
        ys = [yy for yy in range(y0, y1) for x in range(x0, x1) if cond(*px[x, yy])]
        return (min(ys) + max(ys)) / 2 if ys else None

    grn = lambda r, g, b: g > 80 and g - r > 20 and g - b > 20
    red = lambda r, g, b: r > 110 and r - g > 45 and r - b > 45
    misaligned = []
    for i in range(20):
        cy = int(112 / 1000 * h + i * 0.05447 * h)
        y0, y1 = cy - 40, cy + 40
        if y1 > h:
            break
        for cond in (grn, red):
            tri = band_center(335, 378, y0, y1, cond)
            num = band_center(382, 405, y0, y1, cond)
            if tri is not None and num is not None:
                if abs(tri - num) > EXPECT["align_tol"]:
                    misaligned.append(f"row{i+1} d={tri-num:.1f}")
    results.append(("arrow/number alignment", not misaligned,
                    "ok" if not misaligned else ", ".join(misaligned)))

    ok = all(r[1] for r in results)
    print(f"Poster verify: {path}")
    for name, passed, detail in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: verify_poster.py <poster.png>", file=sys.stderr)
        sys.exit(2)
    sys.exit(0 if check(sys.argv[1]) else 1)
