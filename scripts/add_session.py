#!/usr/bin/env python3
"""
add_session.py  —  Add a PokerNow ledger CSV to the tracker.

Usage:
    python scripts/add_session.py <path-to-ledger.csv> [YYYY-MM-DD] [--note "Game night"]

If you omit the date, today's date is used.
The script will prompt you to enter hands won for each player.

PokerNow ledger CSV columns (the script handles both formats):
    Format A: "Player name @ id", net, buy_in, buy_out, stack, gamesCount
    Format B: player_nickname, player_id, buy_in, buy_out, stack, net
"""

import csv
import json
import os
import sys
import re
from datetime import date, datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "sessions"
DATA_FILE    = REPO_ROOT / "data" / "sessions.json"

# ── Parse PokerNow CSV ────────────────────────────────────────────────────────
def parse_pokernow_csv(filepath: str) -> list[dict]:
    """
    Returns a list of dicts: {name, buyIn, buyOut, net}
    Handles both PokerNow export formats automatically.
    """
    players = []
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = [h.strip().lower().replace('"','') for h in reader.fieldnames or []]

        for row in reader:
            # Normalise keys
            clean = {k.strip().lower().replace('"',''): v.strip().strip('"') for k, v in row.items()}

            # Detect format
            # Format A: first column is "Player name @ id"
            first_key = list(clean.keys())[0]
            if '@' in str(list(clean.values())[0]):
                raw_name = list(clean.values())[0]
                name = raw_name.split('@')[0].strip()
                net    = float(clean.get('net', 0))
                buy_in = float(clean.get('buy_in', clean.get('buyin', 0)))
                buy_out= float(clean.get('buy_out', clean.get('buyout', 0)))
            else:
                # Format B
                name   = clean.get('player_nickname', clean.get('nickname', clean.get('name', 'Unknown')))
                net    = float(clean.get('net', 0))
                buy_in = float(clean.get('buy_in', clean.get('buyin', 0)))
                buy_out= float(clean.get('buy_out', clean.get('buyout', 0)))

            if not name or name.lower() in ('player_nickname', 'player name'):
                continue

            players.append({
                'name':   name,
                'buyIn':  round(buy_in, 2),
                'buyOut': round(buy_out, 2),
                'net':    round(net, 2),
            })

    return players


# ── Prompt for hands won ──────────────────────────────────────────────────────
def prompt_hands_won(players: list[dict]) -> list[dict]:
    print("\n── Hands won (press Enter to skip for a player) ──")
    for p in players:
        val = input(f"  {p['name']}: ").strip()
        p['handsWon'] = int(val) if val.isdigit() else None
    return players


# ── Load / save sessions.json ─────────────────────────────────────────────────
def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"lastUpdated": "", "sessions": []}


def save_data(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["lastUpdated"] = date.today().isoformat()
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n✓ Saved → {DATA_FILE.relative_to(REPO_ROOT)}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python scripts/add_session.py <ledger.csv> [YYYY-MM-DD] [--note \"...\"]")
        sys.exit(1)

    csv_path = args[0]
    session_date = date.today().isoformat()
    note = ""

    # Parse optional args
    for i, a in enumerate(args[1:], 1):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', a):
            session_date = a
        elif a == '--note' and i + 1 < len(args):
            note = args[i + 1]
        elif args[i-1] == '--note':
            note = a  # value after --note

    # Parse CSV
    print(f"\nReading: {csv_path}")
    players = parse_pokernow_csv(csv_path)

    if not players:
        print("No players found in CSV. Check the file format.")
        sys.exit(1)

    print(f"\nFound {len(players)} player(s) for {session_date}:")
    for p in players:
        sign = '+' if p['net'] >= 0 else ''
        print(f"  {p['name']:<20} buy-in: ${p['buyIn']:.2f}  net: {sign}${p['net']:.2f}")

    # Prompt hands won
    players = prompt_hands_won(players)

    # Build session entry
    session = {
        "id":      session_date,
        "date":    session_date,
        "note":    note or "Private game",
        "players": players,
    }

    # Load existing data
    data = load_data()

    # Check for duplicate date
    existing_ids = [s['id'] for s in data['sessions']]
    if session_date in existing_ids:
        overwrite = input(f"\n⚠️  A session for {session_date} already exists. Overwrite? [y/N] ").strip().lower()
        if overwrite != 'y':
            print("Aborted.")
            sys.exit(0)
        data['sessions'] = [s for s in data['sessions'] if s['id'] != session_date]

    data['sessions'].append(session)
    data['sessions'].sort(key=lambda s: s['date'])

    save_data(data)

    # Also copy the CSV to sessions/ for archiving
    SESSIONS_DIR.mkdir(exist_ok=True)
    import shutil
    dest = SESSIONS_DIR / f"{session_date}.csv"
    shutil.copy2(csv_path, dest)
    print(f"✓ Archived CSV → sessions/{session_date}.csv")

    print("\nDone! Commit and push to update the live tracker.")
    print("  git add data/sessions.json sessions/")
    print(f"  git commit -m 'Add session {session_date}'")
    print("  git push")


if __name__ == '__main__':
    main()
