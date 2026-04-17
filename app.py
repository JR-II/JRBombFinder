import hashlib
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import time 
st.set_page_config(page_title="BF Data", layout="wide")

st.title("BF Data")
st.caption("Daily Home Run Probability Engine")
if "last_refresh_time" not in st.session_state:
st.session_state.last_refresh_time = time.time()

if time.time() - st.session_state.last_refresh_time > AUTO_REFRESH_SECONDS:
st.session_state.last_refresh_time = time.time()
st.session_state.force_tracker_refresh = True
else:
st.session_state.force_tracker_refresh = False
AUTO_REFRESH_SECONDS = 120
TRACKER_FILE = "hr_tracker.csv"
LOCK_FILE = "daily_hr_board_lock.csv"
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
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def now_et_string() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")


def chunked(items, size):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def display_lineup_spot(value):
    return value if value is not None else "—"


def normalize_name(name: str) -> str:
    if not name:
        return ""
    s = str(name).lower().strip()
    s = s.replace(".", "")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join([str(x) for x in col if str(x) != "nan"]).strip() for col in df.columns]
    else:
        df.columns = [str(c).strip() for c in df.columns]
    return df


def find_col(df: pd.DataFrame, candidates: list[str]):
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        for key, original in lowered.items():
            if cand in key:
                return original
    return None


def read_html_best_table(urls: list[str], must_have_any: list[str]) -> pd.DataFrame:
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            html = requests.get(url, headers=headers, timeout=30).text
            tables = pd.read_html(html)
        except Exception:
            continue

        for table in tables:
            table = flatten_columns(table)
            cols = [str(c).lower() for c in table.columns]
            if any(any(needle in col for col in cols) for needle in must_have_any):
                return table

    return pd.DataFrame()


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


def load_board_locks() -> pd.DataFrame:
    if os.path.exists(LOCK_FILE):
        try:
            return pd.read_csv(LOCK_FILE)
        except Exception:
            pass
    return pd.DataFrame()


def save_board_locks(df: pd.DataFrame):
    df.to_csv(LOCK_FILE, index=False)


def get_locked_board_for_date(date_key: str) -> pd.DataFrame:
    locks = load_board_locks()
    if locks.empty or "date" not in locks.columns:
        return pd.DataFrame()
    locked = locks[locks["date"].astype(str) == str(date_key)].copy()
    return locked.reset_index(drop=True)


def ensure_daily_board_lock(live_df: pd.DataFrame) -> pd.DataFrame:
    date_key = today_str()
    locked_today = get_locked_board_for_date(date_key)
    if not locked_today.empty:
        return locked_today

    if live_df.empty:
        return live_df.copy()

    snapshot = live_df.copy()
    snapshot["lock_created_at"] = now_et_string()

    locks = load_board_locks()
    merged = pd.concat([locks, snapshot], ignore_index=True)
    save_board_locks(merged)
    return snapshot.reset_index(drop=True)


def isolate_primary_pitch(pitch_mix: dict):
    if not pitch_mix:
        return None

    sorted_mix = sorted(
        pitch_mix.items(),
        key=lambda x: x[1],
        reverse=True
    )

    top_pitch, top_usage = sorted_mix[0]

    if top_usage >= 50:
        return top_pitch

    if len(sorted_mix) > 1:
        second_usage = sorted_mix[1][1]
        if (top_usage - second_usage) >= 20:
            return top_pitch

    return None


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


def summarize_tracker_by_day(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "date",
            "surfaced_hr_picks",
            "correct_hr",
            "hit_rate_pct"
        ])

    work = df.copy()
    work["result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)

    daily = (
        work.groupby("date", as_index=False)
        .agg(
            surfaced_hr_picks=("player", "count"),
            correct_hr=("result_num", "sum"),
        )
    )

    daily["hit_rate_pct"] = daily.apply(
        lambda row: round(
            (row["correct_hr"] / row["surfaced_hr_picks"]) * 100,
            2
        ) if row["surfaced_hr_picks"] else 0.0,
        axis=1
    )

    daily = daily.sort_values("date", ascending=False).reset_index(drop=True)
    return daily


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


def add_rank_column(df: pd.DataFrame) -> pd.DataFrame:
    ranked = df.copy()
    if "Rank" in ranked.columns:
        ranked = ranked.drop(columns=["Rank"])
    ranked.insert(0, "Rank", range(1, len(ranked) + 1))
    return ranked


def strict_statcast_ok(row: pd.Series) -> bool:
    return bool(
        row.get("Statcast Pass") == "Yes"
        and safe_float(row.get("GroundBall%", 999), 999) < 52
        and (
            safe_float(row.get("Barrel%", 0), 0) >= 10
            or safe_float(row.get("AIR%", 0), 0) >= 55
            or safe_float(row.get("xSLG", 0), 0) >= 0.450
        )
    )


def get_gb_explanation(ground_ball: float, barrel: float, air_pct: float, xslg: float) -> str:
    if ground_ball >= 55:
        return "Stay away: 55%+ GB"
    if ground_ball >= 50:
        if barrel >= 12 or xslg >= 0.500 or air_pct >= 60:
            return "Heavy GB, but real damage traits keep it in play"
        return "Heavy GB downgrade"
    if ground_ball >= 45:
        if barrel >= 11 or xslg >= 0.470 or air_pct >= 58:
            return "Borderline GB, but damage traits keep it alive"
        return "Borderline GB caution"
    return "Clean enough launch shape"


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

            linescore = game.get("linescore", {})
            offense = linescore.get("offense", {})

            away_confirmed = 9 if offense.get("battingOrder") else 0
            home_confirmed = 9 if offense.get("battingOrder") else 0

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
                "away_confirmed_count": away_confirmed,
                "home_confirmed_count": home_confirmed,
                "game_state": game_state,
                "detailed_state": detailed_state,
            })

    return games


@st.cache_data(ttl=300)
def fetch_boxscore(game_pk: int):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


@st.cache_data(ttl=1800)
def get_team_hitters(team_id: int):
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
                    "position": row.get("position", {}).get("abbreviation", "")
                })

        return hitters
    except Exception:
        return []


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


@st.cache_data(ttl=21600)
def fetch_savant_batter_map(year: int):
    expected_urls = [
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=batter&year={year}",
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics?year={year}",
    ]
    percentile_urls = [
        f"https://baseballsavant.mlb.com/leaderboard/percentile-rankings?type=batter&year={year}",
        f"https://baseballsavant.mlb.com/leaderboard/percentile-rankings?year={year}",
    ]
    batted_urls = [
        f"https://baseballsavant.mlb.com/leaderboard/batted-ball?type=batter&year={year}",
        f"https://baseballsavant.mlb.com/leaderboard/batted-ball?year={year}",
    ]

    expected_df = read_html_best_table(expected_urls, ["player", "xslg", "xwoba"])
    percentile_df = read_html_best_table(percentile_urls, ["player", "brl", "ev", "hardhit"])
    batted_df = read_html_best_table(batted_urls, ["player", "air", "ground", "gb"])

    result = {}

    def upsert_row(df: pd.DataFrame, source: str):
        if df.empty:
            return

        player_col = find_col(df, ["player"])
        if player_col is None:
            return

        xslg_col = find_col(df, ["xslg"])
        xwoba_col = find_col(df, ["xwoba"])
        xiso_col = find_col(df, ["xiso"])
        brl_col = find_col(df, ["brl%"])
        ev_col = find_col(df, [" max ev", " ev "])
        hardhit_col = find_col(df, ["hardhit", "hard hit"])
        la_col = find_col(df, [" la ", "launch angle"])
        gb_col = find_col(df, ["gb%"])
        fb_col = find_col(df, ["fb%"])
        ld_col = find_col(df, ["ld%"])
        air_col = find_col(df, ["air%"])

        for _, row in df.iterrows():
            raw_name = row.get(player_col)
            name = normalize_name(raw_name)
            if not name:
                continue

            if name not in result:
                result[name] = {
                    "Savant_xSLG": pd.NA,
                    "Savant_xwOBA": pd.NA,
                    "Savant_xISO": pd.NA,
                    "Savant_Barrel%": pd.NA,
                    "Savant_EV": pd.NA,
                    "Savant_HardHit%": pd.NA,
                    "Savant_LA": pd.NA,
                    "Savant_GB%": pd.NA,
                    "Savant_FB%": pd.NA,
                    "Savant_LD%": pd.NA,
                    "Savant_AIR%": pd.NA,
                }

            if xslg_col is not None and pd.notna(row.get(xslg_col)):
                result[name]["Savant_xSLG"] = safe_float(row.get(xslg_col), pd.NA)
            if xwoba_col is not None and pd.notna(row.get(xwoba_col)):
                result[name]["Savant_xwOBA"] = safe_float(row.get(xwoba_col), pd.NA)
            if xiso_col is not None and pd.notna(row.get(xiso_col)):
                result[name]["Savant_xISO"] = safe_float(row.get(xiso_col), pd.NA)
            if brl_col is not None and pd.notna(row.get(brl_col)):
                result[name]["Savant_Barrel%"] = safe_float(row.get(brl_col), pd.NA)
            if ev_col is not None and pd.notna(row.get(ev_col)):
                result[name]["Savant_EV"] = safe_float(row.get(ev_col), pd.NA)
            if hardhit_col is not None and pd.notna(row.get(hardhit_col)):
                result[name]["Savant_HardHit%"] = safe_float(row.get(hardhit_col), pd.NA)
            if la_col is not None and pd.notna(row.get(la_col)):
                result[name]["Savant_LA"] = safe_float(row.get(la_col), pd.NA)
            if gb_col is not None and pd.notna(row.get(gb_col)):
                result[name]["Savant_GB%"] = safe_float(row.get(gb_col), pd.NA)
            if fb_col is not None and pd.notna(row.get(fb_col)):
                result[name]["Savant_FB%"] = safe_float(row.get(fb_col), pd.NA)
            if ld_col is not None and pd.notna(row.get(ld_col)):
                result[name]["Savant_LD%"] = safe_float(row.get(ld_col), pd.NA)
            if air_col is not None and pd.notna(row.get(air_col)):
                result[name]["Savant_AIR%"] = safe_float(row.get(air_col), pd.NA)

    upsert_row(expected_df, "expected")
    upsert_row(percentile_df, "percentile")
    upsert_row(batted_df, "batted")
    return result


def compute_hitter_live_metrics_from_map(player_id: int, stats_map: dict):
    data = stats_map.get(player_id, {"season": {}, "gamelog": []})
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
    games_played_recent = len(gamelog)

    pa_proxy = max(ab + walks, 1)
    avg = hits / ab if ab else 0.0
    slg = total_bases / ab if ab else 0.0
    iso = max(slg - avg, 0.0)
    xbh = doubles + triples + hrs

    ground_outs = safe_int(season_stat.get("groundOuts", 0))
    air_outs = safe_int(season_stat.get("airOuts", 0))
    out_total = ground_outs + air_outs

    if out_total > 0:
        gb = clip((ground_outs / out_total) * 100, 20, 65)
        fb = clip((air_outs / out_total) * 100, 15, 55)
    else:
        gb = stable_float(f"{player_id}-gb-fallback", 32, 48)
        fb = stable_float(f"{player_id}-fb-fallback", 22, 38)

    ld = clip(100 - gb - fb, 12, 30)

    ev = clip(86 + iso * 18 + (xbh / max(ab, 1)) * 45 + (hits / pa_proxy) * 8, 84, 99)
    hard_hit = clip(26 + iso * 85 + (xbh / pa_proxy) * 140 - (strikeouts / pa_proxy) * 10, 20, 60)
    barrel = clip(2 + iso * 35 + (hrs / pa_proxy) * 160, 1, 20)

    season_games = safe_int(season_stat.get("gamesPlayed", 0))
    season_ab = safe_int(season_stat.get("atBats", 0))

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
        "recent_pa": pa_proxy,
        "recent_games": games_played_recent,
        "season_games": season_games,
        "season_ab": season_ab,
    }


def compute_pitcher_live_metrics_from_map(pitcher_id: int, pitcher_name: str, stats_map: dict):
    if pd.isna(pitcher_id):
        return None

    data = stats_map.get(pitcher_id, {"season": {}, "gamelog": []})
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

        hr9 = (hr_allowed * 9 / ip) if ip > 0 else 0.0
        hit9 = (hits_allowed * 9 / ip) if ip > 0 else 0.0
        whip = ((hits_allowed + walks_allowed) / ip) if ip > 0 else 0.0
    else:
        ip = ip_to_float(season_stat.get("inningsPitched", 0))
        hr_allowed = safe_int(season_stat.get("homeRuns", 0))
        hits_allowed = safe_int(season_stat.get("hits", 0))
        walks_allowed = safe_int(season_stat.get("baseOnBalls", 0))

        hr9 = (hr_allowed * 9 / ip) if ip > 0 else stable_float(f"{pitcher_name}-hr9-fallback", 0.8, 1.6)
        hit9 = (hits_allowed * 9 / ip) if ip > 0 else stable_float(f"{pitcher_name}-hit9-fallback", 6.5, 10.5)
        whip = ((hits_allowed + walks_allowed) / ip) if ip > 0 else stable_float(f"{pitcher_name}-whip-fallback", 1.0, 1.5)

    barrel_allowed = clip(2.5 + hr9 * 4.0 + (hit9 - 6) * 0.5, 3, 15)
    hard_hit_allowed = clip(26 + hr9 * 8 + (whip - 1.0) * 18, 25, 50)

    return {
        "Pitcher_HR9_Last7": round(hr9, 2),
        "Pitcher_Barrel_Allowed": round(barrel_allowed, 1),
        "Pitcher_HardHit_Allowed": round(hard_hit_allowed, 1),
    }


def extract_boxscore_team_hitters(game_pk: int, side: str):
    box = fetch_boxscore(game_pk)
    team_box = box.get("teams", {}).get(side, {}) or {}
    players = team_box.get("players", {}) or {}

    hitters = []
    for _, pdata in players.items():
        pos_type = ((pdata.get("position") or {}).get("type") or (pdata.get("primaryPosition") or {}).get("type") or "")
        if pos_type == "Pitcher":
            continue

        person = pdata.get("person", {}) or {}
        pid = person.get("id")
        full_name = person.get("fullName")
        batting_order = pdata.get("battingOrder")

        lineup_spot = None
        if batting_order:
            try:
                lineup_spot = int(str(batting_order)) // 100
            except Exception:
                lineup_spot = None

        hitters.append({
            "player_id": pid,
            "player_name": full_name,
            "lineup_spot": lineup_spot,
            "confirmed": lineup_spot is not None,
        })

    dedup = {}
    for h in hitters:
        if h["player_id"] is not None:
            dedup[h["player_id"]] = h

    return list(dedup.values())


def get_team_candidate_hitters(game_pk: int, team_id: int, side: str, savant_batter_map: dict):
    boxscore_hitters = extract_boxscore_team_hitters(game_pk, side)

    confirmed = [h for h in boxscore_hitters if h["confirmed"]]
    if confirmed:
        confirmed = sorted(confirmed, key=lambda x: x["lineup_spot"] or 99)
        return confirmed[:9], "CONFIRMED"

    candidate_pool = boxscore_hitters
    if not candidate_pool:
        roster_hitters = get_team_hitters(team_id)
        candidate_pool = [{
            "player_id": h["player_id"],
            "player_name": h["player_name"],
            "lineup_spot": None,
            "confirmed": False,
        } for h in roster_hitters]

    if not candidate_pool:
        return [], "PROJECTED"

    stats_map = fetch_people_stats(tuple(h["player_id"] for h in candidate_pool if h["player_id"]), "hitting")

    scored = []
    for h in candidate_pool:
        metrics = compute_hitter_live_metrics_from_map(h["player_id"], stats_map)
        if metrics is None:
            continue

        sav = savant_batter_map.get(normalize_name(h["player_name"]), {})
        sav_brl = safe_float(sav.get("Savant_Barrel%"), metrics["Barrel%"])
        sav_hh = safe_float(sav.get("Savant_HardHit%"), metrics["HardHit%"])
        sav_air = safe_float(sav.get("Savant_AIR%"), 100 - metrics["GroundBall%"])
        sav_xslg = safe_float(sav.get("Savant_xSLG"), 0.0)
        sav_gb = safe_float(sav.get("Savant_GB%"), metrics["GroundBall%"])

        projected_statcast_pass = (
            sav_brl >= 10 or
            (sav_hh >= 40 and sav_air >= 55) or
            sav_xslg >= 0.450
        )

        projected_recent_pass = (
            metrics["recent_hr"] >= 1 or
            metrics["recent_xbh"] >= 3 or
            metrics["recent_iso"] >= 0.180
        )

        gb_survival = (
            sav_gb < 50
            or (
                sav_gb < 54 and (
                    sav_brl >= 11 or
                    sav_air >= 58 or
                    sav_xslg >= 0.470
                )
            )
        )

        strong_projected_candidate = (
            metrics["recent_pa"] >= 12 and
            metrics["season_games"] >= 3 and
            metrics["season_ab"] >= 8 and
            projected_statcast_pass and
            (
                projected_recent_pass
                or sav_brl >= 13
                or sav_xslg >= 0.500
            ) and
            gb_survival
        )

        if not strong_projected_candidate:
            continue

        lineup_likelihood = (
            sav_brl * 2.4 +
            sav_hh * 1.0 +
            sav_air * 0.45 +
            sav_xslg * 100 +
            metrics["recent_hr"] * 5.5 +
            metrics["recent_xbh"] * 2.0 +
            metrics["recent_iso"] * 18
        )

        scored.append({
            **h,
            "lineup_likelihood": lineup_likelihood
        })

    scored = sorted(scored, key=lambda x: x["lineup_likelihood"], reverse=True)[:6]

    for hitter in scored:
        hitter["lineup_spot"] = None

    return scored, "PROJECTED"


def qualifies_hr_profile(
    barrel: float,
    hard_hit: float,
    air_pct: float,
    xslg: float,
    xwoba: float,
    ground_ball: float,
    recent_hr: int,
    recent_xbh: int,
    recent_iso: float,
    recent_pa: float,
    pitch_hr9: float,
    pitch_barrel_allowed: float,
    pitch_hard_hit_allowed: float,
    lineup_source: str,
):
    elite_override = (
        barrel >= 14 or
        hard_hit >= 48 or
        (air_pct >= 65 and hard_hit >= 42) or
        xslg >= 0.520
    )

    statcast_pass = (
        barrel >= 10 or
        (hard_hit >= 40 and air_pct >= 55) or
        xslg >= 0.450 or
        xwoba >= 0.340 or
        elite_override
    )

    recent_form_pass = (
        recent_hr >= 1 or
        recent_xbh >= 3 or
        recent_iso >= 0.180
    )

    pitcher_attackable = (
        pitch_hr9 >= 1.3 or
        pitch_barrel_allowed >= 8 or
        pitch_hard_hit_allowed >= 40
    )

    awful_hr_shape = (
        ground_ball >= 58 or
        (ground_ball >= 55 and air_pct <= 35) or
        (barrel < 5 and hard_hit < 30 and recent_hr == 0)
    )

    weak_recent_profile = (
        recent_hr == 0 and
        recent_xbh <= 1 and
        hard_hit < 35 and
        barrel < 8 and
        air_pct < 50
    )

    lineup_pass = (
        lineup_source == "CONFIRMED" or
        (lineup_source == "PROJECTED" and recent_hr >= 1 and recent_xbh >= 3 and statcast_pass)
    )

    borderline_gb_survival = (
        ground_ball < 50 or
        elite_override or
        (
            ground_ball < 55 and pitcher_attackable and (
                barrel >= 11 or
                air_pct >= 58 or
                xslg >= 0.470
            )
        )
    )

    hr_eligible = True

    if recent_pa < 8:
        hr_eligible = False
    elif awful_hr_shape and not elite_override:
        hr_eligible = False
    elif ground_ball >= 55 and not elite_override:
        hr_eligible = False
    elif not borderline_gb_survival:
        hr_eligible = False
    elif not statcast_pass:
        hr_eligible = False
    elif not recent_form_pass and not elite_override:
        hr_eligible = False
    elif weak_recent_profile:
        hr_eligible = False
    elif not lineup_pass:
        hr_eligible = False

    return {
        "hr_eligible": hr_eligible,
        "elite_override": elite_override,
        "statcast_pass": statcast_pass,
        "recent_form_pass": recent_form_pass,
        "pitcher_attackable": pitcher_attackable,
        "awful_hr_shape": awful_hr_shape,
        "weak_recent_profile": weak_recent_profile,
    }


def build_hitter_metrics(
    player_id: int,
    player_name: str,
    team: str,
    opp_pitcher: str,
    park_factor: float,
    opp_pitcher_id,
    lineup_spot,
    lineup_source,
    hitter_stats_map,
    pitcher_stats_map,
    savant_batter_map,
):
    live_hitter = compute_hitter_live_metrics_from_map(player_id, hitter_stats_map)
    live_pitcher = compute_pitcher_live_metrics_from_map(
        opp_pitcher_id,
        opp_pitcher,
        pitcher_stats_map,
    )

    if live_hitter is None:
        return None

    sav = savant_batter_map.get(normalize_name(player_name), {})

    ev = safe_float(sav.get("Savant_EV"), live_hitter["EV"])
    hard_hit = safe_float(sav.get("Savant_HardHit%"), live_hitter["HardHit%"])
    fly_ball = safe_float(sav.get("Savant_FB%"), live_hitter["FlyBall%"])
    line_drive = safe_float(sav.get("Savant_LD%"), live_hitter["LineDrive%"])
    ground_ball = safe_float(sav.get("Savant_GB%"), live_hitter["GroundBall%"])
    barrel = safe_float(sav.get("Savant_Barrel%"), live_hitter["Barrel%"])
    air_pct = safe_float(sav.get("Savant_AIR%"), max(0.0, 100 - ground_ball))
    xslg = safe_float(sav.get("Savant_xSLG"), 0.0)
    xwoba = safe_float(sav.get("Savant_xwOBA"), 0.0)
    xiso = safe_float(sav.get("Savant_xISO"), live_hitter["recent_iso"])

    recent_hr = live_hitter["recent_hr"]
    recent_xbh = live_hitter["recent_xbh"]
    recent_iso = live_hitter["recent_iso"]
    recent_avg = live_hitter["recent_avg"]
    recent_rbi = live_hitter["recent_rbi"]
    recent_runs = live_hitter["recent_runs"]
    recent_pa = live_hitter["recent_pa"]

    display_spot = display_lineup_spot(lineup_spot)
    bats = "L" if int(stable_float(f"{player_id}-bat", 0, 10)) % 2 == 0 else "R"

    if live_pitcher is None:
        pitch_hr9 = stable_float(f"{opp_pitcher}-hr9", 0.7, 1.9)
        pitch_barrel_allowed = stable_float(f"{opp_pitcher}-barrel-allowed", 4, 13)
        pitch_hard_hit_allowed = stable_float(f"{opp_pitcher}-hh-allowed", 30, 48)
    else:
        pitch_hr9 = live_pitcher["Pitcher_HR9_Last7"]
        pitch_barrel_allowed = live_pitcher["Pitcher_Barrel_Allowed"]
        pitch_hard_hit_allowed = live_pitcher["Pitcher_HardHit_Allowed"]

    pullside_boost = stable_float(f"{player_id}-pull", -1, 3)
    park_boost = (park_factor - 1.0) * 20

    pitch_mix_example = {
        "FF": stable_float(f"{opp_pitcher}-ff", 25, 55),
        "SL": stable_float(f"{opp_pitcher}-sl", 10, 40),
        "CH": stable_float(f"{opp_pitcher}-ch", 5, 25),
    }

    primary_pitch = isolate_primary_pitch(pitch_mix_example)

    pitch_isolation_bonus = -2.5
    pitch_isolation_valid = "No"

    if primary_pitch is not None:
        pitch_isolation_valid = "Yes"
        hitter_pitch_fit = stable_float(
            f"{player_name}-{primary_pitch}-fit",
            -2.0,
            4.5,
        )
        pitch_isolation_bonus = hitter_pitch_fit

    gb_status = "PASS"
    if ground_ball >= 55:
        gb_status = "AUTO NO"
    elif ground_ball >= 50:
        gb_status = "HEAVY DOWNGRADE"
    elif ground_ball >= 45:
        gb_status = "CAUTION"

    qual = qualifies_hr_profile(
        barrel=barrel,
        hard_hit=hard_hit,
        air_pct=air_pct,
        xslg=xslg,
        xwoba=xwoba,
        ground_ball=ground_ball,
        recent_hr=recent_hr,
        recent_xbh=recent_xbh,
        recent_iso=recent_iso,
        recent_pa=recent_pa,
        pitch_hr9=pitch_hr9,
        pitch_barrel_allowed=pitch_barrel_allowed,
        pitch_hard_hit_allowed=pitch_hard_hit_allowed,
        lineup_source=lineup_source,
    )

    hr_eligible = qual["hr_eligible"]
    statcast_pass = qual["statcast_pass"]
    recent_form_pass = qual["recent_form_pass"]
    pitcher_attackable = qual["pitcher_attackable"]
    elite_override = qual["elite_override"]
    awful_hr_shape = qual["awful_hr_shape"]
    weak_recent_profile = qual["weak_recent_profile"]

    base_score = (
        (barrel - 4) * 4.2 +
        (hard_hit - 28) * 2.5 +
        (air_pct - 45) * 1.2 +
        (ev - 87) * 1.1 +
        (xslg * 100) * 1.2 +
        (xiso * 100) * 0.7 +
        pitch_isolation_bonus +
        (pitch_hr9 - 0.7) * 10.0 +
        (pitch_barrel_allowed - 4) * 0.9 +
        (pitch_hard_hit_allowed - 30) * 0.4 +
        (recent_hr * 3.2) +
        (recent_xbh * 1.5) +
        (recent_iso * 24.0) +
        pullside_boost +
        park_boost
    )

    if lineup_spot is not None:
        if lineup_spot <= 4:
            base_score += 3.5
        elif lineup_spot <= 6:
            base_score += 1.5
        else:
            base_score -= 1.0

    if ground_ball < 40:
        base_score += 4.0
    elif 45 <= ground_ball < 50:
        base_score -= 7.0
    elif 50 <= ground_ball < 55:
        base_score -= 14.0
    elif ground_ball >= 55:
        base_score -= 25.0

    if air_pct >= 65:
        base_score += 5.0
    elif air_pct >= 55:
        base_score += 2.0
    elif air_pct < 45:
        base_score -= 7.0

    if barrel >= 14:
        base_score += 6.0
    elif barrel < 8:
        base_score -= 7.0

    if hard_hit >= 45:
        base_score += 5.0
    elif hard_hit < 35:
        base_score -= 7.0

    if not pitcher_attackable:
        base_score -= 4.0
    if weak_recent_profile:
        base_score -= 10.0
    if awful_hr_shape:
        base_score -= 14.0
    if lineup_source == "PROJECTED" and lineup_spot is None:
        base_score -= 4.0
    if elite_override and ground_ball < 55:
        base_score += 2.5

    if not hr_eligible:
        hr_prob = 0.0
    else:
        hr_prob = max(3.0, min(28.0, base_score / 6.8))

    hrr_score = (
        (ev - 87) * 1.1 +
        (hard_hit - 28) * 1.0 +
        (line_drive - 14) * 0.9 +
        (pitch_hard_hit_allowed - 30) * 0.4 +
        park_boost +
        (recent_runs * 0.7) +
        (recent_rbi * 0.7) +
        (recent_avg * 15)
    )
    if lineup_spot is not None:
        hrr_score += max(0, 10 - lineup_spot) * 1.5

    gb_note = get_gb_explanation(ground_ball, barrel, air_pct, xslg)

    reasons = []
    reasons.append(f"{lineup_source} lineup pool")
    reasons.append("Statcast damage pass" if statcast_pass else "Failed Statcast damage")
    reasons.append("Pitcher attackable" if pitcher_attackable else "Pitcher less attackable")
    reasons.append("Recent damage form" if recent_form_pass else "Weak recent form")
    reasons.append(gb_note)
    reasons.append("Pitch isolated" if pitch_isolation_valid == "Yes" else "No isolated pitch edge")

    if barrel >= 12:
        reasons.append("Strong barrel")
    elif hard_hit >= 40:
        reasons.append("Hard-hit target")
    elif air_pct >= 55:
        reasons.append("Air-ball target")

    strict_flag = strict_statcast_ok(pd.Series({
        "Statcast Pass": "Yes" if statcast_pass else "No",
        "GroundBall%": ground_ball,
        "Barrel%": barrel,
        "AIR%": air_pct,
        "xSLG": xslg,
    }))

    return {
        "Player": player_name,
        "Team": team,
        "Bats": bats,
        "Lineup Spot": display_spot,
        "Lineup Source": lineup_source,
        "EV": round(ev, 1),
        "HardHit%": round(hard_hit, 1),
        "FlyBall%": round(fly_ball, 1),
        "LineDrive%": round(line_drive, 1),
        "GroundBall%": round(ground_ball, 1),
        "Barrel%": round(barrel, 1),
        "AIR%": round(air_pct, 1),
        "xSLG": round(xslg, 3) if xslg else 0.0,
        "xwOBA": round(xwoba, 3) if xwoba else 0.0,
        "Pitcher": opp_pitcher,
        "Pitcher_HR9_Last7": round(pitch_hr9, 2),
        "Pitcher_Barrel_Allowed": round(pitch_barrel_allowed, 1),
        "Pitcher_HardHit_Allowed": round(pitch_hard_hit_allowed, 1),
        "Statcast Pass": "Yes" if statcast_pass else "No",
        "Recent Form Pass": "Yes" if recent_form_pass else "No",
        "Pitcher Attackable": "Yes" if pitcher_attackable else "No",
        "Pitch_Isolation_Valid": pitch_isolation_valid,
        "GB Rule": gb_status,
        "GB Note": gb_note,
        "HR Eligible": hr_eligible,
        "Strict Statcast": "Yes" if strict_flag else "No",
        "HR Probability %": round(hr_prob, 1),
        "HRR Score": round(hrr_score, 1),
        "Why": " | ".join(reasons[:6]),
    }


def classify_hr_tier(prob: float) -> str:
    if prob >= 20:
        return "CORE TARGET"
    if prob >= 14:
        return "STRONG LOOK"
    if prob >= 9:
        return "SLEEPER"
    return "DEEP"


def sort_for_hr(df: pd.DataFrame) -> pd.DataFrame:
    sortable = df.copy()
    sortable["_lineup_sort"] = pd.to_numeric(sortable["Lineup Spot"], errors="coerce").fillna(99)
    sortable = sortable.sort_values(
        by=[
            "HR Probability %",
            "_lineup_sort",
            "Barrel%",
            "HardHit%",
            "AIR%",
            "xSLG",
            "GroundBall%",
            "Pitcher_HR9_Last7",
            "Pitcher_Barrel_Allowed",
            "HRR Score",
        ],
        ascending=[False, True, False, False, False, False, True, False, False, False],
    ).reset_index(drop=True)
    return sortable.drop(columns=["_lineup_sort"])


@st.cache_data(ttl=900)
def build_daily_dataset():
    schedule = get_today_schedule()
    rows = []

    savant_batter_map = fetch_savant_batter_map(CURRENT_SEASON)

    candidate_map = {}
    all_hitter_ids = set()
    all_pitcher_ids = set()

    for game in schedule:
        away_candidates, away_source = get_team_candidate_hitters(
            game["game_pk"], game["away_team_id"], "away", savant_batter_map
        )
        home_candidates, home_source = get_team_candidate_hitters(
            game["game_pk"], game["home_team_id"], "home", savant_batter_map
        )

        candidate_map[(game["game_pk"], "away")] = (away_candidates, away_source)
        candidate_map[(game["game_pk"], "home")] = (home_candidates, home_source)

        if away_source == "CONFIRMED":
            game["away_confirmed_count"] = min(9, len(away_candidates))
        if home_source == "CONFIRMED":
            game["home_confirmed_count"] = min(9, len(home_candidates))

        for h in away_candidates + home_candidates:
            if h.get("player_id") is not None:
                all_hitter_ids.add(h["player_id"])

        if game.get("away_pitcher_id") is not None:
            all_pitcher_ids.add(game["away_pitcher_id"])
        if game.get("home_pitcher_id") is not None:
            all_pitcher_ids.add(game["home_pitcher_id"])

    hitter_stats_map = fetch_people_stats(tuple(all_hitter_ids), "hitting")
    pitcher_stats_map = fetch_people_stats(tuple(all_pitcher_ids), "pitching")

    for game in schedule:
        away_abbr = team_abbr(game["away_team"])
        home_abbr = team_abbr(game["home_team"])
        away_park = PARK_FACTORS.get(home_abbr, 1.00)
        home_park = PARK_FACTORS.get(home_abbr, 1.00)

        away_candidates, away_source = candidate_map[(game["game_pk"], "away")]
        home_candidates, home_source = candidate_map[(game["game_pk"], "home")]

        for hitter in away_candidates:
            metrics = build_hitter_metrics(
                player_id=hitter["player_id"],
                player_name=hitter["player_name"],
                team=away_abbr,
                opp_pitcher=game["home_pitcher"],
                park_factor=away_park,
                opp_pitcher_id=game["home_pitcher_id"],
                lineup_spot=hitter.get("lineup_spot"),
                lineup_source=away_source,
                hitter_stats_map=hitter_stats_map,
                pitcher_stats_map=pitcher_stats_map,
                savant_batter_map=savant_batter_map,
            )
            if metrics is not None:
                rows.append({
                    "date": today_str(),
                    "game_pk": game["game_pk"],
                    "game_state": game["game_state"],
                    "detailed_state": game["detailed_state"],
                    "Game": game["game_key"],
                    "Side": "Away",
                    **metrics
                })

        for hitter in home_candidates:
            metrics = build_hitter_metrics(
                player_id=hitter["player_id"],
                player_name=hitter["player_name"],
                team=home_abbr,
                opp_pitcher=game["away_pitcher"],
                park_factor=home_park,
                opp_pitcher_id=game["away_pitcher_id"],
                lineup_spot=hitter.get("lineup_spot"),
                lineup_source=home_source,
                hitter_stats_map=hitter_stats_map,
                pitcher_stats_map=pitcher_stats_map,
                savant_batter_map=savant_batter_map,
            )
            if metrics is not None:
                rows.append({
                    "date": today_str(),
                    "game_pk": game["game_pk"],
                    "game_state": game["game_state"],
                    "detailed_state": game["detailed_state"],
                    "Game": game["game_key"],
                    "Side": "Home",
                    **metrics
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(), schedule

    df["HR Tier"] = df["HR Probability %"].apply(classify_hr_tier)
    df = sort_for_hr(df)
    return df, schedule


def get_strict_hr_pool(df: pd.DataFrame) -> pd.DataFrame:
    hr_pool = df[df["HR Eligible"]].copy()
    if hr_pool.empty:
        return hr_pool
    hr_pool = sort_for_hr(hr_pool)
    return add_rank_column(hr_pool)


def get_top12_hybrid(df: pd.DataFrame) -> pd.DataFrame:
    hr_pool = df[df["HR Eligible"]].copy()
    if hr_pool.empty:
        return hr_pool

    hr_pool = sort_for_hr(hr_pool)
    strict_pool = hr_pool[hr_pool["Strict Statcast"] == "Yes"].copy()
    strict_pool = sort_for_hr(strict_pool)

    strict_keys = set(zip(strict_pool["Player"], strict_pool["Team"], strict_pool["Game"]))
    fallback_rows = []
    for _, row in hr_pool.iterrows():
        key = (row["Player"], row["Team"], row["Game"])
        if key not in strict_keys:
            fallback_rows.append(row)

    fallback_df = pd.DataFrame(fallback_rows) if fallback_rows else pd.DataFrame(columns=hr_pool.columns)
    top12 = pd.concat([strict_pool, fallback_df], ignore_index=True).head(12)

    if top12.empty:
        return top12

    top12 = sort_for_hr(top12)
    return add_rank_column(top12)


def get_team_game_view(df: pd.DataFrame, game_key: str, team: str):
    team_df = df[(df["Game"] == game_key) & (df["Team"] == team)].copy()
    if team_df.empty:
        return team_df, team_df

    hr_pool = team_df[team_df["HR Eligible"]].copy()
    hr_pool = sort_for_hr(hr_pool).head(4)
    if not hr_pool.empty:
        hr_pool = add_rank_column(hr_pool)

    hrr = team_df.sort_values(
        by=["HRR Score", "LineDrive%", "HardHit%", "GroundBall%"],
        ascending=[False, False, False, True]
    ).head(5)

    return hr_pool, hrr


def build_visible_tracker_pool(df: pd.DataFrame, schedule: list[dict]) -> pd.DataFrame:
    visible_frames = []

    hr_board = df[df["HR Eligible"]].copy()
    if not hr_board.empty:
        hr_board = sort_for_hr(hr_board)
        hr_board["Tracker Source"] = "HR_BOARD"
        visible_frames.append(hr_board)

    top12 = get_top12_hybrid(df).copy()
    if not top12.empty:
        top12["Tracker Source"] = "TOP12"
        visible_frames.append(top12)

    for game in schedule:
        gdf = df[df["Game"] == game["game_key"]].copy()
        if gdf.empty:
            continue

        away_team = team_abbr(game["away_team"])
        home_team = team_abbr(game["home_team"])

        away_hr, _ = get_team_game_view(gdf, game["game_key"], away_team)
        if not away_hr.empty:
            away_hr = away_hr.copy()
            away_hr["Tracker Source"] = "GAME_HR"
            visible_frames.append(away_hr)

        home_hr, _ = get_team_game_view(gdf, game["game_key"], home_team)
        if not home_hr.empty:
            home_hr = home_hr.copy()
            home_hr["Tracker Source"] = "GAME_HR"
            visible_frames.append(home_hr)

    if not visible_frames:
        return pd.DataFrame(columns=df.columns.tolist() + ["Tracker Source"])

    visible_df = pd.concat(visible_frames, ignore_index=True)
    visible_df = visible_df.drop_duplicates(subset=["Player", "Team", "Game"]).reset_index(drop=True)
    return visible_df


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


def sync_tracker_with_board(tracked_df: pd.DataFrame):
    tracker = load_tracker()
    date_key = today_str()

    if tracked_df.empty:
        return tracker

    existing_today = tracker[tracker["date"].astype(str) == date_key].copy()
    existing_keys = set(
        zip(existing_today["player"], existing_today["team"], existing_today["game"])
    )

    new_rows = []
    for _, row in tracked_df.iterrows():
        key = (row["Player"], row["Team"], row["Game"])
        if key in existing_keys:
            continue

        new_rows.append({
            "date": date_key,
            "player": row["Player"],
            "team": row["Team"],
            "game": row["Game"],
            "game_pk": row["game_pk"],
            "hr_probability": row["HR Probability %"],
            "hr_tier": row["HR Tier"],
            "hr_eligible": int(bool(row["HR Eligible"])),
            "result": pd.NA,
            "result_state": "PENDING",
            "game_state": row["game_state"],
            "updated_at": now_et_string(),
        })

    if new_rows:
        tracker = pd.concat([tracker, pd.DataFrame(new_rows)], ignore_index=True)
        save_tracker(tracker)

    return tracker


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
            tracker.loc[rows_mask, "updated_at"] = now_et_string()
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
            tracker.at[idx, "updated_at"] = now_et_string()

    save_tracker(tracker)
    return tracker


c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("Update Board", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

live_df, schedule = build_daily_dataset()
locked_df = ensure_daily_board_lock(live_df)

lineup_mode = get_lineup_mode(schedule) if schedule else "PROJECTED"

tracked_df = build_visible_tracker_pool(locked_df, schedule)
tracker = sync_tracker_with_board(tracked_df)
if st.session_state.get("force_tracker_refresh", False):
tracker = auto_update_tracker_results(tracker, schedule)
summary = summarize_tracker(tracker)
daily_summary = summarize_tracker_by_day(tracker)

with c2:
    st.metric("Games On Slate", len(schedule))
with c3:
    st.metric("Lineup Mode", lineup_mode)
with c4:
    if not locked_df.empty and "lock_created_at" in locked_df.columns:
        lock_time = str(locked_df["lock_created_at"].iloc[0])
        st.caption(f"Slate locked: {lock_time} ET")
    else:
        st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

if locked_df.empty:
    st.warning("No games or hitter data loaded.")
    st.stop()

base_tabs = ["HR Probability", "Top 12", "Hits + Runs + RBIs", "Engine Breakdown", "Accuracy Tracker"]
game_tabs = [g["game_key"] for g in schedule]
tabs = st.tabs(base_tabs + game_tabs)

with tabs[0]:
    st.subheader("HR Probability Board")
    st.caption("Locked slate board. Rankings do not mutate after lock.")
    hr_df = get_strict_hr_pool(locked_df)
    st.dataframe(
        hr_df[[
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "Lineup Source", "HR Probability %", "HR Tier", "GroundBall%",
            "GB Rule", "GB Note", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[1]:
    st.subheader("Top 12 HR Candidates")
    st.caption("Locked slate board. Strict Statcast first, then best remaining eligible bats.")
    top12 = get_top12_hybrid(locked_df)
    st.dataframe(
        top12[[
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "Lineup Source", "HR Probability %", "HR Tier", "GroundBall%",
            "GB Rule", "GB Note", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[2]:
    st.subheader("Hits + Runs + RBIs Board")
    st.caption("Locked slate board. This list stays fixed after lock.")
    hrr = locked_df.copy().sort_values(
        by=["HRR Score", "LineDrive%", "HardHit%", "GroundBall%"],
        ascending=[False, False, False, True]
    ).reset_index(drop=True)
    hrr.insert(0, "Rank", range(1, len(hrr) + 1))
    st.dataframe(
        hrr[[
            "Rank", "Player", "Team", "Game", "Lineup Spot", "Lineup Source",
            "HRR Score", "GroundBall%", "LineDrive%", "EV", "HardHit%", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[3]:
    st.subheader("Engine Breakdown")
    st.caption("Locked slate board. Heavy GB bats are downgraded, not blindly erased unless the profile is truly bad.")
    breakdown = sort_for_hr(locked_df.copy())
    st.dataframe(
        breakdown[[
            "Player", "Team", "Game", "Pitcher", "Lineup Spot", "Lineup Source",
            "EV", "HardHit%", "FlyBall%", "AIR%", "LineDrive%", "GroundBall%", "Barrel%",
            "xSLG", "xwOBA",
            "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed",
            "Statcast Pass", "Strict Statcast", "Recent Form Pass", "Pitcher Attackable",
            "Pitch_Isolation_Valid", "GB Rule", "GB Note", "HR Eligible",
            "HR Probability %", "HRR Score", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[4]:
    st.subheader("Accuracy Tracker")
    st.caption("Only tracks hitters BF Data actually surfaced on the locked visible HR boards.")

    a1, a2, a3 = st.columns(3)
    a1.metric("Today's Surfaced HR Picks", summary["today_total"])
    a2.metric("Today's Correct HR", summary["today_hits"])
    a3.metric("Today's Hit Rate %", summary["today_pct"])

    b1, b2, b3 = st.columns(3)
    b1.metric("All-Time Surfaced HR Picks", summary["all_total"])
    b2.metric("All-Time Correct HR", summary["all_hits"])
    b3.metric("All-Time Hit Rate %", summary["all_pct"])

    st.divider()

    today_tracker = tracker[
        tracker["date"].astype("string").fillna("") == str(today_str())
    ].copy()

    if not today_tracker.empty:
        st.caption("Today's tracked surfaced picks")
        st.dataframe(
            today_tracker.sort_values(
                by=["hr_probability", "player"],
                ascending=[False, True]
            )[[
                "player",
                "team",
                "game",
                "hr_probability",
                "hr_tier",
                "hr_eligible",
                "result",
                "result_state",
                "game_state",
                "updated_at"
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

    if not daily_summary.empty:
        st.divider()
        st.caption("Daily HR prediction accuracy history")
        st.dataframe(
            daily_summary,
            use_container_width=True,
            hide_index=True
        )

    if not tracker.empty:
        st.divider()
        st.subheader("Historical Day Review")

        available_dates = sorted(
            tracker["date"].dropna().astype(str).unique().tolist(),
            reverse=True
        )

        selected_date = st.selectbox(
            "Select a saved tracker date to review",
            available_dates,
            index=0
        )

        selected_day_df = tracker[
            tracker["date"].astype("string").fillna("") == str(selected_date)
        ].copy()

        selected_day_df["result_num"] = pd.to_numeric(
            selected_day_df["result"],
            errors="coerce"
        ).fillna(0).astype(int)

        selected_total = len(selected_day_df)
        selected_hits = int(selected_day_df["result_num"].sum())
        selected_pct = round(
            (selected_hits / selected_total) * 100,
            2
        ) if selected_total else 0.0

        d1, d2, d3 = st.columns(3)
        d1.metric("Selected Day Surfaced HR Picks", selected_total)
        d2.metric("Selected Day Correct HR", selected_hits)
        d3.metric("Selected Day Hit Rate %", selected_pct)

        st.caption(f"Tracked surfaced picks for {selected_date}")
        st.dataframe(
            selected_day_df.sort_values(
                by=["hr_probability", "player"],
                ascending=[False, True]
            )[[
                "player",
                "team",
                "game",
                "hr_probability",
                "hr_tier",
                "hr_eligible",
                "result",
                "result_state",
                "game_state",
                "updated_at"
            ]],
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

        gdf = locked_df[locked_df["Game"] == game["game_key"]].copy()
        away_team = team_abbr(game["away_team"])
        home_team = team_abbr(game["home_team"])

        left, right = st.columns(2)

        with left:
            st.markdown(f"### {away_team}")
            away_source = gdf[gdf["Team"] == away_team]["Lineup Source"].iloc[0] if not gdf[gdf["Team"] == away_team].empty else "N/A"
            st.caption(f"Confirmed hitters: {game.get('away_confirmed_count', 0)}/9 | Pool locked as: {away_source}")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], away_team)
            if not team_hr.empty:
                st.markdown("**Best HR hitters**")
                st.dataframe(
                    team_hr[[
                        "Rank", "Player", "Lineup Spot", "Lineup Source", "Statcast Pass",
                        "Strict Statcast", "Recent Form Pass", "Pitcher Attackable", "HR Probability %",
                        "HR Tier", "GroundBall%", "GB Rule", "GB Note", "HardHit%", "FlyBall%",
                        "AIR%", "xSLG", "xwOBA", "Barrel%", "Why"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No HR-qualified bats surfaced.")

            st.markdown("**Best Hits + Runs + RBIs**")
            if not team_hrr.empty:
                st.dataframe(
                    team_hrr[[
                        "Player", "Lineup Spot", "Lineup Source", "HRR Score",
                        "GroundBall%", "LineDrive%", "Why"
                    ]].head(5),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No HRR bats surfaced.")

        with right:
            st.markdown(f"### {home_team}")
            home_source = gdf[gdf["Team"] == home_team]["Lineup Source"].iloc[0] if not gdf[gdf["Team"] == home_team].empty else "N/A"
            st.caption(f"Confirmed hitters: {game.get('home_confirmed_count', 0)}/9 | Pool locked as: {home_source}")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], home_team)
            if not team_hr.empty:
                st.markdown("**Best HR hitters**")
                st.dataframe(
                    team_hr[[
                        "Rank", "Player", "Lineup Spot", "Lineup Source", "Statcast Pass",
                        "Strict Statcast", "Recent Form Pass", "Pitcher Attackable", "HR Probability %",
                        "HR Tier", "GroundBall%", "GB Rule", "GB Note", "HardHit%", "FlyBall%",
                        "AIR%", "xSLG", "xwOBA", "Barrel%", "Why"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No HR-qualified bats surfaced.")

            st.markdown("**Best Hits + Runs + RBIs**")
            if not team_hrr.empty:
                st.dataframe(
                    team_hrr[[
                        "Player", "Lineup Spot", "Lineup Source", "HRR Score",
                        "GroundBall%", "LineDrive%", "Why"
                    ]].head(5),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No HRR bats surfaced.")
