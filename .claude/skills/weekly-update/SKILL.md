---
name: weekly-update
description: Record a week of MTG league results from EventLink round photos and produce the standings poster. Use whenever the user uploads/points to photos of EventLink round results (screens showing "MATCH RESULTS", Player #1/#2 and game scores) and wants the week added and a poster made — e.g. "here are this week's photos", "add week 3", "week's results are on the Desktop". Also handles the final season-complete poster after playoffs.
---

# Weekly league update

Turn EventLink round photos into updated JSON + a standings poster, then deliver it.
All scoring reuses `simulate.py`, so the poster always agrees with the dashboard.

Paths (repo root = `/Users/home/Documents/league-modeling`):

- Poster renderer: `automation/poster.py` (run with `.venv/bin/python`)
- Match ingest: `automation/add_matches.py`
- Delivery: `automation/deliver.py`
- Data: `automation/decks.json`, `automation/name_map.json`, `automation/automation_config.json`
- League JSONs: `leagues/<id>.json`; active league id in `leagues_config.json`

## Where this runs (trigger & context)

This skill only works inside a **Claude Code session running on the Mac in this
repo** — that's where the scripts, fonts, and data live. The plain Claude iOS/web
chat is NOT Claude Code and cannot see any of this.

The intended flow: the user drives a Claude Code session on the Mac **from their
phone via Remote Control**, coming home from the store, and attaches the EventLink
photos there. Images attached in that session are readable directly. Saying "here
are this week's photos" is enough to trigger this skill — no slash command needed.

Requirements for it to work when triggered remotely:

- The Mac must be **on and awake** (not asleep) with the Claude Code session reachable.
- The Claude Code app needs **Full Disk Access** (System Settings → Privacy &
  Security). Without it, `~/Documents` (this repo) becomes unreadable the moment the
  Mac is **locked** — which is the normal remote-trigger state — and every step
  fails. This is mandatory, not optional.

## Procedure

### 1. Locate the photos

Photos may be attached in chat, or on disk. `~/Desktop` is TCC-protected — if a
read fails with "Operation not permitted", ask the user to move them into the repo
or iCloud folder, or to grant the terminal Full Disk Access. iCloud League folder
(readable) is `automation_config.json → poster_output_dir`.

### 2. Determine the week

Read each photo's capture time (this also orders the rounds):
`mdls -name kMDItemContentCreationDate <file>`.
The **date** identifies the week (e.g. all photos from one evening = that week).
Confirm the week number with the user if there's any doubt. One evening = 4 rounds
= 4 photos normally.

### 3. Read each photo → matches

EventLink screens are often photographed **upside down**. If so, rotate first:
`sips -r 180 <in> --out /tmp/rot.jpeg`, then read the rotated copy.
Each photo is ONE round. Columns are `Player #1 | game_a - game_b | Player #2`.
A row against "Bye" is a bye: `player_b = null`, games as shown (usually 2-0).
Order rounds 1..N by capture time (earliest = round 1).

### 4. Map names

EventLink shows full names; the league uses short keys. Translate via
`name_map.json`. For any name NOT in the map, apply the "FirstName LastInitial"
rule (e.g. "Jane Smith" → "Jane S") and **explicitly confirm with the user**
before proceeding; once confirmed, add it to `name_map.json`.

### 5. Apply deck changes (only if mentioned)

If the user said someone swapped decks, edit `automation/decks.json` accordingly.
Otherwise leave it — decks are sticky.

### 6. Write the matches

Pipe the confirmed matches (JSON list, short keys or full names both fine) to:
`.venv/bin/python automation/add_matches.py`
It validates names, skips duplicates (safe to re-run), and writes the active
league JSON. Use `--dry-run` first if unsure.

### 7. Confirm before writing

Show the total standings for this week's parsed matches and ask the
user to confirm. A single misread score corrupts standings — always get a thumbs-up.

### 8. Render the poster

Regular week:
`.venv/bin/python automation/poster.py --week <N> --out "<icloud>/<season_folder>/week<NN>-<mmmDD>.png"`

- `<icloud>` = `poster_output_dir`; `<season_folder>` from the league's theme.
- Filename matches existing convention, e.g. `week03-sep25.png` (date from EXIF).

Final / season-complete poster (11th, after playoffs):
`.venv/bin/python automation/poster.py --final --champion "<winner key>" --out "<...>/final.png"`

- `--champion` is the **playoff winner** (crown + gold name); most-total-points
  player's total is auto-gold. Get the playoff winner from `playoffs` in the
  league JSON or ask the user.

Then Read the output PNG to eyeball it before sending.

### 9. Deliver

- Always present the PNG in the chat (primary channel).
- Best-effort text to Martin: `.venv/bin/python automation/deliver.py "<png>"`
  (reads recipients from `automation_config.json`). Requires Messages.app signed
  into iMessage and the terminal's **Automation → Messages** permission granted
  (approved once while unlocked). May still fail when the Mac is locked/asleep —
  that's fine; report success or failure but don't block on it.

### 10. Offer to commit

Offer to commit the updated league JSON (and decks/name_map if changed) with a
message like "season 3 week 3". Don't commit the poster PNG (it lives in iCloud).

## Poster semantics (already handled by poster.py)

- Ranking: best-N score, then OMW%, then GW%.
- 🏆 trophy: player won every round in any completed week.
- 👑 crown: reigning champion during the season (`theme.reigning_champion`);
  on the final poster it's the playoff winner (`--champion`).
- Gold: final poster only — champion's NAME gold; most-total-points player's total gold.
- Display names: first name only, disambiguated to the full key on collisions.
- Everyone is included (no 16-player cap); layout auto-fits the roster.
