# MTG League Playoff Probability Model

Monte Carlo simulation model for a 10-week Magic: The Gathering league. Calculates playoff qualification probabilities based on current standings and simulated future results.

## Quick Start

Start the web server:

```
python3 server.py
```

Then open **http://localhost:8080/** in your browser.

## Pages

| URL | Description |
|-----|-------------|
| `/` | Current league dashboard (simulation, standings, bracket) |
| `/cumulative` | Cumulative standings across all 2026 leagues |
| `/all-time` | All-time records and career stats |
| `/?league=2025-season-1` | View a specific league by ID |

## Adding Weekly Results

1. Click **"Add Week Results"** in the dashboard header
2. Select the week number
3. Add matchups for each round (Player A, Player B, games won each)
4. Click **Submit** — the simulation re-runs and probabilities update automatically

All data is saved to `leagues/<league-id>.json` and persists between server restarts.

## How It Works

- **50,000 Monte Carlo simulations** of the remaining weeks
- Match outcomes weighted by Bayesian-regressed historical win rates
- Proper 1v1 pairing constraints (every win produces a corresponding loss)
- Player attendance modelled from historical patterns
- Final standings use **best N of 10** weekly scores (configurable per league)
- Top 4 players qualify for playoffs (single-elimination bracket)

## Files

| File | Purpose |
|------|---------|
| `server.py` | Web server (port 8080) with data entry UI |
| `simulate.py` | Simulation engine and HTML dashboard generator |
| `leagues/` | Per-league JSON data files |
| `leagues_config.json` | League registry (active league, league list) |
