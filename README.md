# BETA BLOCKZ — Full Build (Flask)
- Invite-only signup (code: `DUKESLOVESCURRY`)
- Admin login default: `admin@betablockz.local` / `admin123` (change via env)
- Manual balances, manual redeems (up to 24h, balance deducted immediately)
- Dice & Mines (10% house edge, server authoritative)
- VIP titles only with live progress (BETA thresholds divided by 100)
- Display units: **BETA** (1 BETA = 0.01 SOL), commas + two decimals
- Per-user `bonus_due` with one-click **Credit bonus**
- Per-user **claim code** (one-time) and **claim amount**
- PnL & Wager stats (24h/7d/30d) using per-bet pairing
- Purple gradient UI
- Wallet CSV included; upload at Admin → Upload Wallet List

## Run locally
Double-click **start.bat** (Windows) or run `bash start.sh` (Mac/Linux).  
Or manually:  
1) `pip install -r requirements.txt`  
2) `python app.py`  
3) Open http://localhost:5000

## On Replit
1) Create Repl → Import from ZIP → upload this file  
2) Press **Run**

## Env vars (optional)
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `SECRET_KEY`
