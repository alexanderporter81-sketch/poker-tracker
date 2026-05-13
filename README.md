# ♠ Poker Tracker

A shared web tracker for your private PokerNow games. Everyone gets one URL — open it after any session to see who's up, who's down, and the all-time leaderboard.

---

## One-time Setup (15 minutes)

### 1. Create a GitHub repository

1. Go to [github.com](https://github.com) and sign in with your student account.
2. Click **New repository** (green button).
3. Name it something like `poker-tracker`.
4. Set it to **Public** (required for free GitHub Pages).
5. Click **Create repository**.

### 2. Upload these files

On the new repo page, click **uploading an existing file** and drag in **everything** from this folder. Make sure to keep the folder structure intact:

```
poker-tracker/
├── index.html
├── data/
│   ├── sessions.json
│   └── hands_won.json
├── sessions/         ← (empty folder — add a .gitkeep file so GitHub keeps it)
├── scripts/
│   ├── add_session.py
│   └── rebuild_sessions.py
└── .github/
    └── workflows/
        └── process_session.yml
```

> **Tip:** GitHub won't let you upload empty folders. Create a file called `.gitkeep` inside `sessions/` before uploading.

### 3. Enable GitHub Pages

1. In your repo, go to **Settings → Pages**.
2. Under **Branch**, select `main` and folder `/` (root).
3. Click **Save**.
4. After ~30 seconds, your tracker is live at:  
   **`https://<your-username>.github.io/poker-tracker/`**

Share that URL with everyone in the group!

### 4. Enable GitHub Actions permissions

1. Go to **Settings → Actions → General**.
2. Under **Workflow permissions**, select **Read and write permissions**.
3. Click **Save**.

This lets the bot auto-commit updated `sessions.json` when you drop in a new CSV.

---

## After Each Session

### Step 1 — Download the PokerNow ledger

At the end of a game on PokerNow:
1. Click the **≡ Menu** (top-right of the game screen).
2. Select **Export → Ledger CSV**.
3. Save the file as `YYYY-MM-DD.csv` (e.g. `2026-05-13.csv`).

### Step 2 — Add hands won (optional)

If you want to track hands won:
1. Open `data/hands_won.json` in the GitHub repo (click the file, then the ✏️ pencil icon).
2. Add an entry for the session date:
   ```json
   {
     "2026-05-13": {
       "Alex": 15,
       "Bob": 8,
       "Charlie": 6
     }
   }
   ```
3. Commit the change.

### Step 3 — Upload the CSV to trigger the tracker update

1. In your GitHub repo, click the `sessions/` folder.
2. Click **Add file → Upload files**.
3. Drag in your `2026-05-13.csv` file.
4. Click **Commit changes**.

The GitHub Action runs automatically (~30 seconds), rebuilds `sessions.json`, and your tracker URL is updated. Everyone can refresh and see the new results.

---

## Manually Running the Script (Advanced)

If you prefer to run things locally instead of through GitHub's UI:

```bash
# Clone the repo
git clone https://github.com/<your-username>/poker-tracker.git
cd poker-tracker

# Add a session (prompts for hands won)
python scripts/add_session.py path/to/ledger.csv 2026-05-13 --note "Friday night game"

# Push updates
git add data/sessions.json sessions/
git commit -m "Add session 2026-05-13"
git push
```

Python 3.9+ required, no extra packages needed.

---

## File Structure Reference

| File | Purpose |
|---|---|
| `index.html` | The web tracker everyone opens |
| `data/sessions.json` | All session data (auto-generated, don't edit manually) |
| `data/hands_won.json` | Manually enter hands won per session here |
| `sessions/*.csv` | Archived raw PokerNow ledger exports |
| `scripts/add_session.py` | CLI tool to add a session locally |
| `scripts/rebuild_sessions.py` | Rebuilds sessions.json from all CSVs (called by GitHub Action) |
| `.github/workflows/process_session.yml` | GitHub Action that auto-processes new CSVs |

---

## Troubleshooting

**Tracker shows "Couldn't load session data"**  
→ Make sure GitHub Pages is enabled (Settings → Pages) and you're opening the `github.io` URL, not a local file path.

**GitHub Action not running**  
→ Check Settings → Actions → General → Workflow permissions is set to "Read and write".

**Player names look weird**  
→ PokerNow uses whatever nickname the player set. Ask everyone to use consistent names across sessions.

**I want to correct a past session**  
→ Delete the old CSV from `sessions/`, upload a corrected one, or edit `data/sessions.json` directly on GitHub.
