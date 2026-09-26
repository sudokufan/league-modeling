#!/usr/bin/env python3
"""Render a league standings poster PNG matching the hand-made Pages design.

Reuses simulate.derive_stats() for all scoring so the poster always agrees with
the dashboard. Ranking = best-N score, then OMW%, then GW% (same as standings).

Decorations:
  - Trophy  = player went undefeated (won every round) in any completed week.
  - Crown   = reigning champion during the season (config), or the new champion
              on the season-complete (--final) poster.
  - Gold    = final poster only: champion's NAME in gold, and the player with the
              most TOTAL points has that total shown in gold in the Pts column.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import simulate  # noqa: E402

# ---- Fonts ---------------------------------------------------------------
FONT_DIR = os.path.expanduser("~/Library/Fonts")
BELEREN_BOLD = os.path.join(FONT_DIR, "Beleren2016-Bold.ttf")
BELEREN_SC = os.path.join(FONT_DIR, "Beleren2016SmallCaps-Bold.ttf")
MPLANTIN = os.path.join(FONT_DIR, "MPlantin Regular.ttf")
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
EMOJI_STRIKE = 160  # only certain sizes load; 160 is the largest usable strike

# ---- Colours -------------------------------------------------------------
WHITE = (255, 255, 255)
INK = (0, 0, 0)
DECK_INK = (0, 0, 0)
HEADER_GREY = (0, 0, 0)
UP_GREEN = (48, 111, 29)
DOWN_RED = (166, 43, 23)
GOLD = (201, 155, 56)
BAR_BORDER = (177, 189, 198)

# Canvas (A4 portrait-ish, matches reference 1190x1683)
W, H = 1190, 1683


def load_json(path):
    with open(path) as f:
        return json.load(f)


def _emoji_image(char, target_px):
    """Render a colour emoji at the largest strike and scale to target height."""
    font = ImageFont.truetype(EMOJI_FONT, EMOJI_STRIKE)
    canvas = Image.new("RGBA", (EMOJI_STRIKE + 40, EMOJI_STRIKE + 40), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((20, 20), char, font=font, embedded_color=True)
    bbox = canvas.getbbox()
    cropped = canvas.crop(bbox)
    scale = target_px / cropped.height
    return cropped.resize((max(1, int(cropped.width * scale)), target_px), Image.LANCZOS)


def standings_order(raw, max_week=None):
    """Ordered player list + derived stats, up to and including max_week."""
    data = raw
    if max_week is not None:
        data = {**raw, "matches": [m for m in raw["matches"] if m["week"] <= max_week]}
    stats = simulate.derive_stats(data)
    ws = stats["weekly_scores"]
    ostats = stats["overall_stats"]
    n = stats["best_of_n"]
    order = sorted(
        stats["players"],
        key=lambda p: (
            simulate.best_n_score(ws[p], n),
            ostats[p]["omw"],
            ostats[p]["gwp"],
        ),
        reverse=True,
    )
    return order, stats


def display_names(players):
    """First name only, disambiguated to the full key on first-name collisions."""
    from collections import Counter
    firsts = Counter(p.split()[0] for p in players)
    return {p: (p if firsts[p.split()[0]] > 1 else p.split()[0]) for p in players}


def undefeated_players(stats):
    """Players who won every round in at least one completed week."""
    rounds_in_week = stats["rounds_in_week"]
    pwr = stats["per_week_records"]
    out = set()
    for p in stats["players"]:
        for wk, riw in rounds_in_week.items():
            rec = pwr.get(wk, {}).get(p)
            if rec and riw > 0 and rec["l"] == 0 and rec["d"] == 0 and rec["w"] == riw:
                out.add(p)
                break
    return out


def draw_ink_centered(draw, x, cy, text, font, fill, ha="l"):
    """Draw text with its visual (ink) center at y=cy, so numbers line up with
    geometric shapes like the movement triangle regardless of font metrics."""
    l, t, r, b = draw.textbbox((0, 0), text, font=font, anchor=ha + "a")
    draw.text((x, cy - (t + b) / 2), text, font=font, fill=fill, anchor=ha + "a")


def draw_triangle(draw, cx, cy, size, color, up=True):
    h = size
    w = size * 1.3
    if up:
        pts = [(cx, cy - h / 2), (cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2)]
    else:
        pts = [(cx, cy + h / 2), (cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2)]
    draw.polygon(pts, fill=color)


def render(league_id, week=None, final=False, out=None, title=None, champion=None):
    cfg = load_json(os.path.join(HERE, "automation_config.json"))
    decks = load_json(os.path.join(HERE, "decks.json"))["decks"]
    themes = cfg["poster_themes"]
    theme = {**themes["_default"], **themes.get(league_id, {})}

    raw = simulate.load_league_data(league_id=league_id)
    if week is None:
        week = simulate.derive_stats(raw)["weeks_completed"]

    order, stats = standings_order(raw, max_week=week)
    prev_order = None
    if week and week > 1:
        prev_order, _ = standings_order(raw, max_week=week - 1)
    prev_pos = {p: i for i, p in enumerate(prev_order)} if prev_order else {}

    ws = stats["weekly_scores"]
    n = stats["best_of_n"]
    total_weeks = stats["total_weeks"]
    best7 = {p: simulate.best_n_score(ws[p], n) for p in order}
    totals = {p: simulate.total_match_points(ws[p]) for p in order}
    trophies = undefeated_players(stats)

    disp = display_names(stats["players"])
    # On the final poster the champion is the playoff winner (may differ from the
    # best-N leader); default to the standings leader if not supplied.
    champ = champion or (order[0] if order else None)
    crown_player = champ if final else theme.get("reigning_champion")
    gold_name_player = champ if final else None
    gold_pts_player = max(order, key=lambda p: totals[p]) if final else None

    display = theme.get("display_name", league_id)
    if title is None:
        title = f"{display} League" if final else f"{display} League: {week}/{total_weeks}"

    # ---- Canvas + rounded gradient banner -------------------------------
    img = Image.new("RGB", (W, H), WHITE)
    bar_w = int(W * 0.207)       # ~246px wide banner
    radius = int(W * 0.101)      # ~120px corner radius (top-right, bottom-right)
    top = theme["bar_top"]
    bot = theme["bar_bottom"]

    gradient = Image.new("RGB", (bar_w, H))
    gpx = gradient.load()
    for y in range(H):
        t = y / (H - 1)
        col = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(bar_w):
            gpx[x, y] = col

    # Masks: outer = full rounded shape; inner inset 2px on the right/curved
    # side only (left/top/bottom stay flush to the page edge) so the thin grey
    # border appears only along the right edge and the two rounded corners.
    corners = (False, True, True, False)  # tl, tr, br, bl
    mask_outer = Image.new("L", (bar_w, H), 0)
    ImageDraw.Draw(mask_outer).rounded_rectangle(
        (0, 0, bar_w - 1, H - 1), radius=radius, corners=corners, fill=255)
    mask_inner = Image.new("L", (bar_w, H), 0)
    ImageDraw.Draw(mask_inner).rounded_rectangle(
        (0, 0, bar_w - 3, H - 1), radius=radius - 2, corners=corners, fill=255)

    img.paste(Image.new("RGB", (bar_w, H), BAR_BORDER), (0, 0), mask_outer)
    img.paste(gradient, (0, 0), mask_inner)
    draw = ImageDraw.Draw(img)

    # Rotated title: UPPERCASE so all letters render at uniform cap height
    # (mixed case in the small-caps font makes initials tower as full caps).
    title_fs = int(bar_w * 0.40)   # cap height ~79 to match reference
    tf = ImageFont.truetype(BELEREN_SC, title_fs)
    ttext = title.upper()
    tmp = Image.new("RGBA", (int(draw.textlength(ttext, font=tf)) + 40, int(title_fs * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((20, int(title_fs * 0.3)), ttext, font=tf, fill=WHITE)
    tmp = tmp.crop(tmp.getbbox())  # tight crop
    # Reference letters are condensed (~0.845 of natural width) — squash to match.
    tmp = tmp.resize((int(tmp.width * 0.845), tmp.height), Image.LANCZOS)
    tmp = tmp.rotate(90, expand=True)
    img.paste(tmp, (int((bar_w - tmp.width) / 2), int((H - tmp.height) / 2)), tmp)

    # ---- Layout (absolute anchors measured from the reference poster) ----
    move_x = int(W * 0.302)      # movement arrow centre (~360)
    move_num_x = int(W * 0.322)  # movement number, left-anchored (~383)
    pos_x = int(W * 0.398)       # position number, left-anchored (~474)
    name_x = int(W * 0.483)      # player name, left-anchored (~575)
    pts_right = int(W * 0.846)   # points, right-anchored (~1006)

    # Row geometry measured from the reference: first row centre at 0.112*H,
    # row pitch 0.05447*H (~91.7px). Compress the pitch if the roster exceeds
    # what fits, so everyone is still included.
    n_rows = len(order)
    first_center = H * 0.112
    bottom_pad = H * 0.027
    row_h = min(H * 0.05447, (H - bottom_pad - first_center) / max(1, n_rows - 0.5))

    def cy_of(i):
        return first_center + i * row_h

    name_fs = max(16, int(row_h * 0.40))
    deck_fs = max(12, int(row_h * 0.32))
    num_fs = max(16, int(row_h * 0.42))
    nf = ImageFont.truetype(BELEREN_BOLD, name_fs)
    nf_gold = nf
    df = ImageFont.truetype(MPLANTIN, deck_fs)
    numf = ImageFont.truetype(BELEREN_BOLD, num_fs)
    hf = ImageFont.truetype(BELEREN_BOLD, max(15, int(row_h * 0.26)))
    arrow_sz = int(num_fs * 0.70)      # triangle height (~26)
    trophy_px = int(name_fs * 0.82)    # ~30
    crown_px = int(name_fs * 0.55)     # ~20 (smaller than the trophy)

    # Vertical offsets from the row centre line (cy), measured from reference.
    # Numbers are ink-centred on cy. The name baseline sits ~4px above cy so its
    # cap-top matches the reference; the trophy is tied to the name's cap-centre
    # (below) so the two never drift apart. Crown is centred on cy (== the
    # position number's centre).
    baseline_off = -row_h * 0.045      # name baseline just above cy
    deck_gap = row_h * 0.45            # deck baseline below the NAME baseline
                                       # (tied to the name, not cy, so the
                                       # name->deck gap stays tighter than the
                                       # gap to the next player's name)
    # cap height of the name font, for centring the trophy on the name's caps
    name_cap_h = -draw.textbbox((0, 0), "H", font=nf, anchor="ls")[1]

    # Header, ink-centered ~0.75 rows above the first row
    hy = first_center - row_h * 0.75
    draw_ink_centered(draw, pos_x, hy, "Pos.", hf, HEADER_GREY, ha="l")
    draw_ink_centered(draw, name_x, hy, "Player", hf, HEADER_GREY, ha="l")
    draw_ink_centered(draw, pts_right, hy, "Pts.", hf, HEADER_GREY, ha="r")

    for i, p in enumerate(order):
        cy = cy_of(i)
        pos = i + 1

        # Movement triangle (centred on cy) + number (ink-centred on cy so it
        # lines up with the triangle)
        if p in prev_pos:
            delta = prev_pos[p] - i  # positive => moved up
            if delta != 0:
                col = UP_GREEN if delta > 0 else DOWN_RED
                draw_triangle(draw, move_x, cy, arrow_sz, col, up=delta > 0)
                draw_ink_centered(draw, move_num_x, cy, str(abs(delta)), numf, col, ha="l")

        # Position number (ink-centred on cy)
        draw_ink_centered(draw, pos_x, cy, str(pos), numf, INK, ha="l")

        name = disp[p]
        name_col = GOLD if p == gold_name_player else INK
        base_y = cy + baseline_off
        cap_center = base_y - name_cap_h / 2   # vertical centre of the name's caps

        # Crown: small, right edge ~30px before the name, centred on cy (the
        # position number's centre)
        if p == crown_player:
            em = _emoji_image("👑", crown_px)
            img.paste(em, (int(name_x - 30 - em.width), int(cy - em.height / 2)), em)

        # Player name
        draw.text((name_x, base_y), name, font=nf_gold, fill=name_col, anchor="ls")

        # Trophy: inline after the name, centred on the name's caps
        if p in trophies:
            nw = draw.textlength(name, font=nf)
            em = _emoji_image("🏆", trophy_px)
            img.paste(em, (int(name_x + nw + 10), int(cap_center - em.height / 2)), em)

        # Deck subtitle, a fixed gap below the name's baseline
        draw.text((name_x, base_y + deck_gap), decks.get(p, ""), font=df, fill=DECK_INK, anchor="ls")

        # Points (ink-centred on cy); final => most-total player shows total gold
        if p == gold_pts_player:
            draw_ink_centered(draw, pts_right, cy, str(totals[p]), numf, GOLD, ha="r")
        else:
            draw_ink_centered(draw, pts_right, cy, str(best7[p]), numf, INK, ha="r")

    if out is None:
        out = os.path.join("/tmp", f"{league_id}-week{week:02d}.png")
    out = os.path.expanduser(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default=None, help="league id (default: active)")
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--champion", default=None, help="playoff winner (final poster); key like 'Chris G'")
    args = ap.parse_args()
    league_id = args.league or simulate.load_leagues_config()["active_league"]
    path = render(league_id, week=args.week, final=args.final, out=args.out,
                  title=args.title, champion=args.champion)
    print(path)


if __name__ == "__main__":
    main()
