import hashlib
import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="BF Data", layout="wide")

st.title("BF Data")
st.caption("Daily Home Run Probability Engine")

TRACKER_FILE = "hr_tracker.csv"
CURRENT_SEASON = datetime.now().year

TEAM_ABBR = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}

PARK_FACTORS = {
    "ARI": 1.02, "ATL": 1.04, "BAL": 0.99, "BOS": 1.03, "CHC": 1.01,
    "CWS": 1.02, "CIN": 1.08, "CLE": 0.97, "COL": 1.20, "DET": 0.95,
    "HOU": 1.01, "KC": 0.96, "LAA": 0.99, "LAD": 1.01, "MIA": 0.94,
    "MIL": 1.03, "MIN": 1.00, "NYM": 0.98, "NYY": 1.05, "ATH": 0.93,
    "PHI": 1.06, "PIT": 0.95, "SD": 0.98, "SF": 0.92, "SEA": 0.95,
    "STL": 1.00, "TB": 0.97, "TEX": 1.07, "TOR": 1.04, "WSH": 1.00,
}


def stable_float(key: str, low: float, high: float) -> float:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def ip_to_float(ip_value) -> float:
    if ip_value is None:
        return 0.0
    s = str(ip_value)
    if "." not in s:
        return safe_float(s, 0.0)
    whole, frac = s.split(".", 1)
    whole = safe_float(whole, 0.0)
    frac = safe_int(frac, 0)
    if frac == 0:
        return whole
    if frac == 1:
        return whole + (1 / 3)
    if frac == 2:
        return whole + (2 / 3)
    return safe_float(s, 0.0)


def team_abbr(name: str) -> str:
    return TEAM_ABBR.get(name, name[:3].upper())


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def chunked(items, size):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load_tracker() -> pd.DataFrame:
    columns = [
        "date", "player", "team", "game", "game_pk",
        "hr_probability", "hr_tier", "hr_eligible",
        "result", "result_state", "game_state", "updated_at"
    ]
    if os.path.exists(TRACKER_FILE):
        try:
            df = pd.read_csv(TRACKER_FILE)
            for col in columns:
                if col not in df.columns:
                    df[col] = pd.NA
            return df[columns]
        except Exception:
            pass
    return pd.DataFrame(columns=columns)


def save_tracker(df: pd.DataFrame):
    df.to_csv(TRACKER_FILE, index=False)


def summarize_tracker(df: pd.DataFrame):
    if df.empty:
        return {
            "today_total": 0,
            "today_hits": 0,
            "today_pct": 0.0,
            "all_total": 0,
            "all_hits": 0,
            "all_pct": 0.0,
        }

    df = df.copy()
    df["result_num"] = pd.to_numeric(df["result"], errors="coerce").fillna(0).astype(int)

    today_df = df[df["date"].astype(str) == today_str()]
    today_total = len(today_df)
    today_hits = int(today_df["result_num"].sum())
    today_pct = round((today_hits / today_total) * 100, 2) if today_total else 0.0

    all_total = len(df)
    all_hits = int(df["result_num"].sum())
    all_pct = round((all_hits / all_total) * 100, 2) if all_total else 0.0

    return {
        "today_total": today_total,
        "today_hits": today_hits,
        "today_pct": today_pct,
        "all_total": all_total,
        "all_hits": all_hits,
        "all_pct": all_pct,
    }


def get_lineup_mode(schedule_rows: list[dict]) -> str:
    total = len(schedule_rows)
    confirmed = 0
    partial = 0

    for g in schedule_rows:
        away_c = g.get("away_confirmed_count", 0)
        home_c = g.get("home_confirmed_count", 0)

        if away_c >= 9 and home_c >= 9:
            confirmed += 1
        elif away_c > 0 or home_c > 0:
            partial += 1

    if confirmed == total and total > 0:
        return "CONFIRMED"
    if confirmed > 0 or partial > 0:
        return "MIXED"
    return "PROJECTED"


@st.cache_data(ttl=300)
def fetch_schedule_payload():
    url = (
        "https://statsapi.mlb.com/api/v1/schedule"
        f"?sportId=1&date={today_str()}&hydrate=probablePitcher"
    )
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300)
def get_team_probable_pitcher(team_id: int):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}?hydrate=probablePitcher"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        teams = data.get("teams", [])
        if teams:
            probable = teams[0].get("probablePitcher") or {}
            full_name = probable.get("fullName")
            if full_name and str(full_name).strip():
                return full_name
    except Exception:
        pass
    return None


def resolve_pitcher_name(team_id: int, team_block: dict) -> str:
    probable = (team_block or {}).get("probablePitcher") or {}
    full_name = probable.get("fullName")

    if full_name and str(full_name).strip():
        return full_name

    fallback = get_team_probable_pitcher(team_id)
    if fallback:
        return fallback

    return "Starter Pending"


@st.cache_data(ttl=300)
def get_today_schedule():
    data = fetch_schedule_payload()

    games = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            away_block = game["teams"]["away"]
            home_block = game["teams"]["home"]

            away = away_block["team"]["name"]
            home = home_block["team"]["name"]
            away_id = away_block["team"]["id"]
            home_id = home_block["team"]["id"]

            status = game.get("status", {})
            game_state = status.get("abstractGameState", "Preview")
            detailed_state = status.get("detailedState", "Scheduled")

            games.append({
                "game_pk": game["gamePk"],
                "game_key": f"{team_abbr(away)} @ {team_abbr(home)}",
                "away_team": away,
                "home_team": home,
                "away_team_id": away_id,
                "home_team_id": home_id,
                "away_pitcher": resolve_pitcher_name(away_id, away_block),
                "home_pitcher": resolve_pitcher_name(home_id, home_block),
                "away_pitcher_id": ((away_block.get("probablePitcher") or {}).get("id")),
                "home_pitcher_id": ((home_block.get("probablePitcher") or {}).get("id")),
                "venue": game.get("venue", {}).get("name", "Unknown"),
                "game_time": game.get("gameDate", ""),
                "away_confirmed_count": 0,
                "home_confirmed_count": 0,
                "game_state": game_state,
                "detailed_state": detailed_state,
            })

    return games


@st.cache_data(ttl=300)
def fetch_game_feed(game_pk: int):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


@st.cache_data(ttl=1800)
def get_active_team_hitters(team_id: int):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        hitters = []
        for row in data.get("roster", []):
            pos_type = row.get("position", {}).get("type", "")
            if pos_type != "Pitcher":
                hitters.append({
                    "player_id": row["person"]["id"],
                    "player_name": row["person"]["fullName"],
                    "position": row.get("position", {}).get("abbreviation", ""),
                    "lineup_spot": None,
                    "source": "active_roster_fallback",
                })

        return hitters
    except Exception:
        return []


def _extract_side_candidates_from_feed(side_data: dict):
    players_dict = side_data.get("players", {}) or {}
    batting_order_ids = side_data.get("battingOrder", []) or []

    candidates = []
    batting_order_map = {}

    for idx, pid in enumerate(batting_order_ids, start=1):
        batting_order_map[safe_int(pid)] = idx

    for _, pdata in players_dict.items():
        person = pdata.get("person", {}) or {}
        position = pdata.get("position", {}) or {}
        full_name = person.get("fullName")
        pid = person.get("id")
        pos_type = position.get("type", "")
        pos_abbr = position.get("abbreviation", "")
        lineup_spot = batting_order_map.get(pid)

        if not full_name or pd.isna(pid):
            continue
        if pos_type == "Pitcher":
            continue

        candidates.append({
            "player_id": pid,
            "player_name": full_name,
            "position": pos_abbr,
            "lineup_spot": lineup_spot,
            "source": "confirmed_lineup" if lineup_spot is not None else "game_roster",
        })

    candidates = sorted(
        candidates,
        key=lambda x: (
            x["lineup_spot"] is None,
            x["lineup_spot"] if x["lineup_spot"] is not None else 99,
            x["player_name"],
        ),
    )
    return candidates, len(batting_order_ids)


@st.cache_data(ttl=300)
def get_game_candidate_pools(game_pk: int, away_team_id: int, home_team_id: int):
    feed = fetch_game_feed(game_pk)
    live_box = (((feed.get("liveData") or {}).get("boxscore")) or {})
    teams = live_box.get("teams", {}) or {}

    away_candidates = []
    home_candidates = []
    away_confirmed = 0
    home_confirmed = 0

    if teams:
        away_side = teams.get("away", {}) or {}
        home_side = teams.get("home", {}) or {}

        away_candidates, away_confirmed = _extract_side_candidates_from_feed(away_side)
        home_candidates, home_confirmed = _extract_side_candidates_from_feed(home_side)

    if not away_candidates:
        away_candidates = get_active_team_hitters(away_team_id)
    if not home_candidates:
        home_candidates = get_active_team_hitters(home_team_id)

    return {
        "away_candidates": away_candidates,
        "home_candidates": home_candidates,
        "away_confirmed_count": away_confirmed,
        "home_confirmed_count": home_confirmed,
    }


@st.cache_data(ttl=1800)
def fetch_people_stats(person_ids_tuple: tuple, group: str):
    person_ids = [str(x) for x in person_ids_tuple if pd.notna(x)]
    if not person_ids:
        return {}

    results = {}

    for chunk in chunked(person_ids, 40):
        params = {
            "personIds": ",".join(chunk),
            "hydrate": f"stats(group=[{group}],type=[season,gameLog],season={CURRENT_SEASON})"
        }
        try:
            resp = requests.get("https://statsapi.mlb.com/api/v1/people", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        for person in data.get("people", []):
            pid = person.get("id")
            stats = {"season": {}, "gamelog": []}

            for stat_block in person.get("stats", []):
                stat_type = ((stat_block.get("type") or {}).get("displayName") or "").lower()
                splits = stat_block.get("splits") or []

                if stat_type == "season" and splits:
                    stats["season"] = splits[0].get("stat", {}) or {}
                elif stat_type == "gamelog":
                    game_rows = []
                    for split in splits:
                        game_rows.append({
                            "date": split.get("date"),
                            "stat": split.get("stat", {}) or {}
                        })
                    game_rows = sorted(game_rows, key=lambda x: x.get("date") or "", reverse=True)
                    stats["gamelog"] = game_rows

            results[pid] = stats

    return results


def compute_hitter_live_metrics(player_id: int, hitter_stats_map: dict):
    data = hitter_stats_map.get(player_id, {"season": {}, "gamelog": []})
    season_stat = data.get("season", {}) or {}
    gamelog = (data.get("gamelog", []) or [])[:10]

    if not gamelog:
        return None

    ab = sum(safe_int(g["stat"].get("atBats", 0)) for g in gamelog)
    hits = sum(safe_int(g["stat"].get("hits", 0)) for g in gamelog)
    doubles = sum(safe_int(g["stat"].get("doubles", 0)) for g in gamelog)
    triples = sum(safe_int(g["stat"].get("triples", 0)) for g in gamelog)
    hrs = sum(safe_int(g["stat"].get("homeRuns", 0)) for g in gamelog)
    walks = sum(safe_int(g["stat"].get("baseOnBalls", 0)) for g in gamelog)
    strikeouts = sum(safe_int(g["stat"].get("strikeOuts", 0)) for g in gamelog)
    total_bases = sum(safe_int(g["stat"].get("totalBases", 0)) for g in gamelog)
    rbi = sum(safe_int(g["stat"].get("rbi", 0)) for g in gamelog)
    runs = sum(safe_int(g["stat"].get("runs", 0)) for g in gamelog)

    pa_proxy = max(ab + walks, 1)
    avg = hits / ab if ab else 0.0
    slg = total_bases / ab if ab else 0.0
    iso = max(slg - avg, 0.0)
    xbh = doubles + triples + hrs

    ground_outs = safe_int(season_stat.get("groundOuts", 0))
    air_outs = safe_int(season_stat.get("airOuts", 0))
    out_total = ground_outs + air_outs

    if out_total > 0:
        gb = clip((ground_outs / out_total) * 100, 20, 70)
        fb = clip((air_outs / out_total) * 100, 10, 55)
    else:
        gb = stable_float(f"{player_id}-gb-fallback", 32, 48)
        fb = stable_float(f"{player_id}-fb-fallback", 20, 35)

    ld = clip(100 - gb - fb, 8, 30)

    # stricter proxies so weak recent hitters do not surface as strong looks
    ev = clip(82 + iso * 28 + (xbh / max(ab, 1)) * 35 + avg * 20, 78, 98)
    hard_hit = clip(12 + iso * 90 + (xbh / pa_proxy) * 90 - (strikeouts / pa_proxy) * 10, 8, 60)
    barrel = clip((hrs / max(pa_proxy, 1)) * 120 + (xbh / pa_proxy) * 18 + iso * 14, 0, 18)

    return {
        "EV": round(ev, 1),
        "HardHit%": round(hard_hit, 1),
        "FlyBall%": round(fb, 1),
        "LineDrive%": round(ld, 1),
        "GroundBall%": round(gb, 1),
        "Barrel%": round(barrel, 1),
        "recent_hr": hrs,
        "recent_xbh": xbh,
        "recent_iso": iso,
        "recent_avg": avg,
        "recent_rbi": rbi,
        "recent_runs": runs,
        "recent_ab": ab,
        "recent_pa": pa_proxy,
    }


def compute_pitcher_live_metrics(pitcher_id: int, pitcher_name: str, pitcher_stats_map: dict):
    if pd.isna(pitcher_id):
        return None

    data = pitcher_stats_map.get(pitcher_id, {"season": {}, "gamelog": []})
    season_stat = data.get("season", {}) or {}
    gamelog = data.get("gamelog", []) or []

    if gamelog:
        starts_only = [g for g in gamelog if safe_int(g["stat"].get("gamesStarted", 0)) > 0]
        use_logs = starts_only[:7] if starts_only else gamelog[:7]
    else:
        use_logs = []

    if use_logs:
        ip = sum(ip_to_float(g["stat"].get("inningsPitched", 0)) for g in use_logs)
        hr_allowed = sum(safe_int(g["stat"].get("homeRuns", 0)) for g in use_logs)
        hits_allowed = sum(safe_int(g["stat"].get("hits", 0)) for g in use_logs)
        walks_allowed = sum(safe_int(g["stat"].get("baseOnBalls", 0)) for g in use_logs)
        whip = ((hits_allowed + walks_allowed) / ip) if ip > 0 else 0.0
        hr9 = (hr_allowed * 9 / ip) if ip > 0 else 0.0
        hit9 = (hits_allowed * 9 / ip) if ip > 0 else 0.0
    else:
        ip = ip_to_float(season_stat.get("inningsPitched", 0))
        hr_allowed = safe_int(season_stat.get("homeRuns", 0))
        hits_allowed = safe_int(season_stat.get("hits", 0))
        walks_allowed = safe_int(season_stat.get("baseOnBalls", 0))
        hr9 = (hr_allowed * 9 / ip) if ip > 0 else stable_float(f"{pitcher_name}-hr9-fallback", 0.8, 1.6)
        hit9 = (hits_allowed * 9 / ip) if ip > 0 else stable_float(f"{pitcher_name}-hit9-fallback", 6.5, 10.5)
        whip = ((hits_allowed + walks_allowed) / ip) if ip > 0 else stable_float(f"{pitcher_name}-whip-fallback", 1.0, 1.5)

    barrel_allowed = clip(2.5 + hr9 * 4.0 + (hit9 - 6) * 0.5, 3, 15)
    hard_hit_allowed = clip(22 + hr9 * 8 + (whip - 1.0) * 18, 20, 50)

    return {
        "Pitcher_HR9_Last7": round(hr9, 2),
        "Pitcher_Barrel_Allowed": round(barrel_allowed, 1),
        "Pitcher_HardHit_Allowed": round(hard_hit_allowed, 1),
    }


def build_hitter_metrics(
    player_id: int,
    player_name: str,
    team: str,
    opp_pitcher: str,
    park_factor: float,
    hitter_stats_map: dict,
    pitcher_stats_map: dict,
    opp_pitcher_id=None,
    lineup_spot=None,
    candidate_source="unknown",
):
    live_hitter = compute_hitter_live_metrics(player_id, hitter_stats_map)
    live_pitcher = compute_pitcher_live_metrics(opp_pitcher_id, opp_pitcher, pitcher_stats_map)

    if live_hitter is None:
        ev = stable_float(f"{player_id}-ev", 84, 95)
        hard_hit = stable_float(f"{player_id}-hh", 18, 42)
        fly_ball = stable_float(f"{player_id}-fb", 18, 35)
        line_drive = stable_float(f"{player_id}-ld", 12, 24)
        ground_ball = stable_float(f"{player_id}-gb", 30, 56)
        barrel = stable_float(f"{player_id}-barrel", 2, 10)
        recent_hr = 0
        recent_xbh = 0
        recent_iso = 0.0
        recent_avg = 0.0
        recent_rbi = 0
        recent_runs = 0
        recent_ab = 0
        recent_pa = 0
    else:
        ev = live_hitter["EV"]
        hard_hit = live_hitter["HardHit%"]
        fly_ball = live_hitter["FlyBall%"]
        line_drive = live_hitter["LineDrive%"]
        ground_ball = live_hitter["GroundBall%"]
        barrel = live_hitter["Barrel%"]
        recent_hr = live_hitter["recent_hr"]
        recent_xbh = live_hitter["recent_xbh"]
        recent_iso = live_hitter["recent_iso"]
        recent_avg = live_hitter["recent_avg"]
        recent_rbi = live_hitter["recent_rbi"]
        recent_runs = live_hitter["recent_runs"]
        recent_ab = live_hitter["recent_ab"]
        recent_pa = live_hitter["recent_pa"]

    bats = "L" if int(stable_float(f"{player_id}-bat", 0, 10)) % 2 == 0 else "R"

    if live_pitcher is None:
        pitch_hr9 = stable_float(f"{opp_pitcher}-hr9", 0.7, 1.9)
        pitch_barrel_allowed = stable_float(f"{opp_pitcher}-barrel-allowed", 4, 13)
        pitch_hard_hit_allowed = stable_float(f"{opp_pitcher}-hh-allowed", 30, 48)
    else:
        pitch_hr9 = live_pitcher["Pitcher_HR9_Last7"]
        pitch_barrel_allowed = live_pitcher["Pitcher_Barrel_Allowed"]
        pitch_hard_hit_allowed = live_pitcher["Pitcher_HardHit_Allowed"]

    # still no live pitch-mix feed in this build
    isolate = False
    weather_boost = 0.0
    pullside_boost = stable_float(f"{player_id}-pull", -1, 2)
    park_boost = (park_factor - 1.0) * 20

    gb_status = "PASS"
    if ground_ball >= 50:
        gb_status = "AUTO NO"
    elif ground_ball >= 45:
        gb_status = "HEAVY DOWNGRADE"

    weak_recent_form = (
        recent_hr == 0 and
        recent_xbh <= 1 and
        recent_iso < 0.120 and
        recent_avg < 0.230
    )

    no_power_shape = (
        fly_ball < 20 and
        barrel < 6 and
        hard_hit < 30
    )

    compensator_count = sum([
        barrel >= 12,
        hard_hit >= 42,
        fly_ball >= 33,
        line_drive >= 24,
        pitch_hr9 >= 1.5,
        recent_hr >= 2,
        recent_xbh >= 3,
        park_factor >= 1.05
    ])

    hr_eligible = True
    if ground_ball >= 50:
        hr_eligible = False
    elif ground_ball >= 45 and compensator_count == 0:
        hr_eligible = False
    elif weak_recent_form and no_power_shape:
        hr_eligible = False
    elif recent_ab >= 8 and recent_hr == 0 and recent_xbh == 0 and hard_hit < 28 and barrel < 5:
        hr_eligible = False

    base_score = (
        (ev - 84) * 1.4 +
        (hard_hit - 20) * 1.2 +
        (fly_ball - 18) * 1.4 +
        (line_drive - 12) * 0.7 +
        (barrel - 2) * 2.0 +
        (pitch_hr9 - 0.7) * 14 +
        (pitch_barrel_allowed - 4) * 0.8 +
        (pitch_hard_hit_allowed - 25) * 0.4 +
        pullside_boost +
        park_boost +
        (recent_hr * 2.8) +
        (recent_xbh * 1.1) +
        (recent_iso * 18) +
        (recent_avg * 18)
    )

    if lineup_spot is not None:
        if lineup_spot <= 4:
            base_score += 3
        elif lineup_spot <= 6:
            base_score += 1.5

    if ground_ball < 40:
        base_score += 5
    elif 45 <= ground_ball < 50:
        base_score -= 8
    elif ground_ball >= 50:
        base_score -= 20

    if fly_ball >= 30:
        base_score += 4
    elif fly_ball < 25:
        base_score -= 4

    if weak_recent_form:
        base_score -= 12
    if no_power_shape:
        base_score -= 10
    if recent_hr == 0 and recent_xbh == 0:
        base_score -= 6
    if candidate_source == "active_roster_fallback":
        base_score -= 6

    if not hr_eligible:
        hr_prob = 0.0
    else:
        hr_prob = max(2.0, min(28.0, base_score / 4.5))

    hrr_score = (
        (ev - 84) * 1.0 +
        (hard_hit - 20) * 0.9 +
        (line_drive - 12) * 0.8 +
        (pitch_hard_hit_allowed - 25) * 0.4 +
        park_boost +
        (recent_runs * 0.8) +
        (recent_rbi * 0.8) +
        (recent_avg * 18)
    )
    if lineup_spot is not None:
        hrr_score += max(0, 10 - lineup_spot) * 1.2

    reasons = []
    if candidate_source == "confirmed_lineup":
        reasons.append("Confirmed lineup bat")
    elif candidate_source == "game_roster":
        reasons.append("Game-day roster bat")
    else:
        reasons.append("Roster fallback")

    if ground_ball >= 50:
        reasons.append("GB% 50%+ automatic HR fade")
    elif ground_ball >= 45:
        reasons.append("High GB caution tier")
    else:
        reasons.append("Air-ball profile survives GB gate")

    if ev >= 95:
        reasons.append("Strong recent EV proxy")
    if hard_hit >= 40:
        reasons.append("Hard-hit target")
    if fly_ball >= 30:
        reasons.append("Fly-ball target")
    elif fly_ball < 25:
        reasons.append("Low fly-ball downgrade")
    if line_drive >= 24:
        reasons.append("Strong line-drive rate")
    if barrel >= 12:
        reasons.append("Strong barrel proxy")
    if pitch_hr9 >= 1.5:
        reasons.append("Pitcher HR/9 attack spot")
    elif pitch_hr9 >= 1.3:
        reasons.append("Pitcher HR/9 usable")
    if recent_hr >= 2:
        reasons.append("Recent HR form")
    if recent_xbh >= 3:
        reasons.append("Recent XBH form")
    if weak_recent_form:
        reasons.append("Weak recent HR form")
    if park_factor >= 1.05:
        reasons.append("Strong HR park")

    return {
        "Player": player_name,
        "Team": team,
        "Bats": bats,
        "Lineup Spot": lineup_spot if lineup_spot is not None else "—",
        "EV": round(ev, 1),
        "HardHit%": round(hard_hit, 1),
        "FlyBall%": round(fly_ball, 1),
        "LineDrive%": round(line_drive, 1),
        "GroundBall%": round(ground_ball, 1),
        "Barrel%": round(barrel, 1),
        "Pitcher": opp_pitcher,
        "Pitcher_HR9_Last7": round(pitch_hr9, 2),
        "Pitch_Isolation_Valid": "Unavailable",
        "GB Rule": gb_status,
        "HR Eligible": hr_eligible,
        "HR Probability %": round(hr_prob, 1),
        "HRR Score": round(hrr_score, 1),
        "Why": " | ".join(reasons[:6]),
        "Candidate Source": candidate_source,
    }


def classify_hr_tier(prob: float) -> str:
    if prob >= 18:
        return "CORE TARGET"
    if prob >= 13:
        return "STRONG LOOK"
    if prob >= 8:
        return "SLEEPER"
    return "DEEP"


def sort_for_hr(df: pd.DataFrame) -> pd.DataFrame:
    sortable = df.copy()
    sortable["_lineup_sort"] = pd.to_numeric(sortable["Lineup Spot"], errors="coerce").fillna(99)

    sortable = sortable.sort_values(
        by=[
            "HR Probability %",
            "GroundBall%",
            "HardHit%",
            "FlyBall%",
            "LineDrive%",
            "Barrel%",
            "_lineup_sort",
            "HRR Score",
        ],
        ascending=[False, True, False, False, False, False, True, False],
    ).reset_index(drop=True)

    return sortable.drop(columns=["_lineup_sort"])


@st.cache_data(ttl=900)
def build_daily_dataset():
    schedule = get_today_schedule()

    candidate_map = {}
    hitter_ids = set()
    pitcher_ids = set()

    for game in schedule:
        pools = get_game_candidate_pools(game["game_pk"], game["away_team_id"], game["home_team_id"])
        candidate_map[game["game_pk"]] = pools
        game["away_confirmed_count"] = pools["away_confirmed_count"]
        game["home_confirmed_count"] = pools["home_confirmed_count"]

        for h in pools["away_candidates"]:
            hitter_ids.add(h["player_id"])
        for h in pools["home_candidates"]:
            hitter_ids.add(h["player_id"])

        if pd.notna(game["away_pitcher_id"]):
            pitcher_ids.add(game["away_pitcher_id"])
        if pd.notna(game["home_pitcher_id"]):
            pitcher_ids.add(game["home_pitcher_id"])

    hitter_stats_map = fetch_people_stats(tuple(sorted(hitter_ids)), "hitting")
    pitcher_stats_map = fetch_people_stats(tuple(sorted(pitcher_ids)), "pitching")

    rows = []

    for game in schedule:
        away_abbr = team_abbr(game["away_team"])
        home_abbr = team_abbr(game["home_team"])
        away_park = PARK_FACTORS.get(home_abbr, 1.00)
        home_park = PARK_FACTORS.get(home_abbr, 1.00)

        pools = candidate_map.get(game["game_pk"], {})
        away_candidates = pools.get("away_candidates", [])
        home_candidates = pools.get("home_candidates", [])

        for hitter in away_candidates:
            rows.append({
                "date": today_str(),
                "game_pk": game["game_pk"],
                "game_state": game["game_state"],
                "detailed_state": game["detailed_state"],
                "Game": game["game_key"],
                "Side": "Away",
                **build_hitter_metrics(
                    player_id=hitter["player_id"],
                    player_name=hitter["player_name"],
                    team=away_abbr,
                    opp_pitcher=game["home_pitcher"],
                    park_factor=away_park,
                    hitter_stats_map=hitter_stats_map,
                    pitcher_stats_map=pitcher_stats_map,
                    opp_pitcher_id=game["home_pitcher_id"],
                    lineup_spot=hitter.get("lineup_spot"),
                    candidate_source=hitter.get("source", "unknown"),
                )
            })

        for hitter in home_candidates:
            rows.append({
                "date": today_str(),
                "game_pk": game["game_pk"],
                "game_state": game["game_state"],
                "detailed_state": game["detailed_state"],
                "Game": game["game_key"],
                "Side": "Home",
                **build_hitter_metrics(
                    player_id=hitter["player_id"],
                    player_name=hitter["player_name"],
                    team=home_abbr,
                    opp_pitcher=game["away_pitcher"],
                    park_factor=home_park,
                    hitter_stats_map=hitter_stats_map,
                    pitcher_stats_map=pitcher_stats_map,
                    opp_pitcher_id=game["away_pitcher_id"],
                    lineup_spot=hitter.get("lineup_spot"),
                    candidate_source=hitter.get("source", "unknown"),
                )
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(), schedule

    df["HR Tier"] = df["HR Probability %"].apply(classify_hr_tier)
    df = sort_for_hr(df)
    return df, schedule


def get_team_game_view(df: pd.DataFrame, game_key: str, team: str):
    team_df = df[(df["Game"] == game_key) & (df["Team"] == team)].copy()
    if team_df.empty:
        return team_df, team_df

    hr_pool = team_df[team_df["HR Eligible"]].copy()
    hr_pool = sort_for_hr(hr_pool)

    # confirmed lineup: usually show best 2-5, projected fallback still capped
    selected = hr_pool.head(5)

    hrr = team_df.sort_values(
        by=["HRR Score", "LineDrive%", "HardHit%", "GroundBall%"],
        ascending=[False, False, False, True]
    ).head(5)

    return selected, hrr


@st.cache_data(ttl=120)
def get_boxscore_homers(game_pk: int):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {}

    homer_map = {}

    for side in ["away", "home"]:
        team_data = data.get("teams", {}).get(side, {})
        players = team_data.get("players", {})
        for _, player_data in players.items():
            person = player_data.get("person", {})
            full_name = person.get("fullName")
            batting = player_data.get("stats", {}).get("batting", {})
            hr_count = batting.get("homeRuns", 0)
            if full_name:
                homer_map[full_name] = int(hr_count)

    return homer_map


def sync_tracker_with_board(df: pd.DataFrame):
    tracker = load_tracker()
    date_key = today_str()

    existing_today = tracker[tracker["date"].astype(str) == date_key].copy()
    existing_map = {
        (row["player"], row["team"], row["game"]): row
        for _, row in existing_today.iterrows()
    }

    snapshot_rows = []
    for _, row in df.iterrows():
        key = (row["Player"], row["Team"], row["Game"])
        existing = existing_map.get(key, {})

        snapshot_rows.append({
            "date": date_key,
            "player": row["Player"],
            "team": row["Team"],
            "game": row["Game"],
            "game_pk": row["game_pk"],
            "hr_probability": row["HR Probability %"],
            "hr_tier": row["HR Tier"],
            "hr_eligible": int(bool(row["HR Eligible"])),
            "result": existing.get("result", pd.NA),
            "result_state": existing.get("result_state", "PENDING"),
            "game_state": row["game_state"],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    keep_old = tracker[tracker["date"].astype(str) != date_key].copy()
    merged = pd.concat([keep_old, pd.DataFrame(snapshot_rows)], ignore_index=True)
    save_tracker(merged)
    return merged


def auto_update_tracker_results(tracker: pd.DataFrame, schedule: list[dict]):
    if tracker.empty:
        return tracker

    tracker = tracker.copy()
    date_key = today_str()
    today_mask = tracker["date"].astype(str) == date_key

    for game in schedule:
        game_pk = game["game_pk"]
        game_state = game.get("game_state", "Preview")
        detailed_state = game.get("detailed_state", "Scheduled")

        rows_mask = today_mask & (tracker["game_pk"] == game_pk)
        if not rows_mask.any():
            continue

        if game_state == "Preview":
            tracker.loc[rows_mask, "result_state"] = "PREGAME"
            tracker.loc[rows_mask, "game_state"] = detailed_state
            continue

        homer_map = get_boxscore_homers(game_pk)

        for idx in tracker.index[rows_mask]:
            player = tracker.at[idx, "player"]
            hr_count = int(homer_map.get(player, 0))

            if hr_count > 0:
                tracker.at[idx, "result"] = 1
                tracker.at[idx, "result_state"] = "HOMERED"
            else:
                if game_state == "Final":
                    tracker.at[idx, "result"] = 0
                    tracker.at[idx, "result_state"] = "FINAL_NO_HR"
                else:
                    tracker.at[idx, "result_state"] = "LIVE"

            tracker.at[idx, "game_state"] = detailed_state
            tracker.at[idx, "updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_tracker(tracker)
    return tracker


c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("Update Board", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

df, schedule = build_daily_dataset()
lineup_mode = get_lineup_mode(schedule) if schedule else "PROJECTED"

tracker = sync_tracker_with_board(df)
tracker = auto_update_tracker_results(tracker, schedule)
summary = summarize_tracker(tracker)

with c2:
    st.metric("Games On Slate", len(schedule))
with c3:
    st.metric("Lineup Mode", lineup_mode)
with c4:
    st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

if df.empty:
    st.warning("No games or hitter data loaded.")
    st.stop()

base_tabs = ["HR Probability", "Top 12", "Hits + Runs + RBIs", "Engine Breakdown", "Accuracy Tracker"]
game_tabs = [g["game_key"] for g in schedule]
tabs = st.tabs(base_tabs + game_tabs)

with tabs[0]:
    st.subheader("HR Probability Board")
    hr_df = sort_for_hr(df[df["HR Eligible"]].copy())
    hr_df.insert(0, "Rank", range(1, len(hr_df) + 1))
    st.dataframe(
        hr_df[[
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "HR Probability %", "HR Tier", "GroundBall%", "HardHit%",
            "FlyBall%", "LineDrive%", "Barrel%", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[1]:
    st.subheader("Top 12 HR Candidates")
    top12 = sort_for_hr(df[df["HR Eligible"]].copy()).head(12)
    top12.insert(0, "Rank", range(1, len(top12) + 1))
    st.dataframe(
        top12[[
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "HR Probability %", "HR Tier", "GroundBall%",
            "HardHit%", "FlyBall%", "LineDrive%", "Barrel%", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[2]:
    st.subheader("Hits + Runs + RBIs Board")
    hrr = df.copy().sort_values(
        by=["HRR Score", "LineDrive%", "HardHit%", "GroundBall%"],
        ascending=[False, False, False, True]
    ).reset_index(drop=True)
    hrr.insert(0, "Rank", range(1, len(hrr) + 1))
    st.dataframe(
        hrr[[
            "Rank", "Player", "Team", "Game", "Lineup Spot", "HRR Score",
            "GroundBall%", "LineDrive%", "EV", "HardHit%", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[3]:
    st.subheader("Engine Breakdown")
    st.caption("GB 50%+ = automatic HR no | GB 45–49.9% = heavy downgrade | lineup spots only shown when real.")
    breakdown = sort_for_hr(df.copy())
    st.dataframe(
        breakdown[[
            "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "Candidate Source", "EV", "HardHit%", "FlyBall%",
            "LineDrive%", "GroundBall%", "Barrel%", "Pitcher_HR9_Last7",
            "Pitch_Isolation_Valid", "GB Rule", "HR Eligible",
            "HR Probability %", "HRR Score", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[4]:
    st.subheader("Accuracy Tracker")
    st.caption("Auto-tracks every hitter listed by BF Data and updates HR results as games progress/finalize.")

    a1, a2, a3 = st.columns(3)
    a1.metric("Today's Listed Hitters", summary["today_total"])
    a2.metric("Today's Correct HR", summary["today_hits"])
    a3.metric("Today's Hit Rate %", summary["today_pct"])

    b1, b2, b3 = st.columns(3)
    b1.metric("All-Time Listed Hitters", summary["all_total"])
    b2.metric("All-Time Correct HR", summary["all_hits"])
    b3.metric("All-Time Hit Rate %", summary["all_pct"])

    st.divider()

    today_tracker = tracker[tracker["date"].astype(str) == today_str()].copy()
    if not today_tracker.empty:
        st.caption("Today's tracked hitters")
        st.dataframe(
            today_tracker.sort_values(
                by=["hr_probability", "player"],
                ascending=[False, True]
            )[[
                "player", "team", "game", "hr_probability", "hr_tier",
                "hr_eligible", "result", "result_state", "game_state", "updated_at"
            ]],
            use_container_width=True,
            hide_index=True
        )

    if not tracker.empty:
        st.divider()
        st.caption("Full tracker history")
        st.dataframe(
            tracker.sort_values(
                by=["date", "hr_probability", "player"],
                ascending=[False, False, True]
            ),
            use_container_width=True,
            hide_index=True
        )

for idx, game in enumerate(schedule, start=5):
    with tabs[idx]:
        st.subheader(game["game_key"])
        st.caption(
            f"{game['away_team']} @ {game['home_team']}  |  "
            f"Venue: {game['venue']}  |  "
            f"Away starter: {game['away_pitcher']}  |  "
            f"Home starter: {game['home_pitcher']}"
        )

        gdf = df[df["Game"] == game["game_key"]].copy()
        away_team = team_abbr(game["away_team"])
        home_team = team_abbr(game["home_team"])

        left, right = st.columns(2)

        with left:
            st.markdown(f"### {away_team}")
            st.caption(f"Confirmed hitters: {game.get('away_confirmed_count', 0)}/9")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], away_team)
            if not team_hr.empty:
                st.markdown("**Best HR hitters**")
                st.dataframe(
                    team_hr[[
                        "Player", "HR Tier", "HR Probability %", "GroundBall%",
                        "HardHit%", "FlyBall%", "LineDrive%", "Barrel%", "Lineup Spot", "Why"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )
            st.markdown("**Best Hits + Runs + RBIs**")
            st.dataframe(
                team_hrr[[
                    "Player", "HRR Score", "Lineup Spot", "GroundBall%",
                    "LineDrive%", "Why"
                ]].head(5),
                use_container_width=True,
                hide_index=True
            )

        with right:
            st.markdown(f"### {home_team}")
            st.caption(f"Confirmed hitters: {game.get('home_confirmed_count', 0)}/9")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], home_team)
            if not team_hr.empty:
                st.markdown("**Best HR hitters**")
                st.dataframe(
                    team_hr[[
                        "Player", "HR Tier", "HR Probability %", "GroundBall%",
                        "HardHit%", "FlyBall%", "LineDrive%", "Barrel%", "Lineup Spot", "Why"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )
            st.markdown("**Best Hits + Runs + RBIs**")
            st.dataframe(
                team_hrr[[
                    "Player", "HRR Score", "Lineup Spot", "GroundBall%",
                    "LineDrive%", "Why"
                ]].head(5),
                use_container_width=True,
                hide_index=True
            )
