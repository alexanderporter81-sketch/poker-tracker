#!/usr/bin/env python3
"""
rebuild_sessions.py  —  Rebuild data/sessions.json from all CSVs in sessions/.

Called automatically by the GitHub Action, or run manually:
    python scripts/rebuild_sessions.py

- Parses every sessions/YYYY-MM-DD.csv for financial data.
- Merges in hands-won data from data/hands_won.json (if it exists).
- Writes the result to data/sessions.json.

To record hands won for a session, edit data/hands_won.json like this:
{
  "2026-05-13": { "Alex": 15, "Bob": 8, "Charlie": 6 }
}
"""

import csv
import json
import re
from datetime import date
from pathlib import Path

REPO_ROOT     = Path(__file__).resolve().parent.parent
SESSIONS_DIR  = REPO_ROOT / "sessions"
DATA_FILE     = REPO_ROOT / "data" / "sessions.json"
HANDS_FILE    = REPO_ROOT / "data" / "hands_won.json"


def parse_pokernow_csv(filepath: Path) -> list[dict]:
    players = []
    try:
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return []
            for row in reader:
                clean = {k.strip().lower().replace('"', ''): str(v).strip().strip('"')
                         for k, v in row.items()}

                # Format A: first value contains '@'
                first_val = list(clean.values())[0]
                if '@' in first_val:
                    name   = first_val.split('@')[0].strip()
                    net    = float(clean.get('net', 0) or 0)
                    buy_in = float(clean.get('buy_in', clean.get('buyin', 0)) or 0)
                    buy_out= float(clean.get('buy_out', clean.get('buyout', 0)) or 0)
                else:
                    name   = clean.get('player_nickname', clean.get('nickname', clean.get('name', '')))
                    net    = float(clean.get('net', 0) or 0)
                    buy_in = float(clean.get('buy_in', clean.get('buyin', 0)) or 0)
                    buy_out= float(clean.get('buy_out', clean.get('buyout', 0)) or 0)

                if not name or name.lower() in ('player_nickname', 'player name', 'name', ''):
                    continue

                players.append({
                    'name':   name,
                    'buyIn':  round(buy_in, 2),
                    'buyOut': round(buy_out, 2),
                    'net':    round(net, 2),
                })
    except Exception as e:
        print(f"  Warning: could not parse {filepath.name}: {e}")
    return players


def main():
    # Load hands_won overrides if present
    hands_won = {}
    if HANDS_FILE.exists():
        with open(HANDS_FILE) as f:
            hands_won = json.load(f)
        print(f"Loaded hands_won data for {len(hands_won)} session(s)")

    # Find all dated CSVs
    csv_files = sorted(SESSIONS_DIR.glob('*.csv')) if SESSIONS_DIR.exists() else []
    print(f"Found {len(csv_files)} CSV file(s) in sessions/")

    sessions = []
    for csv_path in csv_files:
        # Expect filename: YYYY-MM-DD.csv (optionally with suffix like YYYY-MM-DD-game2.csv)
        stem = csv_path.stem
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', stem)
        if not date_match:
            print(f"  Skipping {csv_path.name} (filename must start with YYYY-MM-DD)")
            continue

        session_date = date_match.group(1)
        players = parse_pokernow_csv(csv_path)
        if not players:
            print(f"  Skipping {csv_path.name} (no players found)")
            continue

        # Merge hands won
        hw = hands_won.get(session_date, {})
        for p in players:
            p['handsWon'] = hw.get(p['name'], None)

        sessions.append({
            "id":      stem,        # use full stem as id (handles duplicates like 2026-05-13-game2)
            "date":    session_date,
            "note":    "Private game",
            "players": players,
        })
        print(f"  Processed {csv_path.name} — {len(players)} player(s)")

    sessions.sort(key=lambda s: s['date'])

    data = {
        "lastUpdated": date.today().isoformat(),
        "sessions":    sessions,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Written {len(sessions)} session(s) to data/sessions.json")


if __name__ == '__main__':
    main()
