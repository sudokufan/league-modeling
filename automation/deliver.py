#!/usr/bin/env python3
"""Best-effort delivery of a poster PNG via iMessage (macOS Messages.app).

The poster is ALSO returned in the Claude chat by the runbook, so this is a
bonus channel. It requires Messages.app signed into iMessage; it may fail
silently or error when the Mac is locked/asleep — that's expected and tolerated.

Usage: deliver.py <image_path> [--to "+447403611477" ...]
If --to is omitted, recipients come from automation_config.json.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

APPLESCRIPT = '''
on run argv
    set imagePath to item 1 of argv
    set targetId to item 2 of argv
    tell application "Messages"
        set svc to 1st account whose service type = iMessage
        set theBuddy to participant targetId of svc
        send (POSIX file imagePath) to theBuddy
    end tell
end run
'''


def send_one(image_path, recipient):
    try:
        subprocess.run(
            ["osascript", "-e", APPLESCRIPT, image_path, recipient],
            check=True, capture_output=True, text=True, timeout=60,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or e.stdout or str(e)).strip()
    except Exception as e:  # timeout, osascript missing, etc.
        return False, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--to", action="append", default=None, help="phone/email; repeatable")
    args = ap.parse_args()

    image_path = os.path.abspath(os.path.expanduser(args.image))
    if not os.path.exists(image_path):
        print(f"image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    if args.to:
        recipients = [{"name": t, "number": t} for t in args.to]
    else:
        cfg = json.load(open(os.path.join(HERE, "automation_config.json")))
        recipients = cfg["delivery"]["imessage_recipients"]

    any_fail = False
    for r in recipients:
        ok, err = send_one(image_path, r["number"])
        if ok:
            print(f"✓ sent to {r['name']} ({r['number']})")
        else:
            any_fail = True
            print(f"✗ failed to {r['name']} ({r['number']}): {err}")
    # Best-effort: exit 0 even on failure so the workflow isn't blocked.
    sys.exit(0)


if __name__ == "__main__":
    main()
