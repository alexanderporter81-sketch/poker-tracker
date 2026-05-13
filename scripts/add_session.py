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
def detect_cents(players_raw: list[dict]) -> bool:
    buy_ins = [p['buy_in'] for p in players_raw if p['buy_in'] > 0]
    return bool(buy_ins) and (sum(buy_ins) / len(buy_ins)) >= 1000


def parse_pokernow_csv(filepath: str) -> tuple[list[dict], str | None]:
    """
    Returns (players, auto_detected_date_or_None).
    Handles both PokerNow export formats and auto-converts cents to dollars.
    """
    players_raw = []
    auto_date = None

    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip().lower().replace('"',''): str(v).strip().strip('"') for k, v in row.items()}

            # Auto-detect date from session_start_at
            if not auto_date:
                ts = clean.get('session_start_at', '')
                m = re.match(r'(\d{4}-\d{2}-\d{2})', ts)
                if m:
                    auto_date = m.group(1)

            first_val = str(list(clean.values())[0])
            if '@' in first_val:
                name    = first_val.split('@')[0].strip()
                net     = float(clean.get('net', 0) or 0)
                buy_in  = float(clean.get('buy_in', clean.get('buyin', 0)) or 0)
                buy_out = float(clean.get('buy_out', clean.get('buyout', 0)) or 0)
            else:
                name    = clean.get('player_nickname', clean.get('nickname', clean.get('name', 'Unknown')))
                net     = float(clean.get('net', 0) or 0)
                buy_in  = float(clean.get('buy_in', clean.get('buyin', 0)) or 0)
                buy_out = float(clean.get('buy_out', clean.get('buyout', 0)) or 0)

            if not name or name.lower() in ('player_nickname', 'player name'):
                continue

            players_raw.append({'name': name, 'buy_in': buy_in, 'buy_out': buy_out, 'net': net})

    if not players_raw:
        return [], auto_date

    divisor = 100.0 if detect_cents(players_raw) else 1.0
    if divisor == 100.0:
        print("  (detected cent values — converting to dollars automatically)")

    players = [{
        'name':   p['name'],
        'buyIn':  round(p['buy_in']  / divisor, 2),
        'buyOut': round(p['buy_out'] / divisor, 2),
        'net':    round(p['net']     / divisor, 2),
    } for p in players_raw]

    return players, auto_date


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
    players, auto_date = parse_pokernow_csv(csv_path)

    # Use date from CSV if not provided on command line
    if auto_date and session_date == date.today().isoformat():
        session_date = auto_date
        print(f"  Auto-detected session date from CSV: {session_date}")

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
