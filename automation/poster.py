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
INK = (12, 12, 12)
DECK_GREY = (68, 68, 68)
HEADER_GREY = (12, 12, 12)
UP_GREEN = (66, 148, 66)
DOWN_RED = (176, 48, 28)
GOLD = (201, 155, 56)

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


def draw_triangle(draw, cx, cy, size, color, up=True):
    h = size
    w = size * 1.1
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

    # ---- Canvas + gradient bar ------------------------------------------
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    bar_w = int(W * 0.082)
    top = theme["bar_top"]
    bot = theme["bar_bottom"]
    for y in range(H):
        t = y / (H - 1)
        col = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (bar_w, y)], fill=col)

    # Rotated title in the bar
    title_fs = int(bar_w * 0.52)
    tf = ImageFont.truetype(BELEREN_SC, title_fs)
    tw = draw.textlength(title, font=tf)
    tmp = Image.new("RGBA", (int(tw) + 20, title_fs + 30), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10, 10), title, font=tf, fill=WHITE)
    tmp = tmp.rotate(90, expand=True)
    img.paste(tmp, (int((bar_w - tmp.width) / 2), int((H - tmp.height) / 2)), tmp)

    # ---- Layout ----------------------------------------------------------
    content_left = bar_w + 40
    pts_right = W - 55
    move_x = content_left + 30       # arrow centre
    move_num_x = content_left + 58   # movement number (left-anchored)
    pos_x = content_left + 140       # position number (right-anchored)
    name_x = content_left + 220      # player name (left-anchored)

    top_pad = 150
    bottom_pad = 45
    n_rows = len(order)
    row_h = (H - top_pad - bottom_pad) / n_rows

    # Header (Beleren bold, black, mixed case)
    hf = ImageFont.truetype(BELEREN_BOLD, max(15, int(row_h * 0.24)))
    hy = top_pad - int(row_h * 0.55)
    draw.text((pos_x, hy), "Pos.", font=hf, fill=HEADER_GREY, anchor="rm")
    draw.text((name_x, hy), "Player", font=hf, fill=HEADER_GREY, anchor="lm")
    draw.text((pts_right, hy), "Pts.", font=hf, fill=HEADER_GREY, anchor="rm")

    name_fs = max(16, int(row_h * 0.34))
    deck_fs = max(12, int(row_h * 0.23))
    num_fs = max(16, int(row_h * 0.36))
    move_fs = max(11, int(row_h * 0.22))
    nf = ImageFont.truetype(BELEREN_BOLD, name_fs)
    nf_gold = nf
    df = ImageFont.truetype(MPLANTIN, deck_fs)
    numf = ImageFont.truetype(BELEREN_BOLD, num_fs)
    mf = ImageFont.truetype(BELEREN_BOLD, move_fs)

    for i, p in enumerate(order):
        row_top = top_pad + i * row_h
        cy = row_top + row_h / 2
        pos = i + 1

        # Movement arrow vs previous week
        if p in prev_pos:
            delta = prev_pos[p] - i  # positive => moved up
            if delta > 0:
                draw_triangle(draw, move_x, cy, int(move_fs * 0.9), UP_GREEN, up=True)
                draw.text((move_num_x, cy), str(delta), font=mf, fill=UP_GREEN, anchor="lm")
            elif delta < 0:
                draw_triangle(draw, move_x, cy, int(move_fs * 0.9), DOWN_RED, up=False)
                draw.text((move_num_x, cy), str(-delta), font=mf, fill=DOWN_RED, anchor="lm")

        # Position number
        draw.text((pos_x, cy), str(pos), font=numf, fill=INK, anchor="rm")

        name = disp[p]
        name_col = GOLD if p == gold_name_player else INK
        name_y = cy - row_h * 0.16
        deck_y = cy + row_h * 0.22
        icon_px = int(name_fs * 1.05)

        # Crown sits centered in the gutter between the position number and name
        if p == crown_player:
            em = _emoji_image("👑", int(icon_px * 0.92))
            gutter_cx = (pos_x + name_x) / 2
            img.paste(em, (int(gutter_cx - em.width / 2), int(cy - em.height / 2)), em)

        # Player name (gold if final champion)
        draw.text((name_x, name_y), name, font=nf_gold, fill=name_col, anchor="lm")

        # Trophy sits inline, just after the name
        if p in trophies:
            nw = draw.textlength(name, font=nf)
            em = _emoji_image("🏆", icon_px)
            img.paste(em, (int(name_x + nw + 12), int(name_y - icon_px / 2)), em)

        draw.text((name_x, deck_y), decks.get(p, ""), font=df, fill=DECK_GREY, anchor="lm")

        # Points (best-N; final => most-total player shows total in gold)
        if p == gold_pts_player:
            draw.text((pts_right, cy), str(totals[p]), font=numf, fill=GOLD, anchor="rm")
        else:
            draw.text((pts_right, cy), str(best7[p]), font=numf, fill=INK, anchor="rm")

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
