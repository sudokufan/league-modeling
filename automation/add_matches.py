#!/usr/bin/env python3
"""Append a week's parsed matches to the active league JSON.

Input: JSON (file via --input, or stdin) shaped as a list of matches:
  [{"week":2,"round":3,"player_a":"Liam L","player_b":"Harry S",
    "games_a":1,"games_b":2}, ...]
Player names may be either league short-keys ("Liam L") or EventLink full
names ("Liam Lewis") — full names are translated via name_map.json.
A bye is player_b = null (with games recorded, usually 2-0).

Safeguards:
  - Unknown player names abort the whole write (nothing is half-added).
  - Duplicate matches (same week+round+player pair) are skipped, so re-running
    the same week is safe/idempotent.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import simulate  # noqa: E402


def load_json(path):
    with open(path) as f:
        return json.load(f)


def resolve_name(name, roster, name_map):
    if name is None or name in ("-", "", "Bye", "bye"):
        return None
    if name in roster:
        return name
    if name in name_map:
        return name_map[name]
    return ("UNKNOWN", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default=None, help="league id (default: active)")
    ap.add_argument("--input", default=None, help="JSON file (default: stdin)")
    ap.add_argument("--dry-run", action="store_true", help="validate + report, do not write")
    args = ap.parse_args()

    raw_in = open(args.input).read() if args.input else sys.stdin.read()
    incoming = json.loads(raw_in)

    league_id = args.league or simulate.load_leagues_config()["active_league"]
    data_file = os.path.join(ROOT, "leagues", simulate.get_league_info(league_id)["file"])
    data = load_json(data_file)
    roster = set(data["players"])
    name_map = load_json(os.path.join(HERE, "name_map.json"))["map"]

    # Resolve + validate names first
    unknown = []
    resolved = []
    for m in incoming:
        a = resolve_name(m["player_a"], roster, name_map)
        b = resolve_name(m.get("player_b"), roster, name_map)
        for r in (a, b):
            if isinstance(r, tuple):
                unknown.append(r[1])
        resolved.append({**m, "player_a": a, "player_b": b})

    if unknown:
        print("ABORT — unknown player names (add to name_map.json or fix):", file=sys.stderr)
        for u in sorted(set(unknown)):
            print("  -", u, file=sys.stderr)
        sys.exit(2)

    # Dedupe against existing matches
    def key(m):
        return (m["week"], m["round"], frozenset([m["player_a"], m.get("player_b")]))

    existing = {key(m) for m in data["matches"]}
    added, skipped = [], 0
    for m in resolved:
        if key(m) in existing:
            skipped += 1
            continue
        data["matches"].append({
            "week": m["week"], "round": m["round"],
            "player_a": m["player_a"], "player_b": m["player_b"],
            "games_a": m["games_a"], "games_b": m["games_b"],
        })
        existing.add(key(m))
        added.append(m)

    data["matches"].sort(key=lambda m: (m["week"], m["round"]))

    weeks = sorted({m["week"] for m in added})
    print(f"League: {league_id}")
    print(f"Added {len(added)} matches (weeks {weeks}), skipped {skipped} duplicate(s).")

    if args.dry_run:
        print("(dry-run — not written)")
        return
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {data_file}")


if __name__ == "__main__":
    main()
