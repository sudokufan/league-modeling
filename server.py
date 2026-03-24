#!/usr/bin/env python3
"""
MTG League Web Server
Serves the dashboard and provides API for adding match results.
Supports multiple leagues with league switching.
Uses only the Python standard library.
"""

import json
import os
import re
import sys
from datetime import date
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add project directory to path so we can import simulate
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simulate

PORT = 8080


class LeagueHandler(BaseHTTPRequestHandler):

    def _get_requested_league_id(self):
        """Extract league ID from query string, defaulting to active league."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        league_ids = params.get("league", [None])
        return league_ids[0]

    def _get_data_file_for_league(self, league_id=None):
        """Get the data file path for the requested or active league."""
        return simulate.get_league_data_path(league_id)

    def _send_cors_headers(self):
        """Send CORS headers to allow requests from the React dev server."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            if path == "/api/simulate":
                self._serve_simulation()
            elif path == "/api/league-data":
                self._serve_league_data()
            elif path == "/api/leagues":
                self._serve_leagues_list()
            else:
                self.send_error(404, "Not Found")
        else:
            # Non-API routes: serve React frontend from frontend/dist/ if built,
            # otherwise indicate this is an API-only server.
            dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
            if os.path.isdir(dist_dir):
                # Serve static files from the React build
                file_path = os.path.join(dist_dir, path.lstrip("/"))
                if os.path.isfile(file_path):
                    self._serve_static_file(file_path)
                else:
                    # SPA fallback: serve index.html for all non-file routes
                    index_path = os.path.join(dist_dir, "index.html")
                    if os.path.isfile(index_path):
                        self._serve_static_file(index_path)
                    else:
                        self.send_error(404, "Not Found")
            else:
                # No build available — redirect to React dev server
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"API server -- use the React frontend on port 5173")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/add-results":
            self._handle_add_results()
        elif path == "/api/playoff-results":
            self._handle_playoff_results()
        elif path == "/api/leagues/create":
            self._handle_create_league()
        elif path == "/api/leagues/switch":
            self._handle_switch_league()
        elif path == "/api/leagues/complete":
            self._handle_complete_league()
        else:
            self.send_error(404, "Not Found")

    def _serve_static_file(self, file_path):
        """Serve a static file from the filesystem."""
        import mimetypes
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = "application/octet-stream"
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Error serving file: {e}")

    def _serve_simulation(self):
        """Run Monte Carlo simulation and return results as JSON.

        Includes _league_info and _all_leagues alongside the simulation results
        so the frontend has full league context in a single request.
        """
        try:
            league_id = self._get_requested_league_id()
            result = simulate.run_simulation_api(league_id=league_id)
            league_info = simulate.get_league_info(league_id)
            leagues_config = simulate.load_leagues_config()
            result["_league_info"] = league_info
            result["_all_leagues"] = leagues_config["leagues"]
            self._send_json_response(200, result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def _serve_league_data(self):
        """Return derived league stats as JSON.

        Loads raw league data, runs derive_stats() on it, then attaches
        _league_info (the config entry for this league) and _all_leagues
        (the full list from leagues_config.json).

        Note: derive_stats() uses integer dict keys for per_week_omw,
        per_week_mwp, per_week_records, and per_week_opponents (week numbers).
        Python's json.dumps() converts integer keys to strings, so the frontend
        should treat those objects as string-keyed (e.g. {"1": ..., "2": ...}).
        """
        try:
            league_id = self._get_requested_league_id()
            raw_data = simulate.load_league_data(league_id=league_id)
            result = simulate.derive_stats(raw_data)
            league_info = simulate.get_league_info(league_id)
            leagues_config = simulate.load_leagues_config()
            result["_league_info"] = league_info
            result["_all_leagues"] = leagues_config["leagues"]
            self._send_json_response(200, result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def _serve_leagues_list(self):
        """Return the list of all leagues."""
        try:
            config = simulate.load_leagues_config()
            self._send_json_response(200, config)
        except Exception as e:
            self._send_json_error(500, str(e))

    def _handle_add_results(self):
        """Handle adding or deleting match results."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json_error(400, f"Invalid JSON: {e}")
            return

        league_id = self._get_requested_league_id()
        data_file = self._get_data_file_for_league(league_id)

        try:
            with open(data_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            self._send_json_error(500, f"Error reading data file: {e}")
            return

        # Handle delete_week
        if "delete_week" in payload:
            week_to_delete = payload["delete_week"]
            if not isinstance(week_to_delete, int) or week_to_delete < 1:
                self._send_json_error(400, "Invalid week number for deletion")
                return

            original_count = len(data["matches"])
            data["matches"] = [m for m in data["matches"] if m["week"] != week_to_delete]
            removed = original_count - len(data["matches"])

            if removed == 0:
                self._send_json_error(404, f"No matches found for week {week_to_delete}")
                return

            try:
                with open(data_file, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                self._send_json_error(500, f"Error writing data file: {e}")
                return

            self._send_json_response(200, {
                "success": True,
                "message": f"Deleted {removed} matches from week {week_to_delete}"
            })
            return

        # Handle adding results
        if "matches" not in payload or "week" not in payload:
            self._send_json_error(400, "Missing 'week' or 'matches' in request body")
            return

        week = payload["week"]
        new_matches = payload["matches"]

        # Validate
        if not isinstance(week, int) or week < 1:
            self._send_json_error(400, "Invalid week number")
            return

        config = data.get("config", {})
        total_weeks = config.get("total_weeks", 10)
        if week > total_weeks:
            self._send_json_error(400, f"Week {week} exceeds total weeks ({total_weeks})")
            return

        if not isinstance(new_matches, list) or len(new_matches) == 0:
            self._send_json_error(400, "No matches provided")
            return

        # Validate each match
        for i, match in enumerate(new_matches):
            if "player_a" not in match:
                self._send_json_error(400, f"Match {i+1}: missing player_a")
                return
            if "games_a" not in match or "games_b" not in match:
                self._send_json_error(400, f"Match {i+1}: missing game scores")
                return
            ga = match["games_a"]
            gb = match["games_b"]
            if not isinstance(ga, int) or not isinstance(gb, int):
                self._send_json_error(400, f"Match {i+1}: game scores must be integers")
                return
            if ga < 0 or gb < 0:
                self._send_json_error(400, f"Match {i+1}: game scores cannot be negative")
                return

        # Add any new players to the players list
        existing_players = set(data.get("players", []))
        for match in new_matches:
            pa = match["player_a"]
            pb = match.get("player_b")
            if pa and pa not in existing_players:
                data["players"].append(pa)
                existing_players.add(pa)
            if pb and pb != "-" and pb != "" and pb not in existing_players:
                data["players"].append(pb)
                existing_players.add(pb)

        # Remove existing matches for this week (replace mode)
        data["matches"] = [m for m in data["matches"] if m["week"] != week]

        # Add new matches
        for match in new_matches:
            entry = {
                "week": week,
                "round": match.get("round", 1),
                "player_a": match["player_a"],
                "player_b": match.get("player_b"),
                "games_a": match["games_a"],
                "games_b": match["games_b"],
            }
            data["matches"].append(entry)

        # Sort matches by week then round
        data["matches"].sort(key=lambda m: (m["week"], m["round"]))

        # Write back
        try:
            with open(data_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._send_json_error(500, f"Error writing data file: {e}")
            return

        self._send_json_response(200, {
            "success": True,
            "message": f"Added {len(new_matches)} matches for week {week}"
        })

    def _handle_playoff_results(self):
        """Handle saving playoff match results."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json_error(400, f"Invalid JSON: {e}")
            return

        league_id = self._get_requested_league_id()
        data_file = self._get_data_file_for_league(league_id)

        try:
            with open(data_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            self._send_json_error(500, f"Error reading data file: {e}")
            return

        # Ensure playoffs structure exists
        if "playoffs" not in data or data["playoffs"] is None:
            self._send_json_error(400, "Playoff bracket not initialized. Regular season may not be complete.")
            return

        playoffs = data["playoffs"]
        valid_matches = ["semifinal_1", "semifinal_2", "final", "third_place"]
        updated = []

        for match_key in valid_matches:
            if match_key in payload:
                match_data = payload[match_key]
                ga = match_data.get("games_a")
                gb = match_data.get("games_b")

                if not isinstance(ga, int) or not isinstance(gb, int):
                    self._send_json_error(400, f"{match_key}: game scores must be integers")
                    return
                if ga < 0 or gb < 0:
                    self._send_json_error(400, f"{match_key}: game scores cannot be negative")
                    return

                playoffs[match_key]["games_a"] = ga
                playoffs[match_key]["games_b"] = gb
                updated.append(match_key)

        # Auto-advance: populate final and third-place players from semi results
        sf1 = playoffs.get("semifinal_1", {})
        sf2 = playoffs.get("semifinal_2", {})

        if sf1.get("games_a") is not None and sf1.get("games_b") is not None:
            if sf1["games_a"] > sf1["games_b"]:
                sf1_winner, sf1_loser = sf1["player_a"], sf1["player_b"]
            elif sf1["games_b"] > sf1["games_a"]:
                sf1_winner, sf1_loser = sf1["player_b"], sf1["player_a"]
            else:
                sf1_winner, sf1_loser = sf1["player_a"], sf1["player_b"]
        else:
            sf1_winner, sf1_loser = None, None

        if sf2.get("games_a") is not None and sf2.get("games_b") is not None:
            if sf2["games_a"] > sf2["games_b"]:
                sf2_winner, sf2_loser = sf2["player_a"], sf2["player_b"]
            elif sf2["games_b"] > sf2["games_a"]:
                sf2_winner, sf2_loser = sf2["player_b"], sf2["player_a"]
            else:
                sf2_winner, sf2_loser = sf2["player_a"], sf2["player_b"]
        else:
            sf2_winner, sf2_loser = None, None

        if sf1_winner and sf2_winner:
            playoffs["final"]["player_a"] = sf1_winner
            playoffs["final"]["player_b"] = sf2_winner
        if sf1_loser and sf2_loser:
            playoffs["third_place"]["player_a"] = sf1_loser
            playoffs["third_place"]["player_b"] = sf2_loser

        data["playoffs"] = playoffs

        try:
            with open(data_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._send_json_error(500, f"Error writing data file: {e}")
            return

        self._send_json_response(200, {
            "success": True,
            "message": f"Updated playoff results: {', '.join(updated)}"
        })

    def _handle_create_league(self):
        """Create a new league."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json_error(400, f"Invalid JSON: {e}")
            return

        name = payload.get("name", "").strip()
        display_name = payload.get("display_name", "").strip()
        carry_over_players = payload.get("carry_over_players", False)

        if not name:
            self._send_json_error(400, "League name is required")
            return

        # Generate league ID from name
        league_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        config = simulate.load_leagues_config()

        # Check for duplicate ID
        existing_ids = {lg["id"] for lg in config["leagues"]}
        if league_id in existing_ids:
            self._send_json_error(400, f"A league with ID '{league_id}' already exists")
            return

        # Get players from current active league if carrying over
        players = []
        if carry_over_players:
            try:
                active_data = simulate.load_league_data(league_id=config["active_league"])
                players = list(active_data.get("players", []))
            except Exception:
                pass

        # Get default config from current active league
        default_config = {
            "total_weeks": 10,
            "rounds_per_week": 3,
            "best_of_n": 7,
            "playoff_spots": 4,
            "num_simulations": 50000
        }
        try:
            active_data = simulate.load_league_data(league_id=config["active_league"])
            active_config = active_data.get("config", {})
            for key in default_config:
                if key in active_config:
                    default_config[key] = active_config[key]
        except Exception:
            pass

        # Create new league data file
        new_data = {
            "config": default_config,
            "players": players,
            "matches": []
        }

        league_file = f"{league_id}.json"
        league_path = os.path.join(simulate.LEAGUES_DIR, league_file)

        try:
            os.makedirs(simulate.LEAGUES_DIR, exist_ok=True)
            with open(league_path, "w") as f:
                json.dump(new_data, f, indent=2)
        except Exception as e:
            self._send_json_error(500, f"Error creating league file: {e}")
            return

        # Add to config and set as active
        new_league_entry = {
            "id": league_id,
            "name": name,
            "file": league_file,
            "status": "active",
            "created": date.today().isoformat()
        }
        if display_name:
            new_league_entry["display_name"] = display_name
        config["leagues"].append(new_league_entry)
        config["active_league"] = league_id

        try:
            simulate.save_leagues_config(config)
        except Exception as e:
            self._send_json_error(500, f"Error saving config: {e}")
            return

        self._send_json_response(200, {
            "success": True,
            "id": league_id,
            "message": f"League '{name}' created successfully"
        })

    def _handle_switch_league(self):
        """Switch the active league."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json_error(400, f"Invalid JSON: {e}")
            return

        league_id = payload.get("id", "").strip()
        if not league_id:
            self._send_json_error(400, "League ID is required")
            return

        config = simulate.load_leagues_config()

        # Check league exists
        found = False
        for lg in config["leagues"]:
            if lg["id"] == league_id:
                found = True
                break
        if not found:
            self._send_json_error(404, f"League '{league_id}' not found")
            return

        config["active_league"] = league_id
        try:
            simulate.save_leagues_config(config)
        except Exception as e:
            self._send_json_error(500, f"Error saving config: {e}")
            return

        self._send_json_response(200, {
            "success": True,
            "message": f"Switched active league to '{league_id}'"
        })

    def _handle_complete_league(self):
        """Mark a league as completed."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json_error(400, f"Invalid JSON: {e}")
            return

        league_id = payload.get("id", "").strip()
        if not league_id:
            self._send_json_error(400, "League ID is required")
            return

        config = simulate.load_leagues_config()

        found = False
        for lg in config["leagues"]:
            if lg["id"] == league_id:
                lg["status"] = "completed"
                found = True
                break
        if not found:
            self._send_json_error(404, f"League '{league_id}' not found")
            return

        try:
            simulate.save_leagues_config(config)
        except Exception as e:
            self._send_json_error(500, f"Error saving config: {e}")
            return

        self._send_json_response(200, {
            "success": True,
            "message": f"League '{league_id}' marked as completed"
        })

    def _send_json_response(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_error(self, code, message):
        self._send_json_response(code, {"error": message})

    def log_message(self, format, *args):
        """Override to add cleaner logging."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    server = HTTPServer(("0.0.0.0", PORT), LeagueHandler)
    print(f"MTG League API Server starting...")
    print(f"API:       http://localhost:{PORT}/api/leagues")
    print(f"Leagues:   {simulate.LEAGUES_DIR}")
    print(f"Frontend:  http://localhost:5173/ (React dev server)")
    print(f"Press Ctrl+C to stop.")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
