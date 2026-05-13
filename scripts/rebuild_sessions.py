#!/usr/bin/env python3
"""
rebuild_sessions.py  —  Rebuild data/sessions.json from all CSVs in sessions/.

Called automatically by the GitHub Action, or run manually:
    python scripts/rebuild_sessions.py

- Parses every sessions/YYYY-MM-DD.csv for financial data.
- Merges in hands-won data from data/hands_won.json (if it exists).
- Resolves player IDs against data/players.json for consistent display names.
- Writes the result to data/sessions.json.
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
PLAYERS_FILE  = REPO_ROOT / "data" / "players.json"


def get_divisor(players_raw: list[dict]) -> float:
    buy_ins = [p['buy_in'] for p in players_raw if p['buy_in'] > 0]
    if not buy_ins:
        return 1.0
    avg = sum(buy_ins) / len(buy_ins)
    if avg >= 10000: return 1000.0
    if avg >= 1000:  return 100.0
    return 1.0


def load_players() -> dict:
    """Load id→name mapping from data/players.json."""
    if PLAYERS_FILE.exists():
        data = json.loads(PLAYERS_FILE.read_text())
        return data.get('players', {})
    return {}


def save_players(mapping: dict):
    """Save updated id→name mapping, preserving existing entries."""
    existing = {}
    if PLAYERS_FILE.exists():
        existing = json.loads(PLAYERS_FILE.read_text())
    existing['players'] = mapping
    PLAYERS_FILE.write_text(json.dumps(existing, indent=2))


def resolve_name(player_id: str, nickname: str, mapping: dict) -> str:
    """Return the canonical name for this player ID, or nickname if not mapped."""
    return mapping.get(player_id, nickname)


def parse_pokernow_csv(filepath: Path) -> tuple[list[dict], str | None]:
    """Returns (players_raw_with_ids, session_date_or_None)."""
    players_raw = []
    session_date = None
    try:
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return [], None
            for row in reader:
                clean = {k.strip().lower().replace('"', ''): str(v).strip().strip('"')
                         for k, v in row.items()}

                # Auto-detect session date from session_start_at
                if not session_date:
                    ts = clean.get('session_start_at', '')
                    m = re.match(r'(\d{4}-\d{2}-\d{2})', ts)
                    if m:
                        session_date = m.group(1)

                first_val = list(clean.values())[0]
                if '@' in first_val:
                    # Older format: "Name @ id"
                    parts      = first_val.split('@')
                    name       = parts[0].strip()
                    player_id  = parts[1].strip() if len(parts) > 1 else ''
                    net        = float(clean.get('net', 0) or 0)
                    buy_in     = float(clean.get('buy_in', clean.get('buyin', 0)) or 0)
                    buy_out    = float(clean.get('buy_out', clean.get('buyout', 0)) or 0)
                else:
                    # Current format: separate columns
                    name       = clean.get('player_nickname', clean.get('nickname', clean.get('name', '')))
                    player_id  = clean.get('player_id', '')
                    net        = float(clean.get('net', 0) or 0)
                    buy_in     = float(clean.get('buy_in', clean.get('buyin', 0)) or 0)
                    buy_out    = float(clean.get('buy_out', clean.get('buyout', 0)) or 0)

                if not name or name.lower() in ('player_nickname', 'player name', 'name', ''):
                    continue

                players_raw.append({
                    'name':      name,
                    'player_id': player_id,
                    'buy_in':    buy_in,
                    'buy_out':   buy_out,
                    'net':       net,
                })

    except Exception as e:
        print(f"  Warning: could not parse {filepath.name}: {e}")
        return [], None

    if not players_raw:
        return [], session_date

    divisor = get_divisor(players_raw)
    if divisor > 1:
        print(f"  (chip values detected — dividing by {int(divisor)} to get dollars)")

    players = [{
        'name':      p['name'],
        'playerId':  p['player_id'],
        'buyIn':     round(p['buy_in']  / divisor, 2),
        'buyOut':    round(p['buy_out'] / divisor, 2),
        'net':       round(p['net']     / divisor, 2),
    } for p in players_raw]

    return players, session_date


def main():
    # Load supporting data
    hands_won      = {}
    player_mapping = load_players()

    if HANDS_FILE.exists():
        hands_won = json.loads(HANDS_FILE.read_text())
        print(f"Loaded hands_won data for {len(hands_won)} session(s)")

    print(f"Loaded {len(player_mapping)} player name mapping(s)")

    # Find all CSVs
    csv_files = sorted(SESSIONS_DIR.glob('*.csv')) if SESSIONS_DIR.exists() else []
    print(f"Found {len(csv_files)} CSV file(s) in sessions/")

    sessions = []
    new_players = dict(player_mapping)  # track any new IDs discovered

    for csv_path in csv_files:
        stem = csv_path.stem
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', stem)
        if not date_match:
            print(f"  Skipping {csv_path.name} (filename must start with YYYY-MM-DD)")
            continue

        session_date = date_match.group(1)
        players, csv_date = parse_pokernow_csv(csv_path)
        if csv_date and not date_match:
            session_date = csv_date
        if not players:
            print(f"  Skipping {csv_path.name} (no players found)")
            continue

        # Register new player IDs and resolve display names
        hw = hands_won.get(session_date, {})
        for p in players:
            pid = p.get('playerId', '')
            if pid and pid not in new_players:
                new_players[pid] = p['name']
                print(f"  New player registered: {p['name']} ({pid})")
            # Resolve canonical name
            if pid:
                p['name'] = resolve_name(pid, p['name'], new_players)
            p['handsWon'] = hw.get(p['name'], None)

        sessions.append({
            "id":      stem,
            "date":    session_date,
            "note":    "Private game",
            "players": players,
        })
        print(f"  Processed {csv_path.name} — {len(players)} player(s)")

    # Save updated player mappings if any new IDs found
    if new_players != player_mapping:
        save_players(new_players)
        print(f"\n✓ Updated players.json with {len(new_players)} player(s)")

    sessions.sort(key=lambda s: s['date'])
    data = {
        "lastUpdated": date.today().isoformat(),
        "sessions":    sessions,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2))
    print(f"\n✓ Written {len(sessions)} session(s) to data/sessions.json")


if __name__ == '__main__':
    main()
