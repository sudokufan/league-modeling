#!/usr/bin/env python3
"""
MTG League Playoff Probability Simulator
Monte Carlo simulation for a 10-week Magic: The Gathering league.
Loads data from per-league JSON files and derives all stats from raw match data.
"""

import json
import os
import random
from collections import defaultdict

# ============================================================
# Data Loading & League Config
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LEAGUES_DIR = os.path.join(PROJECT_DIR, "leagues")
LEAGUES_CONFIG_FILE = os.path.join(PROJECT_DIR, "leagues_config.json")

GLOBAL_DRAW_RATE = 0.05  # ~5% draw rate from historical data
MAX_WEEKLY_POINTS = 9


def load_leagues_config() -> dict:
    """Load the leagues configuration file."""
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
            omw = sim_omw[p]
            gwp = overall_stats[p]["gwp"]
            standings.append((p, b7, omw, gwp))

        # Tiebreaker: best-7 desc, OMW desc, GWP desc
        standings.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

        for i, (p, b7, omw, gwp) in enumerate(standings):
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


# ============================================================
# API Entry Points
# ============================================================

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


def main():
    """CLI entry point: load active league and print basic stats."""
    data = load_league_data()
    league = derive_stats(data)
    print(f"League: {league['weeks_completed']}/{league['total_weeks']} weeks completed")
    print(f"Players: {len(league['players'])}")
    if league["weeks_completed"] < league["total_weeks"]:
        print(f"Running {league['num_simulations']:,} simulations...")
        results = run_simulation(league)
        status = check_elimination_clinch(results, league["players"], league["playoff_spots"])
        standings = sorted(league["players"], key=lambda p: (
            results[p]["playoff_prob"], results[p]["current_best7"]
        ), reverse=True)
        print(f"\n{'Player':<15} {'Best-7':>6} {'Playoff%':>9} {'Status':<10}")
        print("-" * 42)
        for p in standings:
            r = results[p]
            print(f"{p:<15} {r['current_best7']:>6} {r['playoff_prob']:>8.1f}% {status[p]['status']:<10}")
    else:
        print("League complete.")


if __name__ == "__main__":
    main()
