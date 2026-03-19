#!/usr/bin/env python3
"""
MTG League Playoff Probability Simulator
Monte Carlo simulation for a 10-week Magic: The Gathering league.
Loads data from league_data.json and derives all stats from raw match data.
"""

import json
import os
import random
import shutil
from collections import defaultdict
from typing import Optional

# ============================================================
# Data Loading & League Config
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LEAGUES_DIR = os.path.join(PROJECT_DIR, "leagues")
LEAGUES_CONFIG_FILE = os.path.join(PROJECT_DIR, "leagues_config.json")
DATA_FILE = os.path.join(PROJECT_DIR, "league_data.json")  # legacy path for backward compat

GLOBAL_DRAW_RATE = 0.05  # ~5% draw rate from historical data
MAX_WEEKLY_POINTS = 9


def _migrate_legacy_data():
    """Migrate league_data.json to leagues/ directory on first run."""
    legacy_file = os.path.join(PROJECT_DIR, "league_data.json")
    if os.path.exists(legacy_file) and not os.path.exists(LEAGUES_DIR):
        os.makedirs(LEAGUES_DIR, exist_ok=True)
        dest = os.path.join(LEAGUES_DIR, "2026-season-1.json")
        shutil.copy2(legacy_file, dest)
        # Create config
        config = {
            "active_league": "2026-season-1",
            "leagues": [
                {
                    "id": "2026-season-1",
                    "name": "2026 Season 1",
                    "file": "2026-season-1.json",
                    "status": "active",
                    "created": "2026-01-01"
                }
            ]
        }
        with open(LEAGUES_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Migrated league_data.json -> leagues/2026-season-1.json")


def load_leagues_config() -> dict:
    """Load the leagues configuration file."""
    _migrate_legacy_data()
    if not os.path.exists(LEAGUES_CONFIG_FILE):
        # Create a default config if none exists
        os.makedirs(LEAGUES_DIR, exist_ok=True)
        config = {
            "active_league": "2026-season-1",
            "leagues": [
                {
                    "id": "2026-season-1",
                    "name": "2026 Season 1",
                    "file": "2026-season-1.json",
                    "status": "active",
                    "created": "2026-01-01"
                }
            ]
        }
        with open(LEAGUES_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return config
    with open(LEAGUES_CONFIG_FILE, "r") as f:
        return json.load(f)


def save_leagues_config(config: dict):
    """Save the leagues configuration file."""
    with open(LEAGUES_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_league_data_path(league_id: str = None) -> str:
    """Get the file path for a league's data file. Defaults to active league."""
    config = load_leagues_config()
    if league_id is None:
        league_id = config["active_league"]
    for league in config["leagues"]:
        if league["id"] == league_id:
            return os.path.join(LEAGUES_DIR, league["file"])
    raise ValueError(f"League '{league_id}' not found in config")


def get_league_info(league_id: str = None) -> dict:
    """Get info dict for a league from config. Defaults to active league."""
    config = load_leagues_config()
    if league_id is None:
        league_id = config["active_league"]
    for league in config["leagues"]:
        if league["id"] == league_id:
            return league
    raise ValueError(f"League '{league_id}' not found in config")


def load_league_data(filepath: str = None, league_id: str = None) -> dict:
    """Load league data from JSON file.

    If filepath is given, load from that path directly.
    If league_id is given, look up its path from config.
    If neither, use the active league from config.
    """
    if filepath is not None:
        with open(filepath, "r") as f:
            return json.load(f)
    path = get_league_data_path(league_id)
    with open(path, "r") as f:
        return json.load(f)


def derive_stats(data: dict) -> dict:
    """
    Derive all league stats from raw match data.
    If no match data exists but weekly_scores_override is provided, use those directly.
    Returns a dict with all computed stats needed for simulation.
    """
    config = data["config"]
    players = data["players"]
    matches = data.get("matches", [])

    total_weeks = config["total_weeks"]
    rounds_per_week = config.get("rounds_per_week", 3)
    best_of_n = config["best_of_n"]
    playoff_spots = config.get("playoff_spots", 4)
    num_simulations = config.get("num_simulations", 50000)

    # If weekly scores are provided directly (no match-level data), use them
    if not matches and "weekly_scores" in data:
        weekly_scores = {}
        weeks_completed = total_weeks
        for p in players:
            scores = data["weekly_scores"].get(p, [])
            # Pad to total_weeks with None
            while len(scores) < total_weeks:
                scores.append(None)
            weekly_scores[p] = scores

        # Build basic overall stats from weekly scores (no match-level detail)
        overall_stats = {}
        for p in players:
            played = [s for s in weekly_scores[p] if s is not None]
            total_pts = sum(played)
            weeks_played = len(played)
            overall_stats[p] = {
                "mp": total_pts, "w": 0, "l": 0, "d": 0,
                "gw": 0, "gl": 0, "gwp": 0, "omw": 0,
            }

        attendance_prob = {p: 0.2 for p in players}  # irrelevant for completed leagues

        return {
            "config": config, "players": players,
            "unofficial_players": data.get("unofficial_players", []),
            "weekly_scores": weekly_scores, "overall_stats": overall_stats,
            "attendance_prob": attendance_prob, "weeks_completed": weeks_completed,
            "total_weeks": total_weeks, "rounds_per_week": rounds_per_week,
            "best_of_n": best_of_n, "playoff_spots": playoff_spots,
            "num_simulations": num_simulations, "matches": [],
            "per_week_records": {}, "per_week_opponents": {},
            "per_week_mwp": {}, "per_week_omw": {}, "overall_omw": {},
            "playoffs": data.get("playoffs"),
        }

    # Determine which weeks have data
    weeks_with_data = set()
    for m in matches:
        weeks_with_data.add(m["week"])
    weeks_completed = max(weeks_with_data) if weeks_with_data else 0

    # Compute weekly scores from match data
    # For each week, for each player, sum match points from all rounds
    weekly_points = defaultdict(lambda: defaultdict(int))  # week -> player -> pts
    players_in_week = defaultdict(set)  # week -> set of players who played

    # Track overall stats
    player_stats = {p: {"w": 0, "l": 0, "d": 0, "gw": 0, "gl": 0} for p in players}

    for m in matches:
        week = m["week"]
        player_a = m["player_a"]
        player_b = m.get("player_b")
        games_a = m["games_a"]
        games_b = m["games_b"]

        players_in_week[week].add(player_a)

        # Bye
        if player_b is None or player_b == "-" or player_b == "":
            # match loss (if DQ'd)
            if games_a == 0 and games_b == 0:
                weekly_points[week][player_a] += 0
                player_stats[player_a]["l"] += 1
                continue
            
            weekly_points[week][player_a] += 3
            # Byes: count as win with games for scoring
            player_stats[player_a]["w"] += 1
            player_stats[player_a]["gw"] += games_a
            player_stats[player_a]["gl"] += games_b
            continue

        players_in_week[week].add(player_b)

        # Ensure player_b is in player list
        if player_b not in player_stats:
            player_stats[player_b] = {"w": 0, "l": 0, "d": 0, "gw": 0, "gl": 0}

        # Record game wins/losses
        player_stats[player_a]["gw"] += games_a
        player_stats[player_a]["gl"] += games_b
        player_stats[player_b]["gw"] += games_b
        player_stats[player_b]["gl"] += games_a

        if games_a > games_b:
            # Player A wins
            weekly_points[week][player_a] += 3
            weekly_points[week][player_b] += 0
            player_stats[player_a]["w"] += 1
            player_stats[player_b]["l"] += 1
        elif games_b > games_a:
            # Player B wins
            weekly_points[week][player_b] += 3
            weekly_points[week][player_a] += 0
            player_stats[player_b]["w"] += 1
            player_stats[player_a]["l"] += 1
        else:
            # Draw
            weekly_points[week][player_a] += 1
            weekly_points[week][player_b] += 1
            player_stats[player_a]["d"] += 1
            player_stats[player_b]["d"] += 1

    # Build weekly scores list for each player (None if didn't play that week)
    weekly_scores = {}
    for p in players:
        scores = []
        for w in range(1, weeks_completed + 1):
            if p in players_in_week[w]:
                score = min(weekly_points[w].get(p, 0), MAX_WEEKLY_POINTS)
                scores.append(score)
            else:
                scores.append(None)
        weekly_scores[p] = scores

    # ============================================================
    # OMW Calculation
    # ============================================================
    # Per-week records and opponents (excluding byes)
    per_week_records = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0, "d": 0}))
    per_week_opponents = defaultdict(lambda: defaultdict(list))

    for m in matches:
        week = m["week"]
        pa = m["player_a"]
        pb = m.get("player_b")
        ga, gb = m["games_a"], m["games_b"]

        if pb is None or pb == "-" or pb == "":
            # Bye counts as a win in record but no opponent for OMW
            per_week_records[week][pa]["w"] += 1
            continue

        per_week_opponents[week][pa].append(pb)
        per_week_opponents[week][pb].append(pa)

        if ga > gb:
            per_week_records[week][pa]["w"] += 1
            per_week_records[week][pb]["l"] += 1
        elif gb > ga:
            per_week_records[week][pb]["w"] += 1
            per_week_records[week][pa]["l"] += 1
        else:
            per_week_records[week][pa]["d"] += 1
            per_week_records[week][pb]["d"] += 1

    # Per-week MWP (floored at 1/3) and OMW
    per_week_mwp = {}  # {week: {player: float}}
    per_week_omw = {}  # {week: {player: float}}

    for w in range(1, weeks_completed + 1):
        per_week_mwp[w] = {}
        for p in per_week_records[w]:
            r = per_week_records[w][p]
            total = r["w"] + r["l"] + r["d"]
            if total > 0:
                raw = (r["w"] * 3 + r["d"] * 1) / (total * 3)
                per_week_mwp[w][p] = max(raw, 1/3)
            else:
                per_week_mwp[w][p] = 1/3

        per_week_omw[w] = {}
        for p in per_week_records[w]:
            opps = per_week_opponents[w][p]
            if opps:
                per_week_omw[w][p] = sum(per_week_mwp[w].get(o, 1/3) for o in opps) / len(opps)
            else:
                per_week_omw[w][p] = 0

    # Overall OMW = average of per-week OMWs
    overall_omw = {}
    for p in players:
        weekly_omws = []
        for w in range(1, weeks_completed + 1):
            if p in per_week_omw[w]:
                weekly_omws.append(per_week_omw[w][p])
        overall_omw[p] = sum(weekly_omws) / len(weekly_omws) if weekly_omws else 0

    # Compute overall stats with derived fields
    overall_stats = {}
    for p in players:
        s = player_stats[p]
        total_games = s["gw"] + s["gl"]
        gwp = s["gw"] / total_games if total_games > 0 else 0.5
        mp = s["w"] * 3 + s["d"] * 1
        overall_stats[p] = {
            "mp": mp,
            "w": s["w"],
            "l": s["l"],
            "d": s["d"],
            "gw": s["gw"],
            "gl": s["gl"],
            "gwp": round(gwp, 3),
            "omw": round(overall_omw[p], 4),
        }

    # Attendance modeling (recency-weighted)
    # - High commitment (100%): 4+ weeks played total — clearly a regular
    # - Likely returning (85%): played the most recent week, <4 total
    # - Moderate (50%): played within last 2 weeks, <4 total, not most recent
    # - Unlikely (20%): haven't played in 3+ weeks and low total
    attendance_prob = {}
    for p in players:
        weeks_played = sum(1 for s in weekly_scores[p] if s is not None)
        # Find most recent week played (1-indexed)
        last_played = 0
        for w_idx in range(len(weekly_scores[p]) - 1, -1, -1):
            if weekly_scores[p][w_idx] is not None:
                last_played = w_idx + 1  # convert to 1-indexed week number
                break
        weeks_since_last = weeks_completed - last_played

        if weeks_played >= 4:
            attendance_prob[p] = 1.0
        elif weeks_since_last == 0:  # played most recent week
            attendance_prob[p] = 0.85
        elif weeks_since_last <= 1:  # played within last 2 weeks
            attendance_prob[p] = 0.50
        else:  # haven't played in 3+ weeks
            attendance_prob[p] = 0.20

    # Load playoff data if present
    playoffs = data.get("playoffs", None)

    return {
        "config": config,
        "players": players,
        "unofficial_players": data.get("unofficial_players", []),
        "weekly_scores": weekly_scores,
        "overall_stats": overall_stats,
        "attendance_prob": attendance_prob,
        "weeks_completed": weeks_completed,
        "total_weeks": total_weeks,
        "rounds_per_week": rounds_per_week,
        "best_of_n": best_of_n,
        "playoff_spots": playoff_spots,
        "num_simulations": num_simulations,
        "matches": matches,
        "per_week_records": dict(per_week_records),
        "per_week_opponents": dict(per_week_opponents),
        "per_week_mwp": per_week_mwp,
        "per_week_omw": per_week_omw,
        "overall_omw": overall_omw,
        "playoffs": playoffs,
    }


# ============================================================
# Player Strength Calculation
# ============================================================

def calculate_strength(stats: dict) -> float:
    """
    Calculate player strength based on match win percentage.
    Regress toward 50% for players with few matches to avoid overconfidence.
    Uses a Bayesian-style regression with virtual matches.
    """
    total_matches = stats["w"] + stats["l"] + stats["d"]
    wins = stats["w"] + stats["d"] * 0.5

    virtual_matches = 6
    virtual_wins = virtual_matches * 0.5

    regressed_winrate = (wins + virtual_wins) / (total_matches + virtual_matches)
    return regressed_winrate


def calculate_all_strengths(overall_stats: dict) -> dict:
    return {p: calculate_strength(s) for p, s in overall_stats.items()}


# ============================================================
# Scoring Helpers
# ============================================================

def ordinal(n: int) -> str:
    """Return ordinal string for an integer (1 -> '1st', 2 -> '2nd', etc.)."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd'][n % 10] if n % 10 < 4 else 'th'}"


def best_n_score(weekly_scores_list: list, n: int = 7) -> int:
    """Sum of the best n weekly scores. Unplayed weeks are excluded."""
    played = [s for s in weekly_scores_list if s is not None]
    played.sort(reverse=True)
    return sum(played[:n])


def total_match_points(weekly_scores_list: list) -> int:
    """Sum of all weekly scores."""
    return sum(s for s in weekly_scores_list if s is not None)


def max_possible_best7(existing_scores: list, weeks_completed: int, total_weeks: int, best_of_n: int) -> int:
    existing = [s for s in existing_scores if s is not None]
    remaining_weeks = total_weeks - weeks_completed
    all_scores = existing + [MAX_WEEKLY_POINTS] * remaining_weeks
    all_scores.sort(reverse=True)
    return sum(all_scores[:best_of_n])


def min_guaranteed_best7(existing_scores: list, best_of_n: int) -> int:
    existing = [s for s in existing_scores if s is not None]
    existing.sort(reverse=True)
    return sum(existing[:best_of_n])


# ============================================================
# Match Simulation
# ============================================================

def simulate_match(player_a: str, player_b: str, strengths: dict) -> tuple:
    """
    Simulate a best-of-3 match between two players.
    Returns (points_a, points_b): one of (3,0), (0,3), or (1,1) for draw.
    """
    str_a = strengths[player_a]
    str_b = strengths[player_b]

    if random.random() < GLOBAL_DRAW_RATE:
        return (1, 1)

    prob_a_wins = str_a / (str_a + str_b)
    if random.random() < prob_a_wins:
        return (3, 0)
    else:
        return (0, 3)


def simulate_week(active_players: list, strengths: dict, rounds_per_week: int) -> tuple:
    """
    Simulate one week of the league.
    Returns (points_dict, records_dict, opponents_dict) where:
    - points_dict: {player: weekly_points}
    - records_dict: {player: {"w": int, "l": int, "d": int}}
    - opponents_dict: {player: [opponent_names]} (excluding byes)
    """
    points = {p: 0 for p in active_players}
    records = {p: {"w": 0, "l": 0, "d": 0} for p in active_players}
    opponents = {p: [] for p in active_players}
    n = len(active_players)

    for round_num in range(rounds_per_week):
        shuffled = list(active_players)
        random.shuffle(shuffled)

        if n % 2 == 1:
            bye_player = shuffled[-1]
            points[bye_player] += 3
            records[bye_player]["w"] += 1
            shuffled = shuffled[:-1]

        for i in range(0, len(shuffled), 2):
            pa, pb = shuffled[i], shuffled[i + 1]
            pts_a, pts_b = simulate_match(pa, pb, strengths)
            points[pa] += pts_a
            points[pb] += pts_b
            opponents[pa].append(pb)
            opponents[pb].append(pa)

            if pts_a == 3:
                records[pa]["w"] += 1
                records[pb]["l"] += 1
            elif pts_b == 3:
                records[pb]["w"] += 1
                records[pa]["l"] += 1
            else:  # draw (1,1)
                records[pa]["d"] += 1
                records[pb]["d"] += 1

    for p in points:
        points[p] = min(points[p], MAX_WEEKLY_POINTS)

    return points, records, opponents


# ============================================================
# Monte Carlo Simulation
# ============================================================

def compute_omw_for_sim(historical_omw_data: dict, sim_week_data: list, players: list) -> dict:
    """
    Compute overall OMW for a simulation run.
    historical_omw_data: {week_num: {player: omw_value}} for completed weeks
    sim_week_data: list of (records_dict, opponents_dict) for simulated weeks
    Returns {player: overall_omw}
    """
    player_weekly_omws = defaultdict(list)

    # Add historical weekly OMW values
    for w in sorted(historical_omw_data.keys()):
        for p, omw in historical_omw_data[w].items():
            player_weekly_omws[p].append(omw)

    # Compute OMW for each simulated week
    for records, opponents in sim_week_data:
        # Compute MWP for each player this week (floored at 1/3)
        week_mwp = {}
        for p in records:
            r = records[p]
            total = r["w"] + r["l"] + r["d"]
            if total > 0:
                raw = (r["w"] * 3 + r["d"] * 1) / (total * 3)
                week_mwp[p] = max(raw, 1/3)
            else:
                week_mwp[p] = 1/3

        # Compute OMW for each player this week
        for p in records:
            opps = opponents.get(p, [])
            if opps:
                omw = sum(week_mwp.get(o, 1/3) for o in opps) / len(opps)
            else:
                omw = 0
            player_weekly_omws[p].append(omw)

    # Overall OMW = average of all weekly OMWs
    result = {}
    for p in players:
        omws = player_weekly_omws[p]
        result[p] = sum(omws) / len(omws) if omws else 0

    return result


def run_simulation(league: dict) -> dict:
    """
    Run the full Monte Carlo simulation.
    Returns results per player.
    """
    players = league["players"]
    weekly_scores = league["weekly_scores"]
    overall_stats = league["overall_stats"]
    attendance_prob = league["attendance_prob"]
    weeks_completed = league["weeks_completed"]
    total_weeks = league["total_weeks"]
    rounds_per_week = league["rounds_per_week"]
    best_of_n = league["best_of_n"]
    playoff_spots = league["playoff_spots"]
    num_simulations = league["num_simulations"]
    historical_omw = league["per_week_omw"]  # {week: {player: omw}}

    strengths = calculate_all_strengths(overall_stats)
    remaining_weeks = total_weeks - weeks_completed

    playoff_counts = defaultdict(int)
    position_counts = defaultdict(lambda: defaultdict(int))

    for sim in range(num_simulations):
        sim_scores = {p: list(weekly_scores[p]) for p in players}
        sim_week_data = []  # [(records, opponents), ...] for simulated weeks

        for week in range(remaining_weeks):
            active = [p for p in players if random.random() < attendance_prob[p]]

            if len(active) < 2:
                for p in players:
                    sim_scores[p].append(None)
                continue

            week_points, week_records, week_opponents = simulate_week(active, strengths, rounds_per_week)
            sim_week_data.append((week_records, week_opponents))

            for p in players:
                if p in week_points:
                    sim_scores[p].append(week_points[p])
                else:
                    sim_scores[p].append(None)

        # Compute OMW for tiebreaking
        sim_omw = compute_omw_for_sim(historical_omw, sim_week_data, players)

        standings = []
        for p in players:
            b7 = best_n_score(sim_scores[p], best_of_n)
            tmp = total_match_points(sim_scores[p])
            omw = sim_omw[p]
            gwp = overall_stats[p]["gwp"]
            standings.append((p, b7, tmp, omw, gwp))

        # Tiebreaker: best-7 desc, total MP desc, OMW desc, GWP desc
        standings.sort(key=lambda x: (x[1], x[2], x[3], x[4]), reverse=True)

        for i, (p, b7, tmp, omw, gwp) in enumerate(standings):
            pos = i + 1
            position_counts[p][pos] += 1
            if pos <= playoff_spots:
                playoff_counts[p] += 1

    results = {}
    for p in players:
        results[p] = {
            "playoff_prob": playoff_counts[p] / num_simulations * 100,
            "playoff_count": playoff_counts[p],
            "positions": dict(position_counts[p]),
            "current_best7": best_n_score(weekly_scores[p], best_of_n),
            "max_possible_best7": max_possible_best7(weekly_scores[p], weeks_completed, total_weeks, best_of_n),
            "min_guaranteed_best7": min_guaranteed_best7(weekly_scores[p], best_of_n),
            "total_match_pts": total_match_points(weekly_scores[p]),
            "weeks_played": sum(1 for s in weekly_scores[p] if s is not None),
        }

    return results


# ============================================================
# Mathematical Elimination/Clinch Check
# ============================================================

def check_elimination_clinch(results: dict, players: list, playoff_spots: int) -> dict:
    max_scores = {p: results[p]["max_possible_best7"] for p in players}
    min_scores = {p: results[p]["min_guaranteed_best7"] for p in players}

    status = {}
    for p in players:
        other_mins = sorted([min_scores[q] for q in players if q != p], reverse=True)
        if len(other_mins) >= playoff_spots and max_scores[p] < other_mins[playoff_spots - 1]:
            status[p] = {"status": "eliminated"}
        else:
            status[p] = {"status": "alive"}

        other_maxes = sorted([max_scores[q] for q in players if q != p], reverse=True)
        if len(other_maxes) >= playoff_spots and min_scores[p] > other_maxes[playoff_spots - 1]:
            status[p] = {"status": "clinched"}

    return status


# ============================================================
# Insight Generation
# ============================================================

def generate_insights(results: dict, status: dict, players: list, playoff_spots: int,
                      weeks_completed: int, total_weeks: int, overall_omw: dict = None,
                      weekly_scores: dict = None, overall_stats: dict = None,
                      unofficial_players: set = None, best_of_n: int = 7,
                      matches: list = None) -> list:
    """Generate key insight cards for the league. Returns list of dicts with title/player/value/detail."""
    insights = []
    if not weekly_scores or not overall_stats:
        return insights

    unofficial = unofficial_players or set()
    official_players = [p for p in players if p not in unofficial]

    omw = overall_omw or {}
    ranked = sorted(official_players, key=lambda p: (
        results[p]["current_best7"], results[p]["total_match_pts"], omw.get(p, 0)
    ), reverse=True)

    # Best win rate
    best_wr_player = None
    best_wr = 0
    for p in official_players:
        s = overall_stats[p]
        total = s["w"] + s["l"] + s["d"]
        if total >= 3:  # minimum sample
            wr = (s["w"] + s["d"] * 0.5) / total if total else 0
            if wr > best_wr:
                best_wr = wr
                best_wr_player = p
    if best_wr_player:
        s = overall_stats[best_wr_player]
        insights.append({
            "title": "Highest Win Rate",
            "player": best_wr_player,
            "value": f"{best_wr*100:.0f}%",
            "detail": f"{s['w']}-{s['l']}-{s['d']} record"
        })

    # Most 9-point nights
    nine_counts = {}
    for p in official_players:
        nines = sum(1 for s in weekly_scores.get(p, []) if s == 9)
        if nines > 0:
            nine_counts[p] = nines
    if nine_counts:
        top_nine = max(nine_counts, key=nine_counts.get)
        insights.append({
            "title": "Most Perfect Nights",
            "player": top_nine,
            "value": str(nine_counts[top_nine]),
            "detail": "Undefeated 9-point weeks"
        })

    # Best attendance
    attend_counts = {}
    for p in official_players:
        attend_counts[p] = sum(1 for s in weekly_scores.get(p, []) if s is not None)
    if attend_counts:
        best_attend = max(attend_counts, key=attend_counts.get)
        insights.append({
            "title": "Iron Player",
            "player": best_attend,
            "value": f"{attend_counts[best_attend]}/{weeks_completed}",
            "detail": "Weeks attended"
        })

    # Worst to First (biggest climb from worst rank at any point to final rank)
    if weeks_completed >= 4:
        final_rank = {p: i+1 for i, p in enumerate(ranked)}
        worst_rank = {p: 1 for p in official_players}
        for w in range(1, weeks_completed + 1):
            week_ranked = sorted(official_players, key=lambda p: (
                best_n_score(weekly_scores[p][:w], min(w, best_of_n)),
            ), reverse=True)
            for i, p in enumerate(week_ranked):
                worst_rank[p] = max(worst_rank[p], i + 1)
        best_climb = 0
        climber = None
        worst_at = 0
        for p in official_players:
            climb = worst_rank[p] - final_rank[p]
            if climb > best_climb:
                best_climb = climb
                climber = p
                worst_at = worst_rank[p]
        if climber and best_climb > 1:
            insights.append({
                "title": "Worst to First",
                "player": climber,
                "value": f"+{best_climb}",
                "detail": f"Ranked {worst_at}{('th' if worst_at > 3 else ['st','nd','rd'][worst_at-1])} at worst → finished {final_rank[climber]}{('th' if final_rank[climber] > 3 else ['st','nd','rd'][final_rank[climber]-1])}"
            })

    # Highest single week score
    best_week_score = 0
    best_week_player = None
    for p in official_players:
        for s in weekly_scores.get(p, []):
            if s is not None and s > best_week_score:
                best_week_score = s
                best_week_player = p
    # Only show if it's interesting (9 points)
    if best_week_player and best_week_score == 9:
        # Count how many got 9
        nine_players = [p for p in official_players if 9 in [s for s in weekly_scores.get(p, []) if s is not None]]
        if len(nine_players) <= 3:
            insights.append({
                "title": "Undefeated Club",
                "player": ", ".join(nine_players),
                "value": "9 pts",
                "detail": "Achieved a perfect night"
            })

    # Most "almost there" nights: won rounds 1 and 2, then lost round 3,
    # while never having recorded a perfect 3-0 week in this league.
    if matches:
        weekly_nines = {p for p in official_players if 9 in [s for s in weekly_scores.get(p, []) if s is not None]}
        round_results = defaultdict(dict)  # player -> {week: {round: 'W'/'L'/'D'}}

        for m in matches:
            week = m["week"]
            round_num = m["round"]
            pa = m["player_a"]
            pb = m.get("player_b")
            ga = m["games_a"]
            gb = m["games_b"]

            if pb is None or pb == "-" or pb == "":
                result_a = "L" if ga == 0 and gb == 0 else "W"
                if pa in official_players:
                    round_results[pa].setdefault(week, {})[round_num] = result_a
                continue

            if ga > gb:
                result_a, result_b = "W", "L"
            elif gb > ga:
                result_a, result_b = "L", "W"
            else:
                result_a = result_b = "D"

            if pa in official_players:
                round_results[pa].setdefault(week, {})[round_num] = result_a
            if pb in official_players:
                round_results[pb].setdefault(week, {})[round_num] = result_b

        almost_there_counts = {}
        for p in official_players:
            if p in weekly_nines:
                continue
            count = 0
            for week_map in round_results[p].values():
                if week_map.get(1) == "W" and week_map.get(2) == "W" and week_map.get(3) == "L":
                    count += 1
            if count > 0:
                almost_there_counts[p] = count

        if almost_there_counts:
            top_count = max(almost_there_counts.values())
            leaders = sorted([p for p, count in almost_there_counts.items() if count == top_count])
            insights.append({
                "title": "Almost There",
                "player": ", ".join(leaders),
                "value": str(top_count),
                "detail": "Started 2-0, then lost Round 3"
            })

    return insights


# ============================================================
# Playoff Bracket Helpers
# ============================================================

def get_playoff_seedings(standings_order: list, playoff_spots: int) -> list:
    """Return the top N players from standings as seeds."""
    return standings_order[:playoff_spots]


def initialize_playoffs(seeds: list) -> dict:
    """Create initial playoff structure from seeds. Seed 1 vs 4, Seed 2 vs 3."""
    return {
        "semifinal_1": {"player_a": seeds[0], "player_b": seeds[3], "games_a": None, "games_b": None},
        "semifinal_2": {"player_a": seeds[1], "player_b": seeds[2], "games_a": None, "games_b": None},
        "final": {"player_a": None, "player_b": None, "games_a": None, "games_b": None},
        "third_place": {"player_a": None, "player_b": None, "games_a": None, "games_b": None},
    }


def get_match_winner_loser(match: dict):
    """Return (winner, loser) for a completed match, or (None, None)."""
    if match["games_a"] is None or match["games_b"] is None:
        return None, None
    if match["games_a"] > match["games_b"]:
        return match["player_a"], match["player_b"]
    elif match["games_b"] > match["games_a"]:
        return match["player_b"], match["player_a"]
    else:
        # Draw - treat player_a as winner (higher seed advantage)
        return match["player_a"], match["player_b"]


def are_playoffs_complete(playoffs: dict) -> bool:
    """Check if all 4 playoff matches have results."""
    for key in ["semifinal_1", "semifinal_2", "final", "third_place"]:
        m = playoffs.get(key, {})
        if m.get("games_a") is None or m.get("games_b") is None:
            return False
    return True


def generate_bracket_html(playoffs: dict, seeds: list, is_projected: bool, weeks_completed: int, results: dict, overall_stats: dict, best_of_n: int, overall_omw: dict, server_mode: bool) -> str:
    """Generate the playoff bracket HTML section."""

    title = "Playoff Bracket (Projected)" if is_projected else "Playoff Bracket"
    projected_class = "bracket-projected" if is_projected else ""

    # Extract match data
    sf1 = playoffs.get("semifinal_1", {})
    sf2 = playoffs.get("semifinal_2", {})
    final = playoffs.get("final", {})
    third = playoffs.get("third_place", {})

    def player_display(name, seed=None):
        if name is None:
            return "TBD"
        seed_str = f"[{seed}] " if seed else ""
        return f"{seed_str}{name}"

    def score_display(match):
        if match.get("games_a") is None or match.get("games_b") is None:
            return ""
        return f"{match['games_a']} - {match['games_b']}"

    def match_class(match, side):
        """Return CSS class for winner/loser highlighting."""
        if match.get("games_a") is None or match.get("games_b") is None:
            return ""
        if side == "a":
            if match["games_a"] > match["games_b"]:
                return "bracket-winner"
            elif match["games_a"] < match["games_b"]:
                return "bracket-loser"
        else:
            if match["games_b"] > match["games_a"]:
                return "bracket-winner"
            elif match["games_b"] < match["games_a"]:
                return "bracket-loser"
        return ""  # draw

    # Determine seed numbers
    seed_map = {}
    for i, s in enumerate(seeds):
        seed_map[s] = i + 1

    def get_seed(name):
        return seed_map.get(name)

    # Winners/losers for advancing
    sf1_winner, sf1_loser = get_match_winner_loser(sf1)
    sf2_winner, sf2_loser = get_match_winner_loser(sf2)
    final_winner, final_loser = get_match_winner_loser(final)
    third_winner, third_loser = get_match_winner_loser(third)

    playoffs_complete = are_playoffs_complete(playoffs)

    # Champion banner
    champion_html = ""
    if playoffs_complete and final_winner:
        # Check for regular season MVP
        # MVP = player with highest best-7 from regular season
        mvp = seeds[0]  # seed 1 has highest best-7 by definition

        champion_html = f"""
        <div class="champion-banner">
            <div class="champion-trophy">&#127942;</div>
            <div class="champion-name">{final_winner}</div>
            <div class="champion-label">LEAGUE CHAMPION</div>
        </div>"""

    # Awards section
    awards_html = ""
    if playoffs_complete and final_winner:
        mvp = seeds[0]
        if mvp == final_winner:
            awards_html = f"""
            <div class="awards-section">
                <div class="award-card award-champion">
                    <div class="award-icon">&#127942;</div>
                    <div class="award-title">League Champion</div>
                    <div class="award-player">{final_winner}</div>
                </div>
                <div class="award-card award-mvp">
                    <div class="award-icon">&#11088;</div>
                    <div class="award-title">Regular Season MVP</div>
                    <div class="award-player">{mvp}</div>
                </div>
                <div class="award-note">{final_winner} completed the double!</div>
            </div>"""
        else:
            awards_html = f"""
            <div class="awards-section">
                <div class="award-card award-champion">
                    <div class="award-icon">&#127942;</div>
                    <div class="award-title">League Champion</div>
                    <div class="award-player">{final_winner}</div>
                </div>
                <div class="award-card award-mvp">
                    <div class="award-icon">&#11088;</div>
                    <div class="award-title">Regular Season MVP</div>
                    <div class="award-player">{mvp}</div>
                </div>
            </div>"""

    # Build the bracket layout
    bracket_html = f"""
<div class="card {projected_class}">
    <h2>{title}</h2>
    {champion_html}
    <div class="bracket-container">
        <div class="bracket-round bracket-semis">
            <div class="bracket-round-title">Semifinals</div>
            <div class="bracket-match" id="sf1-match">
                <div class="bracket-match-label">SF1</div>
                <div class="bracket-slot {match_class(sf1, 'a')}">
                    <span class="bracket-seed">{get_seed(sf1.get('player_a')) or ''}</span>
                    <span class="bracket-name">{sf1.get('player_a') or 'TBD'}</span>
                    <span class="bracket-score">{sf1.get('games_a') if sf1.get('games_a') is not None else ''}</span>
                </div>
                <div class="bracket-slot {match_class(sf1, 'b')}">
                    <span class="bracket-seed">{get_seed(sf1.get('player_b')) or ''}</span>
                    <span class="bracket-name">{sf1.get('player_b') or 'TBD'}</span>
                    <span class="bracket-score">{sf1.get('games_b') if sf1.get('games_b') is not None else ''}</span>
                </div>
            </div>
            <div class="bracket-match" id="sf2-match">
                <div class="bracket-match-label">SF2</div>
                <div class="bracket-slot {match_class(sf2, 'a')}">
                    <span class="bracket-seed">{get_seed(sf2.get('player_a')) or ''}</span>
                    <span class="bracket-name">{sf2.get('player_a') or 'TBD'}</span>
                    <span class="bracket-score">{sf2.get('games_a') if sf2.get('games_a') is not None else ''}</span>
                </div>
                <div class="bracket-slot {match_class(sf2, 'b')}">
                    <span class="bracket-seed">{get_seed(sf2.get('player_b')) or ''}</span>
                    <span class="bracket-name">{sf2.get('player_b') or 'TBD'}</span>
                    <span class="bracket-score">{sf2.get('games_b') if sf2.get('games_b') is not None else ''}</span>
                </div>
            </div>
        </div>

        <div class="bracket-connector-col">
            <div class="bracket-connector-top"></div>
            <div class="bracket-connector-bottom"></div>
        </div>

        <div class="bracket-round bracket-final">
            <div class="bracket-round-title">Final</div>
            <div class="bracket-match" id="final-match">
                <div class="bracket-match-label">Final</div>
                <div class="bracket-slot {match_class(final, 'a')}">
                    <span class="bracket-seed">{get_seed(final.get('player_a')) or ''}</span>
                    <span class="bracket-name">{final.get('player_a') or 'TBD'}</span>
                    <span class="bracket-score">{final.get('games_a') if final.get('games_a') is not None else ''}</span>
                </div>
                <div class="bracket-slot {match_class(final, 'b')}">
                    <span class="bracket-seed">{get_seed(final.get('player_b')) or ''}</span>
                    <span class="bracket-name">{final.get('player_b') or 'TBD'}</span>
                    <span class="bracket-score">{final.get('games_b') if final.get('games_b') is not None else ''}</span>
                </div>
            </div>
        </div>

        <div class="bracket-champion-col">
            <div class="bracket-champion-slot {'bracket-winner' if final_winner else ''}">
                {final_winner if final_winner else ''}
            </div>
        </div>
    </div>

    <div class="bracket-third-place">
        <div class="bracket-round-title">Third Place Match</div>
        <div class="bracket-match" id="third-match">
            <div class="bracket-slot {match_class(third, 'a')}">
                <span class="bracket-seed">{get_seed(third.get('player_a')) or ''}</span>
                <span class="bracket-name">{third.get('player_a') or 'TBD'}</span>
                <span class="bracket-score">{third.get('games_a') if third.get('games_a') is not None else ''}</span>
            </div>
            <div class="bracket-slot {match_class(third, 'b')}">
                <span class="bracket-seed">{get_seed(third.get('player_b')) or ''}</span>
                <span class="bracket-name">{third.get('player_b') or 'TBD'}</span>
                <span class="bracket-score">{third.get('games_b') if third.get('games_b') is not None else ''}</span>
            </div>
            <div class="bracket-result">
                {f'{third_winner} (3rd) / {third_loser} (4th)' if third_winner else ''}
            </div>
        </div>
    </div>

    {awards_html}
</div>
"""
    return bracket_html


# ============================================================
# HTML Dashboard Generation
# ============================================================

def generate_html(league: dict, results: dict, status: dict, insights: list, server_mode: bool = False, league_info: dict = None, skip_simulation: bool = False) -> str:
    """Generate the HTML dashboard."""
    players = league["players"]
    weekly_scores = league["weekly_scores"]
    overall_stats = league["overall_stats"]
    weeks_completed = league["weeks_completed"]
    total_weeks = league["total_weeks"]
    best_of_n = league["best_of_n"]
    playoff_spots = league["playoff_spots"]
    num_simulations = league["num_simulations"]
    matches = league["matches"]

    overall_omw = league.get("overall_omw", {})
    unofficial_players = set(league.get("unofficial_players", []))

    # League info for multi-league support
    is_completed = league_info and league_info.get("status") == "completed"
    league_name = league_info["name"] if league_info else "MTG League"
    league_display_name = league_info.get("display_name", "") if league_info else ""
    all_leagues = league_info.get("_all_leagues", []) if league_info else []
    current_league_id = league_info.get("id", "") if league_info else ""

    # ---- Chart data preparation ----
    # Only include players who've played 2+ weeks for chart readability
    chart_players = [p for p in players if sum(1 for s in weekly_scores[p] if s is not None) >= 2]
    # Sort by current best-7 descending so legend order matches standings
    chart_players.sort(key=lambda p: best_n_score(weekly_scores[p], best_of_n), reverse=True)

    # Distinct colours for up to 16 players
    chart_colors = [
        "#e94560", "#2ecc71", "#3498db", "#f1c40f", "#9b59b6",
        "#e67e22", "#1abc9c", "#e74c3c", "#00bcd4", "#ff9800",
        "#8bc34a", "#ff5722", "#607d8b", "#cddc39", "#795548", "#9e9e9e",
    ]

    # Build running best-7 data and weekly scores data
    chart_best7_data = {}    # {player: [running_best7, ...]}
    for p in chart_players:
        scores = weekly_scores[p]
        running_best7 = []
        for w_idx in range(weeks_completed):
            played_so_far = [s for s in scores[:w_idx+1] if s is not None]
            if played_so_far:
                played_so_far.sort(reverse=True)
                running_best7.append(sum(played_so_far[:best_of_n]))
            else:
                running_best7.append(None)
        chart_best7_data[p] = running_best7

    # Build Chart.js datasets JSON
    import json as _json
    week_labels = [f"Week {i+1}" for i in range(weeks_completed)]
    week_labels_json = _json.dumps(week_labels)

    best7_datasets = []
    for i, p in enumerate(chart_players):
        color = chart_colors[i % len(chart_colors)]
        best7_datasets.append({
            "label": p,
            "data": chart_best7_data[p],
            "borderColor": color,
            "backgroundColor": color,
            "tension": 0.3,
            "pointRadius": 5,
            "pointHoverRadius": 7,
            "borderWidth": 2.5,
            "spanGaps": True,
        })
    best7_datasets_json = _json.dumps(best7_datasets)

    standings_order = sorted(players, key=lambda p: (
        results[p]["current_best7"],
        results[p]["total_match_pts"],
        overall_omw.get(p, 0),
        overall_stats[p]["gwp"]
    ), reverse=True)

    prob_order = sorted(players, key=lambda p: (
        results[p]["playoff_prob"],
        results[p]["current_best7"]
    ), reverse=True)

    def weekly_cells(player: str) -> str:
        cells = ""
        scores = weekly_scores[player]
        for i in range(total_weeks):
            if i < len(scores) and scores[i] is not None:
                val = scores[i]
                if val == MAX_WEEKLY_POINTS:
                    cls = "score-max"
                elif val >= 6:
                    cls = "score-high"
                elif val >= 3:
                    cls = "score-mid"
                else:
                    cls = "score-low"
                cells += f'<td class="{cls}">{val}</td>'
            elif i < weeks_completed:
                cells += '<td class="score-absent">-</td>'
            else:
                cells += '<td class="score-future"></td>'
        return cells

    defending_champion = "Sami"

    standings_rows = ""
    has_unofficial = len(unofficial_players) > 0
    for rank, p in enumerate(standings_order, 1):
        is_unofficial = p in unofficial_players
        row_class = "unofficial" if is_unofficial else ("top4" if rank <= playoff_spots else "")
        b7 = results[p]["current_best7"]
        omw_val = overall_omw.get(p, 0)
        name_class = "player-name defending-champ" if p == defending_champion else "player-name"
        display_name = f"{p} *" if is_unofficial else p
        standings_rows += f"""
        <tr class="{row_class}">
            <td class="rank">{rank}</td>
            <td class="{name_class}">{display_name}</td>
            {weekly_cells(p)}
            <td class="best7">{b7}</td>
            <td class="total-pts">{results[p]['total_match_pts']}</td>
            <td class="omw-col">{omw_val*100:.1f}%</td>
        </tr>"""

    prob_cards = ""
    for p in prob_order:
        prob = results[p]["playoff_prob"]
        curr = results[p]["current_best7"]
        max_p = results[p]["max_possible_best7"]
        stat = status[p]["status"]

        if prob >= 75:
            bar_color = "#2ecc71"
        elif prob >= 50:
            bar_color = "#f1c40f"
        elif prob >= 25:
            bar_color = "#e67e22"
        else:
            bar_color = "#e74c3c"

        badge = ""
        if stat == "clinched":
            badge = '<span class="badge clinched">CLINCHED</span>'
        elif stat == "eliminated":
            badge = '<span class="badge eliminated">ELIMINATED</span>'
        elif prob == 0:
            badge = '<span class="badge eliminated">ELIMINATED</span>'
        elif prob >= 99.9:
            badge = '<span class="badge clinched">CLINCHED</span>'

        stats_info = overall_stats[p]
        record = f"{stats_info['w']}-{stats_info['l']}-{stats_info['d']}"
        omw_display = overall_omw.get(p, 0)

        prob_cards += f"""
        <div class="prob-card">
            <div class="prob-header">
                <span class="prob-player">{p}</span>
                <span class="prob-pct">{prob:.1f}%</span>
                {badge}
            </div>
            <div class="prob-bar-bg">
                <div class="prob-bar" style="width: {max(prob, 0.5)}%; background: {bar_color};"></div>
            </div>
            <div class="prob-details">
                <span>Record: {record}</span>
                <span>Best 7: {curr}</span>
                <span>Max Possible: {max_p}</span>
                <span>OMW%: {omw_display*100:.1f}%</span>
                <span>GW%: {stats_info['gwp']*100:.1f}%</span>
            </div>
        </div>"""

    # Generate playoff bracket section (only if league has playoffs)
    playoffs = league.get("playoffs")
    bracket_section = ""
    is_projected = weeks_completed < total_weeks
    if playoff_spots >= 4:
        is_projected = weeks_completed < total_weeks
        if is_projected:
            seeds = standings_order[:playoff_spots]
            projected_playoffs = initialize_playoffs(seeds)
            bracket_section = generate_bracket_html(
                projected_playoffs, seeds, True, weeks_completed, results,
                overall_stats, best_of_n, overall_omw, server_mode
            )
        else:
            seeds = standings_order[:playoff_spots]
            if playoffs is None:
                playoffs = initialize_playoffs(seeds)
            bracket_section = generate_bracket_html(
                playoffs, seeds, False, weeks_completed, results,
                overall_stats, best_of_n, overall_omw, server_mode
            )

    insights_html = ""
    if insights:
        cards = ""
        for ins in insights:
            if isinstance(ins, dict):
                cards += f"""<div class="insight-card">
                    <div class="insight-title">{ins['title']}</div>
                    <div class="insight-player">{ins['player']}</div>
                    <div class="insight-value">{ins['value']}</div>
                    <div class="insight-detail">{ins['detail']}</div>
                </div>"""
            else:
                cards += f'<div class="insight-item">{ins}</div>\n'
        insights_html = f"""<div class="card">
            <h2>Key Insights</h2>
            <div class="insights-grid">{cards}</div>
        </div>"""

    week_headers = ""
    entered_weeks_set = set(m["week"] for m in matches)
    for i in range(1, total_weeks + 1):
        if i in entered_weeks_set:
            week_headers += f'<th class="week-header active clickable" onclick="toggleWeekDetail({i})" title="Click to view Week {i} details">W{i}</th>'
        elif i <= weeks_completed:
            week_headers += f'<th class="week-header active">W{i}</th>'
        else:
            week_headers += f'<th class="week-header future">W{i}</th>'

    # Build per-week detail panels (match results + standings)
    per_week_mwp = league.get("per_week_mwp", {})
    per_week_omw_data = league.get("per_week_omw", {})
    per_week_records = league.get("per_week_records", {})

    # Build player rank lookup for sorting match display order
    player_rank = {}
    for rank, p in enumerate(standings_order):
        player_rank[p] = rank

    week_detail_panels = ""
    for w in sorted(entered_weeks_set):
        week_matches = [m for m in matches if m["week"] == w]
        rounds_grouped = defaultdict(list)
        for m in week_matches:
            rounds_grouped[m["round"]].append(m)

        rounds_html = ""
        for r in sorted(rounds_grouped.keys()):
            rows = ""
            # Sort matchups: byes at bottom, then by best-ranked player (lowest rank = highest standing)
            round_matches = sorted(rounds_grouped[r], key=lambda m: (
                1 if m.get("player_b") is None else 0,
                min(player_rank.get(m["player_a"], 999),
                    player_rank.get(m.get("player_b") or "", 999))
            ))
            for m in round_matches:
                pa = m["player_a"]
                pb = m.get("player_b")
                ga, gb = m["games_a"], m["games_b"]
                if pb is None:
                    # Bye — winner on left
                    left, right = pa, "BYE"
                    score_display = f"{ga} - {gb}"
                    result_class = "result-win"
                elif ga > gb:
                    # Player A won — already on left
                    left, right = pa, pb
                    score_display = f"{ga} - {gb}"
                    result_class = "result-win"
                elif gb > ga:
                    # Player B won — swap so winner is on left
                    left, right = pb, pa
                    score_display = f"{gb} - {ga}"
                    result_class = "result-win"
                else:
                    # Draw — keep original order
                    left, right = pa, pb
                    score_display = f"{ga} - {gb}"
                    result_class = "result-draw"
                rows += f"""<tr>
                    <td class="wd-player">{left}</td>
                    <td class="wd-score {result_class}">{score_display}</td>
                    <td class="wd-player">{right}</td>
                </tr>"""
            rounds_html += f"""<div class="wd-round">
                <h4>Round {r}</h4>
                <table class="wd-table">{rows}</table>
            </div>"""

        # Weekly standings for this week
        week_players = set()
        week_records_local = defaultdict(lambda: {"w": 0, "l": 0, "d": 0, "pts": 0})
        for m in week_matches:
            pa = m["player_a"]
            pb = m.get("player_b")
            ga, gb = m["games_a"], m["games_b"]
            week_players.add(pa)
            if pb is None:
                week_records_local[pa]["w"] += 1
                week_records_local[pa]["pts"] += 3
            else:
                week_players.add(pb)
                if ga > gb:
                    week_records_local[pa]["w"] += 1
                    week_records_local[pa]["pts"] += 3
                    week_records_local[pb]["l"] += 1
                elif gb > ga:
                    week_records_local[pb]["w"] += 1
                    week_records_local[pb]["pts"] += 3
                    week_records_local[pa]["l"] += 1
                else:
                    week_records_local[pa]["d"] += 1
                    week_records_local[pa]["pts"] += 1
                    week_records_local[pb]["d"] += 1
                    week_records_local[pb]["pts"] += 1

        standings_list = sorted(week_players, key=lambda p: (
            week_records_local[p]["pts"],
            per_week_omw_data.get(w, {}).get(p, 0)
        ), reverse=True)

        standings_rows_wd = ""
        week_omw_lookup = per_week_omw_data.get(w, {})
        for pos, p in enumerate(standings_list, 1):
            rec = week_records_local[p]
            omw_w = week_omw_lookup.get(p, 0)
            standings_rows_wd += f"""<tr>
                <td class="wd-pos">{pos}</td>
                <td class="wd-player">{p}</td>
                <td>{rec['w']}-{rec['l']}-{rec['d']}</td>
                <td class="wd-pts">{rec['pts']}</td>
                <td>{omw_w*100:.1f}%</td>
            </tr>"""

        delete_btn = f'<button class="btn-delete-week" onclick="deleteWeek({w})" style="margin-top:12px;">Delete Week {w} Data</button>' if server_mode else ''

        week_detail_panels += f"""
        <div id="weekDetail-{w}" class="week-detail-panel" style="display:none;">
            <div class="card" style="margin-top:0;">
                <div class="wd-header">
                    <h2>Week {w} Results</h2>
                    <button class="modal-close" onclick="toggleWeekDetail({w})">&times;</button>
                </div>
                <div class="wd-content">
                    <div class="wd-rounds">{rounds_html}</div>
                    <div class="wd-standings">
                        <h4>Standings</h4>
                        <table class="wd-table wd-standings-table">
                            <thead><tr>
                                <th>#</th><th>Player</th><th>Record</th><th>Pts</th><th>OMW%</th>
                            </tr></thead>
                            <tbody>{standings_rows_wd}</tbody>
                        </table>
                    </div>
                </div>
                {delete_btn}
            </div>
        </div>"""

    # Players JSON for the form
    players_json = json.dumps(players)

    # Compute playoff JSON data for JS
    playoffs_for_js = playoffs if not is_projected and playoffs else None
    sf1_pa_js = ""
    sf1_pb_js = ""
    sf2_pa_js = ""
    sf2_pb_js = ""
    if playoffs_for_js:
        sf1_pa_js = playoffs_for_js.get("semifinal_1", {}).get("player_a", "") or ""
        sf1_pb_js = playoffs_for_js.get("semifinal_1", {}).get("player_b", "") or ""
        sf2_pa_js = playoffs_for_js.get("semifinal_2", {}).get("player_a", "") or ""
        sf2_pb_js = playoffs_for_js.get("semifinal_2", {}).get("player_b", "") or ""

    # Server-mode UI additions (data entry modal + scripts)
    server_ui = ""
    if server_mode:
        if weeks_completed >= total_weeks:
            # Playoff data entry mode
            playoff_btn_label = "Enter Playoff Results"
            playoff_modal_title = "Enter Playoff Results"
        else:
            playoff_btn_label = ""
            playoff_modal_title = ""

        # Determine which button to show
        if weeks_completed >= total_weeks:
            action_button = f"""
<!-- Enter Playoff Results Button -->
<div style="text-align: center; margin-bottom: 24px;">
    <button id="btnAddWeek" class="btn-primary" onclick="openPlayoffModal()">Enter Playoff Results</button>
</div>"""
        else:
            action_button = f"""
<!-- Add Week Results Button -->
<div style="text-align: center; margin-bottom: 24px;">
    <button id="btnAddWeek" class="btn-primary" onclick="openModal()">Add Week Results</button>
</div>"""

        # Playoff modal (only when weeks_completed >= total_weeks)
        playoff_modal = ""
        if weeks_completed >= total_weeks:
            playoff_modal = f"""
<!-- Playoff Modal Overlay -->
<div id="playoffModalOverlay" class="modal-overlay" style="display:none;" onclick="if(event.target===this)closePlayoffModal()">
<div class="modal-content">
    <div class="modal-header">
        <h2>Enter Playoff Results</h2>
        <button class="modal-close" onclick="closePlayoffModal()">&times;</button>
    </div>
    <div class="modal-body">
        <div class="round-section">
            <h3>Semifinal 1: {sf1_pa_js} vs {sf1_pb_js}</h3>
            <div class="matchup-row">
                <span class="bracket-name" style="min-width:100px;color:#e0e0e0;font-weight:600;">{sf1_pa_js}</span>
                <select class="games-select" id="sf1-ga">
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="dash-label">-</span>
                <select class="games-select" id="sf1-gb">
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="bracket-name" style="min-width:100px;color:#e0e0e0;font-weight:600;">{sf1_pb_js}</span>
            </div>
        </div>
        <div class="round-section">
            <h3>Semifinal 2: {sf2_pa_js} vs {sf2_pb_js}</h3>
            <div class="matchup-row">
                <span class="bracket-name" style="min-width:100px;color:#e0e0e0;font-weight:600;">{sf2_pa_js}</span>
                <select class="games-select" id="sf2-ga">
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="dash-label">-</span>
                <select class="games-select" id="sf2-gb">
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="bracket-name" style="min-width:100px;color:#e0e0e0;font-weight:600;">{sf2_pb_js}</span>
            </div>
        </div>
        <div class="round-section" id="finalSection">
            <h3>Final: <span id="finalPlayersLabel">TBD vs TBD</span></h3>
            <div class="matchup-row">
                <span class="bracket-name" id="finalPlayerALabel" style="min-width:100px;color:#e0e0e0;font-weight:600;">TBD</span>
                <select class="games-select" id="final-ga" disabled>
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="dash-label">-</span>
                <select class="games-select" id="final-gb" disabled>
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="bracket-name" id="finalPlayerBLabel" style="min-width:100px;color:#e0e0e0;font-weight:600;">TBD</span>
            </div>
        </div>
        <div class="round-section" id="thirdSection">
            <h3>Third Place: <span id="thirdPlayersLabel">TBD vs TBD</span></h3>
            <div class="matchup-row">
                <span class="bracket-name" id="thirdPlayerALabel" style="min-width:100px;color:#e0e0e0;font-weight:600;">TBD</span>
                <select class="games-select" id="third-ga" disabled>
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="dash-label">-</span>
                <select class="games-select" id="third-gb" disabled>
                    <option value="">-</option><option value="0">0</option><option value="1">1</option><option value="2">2</option>
                </select>
                <span class="bracket-name" id="thirdPlayerBLabel" style="min-width:100px;color:#e0e0e0;font-weight:600;">TBD</span>
            </div>
        </div>

        <div id="playoffValidationErrors" class="validation-errors" style="display:none;"></div>

        <div class="modal-actions">
            <button class="btn-secondary" onclick="closePlayoffModal()">Cancel</button>
            <button class="btn-primary" id="btnPlayoffSubmit" onclick="submitPlayoffResults()">Submit Playoff Results</button>
        </div>
    </div>
</div>
</div>

<script>
const SF1_PA = '{sf1_pa_js}';
const SF1_PB = '{sf1_pb_js}';
const SF2_PA = '{sf2_pa_js}';
const SF2_PB = '{sf2_pb_js}';

function getWinnerLoser(ga, gb, pa, pb) {{
    if (ga === '' || gb === '') return [null, null];
    ga = parseInt(ga); gb = parseInt(gb);
    if (ga > gb) return [pa, pb];
    if (gb > ga) return [pb, pa];
    return [pa, pb]; // draw: higher seed wins
}}

function updatePlayoffAdvancement() {{
    const sf1ga = document.getElementById('sf1-ga').value;
    const sf1gb = document.getElementById('sf1-gb').value;
    const sf2ga = document.getElementById('sf2-ga').value;
    const sf2gb = document.getElementById('sf2-gb').value;

    const [sf1w, sf1l] = getWinnerLoser(sf1ga, sf1gb, SF1_PA, SF1_PB);
    const [sf2w, sf2l] = getWinnerLoser(sf2ga, sf2gb, SF2_PA, SF2_PB);

    // Update final
    if (sf1w && sf2w) {{
        document.getElementById('finalPlayersLabel').textContent = sf1w + ' vs ' + sf2w;
        document.getElementById('finalPlayerALabel').textContent = sf1w;
        document.getElementById('finalPlayerBLabel').textContent = sf2w;
        document.getElementById('final-ga').disabled = false;
        document.getElementById('final-gb').disabled = false;
    }} else {{
        document.getElementById('finalPlayersLabel').textContent = 'TBD vs TBD';
        document.getElementById('finalPlayerALabel').textContent = 'TBD';
        document.getElementById('finalPlayerBLabel').textContent = 'TBD';
        document.getElementById('final-ga').disabled = true;
        document.getElementById('final-gb').disabled = true;
        document.getElementById('final-ga').value = '';
        document.getElementById('final-gb').value = '';
    }}

    // Update third place
    if (sf1l && sf2l) {{
        document.getElementById('thirdPlayersLabel').textContent = sf1l + ' vs ' + sf2l;
        document.getElementById('thirdPlayerALabel').textContent = sf1l;
        document.getElementById('thirdPlayerBLabel').textContent = sf2l;
        document.getElementById('third-ga').disabled = false;
        document.getElementById('third-gb').disabled = false;
    }} else {{
        document.getElementById('thirdPlayersLabel').textContent = 'TBD vs TBD';
        document.getElementById('thirdPlayerALabel').textContent = 'TBD';
        document.getElementById('thirdPlayerBLabel').textContent = 'TBD';
        document.getElementById('third-ga').disabled = true;
        document.getElementById('third-gb').disabled = true;
        document.getElementById('third-ga').value = '';
        document.getElementById('third-gb').value = '';
    }}
}}

// Attach change listeners to semifinal selects
['sf1-ga', 'sf1-gb', 'sf2-ga', 'sf2-gb'].forEach(function(id) {{
    document.getElementById(id).addEventListener('change', updatePlayoffAdvancement);
}});

function openPlayoffModal() {{
    document.getElementById('playoffModalOverlay').style.display = 'flex';
}}

function closePlayoffModal() {{
    document.getElementById('playoffModalOverlay').style.display = 'none';
    document.getElementById('playoffValidationErrors').style.display = 'none';
}}

function submitPlayoffResults() {{
    const errDiv = document.getElementById('playoffValidationErrors');
    const errors = [];

    const sf1ga = document.getElementById('sf1-ga').value;
    const sf1gb = document.getElementById('sf1-gb').value;
    const sf2ga = document.getElementById('sf2-ga').value;
    const sf2gb = document.getElementById('sf2-gb').value;
    const finalga = document.getElementById('final-ga').value;
    const finalgb = document.getElementById('final-gb').value;
    const thirdga = document.getElementById('third-ga').value;
    const thirdgb = document.getElementById('third-gb').value;

    const data = {{}};

    // Collect semifinal data (required)
    if (sf1ga !== '' && sf1gb !== '') {{
        data.semifinal_1 = {{ games_a: parseInt(sf1ga), games_b: parseInt(sf1gb) }};
    }}
    if (sf2ga !== '' && sf2gb !== '') {{
        data.semifinal_2 = {{ games_a: parseInt(sf2ga), games_b: parseInt(sf2gb) }};
    }}
    if (finalga !== '' && finalgb !== '') {{
        data.final = {{ games_a: parseInt(finalga), games_b: parseInt(finalgb) }};
    }}
    if (thirdga !== '' && thirdgb !== '') {{
        data.third_place = {{ games_a: parseInt(thirdga), games_b: parseInt(thirdgb) }};
    }}

    // Validate: must have at least semifinals
    if (!data.semifinal_1 && !data.semifinal_2 && !data.final && !data.third_place) {{
        errors.push('Please enter at least one match result');
    }}

    // Validate: final/third require semis
    if (data.final && (!data.semifinal_1 || !data.semifinal_2)) {{
        errors.push('Both semifinals must be completed before entering the final');
    }}
    if (data.third_place && (!data.semifinal_1 || !data.semifinal_2)) {{
        errors.push('Both semifinals must be completed before entering the third place match');
    }}

    if (errors.length > 0) {{
        errDiv.style.display = 'block';
        errDiv.textContent = errors.join('\\n');
        return;
    }}

    errDiv.style.display = 'none';
    document.getElementById('btnPlayoffSubmit').disabled = true;
    document.getElementById('btnPlayoffSubmit').textContent = 'Submitting...';

    fetch(leagueApiUrl('/api/playoff-results'), {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data)
    }})
    .then(resp => resp.json())
    .then(result => {{
        if (result.error) {{
            errDiv.style.display = 'block';
            errDiv.textContent = result.error;
            document.getElementById('btnPlayoffSubmit').disabled = false;
            document.getElementById('btnPlayoffSubmit').textContent = 'Submit Playoff Results';
        }} else {{
            closePlayoffModal();
            document.getElementById('loadingOverlay').style.display = 'flex';
            window.location.reload();
        }}
    }})
    .catch(err => {{
        errDiv.style.display = 'block';
        errDiv.textContent = 'Network error: ' + err.message;
        document.getElementById('btnPlayoffSubmit').disabled = false;
        document.getElementById('btnPlayoffSubmit').textContent = 'Submit Playoff Results';
    }});
}}
</script>
"""

        server_ui = f"""
{action_button}

<!-- Modal Overlay -->
<div id="modalOverlay" class="modal-overlay" style="display:none;" onclick="if(event.target===this)closeModal()">
<div class="modal-content">
    <div class="modal-header">
        <h2>Add Week Results</h2>
        <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body">
        <div class="form-group">
            <label for="weekNumber">Week Number</label>
            <input type="number" id="weekNumber" min="1" max="{total_weeks}" value="{weeks_completed + 1}">
        </div>

        <div id="roundsContainer">
            <div class="round-section" id="round1">
                <h3>Round 1</h3>
                <div class="matchups" id="matchups-1"></div>
                <button class="btn-add-matchup" onclick="addMatchup(1)">+ Add Matchup</button>
            </div>
            <div class="round-section" id="round2">
                <h3>Round 2</h3>
                <div class="matchups" id="matchups-2"></div>
                <button class="btn-add-matchup" onclick="addMatchup(2)">+ Add Matchup</button>
            </div>
            <div class="round-section" id="round3">
                <h3>Round 3</h3>
                <div class="matchups" id="matchups-3"></div>
                <button class="btn-add-matchup" onclick="addMatchup(3)">+ Add Matchup</button>
            </div>
        </div>

        <div id="validationErrors" class="validation-errors" style="display:none;"></div>

        <div class="modal-actions">
            <button class="btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn-primary" id="btnSubmit" onclick="submitResults()">Submit Week Results</button>
        </div>
    </div>
</div>
</div>

<!-- Loading Overlay -->
<div id="loadingOverlay" class="loading-overlay" style="display:none;">
    <div class="loading-spinner">
        <div class="spinner"></div>
        <p>Running simulation...</p>
        <p style="font-size:0.8em;color:#888;">This may take a few seconds</p>
    </div>
</div>

<script>
const CURRENT_LEAGUE_ID = '{current_league_id}';
function leagueApiUrl(path) {{
    return path + (CURRENT_LEAGUE_ID ? '?league=' + encodeURIComponent(CURRENT_LEAGUE_ID) : '');
}}
const PLAYERS = {players_json};
let matchupCounter = 0;

function makePlayerOptions(selected, includebye) {{
    let opts = '<option value="">-- Select --</option>';
    PLAYERS.forEach(p => {{
        const sel = (p === selected) ? ' selected' : '';
        opts += '<option value="' + p + '"' + sel + '>' + p + '</option>';
    }});
    if (includebye) {{
        const sel = (selected === 'BYE') ? ' selected' : '';
        opts += '<option value="BYE"' + sel + '>BYE</option>';
    }}
    opts += '<option value="__NEW__">+ Add New Player</option>';
    return opts;
}}

function addMatchup(roundNum) {{
    matchupCounter++;
    const id = 'matchup-' + matchupCounter;
    const container = document.getElementById('matchups-' + roundNum);
    const div = document.createElement('div');
    div.className = 'matchup-row';
    div.id = id;
    div.dataset.round = roundNum;
    div.innerHTML = `
        <select class="player-select player-a" onchange="handlePlayerSelect(this, ${{roundNum}})">
            ${{makePlayerOptions('', false)}}
        </select>
        <span class="vs-label">vs</span>
        <select class="player-select player-b" onchange="handlePlayerSelect(this, ${{roundNum}})">
            ${{makePlayerOptions('', true)}}
        </select>
        <select class="games-select games-a">
            <option value="0">0</option><option value="1">1</option><option value="2" selected>2</option>
        </select>
        <span class="dash-label">-</span>
        <select class="games-select games-b">
            <option value="0" selected>0</option><option value="1">1</option><option value="2">2</option>
        </select>
        <button class="btn-remove" onclick="removeMatchup('${{id}}')" title="Remove">&times;</button>
    `;
    container.appendChild(div);
    validateRound(roundNum);
}}

function removeMatchup(id) {{
    const el = document.getElementById(id);
    const roundNum = parseInt(el.dataset.round);
    el.remove();
    validateRound(roundNum);
}}

function handlePlayerSelect(sel, roundNum) {{
    if (sel.value === '__NEW__') {{
        const name = prompt('Enter new player name:');
        if (name && name.trim()) {{
            const trimmed = name.trim();
            if (!PLAYERS.includes(trimmed)) {{
                PLAYERS.push(trimmed);
            }}
            // Rebuild all dropdowns to include the new player
            document.querySelectorAll('.player-select').forEach(s => {{
                const currentVal = s.value;
                const isBSide = s.classList.contains('player-b');
                s.innerHTML = makePlayerOptions(currentVal === '__NEW__' ? '' : currentVal, isBSide);
            }});
            sel.value = trimmed;
        }} else {{
            sel.value = '';
        }}
    }}
    validateRound(roundNum);
}}

function validateRound(roundNum) {{
    const rows = document.querySelectorAll('#matchups-' + roundNum + ' .matchup-row');
    const playerCounts = {{}};
    rows.forEach(row => {{
        const a = row.querySelector('.player-a').value;
        const b = row.querySelector('.player-b').value;
        if (a && a !== '__NEW__') playerCounts[a] = (playerCounts[a] || 0) + 1;
        if (b && b !== 'BYE' && b !== '__NEW__' && b !== '') playerCounts[b] = (playerCounts[b] || 0) + 1;
    }});

    rows.forEach(row => {{
        const a = row.querySelector('.player-a');
        const b = row.querySelector('.player-b');
        a.style.borderColor = (a.value && playerCounts[a.value] > 1) ? '#e94560' : '';
        if (b.value && b.value !== 'BYE' && playerCounts[b.value] > 1) {{
            b.style.borderColor = '#e94560';
        }} else {{
            b.style.borderColor = '';
        }}

        // Warn if both game scores are 0
        const ga = parseInt(row.querySelector('.games-a').value);
        const gb = parseInt(row.querySelector('.games-b').value);
        if (a.value && (b.value || b.value === 'BYE')) {{
            if (ga === 0 && gb === 0 && b.value !== 'BYE') {{
                row.style.background = 'rgba(233, 69, 96, 0.15)';
            }} else {{
                row.style.background = '';
            }}
        }}
    }});
}}

function collectResults() {{
    const week = parseInt(document.getElementById('weekNumber').value);
    if (!week || week < 1 || week > {total_weeks}) {{
        return {{ error: 'Invalid week number' }};
    }}

    const matches = [];
    const errors = [];

    for (let r = 1; r <= 3; r++) {{
        const rows = document.querySelectorAll('#matchups-' + r + ' .matchup-row');
        const playersInRound = [];

        rows.forEach(row => {{
            const playerA = row.querySelector('.player-a').value;
            const playerB = row.querySelector('.player-b').value;
            const gamesA = parseInt(row.querySelector('.games-a').value);
            const gamesB = parseInt(row.querySelector('.games-b').value);

            if (!playerA) {{
                errors.push('Round ' + r + ': Player A not selected in a matchup');
                return;
            }}

            if (playersInRound.includes(playerA)) {{
                errors.push('Round ' + r + ': ' + playerA + ' appears multiple times');
            }}
            playersInRound.push(playerA);

            const isBye = (!playerB || playerB === 'BYE');

            if (!isBye) {{
                if (playersInRound.includes(playerB)) {{
                    errors.push('Round ' + r + ': ' + playerB + ' appears multiple times');
                }}
                playersInRound.push(playerB);

                if (gamesA === 0 && gamesB === 0) {{
                    errors.push('Round ' + r + ': ' + playerA + ' vs ' + playerB + ' both have 0 games won');
                }}
            }}

            matches.push({{
                week: week,
                round: r,
                player_a: playerA,
                player_b: isBye ? null : playerB,
                games_a: gamesA,
                games_b: isBye ? 0 : gamesB
            }});
        }});
    }}

    if (matches.length === 0) {{
        errors.push('No matchups entered');
    }}

    if (errors.length > 0) {{
        return {{ error: errors.join('\\n') }};
    }}

    return {{ week: week, matches: matches }};
}}

function submitResults() {{
    const data = collectResults();
    if (data.error) {{
        const errDiv = document.getElementById('validationErrors');
        errDiv.style.display = 'block';
        errDiv.textContent = data.error;
        return;
    }}

    document.getElementById('validationErrors').style.display = 'none';
    document.getElementById('btnSubmit').disabled = true;
    document.getElementById('btnSubmit').textContent = 'Submitting...';

    fetch(leagueApiUrl('/api/add-results'), {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data)
    }})
    .then(resp => resp.json())
    .then(result => {{
        if (result.error) {{
            const errDiv = document.getElementById('validationErrors');
            errDiv.style.display = 'block';
            errDiv.textContent = result.error;
            document.getElementById('btnSubmit').disabled = false;
            document.getElementById('btnSubmit').textContent = 'Submit Week Results';
        }} else {{
            closeModal();
            document.getElementById('loadingOverlay').style.display = 'flex';
            // Reload page to get fresh simulation
            window.location.reload();
        }}
    }})
    .catch(err => {{
        const errDiv = document.getElementById('validationErrors');
        errDiv.style.display = 'block';
        errDiv.textContent = 'Network error: ' + err.message;
        document.getElementById('btnSubmit').disabled = false;
        document.getElementById('btnSubmit').textContent = 'Submit Week Results';
    }});
}}

function deleteWeek(week) {{
    if (!confirm('Delete all results for Week ' + week + '? This cannot be undone.')) return;

    document.getElementById('loadingOverlay').style.display = 'flex';

    fetch(leagueApiUrl('/api/add-results'), {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ delete_week: week }})
    }})
    .then(resp => resp.json())
    .then(result => {{
        if (result.error) {{
            alert('Error: ' + result.error);
            document.getElementById('loadingOverlay').style.display = 'none';
        }} else {{
            window.location.reload();
        }}
    }})
    .catch(err => {{
        alert('Network error: ' + err.message);
        document.getElementById('loadingOverlay').style.display = 'none';
    }});
}}

function openModal() {{
    document.getElementById('modalOverlay').style.display = 'flex';
    // Add one matchup to each round by default
    for (let r = 1; r <= 3; r++) {{
        if (document.getElementById('matchups-' + r).children.length === 0) {{
            addMatchup(r);
        }}
    }}
}}

function closeModal() {{
    document.getElementById('modalOverlay').style.display = 'none';
    // Clear matchups
    for (let r = 1; r <= 3; r++) {{
        document.getElementById('matchups-' + r).innerHTML = '';
    }}
    document.getElementById('validationErrors').style.display = 'none';
    document.getElementById('btnSubmit').disabled = false;
    document.getElementById('btnSubmit').textContent = 'Submit Week Results';
}}
</script>

{playoff_modal}
"""

    # Additional CSS for server mode
    server_css = ""
    if server_mode:
        server_css = """
/* Button Styles */
.btn-primary {
    background: #e94560;
    color: #fff;
    border: none;
    padding: 12px 32px;
    border-radius: 8px;
    font-size: 1em;
    font-weight: 600;
    cursor: pointer;
    letter-spacing: 0.5px;
    transition: background 0.2s;
}
.btn-primary:hover { background: #c73a52; }
.btn-primary:disabled { background: #555; cursor: not-allowed; }
.spinner {{
    width: 40px; height: 40px; margin: 0 auto;
    border: 4px solid rgba(233,69,96,0.2);
    border-top-color: #e94560;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.btn-secondary {
    background: #0f3460;
    color: #ccc;
    border: 1px solid #16213e;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 0.95em;
    cursor: pointer;
    transition: background 0.2s;
}
.btn-secondary:hover { background: #16213e; }

/* Entered Weeks */
.entered-weeks-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}
.entered-week {
    background: #1a1a2e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.entered-week-label {
    font-weight: 600;
    color: #e0e0e0;
}
.entered-week-info {
    color: #888;
    font-size: 0.85em;
}
.btn-delete-week {
    background: transparent;
    color: #e74c3c;
    border: 1px solid #e74c3c;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 0.8em;
    cursor: pointer;
    transition: all 0.2s;
}
.btn-delete-week:hover {
    background: #e74c3c;
    color: #fff;
}

/* Modal */
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    overflow-y: auto;
    padding: 20px;
}
.modal-content {
    background: #16213e;
    border: 1px solid #0f3460;
    border-radius: 12px;
    width: 100%;
    max-width: 800px;
    max-height: 90vh;
    overflow-y: auto;
}
.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid #0f3460;
}
.modal-header h2 {
    color: #e94560;
    font-size: 1.3em;
    margin: 0;
    border: none;
    padding: 0;
}
.modal-close {
    background: none;
    border: none;
    color: #888;
    font-size: 1.8em;
    cursor: pointer;
    padding: 0 8px;
    line-height: 1;
}
.modal-close:hover { color: #e94560; }
.modal-body {
    padding: 24px;
}
.form-group {
    margin-bottom: 20px;
}
.form-group label {
    display: block;
    color: #ccc;
    font-weight: 600;
    margin-bottom: 6px;
    font-size: 0.9em;
}
.form-group input[type="number"] {
    background: #1a1a2e;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 1em;
    width: 100px;
}

/* Round Sections */
.round-section {
    margin-bottom: 20px;
    border: 1px solid #0f3460;
    border-radius: 8px;
    padding: 16px;
    background: #1a1a2e;
}
.round-section h3 {
    color: #e94560;
    font-size: 1em;
    margin-bottom: 12px;
}

/* Matchup Rows */
.matchup-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding: 8px;
    border-radius: 6px;
    background: #16213e;
    flex-wrap: wrap;
}
.player-select {
    background: #1a1a2e;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 0.9em;
    min-width: 150px;
}
.games-select {
    background: #1a1a2e;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 0.9em;
    width: 50px;
    text-align: center;
}
.vs-label, .dash-label {
    color: #888;
    font-size: 0.85em;
    font-weight: 600;
}
.btn-add-matchup {
    background: transparent;
    border: 1px dashed #0f3460;
    color: #888;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85em;
    margin-top: 6px;
    transition: all 0.2s;
}
.btn-add-matchup:hover {
    border-color: #e94560;
    color: #e94560;
}
.btn-remove {
    background: transparent;
    border: none;
    color: #e74c3c;
    font-size: 1.3em;
    cursor: pointer;
    padding: 2px 8px;
    line-height: 1;
}
.btn-remove:hover { color: #ff6b6b; }

/* Validation */
.validation-errors {
    background: rgba(231, 76, 60, 0.15);
    border: 1px solid #e74c3c;
    border-radius: 6px;
    padding: 12px 16px;
    color: #e74c3c;
    font-size: 0.9em;
    margin-bottom: 16px;
    white-space: pre-line;
}

/* Modal Actions */
.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #0f3460;
}

/* Loading Overlay */
.loading-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
}
.loading-spinner {
    text-align: center;
    color: #e0e0e0;
}
.spinner {
    width: 50px;
    height: 50px;
    border: 4px solid #0f3460;
    border-top-color: #e94560;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 16px;
}
@keyframes spin {
    to { transform: rotate(360deg); }
}
"""

    # Build league-aware template variables
    completed_badge = '<span class="completed-badge">COMPLETED</span>' if is_completed else ''

    if is_completed:
        subtitle_text = f"Week {weeks_completed}/{total_weeks} &middot; Best {best_of_n} of {total_weeks} &middot; {'Top ' + str(playoff_spots) + ' qualified' if playoff_spots > 0 else 'No playoffs'}"
    else:
        subtitle_text = f"Week {weeks_completed}/{total_weeks} &middot; Best {best_of_n} of {total_weeks} &middot; Top {playoff_spots} qualify"

    completed_banner = ''
    if is_completed:
        completed_banner = """<div class="completed-banner"><div class="completed-banner-inner">This league has been completed. Showing final results.</div></div>"""

    # Probability section
    if is_completed or weeks_completed >= total_weeks:
        prob_section = ""
    elif skip_simulation:
        # Lazy-load mode: show button, fetch simulation on demand
        prob_section = f"""<div class="card" id="probSection">
    <h2>Playoff Probability</h2>
    <div id="probPlaceholder" style="text-align:center; padding: 30px 0;">
        <button class="btn-primary" id="btnPredict" onclick="runPrediction()">Predict the Playoffs</button>
        <p style="color:#888; font-size:0.82em; margin-top:10px;">Runs {num_simulations:,} Monte Carlo simulations</p>
    </div>
    <div id="probSpinner" style="display:none; text-align:center; padding: 40px 0;">
        <div class="spinner"></div>
        <p style="color:#888; font-size:0.85em; margin-top:16px;">Running simulations...</p>
    </div>
    <div class="prob-grid" id="probGrid" style="display:none;">
    </div>
</div>"""
    else:
        prob_section = f"""<div class="card">
    <h2>Playoff Probability</h2>
    <div class="prob-grid">
        {prob_cards}
    </div>
</div>"""

    # Methodology section (not shown for completed leagues)
    if is_completed:
        methodology_section = ""
    else:
        remaining = total_weeks - weeks_completed
        draw_pct = f"{GLOBAL_DRAW_RATE*100:.0f}"
        methodology_section = f"""<div class="card">
    <div class="methodology">
        <h3>Methodology</h3>
        <p>
            This model runs {num_simulations:,} Monte Carlo simulations of the remaining {remaining} weeks.
            Each simulation models player attendance based on historical patterns (core players at 100%,
            occasional players at 20%), random 1v1 pairings with bye handling for odd player counts,
            and match outcomes weighted by Bayesian-regressed historical match win percentages.
            The global draw rate is set at {draw_pct}% based on observed data.
            Final standings use best-{best_of_n}-of-{total_weeks} scoring, with ties broken by total match points,
            then Opponent Match Win percentage (OMW%), then game win percentage.
            OMW% is computed per-week as the average of each opponent's match win percentage
            (floored at 33.3%), then averaged across all weeks played. A player is marked "CLINCHED" if their minimum guaranteed best-{best_of_n} exceeds
            the maximum possible best-{best_of_n} of enough opponents, and "ELIMINATED" if their maximum possible
            best-{best_of_n} cannot reach the minimum guaranteed of enough opponents to break into the top {playoff_spots}.
        </p>
    </div>
</div>"""

    # League selector (server mode only)
    league_selector_html = ""
    league_selector_css = ""
    if server_mode and all_leagues:
        import json as _json2
        leagues_json = _json2.dumps(all_leagues)
        league_options = ""
        for lg in all_leagues:
            selected = "selected" if lg["id"] == current_league_id else ""
            status_label = f' ({lg["status"]})' if lg["status"] != "active" else ""
            display = lg.get("display_name", lg["name"])
            league_options += f'<option value="{lg["id"]}" {selected}>{lg["name"]} — {display}{status_label}</option>' if lg.get("display_name") else f'<option value="{lg["id"]}" {selected}>{lg["name"]}{status_label}</option>'
        league_selector_html = f"""
    <div class="league-selector">
        <select id="leagueSelect" onchange="switchLeague(this.value)">
            {league_options}
        </select>
        <div class="league-actions">
            <button class="league-action-btn" onclick="openNewLeagueModal()" title="Create New League">New League</button>
            {'<button class="league-action-btn league-action-complete" onclick="completeCurrentLeague()" title="Mark as Completed">Complete Season</button>' if not is_completed else ''}
        </div>
    </div>

<!-- New League Modal -->
<div id="newLeagueModalOverlay" class="modal-overlay" style="display:none;" onclick="if(event.target===this)closeNewLeagueModal()">
<div class="modal-content modal-sm">
    <div class="modal-header">
        <h2>Create New League</h2>
        <button class="modal-close" onclick="closeNewLeagueModal()">&times;</button>
    </div>
    <div class="modal-body">
        <div class="form-group">
            <label for="newLeagueName">Season Name</label>
            <input type="text" id="newLeagueName" class="form-input" placeholder="e.g. 2026 Season 2">
        </div>
        <div class="form-group">
            <label for="newLeagueDisplayName">League Name <span class="form-hint">(optional)</span></label>
            <input type="text" id="newLeagueDisplayName" class="form-input" placeholder="e.g. Lorwyn League">
        </div>
        <div class="form-group">
            <label class="form-checkbox">
                <input type="checkbox" id="carryOverPlayers" checked>
                <span>Carry over player list from current league</span>
            </label>
        </div>
        <div id="newLeagueErrors" class="validation-errors" style="display:none;"></div>
        <div class="modal-actions">
            <button class="btn-secondary" onclick="closeNewLeagueModal()">Cancel</button>
            <button class="btn-primary" id="btnCreateLeague" onclick="createNewLeague()">Create League</button>
        </div>
    </div>
</div>
</div>

<script>
function switchLeague(leagueId) {{
    window.location.href = '/?league=' + encodeURIComponent(leagueId);
}}
function openNewLeagueModal() {{
    document.getElementById('newLeagueModalOverlay').style.display = 'flex';
}}
function closeNewLeagueModal() {{
    document.getElementById('newLeagueModalOverlay').style.display = 'none';
    document.getElementById('newLeagueErrors').style.display = 'none';
}}
function createNewLeague() {{
    const name = document.getElementById('newLeagueName').value.trim();
    const displayName = document.getElementById('newLeagueDisplayName').value.trim();
    const carry = document.getElementById('carryOverPlayers').checked;
    const errDiv = document.getElementById('newLeagueErrors');
    if (!name) {{
        errDiv.style.display = 'block';
        errDiv.textContent = 'Please enter a league name';
        return;
    }}
    errDiv.style.display = 'none';
    document.getElementById('btnCreateLeague').disabled = true;
    document.getElementById('btnCreateLeague').textContent = 'Creating...';
    fetch('/api/leagues/create', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name: name, display_name: displayName || undefined, carry_over_players: carry }})
    }})
    .then(r => r.json())
    .then(result => {{
        if (result.error) {{
            errDiv.style.display = 'block';
            errDiv.textContent = result.error;
            document.getElementById('btnCreateLeague').disabled = false;
            document.getElementById('btnCreateLeague').textContent = 'Create League';
        }} else {{
            window.location.href = '/?league=' + encodeURIComponent(result.id);
        }}
    }})
    .catch(err => {{
        errDiv.style.display = 'block';
        errDiv.textContent = 'Network error: ' + err.message;
        document.getElementById('btnCreateLeague').disabled = false;
        document.getElementById('btnCreateLeague').textContent = 'Create League';
    }});
}}
function completeCurrentLeague() {{
    if (!confirm('Mark this league as completed? Simulation will no longer run for it.')) return;
    fetch('/api/leagues/complete', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ id: '{current_league_id}' }})
    }})
    .then(r => r.json())
    .then(result => {{
        if (result.error) {{
            alert('Error: ' + result.error);
        }} else {{
            window.location.reload();
        }}
    }})
    .catch(err => alert('Network error: ' + err.message));
}}
</script>"""

        league_selector_css = """
/* League Selector */
.league-selector {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 16px;
    flex-wrap: wrap;
}
.league-selector select {
    background: #0f3460;
    border: 1px solid rgba(233,69,96,0.25);
    color: #e0e0e0;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 0.88em;
    cursor: pointer;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    padding-right: 30px;
    min-width: 200px;
    transition: border-color 0.2s;
}
.league-selector select:hover,
.league-selector select:focus {
    border-color: #e94560;
    outline: none;
}
.league-actions {
    display: flex;
    gap: 6px;
}
.league-action-btn {
    background: transparent;
    border: 1px solid #0f3460;
    color: #888;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.8em;
    cursor: pointer;
    transition: all 0.2s;
    letter-spacing: 0.3px;
}
.league-action-btn:hover {
    border-color: #e94560;
    color: #e94560;
}
.league-action-complete {
    color: #f1c40f;
    border-color: rgba(241,196,15,0.25);
}
.league-action-complete:hover {
    border-color: #f1c40f;
    color: #f1c40f;
}
/* Form controls */
.form-input {
    background: #0a0a1a;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 1em;
    width: 100%;
    transition: border-color 0.2s;
}
.form-input:focus {
    border-color: #e94560;
    outline: none;
}
.form-input::placeholder {
    color: #555;
}
.form-hint {
    color: #555;
    font-weight: 400;
    font-size: 0.85em;
}
.form-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 0.92em;
    color: #ccc;
}
.form-checkbox input[type="checkbox"] {
    accent-color: #e94560;
    width: 16px;
    height: 16px;
}
.modal-sm {
    max-width: 450px;
}
.form-group {
    margin-bottom: 16px;
}
.form-group label {
    display: block;
    font-size: 0.85em;
    font-weight: 600;
    color: #ccc;
    margin-bottom: 6px;
    letter-spacing: 0.3px;
}
/* Completed Badge */
.completed-badge {
    background: #2ecc71;
    color: #1a1a2e;
    font-size: 0.4em;
    padding: 4px 12px;
    border-radius: 4px;
    font-weight: 700;
    letter-spacing: 1px;
    vertical-align: middle;
    margin-left: 10px;
}
/* Completed Banner */
.completed-banner {
    text-align: center;
    margin-bottom: 24px;
}
.completed-banner-inner {
    display: inline-block;
    background: rgba(46, 204, 113, 0.1);
    border: 1px solid rgba(46, 204, 113, 0.3);
    color: #2ecc71;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 0.9em;
    font-weight: 600;
}
"""
    else:
        # Even outside server mode, provide the CSS for completed badge/banner
        league_selector_css = """
.completed-badge {
    background: #2ecc71;
    color: #1a1a2e;
    font-size: 0.4em;
    padding: 4px 12px;
    border-radius: 4px;
    font-weight: 700;
    letter-spacing: 1px;
    vertical-align: middle;
    margin-left: 10px;
}
.completed-banner {
    text-align: center;
    margin-bottom: 24px;
}
.completed-banner-inner {
    display: inline-block;
    background: rgba(46, 204, 113, 0.1);
    border: 1px solid rgba(46, 204, 113, 0.3);
    color: #2ecc71;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 0.9em;
    font-weight: 600;
}
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MTG League Playoff Model</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}
body {{
    background: #0a0a1a;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    padding: 20px;
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
}}
.header {{
    text-align: center;
    padding: 24px 0 0;
    margin-bottom: 24px;
}}
.header-top {{
    margin-bottom: 4px;
}}
.header h1 {{
    font-size: 1.8em;
    color: #e94560;
    letter-spacing: 1px;
    margin-bottom: 2px;
}}
.league-display-name {{
    font-size: 1em;
    color: #666;
    font-style: italic;
    margin-bottom: 4px;
}}
.header .subtitle {{
    color: #888;
    font-size: 0.85em;
}}
.nav-links {{
    display: inline-flex;
    gap: 4px;
    margin: 16px 0 24px;
    padding: 4px;
    background: #0f3460;
    border-radius: 10px;
}}
.nav-links a {{
    color: #888;
    text-decoration: none;
    padding: 7px 18px;
    border-radius: 7px;
    font-size: 0.82em;
    font-weight: 500;
    transition: all 0.2s;
    letter-spacing: 0.3px;
}}
.nav-links a:hover {{
    color: #e0e0e0;
    background: rgba(255,255,255,0.06);
}}
.nav-links a.active {{
    background: #e94560;
    color: #fff;
    font-weight: 600;
}}
.card {{
    background: #16213e;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    border: 1px solid #0f3460;
}}
.card h2 {{
    color: #e94560;
    font-size: 1.3em;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #0f3460;
}}
/* Standings Table */
.standings-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
}}
.standings-table th {{
    background: #0f3460;
    color: #e0e0e0;
    padding: 10px 8px;
    text-align: center;
    font-weight: 600;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.standings-table td {{
    padding: 8px;
    text-align: center;
    border-bottom: 1px solid #1a1a2e;
}}
.standings-table tr:hover {{
    background: rgba(233,69,96,0.06);
}}
.standings-table tr.top4 {{
    background: rgba(46, 204, 113, 0.08);
}}
.standings-table tr.top4:hover {{
    background: rgba(46, 204, 113, 0.15);
}}
.standings-table tr.unofficial {{
    opacity: 0.45;
}}
.rank {{
    font-weight: bold;
    color: #888;
    width: 40px;
}}
.player-name {{
    text-align: left !important;
    font-weight: 600;
    color: #f0f0f0;
    white-space: nowrap;
}}
.best7 {{
    font-weight: bold;
    color: #2ecc71;
    font-size: 1.05em;
}}
.total-pts {{
    color: #aaa;
}}
.omw-col {{
    color: #aaa;
    font-size: 0.9em;
}}
.defending-champ {{
    color: #f1c40f !important;
}}
.score-max {{ color: #2ecc71; font-weight: bold; }}
.score-high {{ color: #a8d8a8; }}
.score-mid {{ color: #ccc; }}
.score-low {{ color: #e74c3c; }}
.score-absent {{ color: #555; }}
.score-future {{ color: #333; }}
.week-header.future {{ color: #555; }}
.week-header.active {{ color: #ccc; }}
.week-header.clickable {{ cursor: pointer; position: relative; }}
.week-header.clickable:hover {{ color: #e94560; background: #1a2744; }}
.week-header.clickable.selected {{ color: #e94560; border-bottom: 2px solid #e94560; }}

/* Week Detail Panels */
.week-detail-panel {{
    margin-bottom: 24px;
}}
.wd-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #0f3460;
}}
.wd-header h2 {{
    color: #e94560;
    font-size: 1.3em;
    margin: 0;
    padding: 0;
    border: none;
}}
.wd-content {{
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}}
.wd-rounds {{
    flex: 1;
    min-width: 300px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}}
.wd-round {{
    flex: 1;
    min-width: 200px;
}}
.wd-round h4 {{
    color: #e94560;
    font-size: 0.9em;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.wd-standings {{
    min-width: 280px;
}}
.wd-standings h4 {{
    color: #e94560;
    font-size: 0.9em;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.wd-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
}}
.wd-table th {{
    background: #0f3460;
    color: #aaa;
    padding: 6px 10px;
    text-align: center;
    font-size: 0.85em;
    font-weight: 600;
}}
.wd-table td {{
    padding: 6px 10px;
    text-align: center;
    border-bottom: 1px solid rgba(15,52,96,0.5);
    color: #ccc;
}}
.wd-player {{ font-weight: 600; color: #e0e0e0; text-align: left !important; }}
.wd-pos {{ color: #888; width: 30px; }}
.wd-pts {{ font-weight: 700; color: #2ecc71; }}
.wd-score {{ font-weight: 600; white-space: nowrap; }}
.result-win {{ color: #2ecc71; }}
.result-loss {{ color: #e74c3c; }}
.result-draw {{ color: #f1c40f; }}
.wd-standings-table td {{ text-align: center; }}
.wd-standings-table td.wd-player {{ text-align: left !important; }}
/* Probability Cards */
.prob-grid {{
    display: grid;
    gap: 12px;
}}
.prob-card {{
    background: #1a1a2e;
    border: 1px solid #0f3460;
    border-radius: 8px;
    padding: 14px 18px;
}}
.prob-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}}
.prob-player {{
    font-weight: 700;
    font-size: 1.05em;
    min-width: 140px;
}}
.prob-pct {{
    font-weight: 700;
    font-size: 1.1em;
    min-width: 60px;
}}
.badge {{
    font-size: 0.7em;
    padding: 3px 10px;
    border-radius: 4px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
.badge.clinched {{
    background: #2ecc71;
    color: #1a1a2e;
}}
.badge.eliminated {{
    background: #e74c3c;
    color: #fff;
}}
.prob-bar-bg {{
    background: #0f3460;
    border-radius: 6px;
    height: 10px;
    overflow: hidden;
    margin-bottom: 8px;
}}
.prob-bar {{
    height: 100%;
    border-radius: 6px;
    transition: width 0.3s ease;
    min-width: 3px;
}}
.prob-details {{
    display: flex;
    gap: 20px;
    font-size: 0.82em;
    color: #888;
}}
/* Insights */
.insights-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
}}
.insight-card {{
    background: #1a1a2e;
    border-top: 3px solid #e94560;
    padding: 16px;
    border-radius: 8px;
    text-align: center;
}}
.insight-title {{
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #e94560;
    margin-bottom: 8px;
}}
.insight-player {{
    font-size: 1.1em;
    font-weight: 700;
    color: #e0e0e0;
    margin-bottom: 4px;
}}
.insight-value {{
    font-size: 1.6em;
    font-weight: 700;
    color: #2ecc71;
    margin-bottom: 4px;
}}
.insight-detail {{
    font-size: 0.78em;
    color: #888;
}}
.insight-item {{
    background: #1a1a2e;
    border-left: 3px solid #e94560;
    padding: 12px 16px;
    border-radius: 0 6px 6px 0;
    font-size: 0.92em;
    line-height: 1.5;
}}
/* Methodology */
.methodology {{
    font-size: 0.82em;
    color: #666;
    line-height: 1.7;
    padding: 16px;
    background: #12122a;
    border-radius: 8px;
}}
.methodology h3 {{
    color: #888;
    margin-bottom: 8px;
    font-size: 1em;
}}
.top4-marker {{
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #2ecc71;
    border-radius: 50%;
    margin-right: 6px;
}}

/* Responsive: make standings table horizontally scrollable */
.table-wrapper {{
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin: 0 -4px;
    padding: 0 4px;
}}

@media (max-width: 768px) {{
    body {{ padding: 10px; }}
    .header h1 {{ font-size: 1.3em; }}
    .header .subtitle {{ font-size: 0.75em; }}
    .nav-links {{ gap: 2px; padding: 3px; }}
    .nav-links a {{ font-size: 0.75em; padding: 6px 10px; }}
    .league-selector {{ gap: 8px; }}
    .league-selector select {{ min-width: 160px; font-size: 0.82em; padding: 6px 10px; }}
    .league-actions {{ gap: 4px; }}
    .league-action-btn {{ font-size: 0.72em; padding: 5px 10px; }}
    .card {{ padding: 14px; margin-bottom: 16px; }}
    .card h2 {{ font-size: 1.1em; }}

    /* Standings table */
    .standings-table {{ font-size: 0.78em; }}
    .standings-table th {{ padding: 6px 4px; font-size: 0.75em; }}
    .standings-table td {{ padding: 5px 4px; }}
    .player-name {{ max-width: 90px; overflow: hidden; text-overflow: ellipsis; }}

    /* Prob cards */
    .prob-header {{ flex-wrap: wrap; gap: 6px; }}
    .prob-player {{ min-width: auto; font-size: 0.95em; }}
    .prob-pct {{ min-width: auto; }}
    .prob-details {{ flex-wrap: wrap; gap: 8px 14px; font-size: 0.78em; }}

    /* Charts */
    .card canvas {{ min-height: 280px; }}

    /* Week detail panels */
    .wd-content {{ flex-direction: column; gap: 16px; }}
    .wd-rounds {{ flex-direction: column; gap: 12px; min-width: auto; }}
    .wd-round {{ min-width: auto; }}
    .wd-standings {{ min-width: auto; }}
    .wd-table {{ font-size: 0.8em; }}
    .wd-table td {{ padding: 5px 6px; }}

    /* Modal */
    .modal-content {{ max-width: 100%; margin: 10px; }}
    .matchup-row {{ gap: 4px; }}
    .player-select {{ min-width: 110px; font-size: 0.82em; }}
    .games-select {{ width: 42px; font-size: 0.82em; }}
}}

@media (max-width: 480px) {{
    body {{ padding: 6px; }}
    .header h1 {{ font-size: 1.1em; }}
    .header .subtitle {{ font-size: 0.72em; }}
    .nav-links a {{ font-size: 0.7em; padding: 5px 8px; }}
    .league-selector {{ flex-direction: column; gap: 6px; }}
    .league-selector select {{ min-width: auto; width: 100%; }}
    .league-actions {{ justify-content: center; }}
    .card {{ padding: 10px; border-radius: 8px; }}
    .standings-table th {{ padding: 4px 2px; font-size: 0.7em; }}
    .standings-table td {{ padding: 4px 2px; font-size: 0.72em; }}
    .player-name {{ max-width: 70px; }}
    .prob-details {{ font-size: 0.72em; }}
    .badge {{ font-size: 0.6em; padding: 2px 6px; }}
}}
/* Playoff Bracket */
.bracket-projected {{
    opacity: 0.7;
    border-style: dashed;
}}
.bracket-container {{
    display: flex;
    align-items: center;
    gap: 0;
    overflow-x: auto;
    padding: 20px 0;
}}
.bracket-round {{
    display: flex;
    flex-direction: column;
    gap: 20px;
}}
.bracket-round-title {{
    color: #888;
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
    margin-bottom: 8px;
    text-align: center;
}}
.bracket-semis {{
    gap: 40px;
}}
.bracket-match {{
    background: #1a1a2e;
    border: 1px solid #0f3460;
    border-radius: 8px;
    overflow: hidden;
    min-width: 200px;
    position: relative;
}}
.bracket-match-label {{
    position: absolute;
    top: 4px;
    right: 8px;
    font-size: 0.65em;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.bracket-slot {{
    display: flex;
    align-items: center;
    padding: 10px 14px;
    gap: 8px;
    border-bottom: 1px solid #0f3460;
    transition: background 0.2s;
}}
.bracket-slot:last-child {{
    border-bottom: none;
}}
.bracket-seed {{
    color: #888;
    font-size: 0.8em;
    font-weight: 600;
    min-width: 20px;
}}
.bracket-name {{
    font-weight: 600;
    flex: 1;
    color: #e0e0e0;
}}
.bracket-score {{
    font-weight: 700;
    color: #aaa;
    min-width: 16px;
    text-align: right;
}}
.bracket-winner {{
    background: rgba(46, 204, 113, 0.12);
}}
.bracket-winner .bracket-name {{
    color: #2ecc71;
}}
.bracket-winner .bracket-score {{
    color: #2ecc71;
}}
.bracket-loser {{
    opacity: 0.5;
}}
.bracket-connector-col {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    width: 40px;
    position: relative;
    align-self: stretch;
}}
.bracket-connector-top,
.bracket-connector-bottom {{
    flex: 1;
    width: 20px;
    position: relative;
}}
.bracket-connector-top {{
    border-right: 2px solid #0f3460;
    border-top: 2px solid #0f3460;
    margin-top: 30px;
    border-top-right-radius: 6px;
}}
.bracket-connector-bottom {{
    border-right: 2px solid #0f3460;
    border-bottom: 2px solid #0f3460;
    margin-bottom: 30px;
    border-bottom-right-radius: 6px;
}}
.bracket-final {{
    justify-content: center;
}}
.bracket-champion-col {{
    display: flex;
    align-items: center;
    padding-left: 20px;
}}
.bracket-champion-slot {{
    font-size: 1.3em;
    font-weight: 800;
    color: #555;
    padding: 16px 20px;
    border-radius: 8px;
    min-width: 100px;
    text-align: center;
}}
.bracket-champion-slot.bracket-winner {{
    color: #2ecc71;
    background: rgba(46, 204, 113, 0.1);
    border: 2px solid #2ecc71;
}}
.bracket-third-place {{
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid #0f3460;
    max-width: 280px;
}}
.bracket-third-place .bracket-match {{
    margin-top: 8px;
}}
.bracket-result {{
    text-align: center;
    padding: 8px;
    font-size: 0.85em;
    color: #888;
    font-weight: 600;
}}
/* Champion Banner */
.champion-banner {{
    text-align: center;
    padding: 24px;
    margin-bottom: 20px;
    background: linear-gradient(135deg, rgba(46, 204, 113, 0.08), rgba(233, 69, 96, 0.08));
    border-radius: 12px;
    border: 2px solid #2ecc71;
}}
.champion-trophy {{
    font-size: 3em;
    margin-bottom: 8px;
}}
.champion-name {{
    font-size: 2em;
    font-weight: 800;
    color: #2ecc71;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
.champion-label {{
    font-size: 1em;
    color: #888;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-top: 4px;
}}
/* Awards */
.awards-section {{
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid #0f3460;
    justify-content: center;
}}
.award-card {{
    background: #1a1a2e;
    border: 1px solid #0f3460;
    border-radius: 10px;
    padding: 20px 28px;
    text-align: center;
    min-width: 200px;
    flex: 1;
    max-width: 300px;
}}
.award-champion {{
    border-color: #2ecc71;
}}
.award-mvp {{
    border-color: #f1c40f;
}}
.award-icon {{
    font-size: 2em;
    margin-bottom: 8px;
}}
.award-title {{
    font-size: 0.85em;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}}
.award-player {{
    font-size: 1.3em;
    font-weight: 700;
    color: #e0e0e0;
}}
.award-champion .award-player {{
    color: #2ecc71;
}}
.award-mvp .award-player {{
    color: #f1c40f;
}}
.award-note {{
    width: 100%;
    text-align: center;
    color: #2ecc71;
    font-weight: 600;
    font-size: 1.1em;
    padding: 8px;
}}

@media (max-width: 768px) {{
    .bracket-container {{
        flex-direction: column;
        align-items: stretch;
    }}
    .bracket-connector-col {{
        display: none;
    }}
    .bracket-champion-col {{
        padding-left: 0;
        justify-content: center;
    }}
    .bracket-match {{
        min-width: auto;
    }}
    .bracket-semis {{
        gap: 16px;
    }}
    .bracket-third-place {{
        max-width: 100%;
    }}
    .awards-section {{
        flex-direction: column;
        align-items: center;
    }}
    .award-card {{
        max-width: 100%;
        width: 100%;
    }}
    .champion-name {{
        font-size: 1.4em;
    }}
}}

@media (max-width: 480px) {{
    .bracket-slot {{
        padding: 8px 10px;
        gap: 6px;
    }}
    .champion-name {{
        font-size: 1.2em;
    }}
    .champion-trophy {{
        font-size: 2em;
    }}
}}
{server_css}
{league_selector_css}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <div class="header-top">
        <div class="header-title">
            <h1>{league_name} {completed_badge}</h1>
            {'<div class="league-display-name">' + league_display_name + '</div>' if league_display_name else ''}
            <div class="subtitle">{subtitle_text}</div>
        </div>
    </div>
    {league_selector_html}
    <nav class="nav-links">
        <a href="/" class="active">League</a>
        <a href="/cumulative">Cumulative 2026</a>
        <a href="/all-time">All-Time</a>
        <a href="/head-to-head">Head-to-Head</a>
    </nav>
</div>

{completed_banner}

{server_ui.split('<!-- Modal Overlay -->')[0] if server_mode and not is_completed else ''}

<div class="card">
    <h2>{'Final Standings' if is_completed else 'Current Standings'}</h2>
    <div class="table-wrapper">
    <table class="standings-table">
        <thead>
            <tr>
                <th>#</th>
                <th style="text-align:left">Player</th>
                {week_headers}
                <th>Best {best_of_n}</th>
                <th>Total</th>
                <th>OMW%</th>
            </tr>
        </thead>
        <tbody>
            {standings_rows}
        </tbody>
    </table>
    </div>
    <div style="margin-top: 10px; font-size: 0.8em; color: #555;">
        {'<span class="top4-marker"></span> Top ' + str(playoff_spots) + ' qualify for playoffs &middot; ' if playoff_spots > 0 else ''}Best {best_of_n} of {total_weeks} weekly scores count
        {'&middot; Click a week header to view match details' if matches else ''}
        {'<br>* Unofficial participant — not eligible for standings' if has_unofficial else ''}
    </div>
</div>

{week_detail_panels}

{prob_section}

{bracket_section}

{insights_html}

<div class="card">
    <h2>League Standings Race</h2>
    <p style="color:#888; font-size:0.85em; margin-bottom:12px;">Running best-{best_of_n} total over the season. Click player names to show/hide.</p>
    <div style="position:relative; height:400px;">
        <canvas id="best7Chart"></canvas>
    </div>
</div>


{methodology_section}

{'<!-- Modal Overlay -->' + server_ui.split('<!-- Modal Overlay -->')[1] if server_mode and not is_completed and '<!-- Modal Overlay -->' in server_ui else ''}

</div>

<script>
function toggleWeekDetail(week) {{
    const panel = document.getElementById('weekDetail-' + week);
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    // Close all panels first
    document.querySelectorAll('.week-detail-panel').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.week-header.clickable').forEach(th => th.classList.remove('selected'));
    if (!isVisible) {{
        panel.style.display = 'block';
        // Highlight the selected week header
        document.querySelectorAll('.week-header.clickable').forEach(th => {{
            if (th.textContent === 'W' + week) th.classList.add('selected');
        }});
        panel.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
    }}
}}
</script>

<script>
(function() {{
    const weekLabels = {week_labels_json};
    const chartDefaults = {{
        color: '#aaa',
        borderColor: '#0f3460',
        font: {{ family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}
    }};
    Chart.defaults.color = chartDefaults.color;
    Chart.defaults.font.family = chartDefaults.font.family;

    const gridColor = 'rgba(15, 52, 96, 0.6)';

    // Best-7 Race Chart
    new Chart(document.getElementById('best7Chart'), {{
        type: 'line',
        data: {{
            labels: weekLabels,
            datasets: {best7_datasets_json}
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
                legend: {{
                    position: 'bottom',
                    labels: {{ padding: 16, usePointStyle: true, pointStyle: 'circle', boxWidth: 8 }}
                }},
                tooltip: {{
                    backgroundColor: '#16213e',
                    borderColor: '#0f3460',
                    borderWidth: 1,
                    titleColor: '#e94560',
                    bodyColor: '#e0e0e0',
                    padding: 12,
                    callbacks: {{
                        label: function(ctx) {{
                            return ctx.dataset.label + ': ' + (ctx.parsed.y !== null ? ctx.parsed.y + ' pts' : 'N/A');
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{ grid: {{ color: gridColor }}, ticks: {{ color: '#888' }} }},
                y: {{
                    grid: {{ color: gridColor }},
                    ticks: {{ color: '#888' }},
                    title: {{ display: true, text: 'Best {best_of_n} Total', color: '#888' }},
                    beginAtZero: true
                }}
            }}
        }}
    }});

}})();
</script>

<script>
function runPrediction() {{
    const btn = document.getElementById('btnPredict');
    const placeholder = document.getElementById('probPlaceholder');
    const spinner = document.getElementById('probSpinner');
    const grid = document.getElementById('probGrid');
    if (!placeholder) return;
    placeholder.style.display = 'none';
    spinner.style.display = 'block';

    const leagueParam = new URLSearchParams(window.location.search).get('league') || '';
    const url = '/api/simulate' + (leagueParam ? '?league=' + encodeURIComponent(leagueParam) : '');

    fetch(url)
        .then(r => r.json())
        .then(data => {{
            spinner.style.display = 'none';
            if (data.error) {{
                placeholder.style.display = 'block';
                placeholder.innerHTML = '<p style="color:#e74c3c;">Error: ' + data.error + '</p>';
                return;
            }}
            // Build probability cards from JSON
            let cards = '';
            data.players.forEach(p => {{
                const prob = p.playoff_prob;
                let barColor = '#e74c3c';
                if (prob >= 75) barColor = '#2ecc71';
                else if (prob >= 50) barColor = '#f1c40f';
                else if (prob >= 25) barColor = '#e67e22';

                let badge = '';
                if (p.status === 'clinched' || prob >= 99.9) badge = '<span class="badge clinched">CLINCHED</span>';
                else if (p.status === 'eliminated' || prob === 0) badge = '<span class="badge eliminated">ELIMINATED</span>';

                cards += `
                <div class="prob-card">
                    <div class="prob-header">
                        <span class="prob-player">${{p.name}}</span>
                        <span class="prob-pct">${{prob.toFixed(1)}}%</span>
                        ${{badge}}
                    </div>
                    <div class="prob-bar-bg">
                        <div class="prob-bar" style="width: ${{Math.max(prob, 0.5)}}%; background: ${{barColor}};"></div>
                    </div>
                    <div class="prob-details">
                        <span>Record: ${{p.record}}</span>
                        <span>Best {best_of_n}: ${{p.current_best7}}</span>
                        <span>Max Possible: ${{p.max_possible}}</span>
                        <span>OMW%: ${{(p.omw * 100).toFixed(1)}}%</span>
                        <span>GW%: ${{(p.gwp * 100).toFixed(1)}}%</span>
                    </div>
                </div>`;
            }});
            grid.innerHTML = cards;
            grid.style.display = 'grid';
        }})
        .catch(err => {{
            spinner.style.display = 'none';
            placeholder.style.display = 'block';
            placeholder.innerHTML = '<p style="color:#e74c3c;">Network error: ' + err.message + '</p>';
        }});
}}
</script>

</body>
</html>"""

    return html


# ============================================================
# Main pipeline (used by both standalone and server)
# ============================================================

def run_full_pipeline(server_mode: bool = False, league_id: str = None, skip_simulation: bool = False) -> str:
    """Load data, run simulation, generate HTML. Returns HTML string.

    Args:
        server_mode: Whether running in server mode (enables data entry UI).
        league_id: Specific league to load. Defaults to active league.
        skip_simulation: If True, skip Monte Carlo simulation (for completed leagues).
    """
    # Load league info
    leagues_config = load_leagues_config()
    if league_id is None:
        league_id = leagues_config["active_league"]

    league_info_item = None
    for lg in leagues_config["leagues"]:
        if lg["id"] == league_id:
            league_info_item = dict(lg)
            break
    if league_info_item is None:
        raise ValueError(f"League '{league_id}' not found")

    # Attach all leagues list for the selector
    league_info_item["_all_leagues"] = leagues_config["leagues"]

    # Auto-skip simulation for completed leagues and server mode (loaded on demand)
    if league_info_item.get("status") == "completed":
        skip_simulation = True
    elif server_mode:
        skip_simulation = True

    data = load_league_data(league_id=league_id)
    league = derive_stats(data)

    data_file_path = get_league_data_path(league_id)

    if skip_simulation:
        print(f"Skipping simulation for league '{league_info_item['name']}' (status: {league_info_item.get('status', 'unknown')})")
        # Build results without simulation — just derive current stats
        players = league["players"]
        weekly_scores = league["weekly_scores"]
        overall_stats = league["overall_stats"]
        best_of_n = league["best_of_n"]
        weeks_completed = league["weeks_completed"]
        total_weeks = league["total_weeks"]

        results = {}
        for p in players:
            results[p] = {
                "playoff_prob": 0,
                "playoff_count": 0,
                "positions": {},
                "current_best7": best_n_score(weekly_scores[p], best_of_n),
                "max_possible_best7": max_possible_best7(weekly_scores[p], weeks_completed, total_weeks, best_of_n),
                "min_guaranteed_best7": min_guaranteed_best7(weekly_scores[p], best_of_n),
                "total_match_pts": total_match_points(weekly_scores[p]),
                "weeks_played": sum(1 for s in weekly_scores[p] if s is not None),
            }
        status = {p: {"status": "alive"} for p in players}
        insights = generate_insights(results, status, players,
                                      league["playoff_spots"], weeks_completed,
                                      total_weeks,
                                      overall_omw=league.get("overall_omw", {}),
                                      weekly_scores=weekly_scores,
                                      overall_stats=overall_stats,
                                      unofficial_players=set(league.get("unofficial_players", [])),
                                      best_of_n=league["best_of_n"],
                                      matches=league.get("matches", []))
    else:
        print(f"Running {league['num_simulations']:,} Monte Carlo simulations...")
        print(f"League: {league['weeks_completed']}/{league['total_weeks']} weeks completed, "
              f"{league['total_weeks'] - league['weeks_completed']} remaining")

        results = run_simulation(league)
        status = check_elimination_clinch(results, league["players"], league["playoff_spots"])
        insights = generate_insights(results, status, league["players"],
                                      league["playoff_spots"], league["weeks_completed"],
                                      league["total_weeks"],
                                      overall_omw=league.get("overall_omw", {}),
                                      weekly_scores=league["weekly_scores"],
                                      overall_stats=league["overall_stats"],
                                      unofficial_players=set(league.get("unofficial_players", [])),
                                      best_of_n=league["best_of_n"],
                                      matches=league.get("matches", []))

    # Auto-populate playoff seedings when regular season is complete (and playoffs exist)
    if league["weeks_completed"] >= league["total_weeks"] and league["playoff_spots"] >= 4:
        overall_omw = league.get("overall_omw", {})
        overall_stats = league["overall_stats"]
        standings_order = sorted(league["players"], key=lambda p: (
            results[p]["current_best7"],
            results[p]["total_match_pts"],
            overall_omw.get(p, 0),
            overall_stats[p]["gwp"]
        ), reverse=True)
        seeds = standings_order[:league["playoff_spots"]]

        if "playoffs" not in data or data["playoffs"] is None:
            data["playoffs"] = initialize_playoffs(seeds)
            with open(data_file_path, "w") as f:
                json.dump(data, f, indent=2)
            league["playoffs"] = data["playoffs"]
            print(f"Playoff seedings auto-populated: {seeds}")
        else:
            # Update semifinal players if not already set
            playoffs = data["playoffs"]
            sf1 = playoffs.get("semifinal_1", {})
            sf2 = playoffs.get("semifinal_2", {})
            if not sf1.get("player_a") or not sf2.get("player_a"):
                playoffs["semifinal_1"]["player_a"] = seeds[0]
                playoffs["semifinal_1"]["player_b"] = seeds[3]
                playoffs["semifinal_2"]["player_a"] = seeds[1]
                playoffs["semifinal_2"]["player_b"] = seeds[2]
                with open(data_file_path, "w") as f:
                    json.dump(data, f, indent=2)
                league["playoffs"] = playoffs

    html = generate_html(league, results, status, insights,
                         server_mode=server_mode,
                         league_info=league_info_item,
                         skip_simulation=skip_simulation)
    return html


def run_simulation_api(league_id: str = None) -> dict:
    """Run Monte Carlo simulation and return results as JSON-serializable dict."""
    data = load_league_data(league_id=league_id)
    league = derive_stats(data)

    if league["weeks_completed"] >= league["total_weeks"]:
        return {"error": "League is complete, no simulation needed"}

    results = run_simulation(league)
    status = check_elimination_clinch(results, league["players"], league["playoff_spots"])

    overall_stats = league["overall_stats"]
    overall_omw = league.get("overall_omw", {})

    # Sort by playoff probability
    prob_order = sorted(league["players"], key=lambda p: (
        results[p]["playoff_prob"], results[p]["current_best7"]
    ), reverse=True)

    players_data = []
    for p in prob_order:
        s = overall_stats[p]
        players_data.append({
            "name": p,
            "playoff_prob": round(results[p]["playoff_prob"], 1),
            "current_best7": results[p]["current_best7"],
            "max_possible": results[p]["max_possible_best7"],
            "record": f"{s['w']}-{s['l']}-{s['d']}",
            "omw": round(overall_omw.get(p, 0), 4),
            "gwp": round(s["gwp"], 3),
            "status": status[p]["status"],
        })

    return {"players": players_data, "num_simulations": league["num_simulations"]}


def generate_cumulative_page(year: int = 2026, server_mode: bool = False) -> str:
    """Generate a cumulative standings page across all leagues in a given year."""
    leagues_config = load_leagues_config()
    year_leagues = [lg for lg in leagues_config["leagues"] if lg["id"].startswith(str(year))]

    if not year_leagues:
        return "<html><body><h1>No leagues found for this year</h1></body></html>"

    # Gather data from each league
    player_totals = defaultdict(lambda: {"best_n_total": 0, "leagues_played": 0,
                                          "total_weeks_played": 0, "total_match_pts": 0,
                                          "nines": 0, "league_details": []})

    all_unofficial = set()
    for lg_info in year_leagues:
        data = load_league_data(league_id=lg_info["id"])
        league = derive_stats(data)
        unofficial = set(league.get("unofficial_players", []))
        all_unofficial |= unofficial
        players = league["players"]
        weekly_scores = league["weekly_scores"]
        best_of_n = league["best_of_n"]

        for p in players:
            best_n = best_n_score(weekly_scores[p], best_of_n)
            weeks_played = sum(1 for s in weekly_scores[p] if s is not None)
            total_pts = total_match_points(weekly_scores[p])
            nines = sum(1 for s in weekly_scores[p] if s == 9)

            player_totals[p]["best_n_total"] += best_n
            player_totals[p]["leagues_played"] += 1
            player_totals[p]["total_weeks_played"] += weeks_played
            player_totals[p]["total_match_pts"] += total_pts
            player_totals[p]["nines"] += nines
            display_name = lg_info.get("display_name", lg_info["name"])
            player_totals[p]["league_details"].append({
                "league": display_name,
                "best_n": best_n,
                "weeks": weeks_played,
                "status": lg_info["status"]
            })

    # Sort by cumulative best-N total
    sorted_players = sorted(player_totals.keys(),
                            key=lambda p: (p not in all_unofficial, player_totals[p]["best_n_total"]),
                            reverse=True)

    # Build HTML
    league_headers = ""
    for lg in year_leagues:
        display = lg.get("display_name", lg["name"])
        status_badge = ' <span style="color:#888;font-size:0.75em;">(in progress)</span>' if lg["status"] == "active" else ""
        league_headers += f"<th>{display}{status_badge}</th>"

    rows = ""
    for rank, p in enumerate(sorted_players, 1):
        t = player_totals[p]
        is_unofficial = p in all_unofficial
        row_class = "unofficial" if is_unofficial else ""
        display_p = f"{p} *" if is_unofficial else p

        league_cells = ""
        for lg in year_leagues:
            display = lg.get("display_name", lg["name"])
            detail = next((d for d in t["league_details"] if d["league"] == display), None)
            if detail:
                league_cells += f'<td>{detail["best_n"]}</td>'
            else:
                league_cells += '<td style="color:#555;">—</td>'

        rows += f"""<tr class="{row_class}">
            <td class="rank">{rank}</td>
            <td class="player-name">{display_p}</td>
            {league_cells}
            <td class="best7" style="font-weight:700;">{t['best_n_total']}</td>
            <td>{t['total_weeks_played']}</td>
            <td>{t['nines']}</td>
        </tr>"""

    # League selector HTML
    all_leagues = leagues_config["leagues"]
    league_options = ""
    for lg in all_leagues:
        display = lg.get("display_name", lg["name"])
        status_label = f' ({lg["status"]})' if lg["status"] != "active" else ""
        opt_display = f'{lg["name"]} — {display}{status_label}' if lg.get("display_name") else f'{lg["name"]}{status_label}'
        league_options += f'<option value="{lg["id"]}">{opt_display}</option>'

    nav_links = f"""<nav class="nav-links">
        <a href="/">League</a>
        <a href="/cumulative" class="active">Cumulative {year}</a>
        <a href="/all-time">All-Time</a>
        <a href="/head-to-head">Head-to-Head</a>
    </nav>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{year} Cumulative Standings</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #0a0a1a; color: #e0e0e0; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
.header {{ text-align: center; padding: 24px 0 0; margin-bottom: 24px; }}
.header h1 {{ font-size: 1.8em; color: #e94560; letter-spacing: 1px; margin-bottom: 4px; }}
.header .subtitle {{ color: #888; font-size: 0.85em; }}
.nav-links {{ display: inline-flex; gap: 4px; margin: 16px 0 24px; padding: 4px; background: #0f3460; border-radius: 10px; }}
.nav-links a {{ color: #888; text-decoration: none; padding: 7px 18px; border-radius: 7px; font-size: 0.82em; font-weight: 500; transition: all 0.2s; letter-spacing: 0.3px; }}
.nav-links a:hover {{ color: #e0e0e0; background: rgba(255,255,255,0.06); }}
.nav-links a.active {{ background: #e94560; color: #fff; font-weight: 600; }}
.card {{ background: #16213e; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #0f3460; }}
.card h2 {{ font-size: 1.3em; color: #e94560; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #0f3460; }}
.table-wrapper {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
th {{ background: #0f3460; color: #e0e0e0; padding: 10px 8px; text-align: center; font-size: 0.82em; text-transform: uppercase; letter-spacing: 0.5px; }}
td {{ padding: 8px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.04); }}
tr:hover {{ background: rgba(233,69,96,0.06); }}
.rank {{ color: #888; font-size: 0.85em; width: 30px; }}
.player-name {{ text-align: left !important; font-weight: 600; white-space: nowrap; }}
.best7 {{ color: #2ecc71; }}
tr.unofficial {{ opacity: 0.45; }}
.note {{ font-size: 0.8em; color: #555; margin-top: 10px; }}
@media (max-width: 600px) {{
    .container {{ padding: 10px; }}
    .header h1 {{ font-size: 1.3em; }}
    table {{ font-size: 0.78em; }}
    th {{ padding: 6px 4px; }}
    td {{ padding: 5px 4px; }}
    .nav-links {{ gap: 2px; padding: 3px; }}
    .nav-links a {{ font-size: 0.75em; padding: 5px 10px; }}
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>{year} Cumulative Standings</h1>
    <div class="subtitle">Running total of best-N scores across all {year} league seasons</div>
</div>

{nav_links}

<div class="card">
    <h2>Cumulative Standings</h2>
    <div class="table-wrapper">
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th style="text-align:left">Player</th>
                {league_headers}
                <th>Cumulative</th>
                <th>Weeks</th>
                <th>9-pt Nights</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    </div>
    <div class="note">
        Cumulative = sum of best-N scores from each league season.
        {'<br>* Unofficial participant' if all_unofficial else ''}
    </div>
</div>

</div>
</body>
</html>"""


def generate_alltime_page(server_mode: bool = False) -> str:
    """Generate an all-time records and stats page across all leagues."""
    leagues_config = load_leagues_config()
    all_leagues = sorted(
        leagues_config["leagues"],
        key=lambda lg: (lg.get("created", ""), lg["id"])
    )

    # Gather data
    player_career = defaultdict(lambda: {
        "leagues": 0, "weeks_played": 0, "nines": 0,
        "best_finishes": [], "completed_finishes": [], "weekly_scores_all": [],
        "highest_weekly": 0, "total_best_n": 0, "best_week_rank": 999,
        "best_week_tied": False,
        "attendance_streak": 0, "max_attendance_streak": 0,
        "undefeated_streak": 0, "max_undefeated_streak": 0,
    })

    league_champions = []
    league_standings_history = []  # list of (league_name, standings_order)
    league_week_sequences = []

    for lg_info in all_leagues:
        data = load_league_data(league_id=lg_info["id"])
        league = derive_stats(data)
        unofficial = set(league.get("unofficial_players", []))
        players = league["players"]
        weekly_scores = league["weekly_scores"]
        best_of_n = league["best_of_n"]
        display_name = lg_info.get("display_name", lg_info["name"])
        is_completed_league = lg_info.get("status") == "completed"
        total_weeks_in_league = len(next(iter(weekly_scores.values()))) if weekly_scores else 0
        league_week_sequences.append({
            "official_players": set(p for p in players if p not in unofficial),
            "weekly_scores": weekly_scores,
            "weeks": total_weeks_in_league,
        })

        # Compute standings
        league_results = {}
        overall_omw = league.get("overall_omw", {})
        overall_stats = league["overall_stats"]
        for p in players:
            league_results[p] = {
                "current_best7": best_n_score(weekly_scores[p], best_of_n),
                "total_match_pts": total_match_points(weekly_scores[p]),
            }
        official_players = [p for p in players if p not in unofficial]
        standings = sorted(official_players, key=lambda p: (
            league_results[p]["current_best7"],
            league_results[p]["total_match_pts"],
            overall_omw.get(p, 0),
            overall_stats[p].get("gwp", 0)
        ), reverse=True)

        league_standings_history.append((display_name, standings))

        # Check for champion
        playoffs = data.get("playoffs")
        champion = None
        if playoffs:
            final = playoffs.get("final", {})
            if final.get("games_a") is not None and final.get("games_b") is not None:
                winner, _ = get_match_winner_loser(final)
                champion = winner
        if champion:
            league_champions.append({"league": display_name, "player": champion})

        # Compute per-week rankings for best-week-rank stat
        for w in range(total_weeks_in_league):
            week_participants = [(p, weekly_scores[p][w]) for p in official_players
                                 if weekly_scores[p][w] is not None]
            if not week_participants:
                continue
            week_participants.sort(key=lambda x: x[1], reverse=True)
            for p, score in week_participants:
                rank = sum(1 for _, s in week_participants if s > score) + 1
                tied = sum(1 for _, s in week_participants if s == score) > 1
                if p not in unofficial:
                    current_best = player_career[p]["best_week_rank"]
                    current_tied = player_career[p]["best_week_tied"]
                    if rank < current_best or (rank == current_best and current_tied and not tied):
                        player_career[p]["best_week_rank"] = rank
                        player_career[p]["best_week_tied"] = tied

        for p in players:
            if p in unofficial:
                continue
            pc = player_career[p]
            pc["leagues"] += 1
            scores = weekly_scores[p]
            played_scores = [s for s in scores if s is not None]
            pc["weeks_played"] += len(played_scores)
            pc["nines"] += sum(1 for s in played_scores if s == 9)
            pc["weekly_scores_all"].extend(played_scores)
            if played_scores:
                pc["highest_weekly"] = max(pc["highest_weekly"], max(played_scores))
            pc["total_best_n"] += best_n_score(scores, best_of_n)

            # Finish position
            if p in standings:
                pos = standings.index(p) + 1
                finish = {"league": display_name, "position": pos}
                pc["best_finishes"].append(finish)
                if is_completed_league:
                    pc["completed_finishes"].append(finish)

    # Attendance and undefeated streaks carry across league boundaries.
    for p in player_career:
        pc = player_career[p]
        attend_streak = 0
        undef_streak = 0

        for league_seq in league_week_sequences:
            if p in league_seq["official_players"]:
                scores = list(league_seq["weekly_scores"].get(p, []))
            else:
                scores = []

            while len(scores) < league_seq["weeks"]:
                scores.append(None)

            for s in scores:
                if s is not None:
                    attend_streak += 1
                    pc["max_attendance_streak"] = max(pc["max_attendance_streak"], attend_streak)
                else:
                    attend_streak = 0

                if s == 9:
                    undef_streak += 1
                    pc["max_undefeated_streak"] = max(pc["max_undefeated_streak"], undef_streak)
                elif s is not None:
                    undef_streak = 0

    # Build records
    records = []

    def find_leaders(key_fn, min_val=1):
        """Find all players tied for the lead on a stat."""
        best_val = max(key_fn(p) for p in player_career)
        if best_val < min_val:
            return [], best_val
        leaders = [p for p in player_career if key_fn(p) == best_val]
        return leaders, best_val

    # Longest attendance streak
    leaders, val = find_leaders(lambda p: player_career[p]["max_attendance_streak"])
    if leaders:
        records.append({
            "title": "Longest Attendance Streak",
            "player": ", ".join(leaders),
            "value": f"{val} weeks",
        })

    # Most consecutive undefeated nights
    leaders, val = find_leaders(lambda p: player_career[p]["max_undefeated_streak"])
    if leaders:
        records.append({
            "title": "Longest Undefeated Streak",
            "player": ", ".join(leaders),
            "value": f"{val} weeks",
        })

    # Most 9-point nights
    leaders, val = find_leaders(lambda p: player_career[p]["nines"])
    if leaders:
        records.append({
            "title": "Most Perfect Nights (9 pts)",
            "player": ", ".join(leaders),
            "value": str(val),
        })

    # Most weeks played
    leaders, val = find_leaders(lambda p: player_career[p]["weeks_played"])
    if leaders:
        records.append({
            "title": "Most Weeks Played",
            "player": ", ".join(leaders),
            "value": str(val),
        })

    # Most top-4 finishes
    for p in player_career:
        player_career[p]["_top4"] = sum(1 for f in player_career[p]["completed_finishes"] if f["position"] <= 4)
    leaders, val = find_leaders(lambda p: player_career[p]["_top4"])
    if leaders:
        records.append({
            "title": "Most Top-4 Finishes",
            "player": ", ".join(leaders),
            "value": str(val),
        })

    # Most league titles (1st place finishes)
    for p in player_career:
        player_career[p]["_titles"] = sum(1 for f in player_career[p]["completed_finishes"] if f["position"] == 1)
    leaders, val = find_leaders(lambda p: player_career[p]["_titles"])
    if leaders:
        records.append({
            "title": "Most League Titles (1st Place)",
            "player": ", ".join(leaders),
            "value": str(val),
        })

    # Build records HTML
    records_cards = ""
    for rec in records:
        records_cards += f"""<div class="insight-card">
            <div class="insight-title">{rec['title']}</div>
            <div class="insight-player">{rec['player']}</div>
            <div class="insight-value">{rec['value']}</div>
        </div>"""

    # Champions list
    champions_html = ""
    if league_champions:
        rows_champ = ""
        for lc in league_champions:
            rows_champ += f"<tr><td>{lc['league']}</td><td class='player-name'>{lc['player']}</td></tr>"
        champions_html = f"""<div class="card">
            <h2>League Champions</h2>
            <table><thead><tr><th style="text-align:left">Season</th><th style="text-align:left">Champion</th></tr></thead>
            <tbody>{rows_champ}</tbody></table>
        </div>"""

    # Player career stats table
    career_sorted = sorted(player_career.keys(), key=lambda p: (
        player_career[p]["total_best_n"], player_career[p]["weeks_played"]
    ), reverse=True)

    career_rows = ""
    for p in career_sorted:
        pc = player_career[p]
        best_finish = min((f["position"] for f in pc["completed_finishes"]), default=0)
        best_finish_str = ordinal(best_finish) if best_finish else '—'
        avg_weekly = sum(pc["weekly_scores_all"]) / len(pc["weekly_scores_all"]) if pc["weekly_scores_all"] else 0
        career_rows += f"""<tr>
            <td class="player-name">{p}</td>
            <td data-val="{pc['leagues']}">{pc['leagues']}</td>
            <td data-val="{pc['weeks_played']}">{pc['weeks_played']}</td>
            <td data-val="{pc['nines']}">{pc['nines']}</td>
            <td data-val="{avg_weekly:.2f}">{avg_weekly:.1f}</td>
            <td data-val="{best_finish if best_finish else 999}">{best_finish_str}</td>
        </tr>"""

    nav_links = """<nav class="nav-links">
        <a href="/">League</a>
        <a href="/cumulative">Cumulative 2026</a>
        <a href="/all-time" class="active">All-Time</a>
        <a href="/head-to-head">Head-to-Head</a>
    </nav>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>All-Time Records</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #0a0a1a; color: #e0e0e0; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
.header {{ text-align: center; padding: 24px 0 0; margin-bottom: 24px; }}
.header h1 {{ font-size: 1.8em; color: #e94560; letter-spacing: 1px; margin-bottom: 4px; }}
.header .subtitle {{ color: #888; font-size: 0.85em; }}
.nav-links {{ display: inline-flex; gap: 4px; margin: 16px 0 24px; padding: 4px; background: #0f3460; border-radius: 10px; }}
.nav-links a {{ color: #888; text-decoration: none; padding: 7px 18px; border-radius: 7px; font-size: 0.82em; font-weight: 500; transition: all 0.2s; letter-spacing: 0.3px; }}
.nav-links a:hover {{ color: #e0e0e0; background: rgba(255,255,255,0.06); }}
.nav-links a.active {{ background: #e94560; color: #fff; font-weight: 600; }}
.card {{ background: #16213e; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #0f3460; }}
.card h2 {{ font-size: 1.3em; color: #e94560; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #0f3460; }}
.insights-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }}
.insight-card {{ background: #1a1a2e; border-top: 3px solid #e94560; padding: 16px; border-radius: 8px; text-align: center; }}
.insight-title {{ font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; color: #e94560; margin-bottom: 8px; }}
.insight-player {{ font-size: 1.1em; font-weight: 700; color: #e0e0e0; margin-bottom: 4px; }}
.insight-value {{ font-size: 1.6em; font-weight: 700; color: #2ecc71; margin-bottom: 4px; }}
.table-wrapper {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
th {{ background: #0f3460; color: #e0e0e0; padding: 10px 8px; text-align: center; font-size: 0.82em; text-transform: uppercase; letter-spacing: 0.5px; }}
th.sortable {{ cursor: pointer; user-select: none; }}
th.sortable:hover {{ background: #153a72; }}
td {{ padding: 8px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.04); }}
tr:hover {{ background: rgba(233,69,96,0.06); }}
.rank {{ color: #888; font-size: 0.85em; width: 30px; }}
.player-name {{ text-align: left !important; font-weight: 600; white-space: nowrap; }}
.best7 {{ color: #2ecc71; }}
@media (max-width: 600px) {{
    .container {{ padding: 10px; }}
    .header h1 {{ font-size: 1.3em; }}
    table {{ font-size: 0.78em; }}
    th {{ padding: 6px 4px; }}
    td {{ padding: 5px 4px; }}
    .nav-links {{ gap: 2px; padding: 3px; }}
    .nav-links a {{ font-size: 0.75em; padding: 5px 10px; }}
    .insights-grid {{ grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }}
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>All-Time Records</h1>
    <div class="subtitle">Career stats and records across all league seasons</div>
</div>

{nav_links}

{champions_html}

<div class="card">
    <h2>Records</h2>
    <div class="insights-grid">
        {records_cards}
    </div>
</div>

<div class="card">
    <h2>Career Stats</h2>
    <div class="table-wrapper">
    <table>
        <thead>
            <tr>
                <th style="text-align:left">Player</th>
                <th class="sortable" data-col="1" data-dir="desc">Seasons</th>
                <th class="sortable" data-col="2" data-dir="desc">Weeks</th>
                <th class="sortable" data-col="3" data-dir="desc">9-pt Nights</th>
                <th class="sortable" data-col="4" data-dir="desc">Avg/Week</th>
                <th class="sortable" data-col="5" data-dir="asc">Best Finish</th>
            </tr>
        </thead>
        <tbody>
            {career_rows}
        </tbody>
    </table>
    </div>
</div>

</div>
<script>
document.querySelectorAll('.sortable').forEach(th => {{
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {{
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const col = parseInt(th.dataset.col);
        const defaultDir = th.dataset.dir || 'desc';
        const currentDir = th.dataset.currentDir || defaultDir;
        const newDir = th.dataset.currentDir ? (currentDir === 'asc' ? 'desc' : 'asc') : defaultDir;
        // Reset all headers
        table.querySelectorAll('.sortable').forEach(h => {{
            h.dataset.currentDir = '';
            h.textContent = h.textContent.replace(/ [▲▼]/, '');
        }});
        th.dataset.currentDir = newDir;
        th.textContent = th.textContent + (newDir === 'asc' ? ' ▲' : ' ▼');
        rows.sort((a, b) => {{
            const av = parseFloat(a.cells[col].dataset.val);
            const bv = parseFloat(b.cells[col].dataset.val);
            return newDir === 'asc' ? av - bv : bv - av;
        }});
        rows.forEach(r => tbody.appendChild(r));
    }});
}});
</script>
</body>
</html>"""


def generate_h2h_page(server_mode: bool = False) -> str:
    """Generate the head-to-head records page."""
    leagues_config = load_leagues_config()
    all_leagues = leagues_config["leagues"]

    # Collect H2H data per league and career totals
    h2h_career = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0, "d": 0, "gw": 0, "gl": 0}))
    league_h2h_sections = []
    all_players_set = set()

    for lg_info in all_leagues:
        data = load_league_data(league_id=lg_info["id"])
        matches = data.get("matches", [])
        if not matches:
            continue

        league = derive_stats(data)
        unofficial = set(league.get("unofficial_players", []))
        display_name = lg_info.get("display_name", lg_info["name"])

        # Build H2H for this league
        h2h_league = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0, "d": 0, "gw": 0, "gl": 0}))
        league_players = set()

        for m in matches:
            pa = m["player_a"]
            pb = m.get("player_b")
            if pb is None or pb == "" or pb == "-":
                continue
            ga, gb = m["games_a"], m["games_b"]
            league_players.add(pa)
            league_players.add(pb)
            all_players_set.add(pa)
            all_players_set.add(pb)

            # Game wins
            h2h_league[pa][pb]["gw"] += ga
            h2h_league[pa][pb]["gl"] += gb
            h2h_league[pb][pa]["gw"] += gb
            h2h_league[pb][pa]["gl"] += ga
            h2h_career[pa][pb]["gw"] += ga
            h2h_career[pa][pb]["gl"] += gb
            h2h_career[pb][pa]["gw"] += gb
            h2h_career[pb][pa]["gl"] += ga

            if ga > gb:
                h2h_league[pa][pb]["w"] += 1
                h2h_league[pb][pa]["l"] += 1
                h2h_career[pa][pb]["w"] += 1
                h2h_career[pb][pa]["l"] += 1
            elif gb > ga:
                h2h_league[pb][pa]["w"] += 1
                h2h_league[pa][pb]["l"] += 1
                h2h_career[pb][pa]["w"] += 1
                h2h_career[pa][pb]["l"] += 1
            else:
                h2h_league[pa][pb]["d"] += 1
                h2h_league[pb][pa]["d"] += 1
                h2h_career[pa][pb]["d"] += 1
                h2h_career[pb][pa]["d"] += 1

        # Build league H2H matrix
        # Sort players by total wins in this league
        lp_sorted = sorted(league_players, key=lambda p: sum(
            h2h_league[p][opp]["w"] for opp in league_players
        ), reverse=True)

        league_h2h_sections.append({
            "name": display_name,
            "league_id": lg_info["id"],
            "h2h": h2h_league,
            "players": lp_sorted,
        })

    if not all_players_set:
        return "<html><body><h1>No match data available for head-to-head records</h1></body></html>"

    # Sort career players by total match wins
    career_sorted = sorted(all_players_set, key=lambda p: sum(
        h2h_career[p][opp]["w"] for opp in all_players_set
    ), reverse=True)

    def build_h2h_matrix(players, h2h_data, show_games=False):
        """Build an HTML matrix table for H2H records."""
        # Header row
        header_cells = '<th class="h2h-corner"></th>'
        for p in players:
            short = p[:8] if len(p) > 8 else p
            header_cells += f'<th class="h2h-col-header" title="{p}">{short}</th>'
        header_cells += '<th class="h2h-col-header h2h-total">W-L-D</th>'

        rows = ""
        for p in players:
            cells = f'<td class="h2h-row-header">{p}</td>'
            total_w, total_l, total_d = 0, 0, 0
            for opp in players:
                if p == opp:
                    cells += '<td class="h2h-self"></td>'
                    continue
                rec = h2h_data[p][opp]
                w, l, d = rec["w"], rec["l"], rec["d"]
                total_w += w
                total_l += l
                total_d += d
                total_matches = w + l + d

                if total_matches == 0:
                    cells += '<td class="h2h-empty">-</td>'
                else:
                    # Color based on record
                    if w > l:
                        cls = "h2h-winning"
                    elif l > w:
                        cls = "h2h-losing"
                    elif w == l and total_matches > 0:
                        cls = "h2h-even"
                    else:
                        cls = ""

                    record_str = f"{w}-{l}"
                    if d > 0:
                        record_str += f"-{d}"
                    if show_games:
                        record_str += f'<span class="h2h-games">({rec["gw"]}-{rec["gl"]})</span>'

                    cells += f'<td class="h2h-cell {cls}">{record_str}</td>'

            total_str = f"{total_w}-{total_l}"
            if total_d > 0:
                total_str += f"-{total_d}"
            cells += f'<td class="h2h-cell h2h-total-cell">{total_str}</td>'
            rows += f"<tr>{cells}</tr>"

        return f"""<div class="table-wrapper">
            <table class="h2h-table">
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    # Build notable rivalries
    rivalries = []
    seen_pairs = set()
    for p in career_sorted:
        for opp in career_sorted:
            if p >= opp:
                continue
            pair = (p, opp)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            rec = h2h_career[p][opp]
            total = rec["w"] + rec["l"] + rec["d"]
            if total < 2:
                continue
            rivalries.append({
                "p1": p, "p2": opp,
                "w1": rec["w"], "w2": rec["l"], "d": rec["d"],
                "gw1": rec["gw"], "gw2": rec["gl"],
                "total": total,
            })

    # Sort: most matches first, then most competitive (closest record)
    rivalries.sort(key=lambda r: (-r["total"], abs(r["w1"] - r["w2"])))

    # Highlight cards
    highlights = []

    # Most played rivalry
    if rivalries:
        top = rivalries[0]
        highlights.append({
            "title": "Most Played Rivalry",
            "value": f"{top['p1']} vs {top['p2']}",
            "detail": f"{top['total']} matches ({top['w1']}-{top['w2']}{'-' + str(top['d']) if top['d'] else ''})",
        })

    # Most dominant (best win% with 3+ matches)
    best_dom = None
    best_dom_pct = 0
    for r in rivalries:
        if r["total"] >= 2:
            pct1 = r["w1"] / r["total"]
            pct2 = r["w2"] / r["total"]
            mx = max(pct1, pct2)
            if mx > best_dom_pct:
                best_dom_pct = mx
                if pct1 >= pct2:
                    best_dom = {"winner": r["p1"], "loser": r["p2"], "w": r["w1"], "l": r["w2"], "d": r["d"], "total": r["total"]}
                else:
                    best_dom = {"winner": r["p2"], "loser": r["p1"], "w": r["w2"], "l": r["w1"], "d": r["d"], "total": r["total"]}
    if best_dom and best_dom["w"] > best_dom["l"]:
        rec_str = f"{best_dom['w']}-{best_dom['l']}"
        if best_dom["d"]:
            rec_str += f"-{best_dom['d']}"
        highlights.append({
            "title": "Most Dominant H2H",
            "value": f"{best_dom['winner']} over {best_dom['loser']}",
            "detail": f"{rec_str} ({best_dom_pct*100:.0f}% win rate)",
        })

    # Closest rivalry (most even with 2+ matches)
    closest = None
    for r in rivalries:
        if r["total"] >= 2 and abs(r["w1"] - r["w2"]) <= 1:
            closest = r
            break
    if closest:
        highlights.append({
            "title": "Closest Rivalry",
            "value": f"{closest['p1']} vs {closest['p2']}",
            "detail": f"{closest['w1']}-{closest['w2']}{'-' + str(closest['d']) if closest['d'] else ''} in {closest['total']} matches",
        })

    # Player with most unique opponents
    opp_counts = {}
    for p in career_sorted:
        opp_counts[p] = sum(1 for opp in career_sorted if opp != p and (h2h_career[p][opp]["w"] + h2h_career[p][opp]["l"] + h2h_career[p][opp]["d"]) > 0)
    most_opps = max(opp_counts, key=opp_counts.get)
    highlights.append({
        "title": "Most Opponents Faced",
        "value": most_opps,
        "detail": f"Played against {opp_counts[most_opps]} different players",
    })

    # Best overall H2H win rate (min 5 matches)
    best_wr_player = None
    best_wr = 0
    for p in career_sorted:
        total_w = sum(h2h_career[p][o]["w"] for o in career_sorted)
        total_l = sum(h2h_career[p][o]["l"] for o in career_sorted)
        total = total_w + total_l
        if total >= 5:
            wr = total_w / total
            if wr > best_wr:
                best_wr = wr
                best_wr_player = p
    if best_wr_player:
        total_w = sum(h2h_career[best_wr_player][o]["w"] for o in career_sorted)
        total_l = sum(h2h_career[best_wr_player][o]["l"] for o in career_sorted)
        highlights.append({
            "title": "Best Match Win Rate",
            "value": best_wr_player,
            "detail": f"{total_w}-{total_l} ({best_wr*100:.0f}%)",
        })

    highlights_html = ""
    for h in highlights:
        highlights_html += f"""<div class="insight-card">
            <div class="insight-title">{h['title']}</div>
            <div class="insight-player">{h['value']}</div>
            <div class="insight-detail">{h['detail']}</div>
        </div>"""

    # Career matrix
    career_matrix = build_h2h_matrix(career_sorted, h2h_career, show_games=True)

    # Per-league matrices
    league_sections = ""
    for sec in league_h2h_sections:
        matrix = build_h2h_matrix(sec["players"], sec["h2h"])
        league_sections += f"""<div class="card">
            <h2>{sec['name']}</h2>
            {matrix}
        </div>"""

    # Rivalries table
    rivalries_rows = ""
    for r in rivalries[:20]:
        # Determine who leads
        if r["w1"] > r["w2"]:
            p1_cls, p2_cls = "h2h-leader", ""
        elif r["w2"] > r["w1"]:
            p1_cls, p2_cls = "", "h2h-leader"
        else:
            p1_cls, p2_cls = "", ""

        record = f'{r["w1"]}-{r["w2"]}'
        if r["d"]:
            record += f'-{r["d"]}'
        games = f'{r["gw1"]}-{r["gw2"]}'

        rivalries_rows += f"""<tr>
            <td class="player-name {p1_cls}">{r['p1']}</td>
            <td class="player-name {p2_cls}">{r['p2']}</td>
            <td>{record}</td>
            <td>{games}</td>
            <td>{r['total']}</td>
        </tr>"""

    nav_links = """<nav class="nav-links">
        <a href="/">League</a>
        <a href="/cumulative">Cumulative 2026</a>
        <a href="/all-time">All-Time</a>
        <a href="/head-to-head" class="active">Head-to-Head</a>
    </nav>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Head-to-Head Records</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #0a0a1a; color: #e0e0e0; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
.header {{ text-align: center; padding: 24px 0 0; margin-bottom: 24px; }}
.header h1 {{ font-size: 1.8em; color: #e94560; letter-spacing: 1px; margin-bottom: 4px; }}
.header .subtitle {{ color: #888; font-size: 0.85em; }}
.nav-links {{ display: inline-flex; gap: 4px; margin: 16px 0 24px; padding: 4px; background: #0f3460; border-radius: 10px; }}
.nav-links a {{ color: #888; text-decoration: none; padding: 7px 18px; border-radius: 7px; font-size: 0.82em; font-weight: 500; transition: all 0.2s; letter-spacing: 0.3px; }}
.nav-links a:hover {{ color: #e0e0e0; background: rgba(255,255,255,0.06); }}
.nav-links a.active {{ background: #e94560; color: #fff; font-weight: 600; }}
.card {{ background: #16213e; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #0f3460; }}
.card h2 {{ font-size: 1.3em; color: #e94560; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #0f3460; }}
.insights-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }}
.insight-card {{ background: #1a1a2e; border-top: 3px solid #e94560; padding: 16px; border-radius: 8px; text-align: center; }}
.insight-title {{ font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; color: #e94560; margin-bottom: 8px; }}
.insight-player {{ font-size: 1em; font-weight: 700; color: #e0e0e0; margin-bottom: 4px; }}
.insight-detail {{ font-size: 0.78em; color: #888; }}
.table-wrapper {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
table {{ border-collapse: collapse; font-size: 0.85em; }}
th {{ background: #0f3460; color: #e0e0e0; padding: 10px 8px; text-align: center; font-size: 0.82em; text-transform: uppercase; letter-spacing: 0.5px; }}
td {{ padding: 6px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.04); }}
tr:hover {{ background: rgba(233,69,96,0.06); }}
.player-name {{ text-align: left !important; font-weight: 600; white-space: nowrap; }}

/* H2H Matrix */
.h2h-table {{ width: auto; min-width: 100%; }}
.h2h-corner {{ min-width: 100px; }}
.h2h-col-header {{ font-size: 0.72em; writing-mode: vertical-lr; text-orientation: mixed; transform: rotate(180deg); padding: 12px 4px; min-width: 36px; white-space: nowrap; }}
.h2h-row-header {{ text-align: left !important; font-weight: 600; white-space: nowrap; padding-right: 12px; position: sticky; left: 0; background: #16213e; z-index: 1; }}
tr:hover .h2h-row-header {{ background: #1a2744; }}
.h2h-self {{ background: #0a0a1a; }}
.h2h-empty {{ color: #333; }}
.h2h-cell {{ font-size: 0.85em; white-space: nowrap; min-width: 44px; }}
.h2h-winning {{ color: #2ecc71; font-weight: 600; }}
.h2h-losing {{ color: #e74c3c; }}
.h2h-even {{ color: #f1c40f; }}
.h2h-games {{ display: block; font-size: 0.75em; color: #555; font-weight: 400; }}
.h2h-total {{ border-left: 2px solid #0f3460 !important; }}
.h2h-total-cell {{ font-weight: 600; color: #ccc; border-left: 2px solid rgba(15,52,96,0.5); }}
.h2h-leader {{ color: #2ecc71 !important; }}

/* Rivalries */
.rivalries-table {{ width: 100%; }}
.rivalries-table th {{ text-align: center; }}

.hint {{ font-size: 0.8em; color: #555; margin-top: 10px; }}

@media (max-width: 768px) {{
    .container {{ padding: 10px; }}
    .header h1 {{ font-size: 1.3em; }}
    .nav-links {{ gap: 2px; padding: 3px; }}
    .nav-links a {{ font-size: 0.75em; padding: 5px 10px; }}
    .h2h-col-header {{ font-size: 0.65em; min-width: 28px; padding: 10px 2px; }}
    .h2h-cell {{ min-width: 36px; font-size: 0.78em; }}
    .h2h-row-header {{ font-size: 0.8em; }}
    .insights-grid {{ grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }}
}}
@media (max-width: 480px) {{
    .h2h-col-header {{ font-size: 0.6em; min-width: 24px; }}
    .h2h-cell {{ min-width: 30px; font-size: 0.72em; }}
    .nav-links a {{ font-size: 0.7em; padding: 5px 8px; }}
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>Head-to-Head Records</h1>
    <div class="subtitle">Match records between every pair of players</div>
</div>

{nav_links}

<div class="card">
    <h2>Highlights</h2>
    <div class="insights-grid">
        {highlights_html}
    </div>
</div>

<div class="card">
    <h2>Career Head-to-Head</h2>
    <p class="hint" style="margin-bottom:12px;">Rows show each player's record against the column player. <span class="h2h-winning">Green</span> = winning record, <span class="h2h-losing" style="color:#e74c3c;">red</span> = losing. Game scores shown in parentheses.</p>
    {career_matrix}
</div>

<div class="card">
    <h2>All Rivalries</h2>
    <div class="table-wrapper">
    <table class="rivalries-table">
        <thead>
            <tr>
                <th style="text-align:left">Player 1</th>
                <th style="text-align:left">Player 2</th>
                <th>Match Record</th>
                <th>Game Record</th>
                <th>Matches</th>
            </tr>
        </thead>
        <tbody>
            {rivalries_rows}
        </tbody>
    </table>
    </div>
    <p class="hint">Match record shows Player 1's wins-losses-draws. Game record shows total games won.</p>
</div>

{league_sections}

</div>
</body>
</html>"""


def main():
    html = run_full_pipeline(server_mode=False)

    output_path = os.path.join(PROJECT_DIR, "league_dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Dashboard written to: {output_path}")


if __name__ == "__main__":
    main()
