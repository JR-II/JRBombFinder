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
AUTO_REFRESH_SECONDS = 120

if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = time.time()

if time.time() - st.session_state.last_refresh_time > AUTO_REFRESH_SECONDS:
    st.session_state.last_refresh_time = time.time()
    st.session_state.force_tracker_refresh = True
else:
    st.session_state.force_tracker_refresh = False
TRACKER_FILE = "hr_tracker.csv"
COMBO_TRACKER_FILE = "hr_combo_tracker.csv"
LOCK_FILE = "daily_hr_board_lock.csv"
CURRENT_SEASON = datetime.now().year

SNAPSHOT_DIR = "tracker_snapshots"


def ensure_snapshot_folder():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def save_daily_tracker_snapshot(tracker_df: pd.DataFrame, snapshot_date: str):
    """Persist the day's tracker state so historical results never disappear."""
    ensure_snapshot_folder()
    tracker_path = os.path.join(SNAPSHOT_DIR, f"hr_tracker_{snapshot_date}.csv")
    tracker_df.to_csv(tracker_path, index=False)


def save_daily_board_snapshot(board_df: pd.DataFrame, snapshot_date: str):
    """Persist the surfaced HR board once per day so surfaced counts cannot be lost."""
    ensure_snapshot_folder()
    board_path = os.path.join(SNAPSHOT_DIR, f"hr_board_{snapshot_date}.csv")
    if not os.path.exists(board_path):
        board_df.to_csv(board_path, index=False)


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

PARK_COORDS = {
    "ARI": (33.4455, -112.0667),
    "ATL": (33.8907, -84.4677),
    "BAL": (39.2840, -76.6217),
    "BOS": (42.3467, -71.0972),
    "CHC": (41.9484, -87.6553),
    "CWS": (41.8300, -87.6339),
    "CIN": (39.0979, -84.5082),
    "CLE": (41.4962, -81.6852),
    "COL": (39.7561, -104.9942),
    "DET": (42.3390, -83.0485),
    "HOU": (29.7573, -95.3555),
    "KC": (39.0517, -94.4803),
    "LAA": (33.8003, -117.8827),
    "LAD": (34.0739, -118.2400),
    "MIA": (25.7781, -80.2197),
    "MIL": (43.0280, -87.9712),
    "MIN": (44.9817, -93.2776),
    "NYM": (40.7571, -73.8458),
    "NYY": (40.8296, -73.9262),
    "ATH": (38.2270, -107.6720),
    "PHI": (39.9057, -75.1665),
    "PIT": (40.4469, -80.0057),
    "SD": (32.7073, -117.1573),
    "SF": (37.7786, -122.3893),
    "SEA": (47.5914, -122.3325),
    "STL": (38.6226, -90.1928),
    "TB": (27.7682, -82.6534),
    "TEX": (32.7473, -97.0842),
    "TOR": (43.6414, -79.3894),
    "WSH": (38.8730, -77.0074),
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


def parse_game_time_et(game_time_value: str):
    if not game_time_value:
        return None
    try:
        raw = str(game_time_value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return None


def format_game_time_et(game_time_value: str) -> str:
    dt = parse_game_time_et(game_time_value)
    if dt is None:
        return "TBD ET"
    try:
        return dt.strftime("%-I:%M %p ET")
    except Exception:
        return dt.strftime("%I:%M %p ET").lstrip("0")


def sort_schedule_rows(schedule_rows: list[dict]) -> list[dict]:
    def _key(game: dict):
        dt = parse_game_time_et(game.get("game_time", ""))
        return (dt is None, dt or datetime.max.replace(tzinfo=ZoneInfo("America/New_York")), game.get("game_key", ""))
    return sorted(schedule_rows, key=_key)


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
        "hr_probability", "hr_tier", "hr_eligible", "tracker_source",
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


def load_combo_tracker() -> pd.DataFrame:
    columns = [
        "date", "combo_id", "combo_label", "combo_size", "legs", "games",
        "avg_leg_probability", "combined_score", "source_pool", "result",
        "result_state", "legs_hit", "total_legs", "updated_at"
    ]
    if os.path.exists(COMBO_TRACKER_FILE):
        try:
            df = pd.read_csv(COMBO_TRACKER_FILE)
            for col in columns:
                if col not in df.columns:
                    df[col] = pd.NA
            return df[columns]
        except Exception:
            pass
    return pd.DataFrame(columns=columns)


def save_combo_tracker(df: pd.DataFrame):
    df.to_csv(COMBO_TRACKER_FILE, index=False)


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


def ensure_daily_board_lock(live_df: pd.DataFrame, schedule: list[dict]) -> pd.DataFrame:
    """Keep projected teams live, but freeze teams once their lineup confirms.
    Manual pregame refresh may rebuild confirmed-team locks before first pitch.
    """
    if live_df.empty:
        return live_df.copy()

    date_key = today_str()
    locks = load_board_locks()

    if not locks.empty and "lock_scope" in locks.columns:
        locks_today = locks[locks["date"].astype(str) == str(date_key)].copy()
    else:
        locks_today = pd.DataFrame(columns=list(live_df.columns) + ["lock_created_at", "lock_scope"])

    confirmed_team_keys = set()
    pregame_confirmed_keys = set()
    for game in schedule:
        game_key = game["game_key"]
        away_team = team_abbr(game["away_team"])
        home_team = team_abbr(game["home_team"])
        game_state = str(game.get("game_state", "Preview"))

        if game.get("away_confirmed_count", 0) >= 9:
            confirmed_team_keys.add((game_key, away_team))
            if game_state == "Preview":
                pregame_confirmed_keys.add((game_key, away_team))
        if game.get("home_confirmed_count", 0) >= 9:
            confirmed_team_keys.add((game_key, home_team))
            if game_state == "Preview":
                pregame_confirmed_keys.add((game_key, home_team))

    rebuild_confirmed = bool(st.session_state.get("manual_refresh_trigger", False))

    if rebuild_confirmed and not locks_today.empty and {"Game", "Team"}.issubset(locks_today.columns):
        drop_mask_today = locks_today.apply(
            lambda r: (r.get("Game"), r.get("Team")) in pregame_confirmed_keys,
            axis=1
        )
        locks_today = locks_today[~drop_mask_today].copy()

        if not locks.empty and {"Game", "Team", "date"}.issubset(locks.columns):
            drop_mask_all = (
                (locks["date"].astype(str) == str(date_key))
                & locks.apply(lambda r: (r.get("Game"), r.get("Team")) in pregame_confirmed_keys, axis=1)
            )
            locks = locks[~drop_mask_all].copy()

    existing_locked_keys = set()
    if not locks_today.empty and {"Game", "Team"}.issubset(locks_today.columns):
        existing_locked_keys = set(zip(locks_today["Game"], locks_today["Team"]))

    new_lock_frames = []
    for game_key, team in confirmed_team_keys:
        if (game_key, team) in existing_locked_keys:
            continue
        team_rows = live_df[(live_df["Game"] == game_key) & (live_df["Team"] == team)].copy()
        if team_rows.empty:
            continue
        team_rows["lock_created_at"] = now_et_string()
        team_rows["lock_scope"] = "CONFIRMED_TEAM"
        new_lock_frames.append(team_rows)

    if new_lock_frames:
        append_df = pd.concat(new_lock_frames, ignore_index=True)
        locks = pd.concat([locks, append_df], ignore_index=True)
        save_board_locks(locks)
        locks_today = pd.concat([locks_today, append_df], ignore_index=True)
    elif rebuild_confirmed:
        save_board_locks(locks)

    output_frames = []
    used_locked_keys = set()
    if not locks_today.empty and {"Game", "Team"}.issubset(locks_today.columns):
        for game_key, team in confirmed_team_keys:
            locked_rows = locks_today[(locks_today["Game"] == game_key) & (locks_today["Team"] == team)].copy()
            if not locked_rows.empty:
                output_frames.append(locked_rows)
                used_locked_keys.add((game_key, team))

    live_rows = []
    for _, row in live_df.iterrows():
        key = (row["Game"], row["Team"])
        if key in confirmed_team_keys and key in used_locked_keys:
            continue
        live_rows.append(row)

    if live_rows:
        output_frames.append(pd.DataFrame(live_rows))

    if not output_frames:
        return live_df.copy().reset_index(drop=True)

    result = pd.concat(output_frames, ignore_index=True)
    return result.reset_index(drop=True)


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


def estimate_handedness_from_name(name: str, role: str = "batter") -> str:
    seed = stable_float(f"{role}-{normalize_name(name)}-hand", 0, 100)
    if role == "pitcher":
        return "L" if seed < 32 else "R"
    return "L" if seed < 45 else "R"


def build_pitch_mix_profile(
    pitcher_name: str,
    pitcher_id,
    pitcher_hr9: float,
    pitcher_barrel_allowed: float,
    pitcher_hard_hit_allowed: float,
    pitcher_throws: str,
) -> dict:
    seed_key = f"{pitcher_id}-{pitcher_name}-{pitcher_throws}"
    ff_base = stable_float(f"{seed_key}-ff", 24, 50)
    sl_base = stable_float(f"{seed_key}-sl", 12, 34)
    ch_base = stable_float(f"{seed_key}-ch", 6, 24)
    cu_base = stable_float(f"{seed_key}-cu", 4, 20)

    if pitcher_throws == "L":
        ch_base += 1.5
        ff_base -= 1.0
    else:
        sl_base += 1.0

    if pitcher_hr9 >= 1.45:
        ff_base += 4.0
    if pitcher_barrel_allowed >= 9.0:
        sl_base += 2.0
    if pitcher_hard_hit_allowed >= 42.0:
        ch_base += 1.5

    mix = {
        "FF": max(ff_base, 5.0),
        "SL": max(sl_base, 5.0),
        "CH": max(ch_base, 3.0),
        "CU": max(cu_base, 2.0),
    }

    total = sum(mix.values())
    if total <= 0:
        return {"FF": 40.0, "SL": 30.0, "CH": 20.0, "CU": 10.0}

    return {
        pitch: round((usage / total) * 100, 1)
        for pitch, usage in mix.items()
    }


def compute_pitch_matchup_score(
    primary_pitch: str | None,
    primary_pitch_usage: float,
    bats: str,
    pitcher_throws: str,
    barrel: float,
    hard_hit: float,
    air_pct: float,
    launch_angle: float,
    xslg: float,
    xwoba: float,
    ground_ball: float,
):
    if primary_pitch is None:
        return 0.0, "No pitch edge", 0.0

    opposite_hand = bats != pitcher_throws
    shape_bonus = max(0.0, (barrel - 8) * 0.35) + max(0.0, (hard_hit - 38) * 0.12)
    lift_bonus = max(0.0, (air_pct - 52) * 0.08) + max(0.0, (18 - abs(launch_angle - 18)) * 0.18)
    contact_quality_bonus = max(0.0, (xslg - 0.430) * 20) + max(0.0, (xwoba - 0.320) * 12)
    gb_penalty = max(0.0, (ground_ball - 48) * 0.16)

    pitch_type_score = 0.0
    pitch_label = "Neutral pitch fit"

    if primary_pitch == "FF":
        pitch_type_score = shape_bonus + lift_bonus + contact_quality_bonus
        if barrel >= 11 and air_pct >= 55:
            pitch_label = "Fastball lift edge"
        else:
            pitch_label = "Fastball contact look"
    elif primary_pitch == "SL":
        pitch_type_score = (shape_bonus * 0.85) + (contact_quality_bonus * 0.85) + (2.0 if opposite_hand else 0.8)
        if opposite_hand and hard_hit >= 42:
            pitch_label = "Opposite-hand slider edge"
        else:
            pitch_label = "Slider damage path"
    elif primary_pitch == "CH":
        pitch_type_score = (contact_quality_bonus * 0.90) + (1.8 if opposite_hand else 0.5) + max(0.0, (launch_angle - 10) * 0.10)
        if opposite_hand and xwoba >= 0.340:
            pitch_label = "Changeup split edge"
        else:
            pitch_label = "Changeup contact path"
    elif primary_pitch == "CU":
        pitch_type_score = (shape_bonus * 0.75) + lift_bonus + max(0.0, (barrel - 9) * 0.22)
        if launch_angle >= 14 and barrel >= 10:
            pitch_label = "Curveball loft edge"
        else:
            pitch_label = "Curveball lift look"

    usage_multiplier = 0.85 + min(primary_pitch_usage, 65.0) / 100.0
    handedness_bonus = 1.4 if opposite_hand else -0.4

    final_score = (pitch_type_score * usage_multiplier) + handedness_bonus - gb_penalty

    if final_score >= 8.0:
        pitch_label = f"Strong {pitch_label.lower()}"
    elif final_score <= 1.5:
        pitch_label = "Weak pitch edge"

    return round(final_score, 2), pitch_label, round(handedness_bonus, 2)


def get_relevant_pitch_context(pitch_mix: dict):
    if not pitch_mix:
        return "BALANCED", [], "Mix"

    sorted_mix = sorted(pitch_mix.items(), key=lambda x: x[1], reverse=True)
    top_usage = sorted_mix[0][1]
    second_usage = sorted_mix[1][1] if len(sorted_mix) > 1 else 0.0
    gap = top_usage - second_usage

    if top_usage >= 50:
        mode = "HARD"
        relevant = sorted_mix[:1]
    elif gap > 20:
        mode = "HARD"
        relevant = sorted_mix[:2]
    elif gap >= 10 or top_usage >= 38:
        mode = "SOFT"
        relevant = sorted_mix[:2]
    else:
        mode = "BALANCED"
        relevant = sorted_mix[:3]

    total = sum(v for _, v in relevant) or 1.0
    weighted = [(p, round(v / total, 4), v) for p, v in relevant]
    label = " + ".join([p for p, _, _ in weighted])
    return mode, weighted, label


def compute_relevant_pitch_matchup(
    pitch_mix: dict,
    bats: str,
    pitcher_throws: str,
    barrel: float,
    hard_hit: float,
    air_pct: float,
    launch_angle: float,
    xslg: float,
    xwoba: float,
    ground_ball: float,
):
    mode, weighted_pitches, label = get_relevant_pitch_context(pitch_mix)
    if not weighted_pitches:
        return {
            "mode": "BALANCED",
            "label": "Mix",
            "score": 0.0,
            "usage": 0.0,
            "gap": 0.0,
            "handedness_edge": 0.0,
            "reason": "No pitch edge",
            "primary_pitch": None,
        }

    weighted_score = 0.0
    weighted_hand = 0.0
    reason_bits = []
    top_usage = weighted_pitches[0][2]
    second_usage = weighted_pitches[1][2] if len(weighted_pitches) > 1 else 0.0

    for pitch, weight, raw_usage in weighted_pitches:
        score, reason, hand = compute_pitch_matchup_score(
            pitch,
            raw_usage,
            bats,
            pitcher_throws,
            barrel,
            hard_hit,
            air_pct,
            launch_angle,
            xslg,
            xwoba,
            ground_ball,
        )
        weighted_score += score * weight
        weighted_hand += hand * weight
        if score >= 1.5:
            reason_bits.append(reason)

    reason = reason_bits[0] if reason_bits else "Weak pitch edge"
    if mode == "SOFT" and weighted_score >= 3.0:
        reason = f"Soft isolate: {label}"
    elif mode == "BALANCED" and weighted_score >= 3.0:
        reason = f"Balanced mix: {label}"
    elif mode == "HARD" and weighted_score >= 4.0:
        reason = f"Hard isolate: {label}"

    return {
        "mode": mode,
        "label": label,
        "score": round(weighted_score, 2),
        "usage": round(top_usage, 1),
        "gap": round(top_usage - second_usage, 1),
        "handedness_edge": round(weighted_hand, 2),
        "reason": reason,
        "primary_pitch": weighted_pitches[0][0],
    }




def compute_statcast_authority(
    ev: float,
    barrel: float,
    hard_hit: float,
    air_pct: float,
    launch_angle: float,
    xslg: float,
    ground_ball: float,
):
    launch_window = max(0.0, 26.0 - abs(launch_angle - 18.0))

    authority_score = (
        max(0.0, barrel - 8.0) * 4.0 +
        max(0.0, hard_hit - 38.0) * 1.8 +
        max(0.0, air_pct - 50.0) * 1.0 +
        max(0.0, ev - 88.0) * 1.25 +
        max(0.0, xslg - 0.430) * 135.0 +
        launch_window * 0.65 -
        max(0.0, ground_ball - 46.0) * 1.4
    )

    if authority_score >= 36:
        return round(authority_score, 2), 1.00, "ELITE"
    if authority_score >= 26:
        return round(authority_score, 2), 0.85, "STRONG"
    if authority_score >= 17:
        return round(authority_score, 2), 0.55, "MEDIUM"
    if authority_score >= 9:
        return round(authority_score, 2), 0.15, "WEAK"
    return round(authority_score, 2), 0.00, "FAIL"


def summarize_tracker(df: pd.DataFrame):
    summary = {
        "today_total": 0,
        "today_hits": 0,
        "today_pct": 0.0,
        "all_total": 0,
        "all_hits": 0,
        "all_pct": 0.0,
        "today_core_total": 0,
        "today_core_hits": 0,
        "today_core_pct": 0.0,
        "all_core_total": 0,
        "all_core_hits": 0,
        "all_core_pct": 0.0,
        "today_top12_total": 0,
        "today_top12_hits": 0,
        "today_top12_pct": 0.0,
        "all_top12_total": 0,
        "all_top12_hits": 0,
        "all_top12_pct": 0.0,
    }
    if df.empty:
        return summary

    work = df.copy()
    if "tracker_source" not in work.columns:
        work["tracker_source"] = "CORE_BOARD"
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str)
    work["result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)

    def _stats(sub: pd.DataFrame):
        total = len(sub)
        hits = int(sub["result_num"].sum()) if total else 0
        pct = round((hits / total) * 100, 2) if total else 0.0
        return total, hits, pct

    today_df = work[work["date"].astype(str) == today_str()].copy()
    summary["today_total"], summary["today_hits"], summary["today_pct"] = _stats(today_df)
    summary["all_total"], summary["all_hits"], summary["all_pct"] = _stats(work)

    today_core = today_df[today_df["tracker_source"].isin(["CORE_BOARD", "GAME_HR"])]
    all_core = work[work["tracker_source"].isin(["CORE_BOARD", "GAME_HR"])]
    summary["today_core_total"], summary["today_core_hits"], summary["today_core_pct"] = _stats(today_core)
    summary["all_core_total"], summary["all_core_hits"], summary["all_core_pct"] = _stats(all_core)

    today_top12 = today_df[today_df["tracker_source"] == "TOP12"]
    all_top12 = work[work["tracker_source"] == "TOP12"]
    summary["today_top12_total"], summary["today_top12_hits"], summary["today_top12_pct"] = _stats(today_top12)
    summary["all_top12_total"], summary["all_top12_hits"], summary["all_top12_pct"] = _stats(all_top12)
    return summary


def summarize_tracker_by_day(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "date",
            "all_surfaced",
            "all_correct_hr",
            "all_hit_rate_pct",
            "core_surfaced",
            "core_correct_hr",
            "core_hit_rate_pct",
            "top12_surfaced",
            "top12_correct_hr",
            "top12_hit_rate_pct",
        ])

    work = df.copy()
    if "tracker_source" not in work.columns:
        work["tracker_source"] = "CORE_BOARD"
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str)
    work["result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)

    all_daily = (
        work.groupby("date", as_index=False)
        .agg(
            all_surfaced=("player", "count"),
            all_correct_hr=("result_num", "sum"),
        )
    )
    all_daily["all_hit_rate_pct"] = all_daily.apply(
        lambda row: round((row["all_correct_hr"] / row["all_surfaced"]) * 100, 2) if row["all_surfaced"] else 0.0,
        axis=1
    )

    core_work = work[work["tracker_source"].isin(["CORE_BOARD", "GAME_HR"])].copy()
    if core_work.empty:
        core_daily = pd.DataFrame(columns=["date", "core_surfaced", "core_correct_hr", "core_hit_rate_pct"])
    else:
        core_daily = (
            core_work.groupby("date", as_index=False)
            .agg(
                core_surfaced=("player", "count"),
                core_correct_hr=("result_num", "sum"),
            )
        )
        core_daily["core_hit_rate_pct"] = core_daily.apply(
            lambda row: round((row["core_correct_hr"] / row["core_surfaced"]) * 100, 2) if row["core_surfaced"] else 0.0,
            axis=1
        )

    top12_work = work[work["tracker_source"] == "TOP12"].copy()
    if top12_work.empty:
        top12_daily = pd.DataFrame(columns=["date", "top12_surfaced", "top12_correct_hr", "top12_hit_rate_pct"])
    else:
        top12_daily = (
            top12_work.groupby("date", as_index=False)
            .agg(
                top12_surfaced=("player", "count"),
                top12_correct_hr=("result_num", "sum"),
            )
        )
        top12_daily["top12_hit_rate_pct"] = top12_daily.apply(
            lambda row: round((row["top12_correct_hr"] / row["top12_surfaced"]) * 100, 2) if row["top12_surfaced"] else 0.0,
            axis=1
        )

    daily = all_daily.merge(core_daily, on="date", how="left").merge(top12_daily, on="date", how="left")
    for col in ["core_surfaced", "core_correct_hr", "core_hit_rate_pct", "top12_surfaced", "top12_correct_hr", "top12_hit_rate_pct"]:
        if col not in daily.columns:
            daily[col] = 0
        daily[col] = daily[col].fillna(0)

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


def passes_air_authority_profile(
    hard_hit: float,
    fly_ball: float,
    line_drive: float,
    ground_ball: float,
    barrel: float,
    ev: float,
    xslg: float,
    recent_hr: int,
    recent_xbh: int,
    recent_iso: float,
) -> dict:
    air_total = fly_ball + line_drive
    air_authority_core = (
        hard_hit >= 40
        and air_total >= 48
        and ground_ball < 50
        and air_total > ground_ball
    )

    authority_override = (
        barrel >= 10
        or ev >= 91
        or xslg >= 0.470
        or recent_hr >= 1
        or recent_xbh >= 3
        or recent_iso >= 0.180
        or (hard_hit >= 45 and air_total >= 45)
    )

    hard_reject = ground_ball >= 55 and not authority_override
    survives = (air_authority_core or authority_override) and not hard_reject

    return {
        "air_authority_core": air_authority_core,
        "authority_override": authority_override,
        "hard_reject": hard_reject,
        "survives": survives,
        "air_total": round(air_total, 1),
    }


def elite_hr_look(row: pd.Series) -> bool:
    barrel = safe_float(row.get("Barrel%", 0), 0)
    hard_hit = safe_float(row.get("HardHit%", 0), 0)
    air_pct = safe_float(row.get("AIR%", 0), 0)
    xslg = safe_float(row.get("xSLG", 0), 0)
    ev = safe_float(row.get("EV", 0), 0)
    gb = safe_float(row.get("GroundBall%", 999), 999)
    return bool(
        (
            barrel >= 10 and hard_hit >= 45 and air_pct >= 55 and ev >= 91 and gb <= 52
        ) or (
            barrel >= 12 and xslg >= 0.490 and air_pct >= 50 and gb <= 54
        ) or (
            hard_hit >= 48 and xslg >= 0.470 and air_pct >= 52 and gb <= 52
        )
    )


def compute_multi_pitch_authority_score(
    pitch_mix_mode: str,
    pitch_matchup_score: float,
    barrel: float,
    hard_hit: float,
    air_pct: float,
    xslg: float,
    ev: float,
    lineup_spot,
    recent_trend: str,
) -> float:
    score = 0.0

    elite_like = (
        (barrel >= 10 and hard_hit >= 45 and air_pct >= 55 and ev >= 91)
        or (barrel >= 12 and xslg >= 0.490)
        or (hard_hit >= 48 and xslg >= 0.470)
    )

    if pitch_mix_mode == "BALANCED":
        if elite_like:
            score += 4.0
        if pitch_matchup_score >= 3.0:
            score += 1.8
        if recent_trend in ["HOT", "LIVE"]:
            score += 1.0
        if lineup_spot is not None and lineup_spot <= 5:
            score += 0.8

    elif pitch_mix_mode == "SOFT":
        if elite_like:
            score += 2.6
        if pitch_matchup_score >= 3.0:
            score += 1.2

    return round(score, 2)

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


def compute_weather_boost(temp_f: float, wind_mph: float) -> tuple[float, str]:
    boost = 0.0
    notes = []

    if temp_f >= 85:
        boost += 2.4
        notes.append("hot carry weather")
    elif temp_f >= 75:
        boost += 1.4
        notes.append("warm carry weather")
    elif temp_f <= 50:
        boost -= 1.8
        notes.append("cold dense air")
    elif temp_f <= 60:
        boost -= 0.8
        notes.append("cool air")

    if wind_mph >= 15:
        boost += 1.6
        notes.append("strong wind")
    elif wind_mph >= 10:
        boost += 0.8
        notes.append("live wind")
    elif wind_mph <= 3:
        notes.append("neutral wind")

    if not notes:
        notes.append("neutral weather")

    return round(boost, 2), " | ".join(notes[:2])


@st.cache_data(ttl=1800)
def fetch_weather_for_park(home_team_abbr: str):
    coords = PARK_COORDS.get(home_team_abbr)
    if not coords:
        return {
            "TempF": 72.0,
            "WindMPH": 7.0,
            "WeatherBoost": 0.0,
            "WeatherNote": "neutral weather",
        }

    lat, lon = coords
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,wind_speed_10m"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph"
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current", {}) or {}
        temp_f = safe_float(current.get("temperature_2m"), 72.0)
        wind_mph = safe_float(current.get("wind_speed_10m"), 7.0)
    except Exception:
        temp_f = 72.0
        wind_mph = 7.0

    boost, note = compute_weather_boost(temp_f, wind_mph)
    return {
        "TempF": round(temp_f, 1),
        "WindMPH": round(wind_mph, 1),
        "WeatherBoost": boost,
        "WeatherNote": note,
    }


@st.cache_data(ttl=1800)
def get_previous_team_game_pk(team_id: int):
    start_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    try:
        start_dt = datetime.now(ZoneInfo("America/New_York"))
        past_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        start_range = (past_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        end_range = (past_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&teamId={team_id}&startDate={start_range}&endDate={end_range}"
        )
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None

    games = []
    for date_block in payload.get("dates", []):
        for game in date_block.get("games", []):
            game_date = game.get("gameDate", "")
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            games.append((game_date, game.get("gamePk")))
    if not games:
        return None
    games = sorted(games, key=lambda x: x[0], reverse=True)
    return games[0][1]


@st.cache_data(ttl=1800)
def fetch_bullpen_fatigue_for_team(team_id: int):
    game_pk = get_previous_team_game_pk(team_id)
    neutral = {
        "BullpenFatigueScore": 0.0,
        "BullpenFatigueNote": "Neutral bullpen rest",
        "BullpenIPPrev": 0.0,
        "BullpenArmsPrev": 0,
        "BullpenPitchesPrev": 0,
    }
    if game_pk is None:
        return neutral

    box = fetch_boxscore(game_pk)
    teams_block = box.get("teams", {}) or {}

    for side in ["away", "home"]:
        team_block = teams_block.get(side, {}) or {}
        team_info = team_block.get("team", {}) or {}
        if team_info.get("id") != team_id:
            continue

        players = team_block.get("players", {}) or {}
        starter_id = None
        for pdata in players.values():
            stats = ((pdata.get("stats") or {}).get("pitching") or {})
            if safe_int(stats.get("gamesStarted", 0)) > 0:
                starter_id = (pdata.get("person") or {}).get("id")
                break

        bullpen_ip = 0.0
        bullpen_pitches = 0
        bullpen_arms = 0

        for pdata in players.values():
            pos_type = ((pdata.get("position") or {}).get("type") or (pdata.get("primaryPosition") or {}).get("type") or "")
            if pos_type != "Pitcher":
                continue

            pid = (pdata.get("person") or {}).get("id")
            if starter_id is not None and pid == starter_id:
                continue

            stats = ((pdata.get("stats") or {}).get("pitching") or {})
            ip = ip_to_float(stats.get("inningsPitched", 0))
            pitches = safe_int(stats.get("numberOfPitches", 0))
            if ip <= 0 and pitches <= 0:
                continue

            bullpen_ip += ip
            bullpen_pitches += pitches
            bullpen_arms += 1

        fatigue_score = 0.0
        notes = []

        if bullpen_ip >= 5.0:
            fatigue_score += 2.1
            notes.append("heavy bullpen usage")
        elif bullpen_ip >= 3.5:
            fatigue_score += 1.1
            notes.append("live bullpen usage")
        else:
            notes.append("rested bullpen")

        if bullpen_arms >= 5:
            fatigue_score += 1.0
            notes.append("many bullpen arms used")
        elif bullpen_arms >= 3:
            fatigue_score += 0.4

        if bullpen_pitches >= 85:
            fatigue_score += 1.0
        elif bullpen_pitches >= 60:
            fatigue_score += 0.5

        if not notes:
            notes.append("neutral bullpen rest")

        return {
            "BullpenFatigueScore": round(fatigue_score, 2),
            "BullpenFatigueNote": " | ".join(notes[:2]),
            "BullpenIPPrev": round(bullpen_ip, 1),
            "BullpenArmsPrev": bullpen_arms,
            "BullpenPitchesPrev": bullpen_pitches,
        }

    return neutral


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

    return sort_schedule_rows(games)


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
        sav_fb = safe_float(sav.get("Savant_FB%"), metrics["FlyBall%"])
        sav_ld = safe_float(sav.get("Savant_LD%"), metrics["LineDrive%"])
        sav_air = safe_float(sav.get("Savant_AIR%"), max(0.0, sav_fb + sav_ld))
        sav_xslg = safe_float(sav.get("Savant_xSLG"), 0.0)
        sav_xwoba = safe_float(sav.get("Savant_xwOBA"), 0.0)
        sav_la = safe_float(sav.get("Savant_LA"), 14.0)
        sav_ev = safe_float(sav.get("Savant_EV"), metrics["EV"])
        sav_gb = safe_float(sav.get("Savant_GB%"), metrics["GroundBall%"])

        profile_gate = passes_air_authority_profile(
            hard_hit=sav_hh,
            fly_ball=sav_fb,
            line_drive=sav_ld,
            ground_ball=sav_gb,
            barrel=sav_brl,
            ev=sav_ev,
            xslg=sav_xslg,
            recent_hr=metrics["recent_hr"],
            recent_xbh=metrics["recent_xbh"],
            recent_iso=metrics["recent_iso"],
        )

        projected_statcast_pass = (
            sav_brl >= 10 or
            (sav_hh >= 40 and (sav_air >= 55 or (sav_fb + sav_ld) >= 48)) or
            sav_xslg >= 0.450 or
            sav_xwoba >= 0.340 or
            profile_gate["survives"]
        )

        projected_recent_pass = (
            metrics["recent_hr"] >= 1 or
            metrics["recent_xbh"] >= 3 or
            metrics["recent_iso"] >= 0.180
        )

        gb_survival = (
            profile_gate["survives"]
            or sav_gb < 50
            or (
                sav_gb < 54 and (
                    sav_brl >= 11 or
                    sav_air >= 58 or
                    sav_xslg >= 0.470
                )
            )
        )

        elite_projection_override = (
            sav_brl >= 13
            or sav_xslg >= 0.500
            or sav_ev >= 91
            or (sav_xwoba >= 0.365 and sav_air >= 57)
            or (sav_la >= 15 and sav_la <= 24 and sav_brl >= 11)
            or profile_gate["authority_override"]
        )

        projected_authority_score, projected_authority_multiplier, projected_authority_tier = compute_statcast_authority(
            safe_float(sav.get("Savant_EV"), metrics["EV"]),
            sav_brl,
            sav_hh,
            sav_air,
            sav_la,
            sav_xslg,
            sav_gb,
        )

        strong_projected_candidate = (
            metrics["recent_pa"] >= 12 and
            metrics["season_games"] >= 3 and
            metrics["season_ab"] >= 8 and
            projected_statcast_pass and
            (
                projected_recent_pass
                or elite_projection_override
                or profile_gate["survives"]
                or projected_authority_tier in ["ELITE", "STRONG"]
                or (projected_authority_tier == "MEDIUM" and sav_brl >= 10)
            ) and
            gb_survival
        )

        if projected_authority_tier == "FAIL" and not elite_projection_override:
            strong_projected_candidate = False
        elif projected_authority_tier == "WEAK" and not (elite_projection_override or projected_recent_pass):
            strong_projected_candidate = False
        elif (
            projected_authority_tier == "MEDIUM"
            and sav_brl < 9
            and sav_hh < 39
            and sav_xslg < 0.440
            and not (elite_projection_override or projected_recent_pass or profile_gate["survives"])
        ):
            strong_projected_candidate = False

        if not strong_projected_candidate:
            continue

        lineup_likelihood = (
            sav_brl * 2.8 +
            sav_hh * 1.1 +
            sav_air * 0.50 +
            sav_xslg * 110 +
            sav_xwoba * 70 +
            max(0, 24 - abs(sav_la - 18)) * 0.6 +
            metrics["recent_hr"] * 5.5 +
            metrics["recent_xbh"] * 2.0 +
            metrics["recent_iso"] * 18 +
            projected_authority_score * 0.9
        )

        if projected_authority_tier == "ELITE":
            lineup_likelihood += 10.0
        elif projected_authority_tier == "STRONG":
            lineup_likelihood += 5.0
        elif projected_authority_tier == "MEDIUM":
            lineup_likelihood += 0.5
        elif projected_authority_tier == "WEAK":
            lineup_likelihood -= 8.0

        scored.append({
            **h,
            "lineup_likelihood": lineup_likelihood
        })

    scored = sorted(scored, key=lambda x: x["lineup_likelihood"], reverse=True)[:8]

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
    fly_ball: float = 0.0,
    line_drive: float = 0.0,
    ev: float = 0.0,
):
    profile_gate = passes_air_authority_profile(
        hard_hit=hard_hit,
        fly_ball=fly_ball,
        line_drive=line_drive,
        ground_ball=ground_ball,
        barrel=barrel,
        ev=ev,
        xslg=xslg,
        recent_hr=recent_hr,
        recent_xbh=recent_xbh,
        recent_iso=recent_iso,
    )

    elite_override = (
        barrel >= 14 or
        hard_hit >= 48 or
        (air_pct >= 65 and hard_hit >= 42) or
        xslg >= 0.520 or
        profile_gate["authority_override"]
    )

    statcast_pass = (
        barrel >= 10 or
        (hard_hit >= 40 and (air_pct >= 55 or profile_gate["air_total"] >= 48)) or
        xslg >= 0.450 or
        xwoba >= 0.340 or
        elite_override or
        profile_gate["survives"]
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
        (ground_ball >= 55 and air_pct <= 35 and not profile_gate["authority_override"]) or
        (barrel < 5 and hard_hit < 30 and recent_hr == 0)
    )

    weak_recent_profile = (
        recent_hr == 0 and
        recent_xbh <= 1 and
        hard_hit < 35 and
        barrel < 8 and
        air_pct < 50 and
        not profile_gate["survives"]
    )

    projected_damage_profile = (
        statcast_pass and (
            recent_hr >= 1
            or recent_xbh >= 2
            or recent_iso >= 0.150
            or elite_override
            or profile_gate["survives"]
            or (barrel >= 10 and hard_hit >= 40)
            or (hard_hit >= 42 and air_pct >= 55)
            or xslg >= 0.470
        )
    )

    lineup_pass = (
        lineup_source == "CONFIRMED" or
        (lineup_source == "PROJECTED" and projected_damage_profile)
    )

    borderline_gb_survival = (
        profile_gate["survives"]
        or ground_ball < 50
        or elite_override
        or (
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
    elif profile_gate["hard_reject"] and not elite_override:
        hr_eligible = False
    elif awful_hr_shape and not elite_override:
        hr_eligible = False
    elif ground_ball >= 55 and not elite_override and not profile_gate["survives"]:
        hr_eligible = False
    elif not borderline_gb_survival:
        hr_eligible = False
    elif not statcast_pass:
        hr_eligible = False
    elif not recent_form_pass and not elite_override and not profile_gate["survives"]:
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
        "air_authority_survival": profile_gate["survives"],
    }



def compute_pitcher_target_score(
    pitch_hr9: float,
    pitch_barrel_allowed: float,
    pitch_hard_hit_allowed: float,
    park_factor: float,
    weather_boost: float,
) -> tuple[float, str]:
    score = 0.0
    bits = []

    if pitch_hr9 >= 2.4:
        score += 18.0
        bits.append("elite HR/9 target")
    elif pitch_hr9 >= 2.0:
        score += 13.0
        bits.append("very high HR/9")
    elif pitch_hr9 >= 1.6:
        score += 8.0
        bits.append("high HR/9")
    elif pitch_hr9 >= 1.25:
        score += 4.0
        bits.append("attackable HR/9")
    else:
        bits.append("normal HR/9")

    if pitch_barrel_allowed >= 11:
        score += 9.0
        bits.append("barrel-prone arm")
    elif pitch_barrel_allowed >= 8:
        score += 5.0
        bits.append("allows barrels")

    if pitch_hard_hit_allowed >= 44:
        score += 7.0
        bits.append("hard contact allowed")
    elif pitch_hard_hit_allowed >= 40:
        score += 4.0
        bits.append("contact damage allowed")

    park_boost = (park_factor - 1.0) * 20
    if park_boost >= 1.0:
        score += park_boost
        bits.append("HR-friendly park")

    if weather_boost >= 1.5:
        score += weather_boost * 2.0
        bits.append("carry weather")

    return round(score, 2), " | ".join(bits[:4])


def compute_matchup_advantage_score(
    ev: float,
    barrel: float,
    hard_hit: float,
    air_pct: float,
    xslg: float,
    xwoba: float,
    ground_ball: float,
    pitch_matchup_score: float,
    pitch_hr9: float,
    pitch_barrel_allowed: float,
    pitch_hard_hit_allowed: float,
    handedness_edge: float,
    lineup_spot,
    recent_trend: str,
    statcast_authority_tier: str,
    pitch_mix_mode: str,
    primary_pitch_usage: float,
    park_factor: float,
    weather_boost: float,
) -> tuple[float, str, str]:
    score = 0.0
    reasons = []

    if ev >= 93:
        score += 9
        reasons.append("elite EV")
    elif ev >= 90:
        score += 5
        reasons.append("strong EV")

    if barrel >= 14:
        score += 12
        reasons.append("elite barrel")
    elif barrel >= 11:
        score += 8
        reasons.append("strong barrel")
    elif barrel >= 9:
        score += 4
        reasons.append("usable barrel")

    if hard_hit >= 48:
        score += 8
        reasons.append("elite hard-hit")
    elif hard_hit >= 42:
        score += 4
        reasons.append("hard-hit edge")

    if air_pct >= 62 and ground_ball <= 45:
        score += 8
        reasons.append("pull/air-style launch shape")
    elif air_pct >= 55:
        score += 5
        reasons.append("air-ball path")

    if xslg >= 0.520:
        score += 9
        reasons.append("elite xSLG")
    elif xslg >= 0.470:
        score += 5
        reasons.append("xSLG edge")

    if xwoba >= 0.365:
        score += 4
        reasons.append("xwOBA edge")

    if pitch_matchup_score >= 7:
        score += 9
        reasons.append("major pitch edge")
    elif pitch_matchup_score >= 4.5:
        score += 6
        reasons.append("pitch edge")
    elif pitch_matchup_score >= 3:
        score += 3
        reasons.append("minor pitch edge")

    if pitch_mix_mode == "HARD" and primary_pitch_usage >= 50:
        score += 6
        reasons.append("heavy pitch exposure")
    elif pitch_mix_mode == "HARD" and primary_pitch_usage >= 38:
        score += 4
        reasons.append("clear pitch exposure")
    elif pitch_mix_mode == "SOFT":
        score += 2
        reasons.append("soft pitch exposure")

    if pitch_hr9 >= 2.0:
        score += 10
        reasons.append("target pitcher HR/9")
    elif pitch_hr9 >= 1.6:
        score += 7
        reasons.append("high pitcher HR/9")
    elif pitch_hr9 >= 1.25:
        score += 3
        reasons.append("attackable pitcher HR/9")

    if pitch_barrel_allowed >= 10:
        score += 6
        reasons.append("pitcher barrel leak")
    elif pitch_barrel_allowed >= 8:
        score += 3
        reasons.append("pitcher allows barrels")

    if pitch_hard_hit_allowed >= 43:
        score += 4
        reasons.append("pitcher allows hard contact")

    if handedness_edge >= 1:
        score += 3
        reasons.append("handedness edge")

    if lineup_spot is not None:
        try:
            spot = int(lineup_spot)
            if spot <= 4:
                score += 5
                reasons.append("premium lineup slot")
            elif spot <= 6:
                score += 2
                reasons.append("playable lineup slot")
        except Exception:
            pass

    if recent_trend == "HOT":
        score += 5
        reasons.append("hot form")
    elif recent_trend == "LIVE":
        score += 3
        reasons.append("live form")
    elif recent_trend == "COLD":
        score -= 4
        reasons.append("cold-form caution")

    if statcast_authority_tier == "ELITE":
        score += 7
        reasons.append("elite Statcast authority")
    elif statcast_authority_tier == "STRONG":
        score += 4
        reasons.append("strong Statcast authority")
    elif statcast_authority_tier in {"WEAK", "FAIL"}:
        score -= 6
        reasons.append("weak authority caution")

    park_boost = (park_factor - 1.0) * 20
    if park_boost >= 1:
        score += park_boost
        reasons.append("park boost")

    if weather_boost >= 1.5:
        score += weather_boost * 2
        reasons.append("weather carry")
    elif weather_boost <= -1:
        score += weather_boost
        reasons.append("weather suppression")

    if ground_ball >= 55:
        score -= 12
        reasons.append("severe GB risk")
    elif ground_ball >= 50:
        score -= 7
        reasons.append("GB downgrade")
    elif ground_ball >= 45:
        score -= 3
        reasons.append("borderline GB")

    if score >= 55:
        label = "HIGH"
    elif score >= 38:
        label = "MED"
    else:
        label = "LOW"

    if not reasons:
        reasons = ["no clear edge"]

    return round(score, 2), label, " | ".join(reasons[:7])


def build_ranking_reasons(row: pd.Series) -> str:
    checks = []
    def sf(col, default=0.0):
        return safe_float(row.get(col, default), default)

    ev = sf("EV")
    barrel = sf("Barrel%")
    hh = sf("HardHit%")
    air = sf("AIR%")
    gb = sf("GroundBall%", 999)
    xslg = sf("xSLG")
    pitch_score = sf("Pitch Matchup Score")
    hr9 = sf("Pitcher_HR9_Last7")
    pbarrel = sf("Pitcher_Barrel_Allowed")
    auth = str(row.get("Statcast Authority Tier", ""))
    trend = str(row.get("Recent Trend", ""))

    if hr9 >= 2.0:
        checks.append(f"major pitcher HR/9 target ({hr9})")
    elif hr9 >= 1.6:
        checks.append(f"high pitcher HR/9 ({hr9})")
    elif hr9 >= 1.25:
        checks.append(f"attackable pitcher HR/9 ({hr9})")

    if barrel >= 14:
        checks.append(f"elite barrel {barrel}%")
    elif barrel >= 11:
        checks.append(f"strong barrel {barrel}%")

    if ev >= 93:
        checks.append(f"elite EV {ev}")
    elif ev >= 90:
        checks.append(f"strong EV {ev}")

    if hh >= 48:
        checks.append(f"elite hard-hit {hh}%")
    elif hh >= 42:
        checks.append(f"hard-hit edge {hh}%")

    if air >= 60 and gb <= 45:
        checks.append("great air-ball/launch shape")
    elif air >= 55:
        checks.append(f"air-ball path {air}%")

    if xslg >= 0.520:
        checks.append(f"elite xSLG {xslg}")
    elif xslg >= 0.470:
        checks.append(f"xSLG edge {xslg}")

    if pitch_score >= 7:
        checks.append(f"major pitch-match edge {pitch_score}")
    elif pitch_score >= 4.5:
        checks.append(f"pitch-match edge {pitch_score}")

    if pbarrel >= 10:
        checks.append(f"pitcher barrel leak {pbarrel}%")
    elif pbarrel >= 8:
        checks.append(f"pitcher allows barrels {pbarrel}%")

    if auth in ["ELITE", "STRONG"]:
        checks.append(f"{auth.lower()} Statcast authority")

    if trend in ["HOT", "LIVE"]:
        checks.append(f"{trend.lower()} recent form")

    if not checks:
        checks.append("ranked by blended matchup score")

    return " | ".join(checks[:8])


def get_best_hr_matchups(df: pd.DataFrame, limit: int = 25) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    board = df.copy()
    if "Matchup Advantage Score" not in board.columns:
        board["Matchup Advantage Score"] = safe_numeric_series(board, "Model Rank Score", 0.0)
    if "Pitcher Target Score" not in board.columns:
        board["Pitcher Target Score"] = safe_numeric_series(board, "Pitcher_HR9_Last7", 0.0) * 10

    eligible = board[board["HR Eligible"].astype(bool)].copy()
    if eligible.empty:
        eligible = board.copy()

    eligible["_global_score"] = (
        safe_numeric_series(eligible, "Matchup Advantage Score", 0.0) * 1.35
        + safe_numeric_series(eligible, "Pitcher Target Score", 0.0) * 1.10
        + safe_numeric_series(eligible, "Statcast Authority Score", 0.0) * 0.85
        + safe_numeric_series(eligible, "Model Rank Score", 0.0) * 0.05
        + safe_numeric_series(eligible, "HR Probability %", 0.0) * 1.4
    )
    eligible = eligible.sort_values("_global_score", ascending=False).drop(columns=["_global_score"]).head(limit)
    return add_rank_column(eligible.reset_index(drop=True))


def get_pitchers_to_target(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    work = df.copy()

    for col in [
        "Game", "Pitcher", "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed",
        "Pitcher_HardHit_Allowed", "TempF", "WindMPH", "WeatherNote", "WeatherBoost"
    ]:
        if col not in work.columns:
            work[col] = pd.NA

    # Never create a duplicate column name. Use an internal temp column, then assign cleanly once.
    work["_bf_pitcher_target_score"] = (
        safe_numeric_series(work, "Pitcher_HR9_Last7", 0.0) * 12
        + safe_numeric_series(work, "Pitcher_Barrel_Allowed", 0.0) * 1.8
        + safe_numeric_series(work, "Pitcher_HardHit_Allowed", 0.0) * 0.8
        + safe_numeric_series(work, "WeatherBoost", 0.0) * 4
    )

    out = (
        work.sort_values("_bf_pitcher_target_score", ascending=False)
        .drop_duplicates(subset=["Game", "Pitcher"])
        .head(15)
        .copy()
    )

    out["Pitcher Target Score"] = pd.to_numeric(
        out["_bf_pitcher_target_score"], errors="coerce"
    ).fillna(0.0).round(2)

    final_cols = [
        "Game", "Pitcher", "Pitcher Target Score", "Pitcher_HR9_Last7",
        "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed",
        "WeatherNote", "TempF", "WindMPH"
    ]

    out = out[[c for c in final_cols if c in out.columns]].copy()
    out = out.loc[:, ~out.columns.duplicated()].reset_index(drop=True)
    return out


c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("Update Board", use_container_width=True):
        st.session_state.manual_refresh_trigger = True
        st.cache_data.clear()
        st.rerun()


live_df, schedule = build_daily_dataset()
locked_df = ensure_daily_board_lock(live_df, schedule)

lineup_mode = get_lineup_mode(schedule) if schedule else "PROJECTED"

tracked_df = build_visible_tracker_pool(locked_df, schedule)
tracker = sync_tracker_with_board(tracked_df)
combo_board = build_combo_board(locked_df)
combo_tracker = sync_combo_tracker_with_board(combo_board)
save_daily_board_snapshot(tracked_df, today_str())

if st.session_state.get("force_tracker_refresh", False) or st.session_state.get("manual_refresh_trigger", False):
    tracker = auto_update_tracker_results(tracker, schedule)
    combo_tracker = auto_update_combo_tracker_results(combo_tracker, schedule)
    st.session_state.manual_refresh_trigger = False

save_daily_tracker_snapshot(tracker, today_str())

summary = summarize_tracker(tracker)
source_summary = summarize_tracker_sources(tracker)
daily_summary = summarize_tracker_by_day(tracker)
combo_summary = summarize_combo_tracker(combo_tracker)

with c2:
    st.metric("Games On Slate", len(schedule))
with c3:
    st.metric("Lineup Mode", lineup_mode)
with c4:
    confirmed_locked = 0
    if not locked_df.empty and "lock_scope" in locked_df.columns:
        confirmed_locked = int((locked_df["lock_scope"].astype(str) == "CONFIRMED_TEAM").sum())
    if confirmed_locked > 0:
        st.caption(f"Projected teams stay live • confirmed teams pregame-rebuild on update • locked confirmed rows: {confirmed_locked}")
    else:
        st.caption(f"Projected teams live • update rebuilds pregame confirmed locks • last refresh: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

if locked_df.empty:
    st.warning("No games or hitter data loaded.")
    st.stop()

base_tabs = ["HR Probability", "Top 12", "Top HR Targets", "Pitchers to Target", "HR Combos", "Hits + Runs + RBIs", "Batter Breakdown", "Accuracy Tracker"]
schedule = sort_schedule_rows(schedule)
game_tabs = [f"{format_game_time_et(g.get('game_time', ''))} | {g['game_key']}" for g in schedule]
tabs = st.tabs(base_tabs + game_tabs)

with tabs[0]:
    st.subheader("HR Probability Board")
    st.caption("Projected teams stay live. Confirmed teams freeze once lineups lock.")
    hr_df = get_strict_hr_pool(locked_df)
    st.dataframe(
        hr_df[[
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "Lineup Source", "HR Probability %", "HR Tier", "GroundBall%",
            "GB Rule", "GB Note", "Matchup Advantage", "Pitcher Target Score", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[1]:
    st.subheader("Top 12 HR Candidates")
    st.caption("Confirmed teams freeze once lineups lock. Projected teams can still update.")
    top12 = get_top12_hybrid(locked_df)
    st.dataframe(
        top12[[
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "Lineup Source", "HR Probability %", "HR Tier", "GroundBall%",
            "GB Rule", "GB Note", "Matchup Advantage", "Pitcher Target Score", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[2]:
    st.subheader("Top HR Targets — Slate-Wide Top 25")
    st.caption("Global slate ranking based on hitter authority, ISO/EV-style power, pitch exposure, pitcher HR/9 vulnerability, weather, park, and matchup advantage.")
    top_targets = get_best_hr_matchups(locked_df, 25)
    if top_targets.empty:
        st.caption("No global HR targets surfaced yet.")
    else:
        target_cols = [
            "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot", "Lineup Source",
            "Matchup Advantage", "Matchup Advantage Score", "Pitcher Target Score", "Pitcher_HR9_Last7",
            "EV", "Barrel%", "HardHit%", "AIR%", "xSLG", "xwOBA",
            "Pitch Mix Mode", "Relevant Pitch Mix", "Primary Pitch Usage",
            "HR Probability %", "HR Tier", "Ranking Reasons"
        ]
        st.dataframe(
            top_targets[[c for c in target_cols if c in top_targets.columns]],
            use_container_width=True,
            hide_index=True
        )

with tabs[3]:
    st.subheader("Pitchers to Target Today")
    st.caption("Attackability board emphasizing HR/9, barrel allowed, hard contact allowed, park/weather carry, and matchup vulnerability.")
    pitcher_targets = get_pitchers_to_target(locked_df)
    if pitcher_targets.empty:
        st.caption("No pitcher target data available yet.")
    else:
        pitcher_targets = pitcher_targets.loc[:, ~pitcher_targets.columns.duplicated()].copy()
        st.dataframe(
            pitcher_targets,
            use_container_width=True,
            hide_index=True
        )

with tabs[4]:
    st.subheader("HR Combos")
    st.caption("Randomized but high-likelihood HR ladders built from the best current board without cloning the same pairings.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Today Combos", combo_summary["today_total"])
    m2.metric("Today Full Hits", combo_summary["today_full_hits"])
    m3.metric("Today Partial Hits", combo_summary["today_partial_hits"])

    if combo_board.empty:
        st.caption("No combos generated yet.")
    else:
        for combo_type in ["2-Leg", "3-Leg", "4-Leg", "5-Leg"]:
            cdf = combo_board[combo_board["Combo Type"] == combo_type].copy()
            if cdf.empty:
                continue
            st.markdown(f"**{combo_type} HR Combos**")
            st.dataframe(
                cdf[["Combo #", "Combo Label", "Avg Leg HR %", "Combined Score", "Games"]],
                use_container_width=True,
                hide_index=True
            )

    if not combo_tracker.empty:
        st.divider()
        st.caption("Tracked combo history")
        st.dataframe(
            combo_tracker.sort_values(by=["date", "combo_size", "combined_score"], ascending=[False, True, False]),
            use_container_width=True,
            hide_index=True
        )

with tabs[5]:
    st.subheader("Hits + Runs + RBIs Board")
    st.caption("Confirmed teams freeze once lineups lock. Projected teams can still update.")
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

with tabs[6]:
    st.subheader("Batter Breakdown")
    st.caption("Projected teams stay live until confirmed. Heavy GB bats are downgraded, not blindly erased unless the profile is truly bad.")
    breakdown = sort_for_hr(locked_df.copy())
    st.dataframe(
        breakdown[[
            "Player", "Team", "Game", "Pitcher", "Lineup Spot", "Lineup Source", "Pitch Mix Mode", "Relevant Pitch Mix",
            "EV", "HardHit%", "FlyBall%", "AIR%", "LaunchAngle", "Recent Trend", "LineDrive%", "GroundBall%", "Barrel%",
            "xSLG", "xwOBA",
            "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed",
            "Pitcher Target Score", "Pitcher Target Label", "Matchup Advantage Score", "Matchup Advantage", "Ranking Reasons",
            "Statcast Pass", "Strict Statcast", "Recent Form Pass", "Pitcher Attackable",
            "Pitch_Isolation_Valid", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "BullpenFatigueScore", "TempF", "WindMPH", "HR Eligible",
            "HR Probability %", "HRR Score", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[7]:
    st.subheader("Accuracy Tracker")
    st.caption("Tracker is broken into separate sections so you can judge Core Board, Top 12, Per-Game HR, and Combos independently.")

    st.markdown("### Today by Section")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown("**Core Board**")
        st.metric("Surfaced", source_summary["CORE_BOARD"]["today_total"])
        st.metric("HR Hit", source_summary["CORE_BOARD"]["today_hits"])
        st.metric("Hit Rate %", source_summary["CORE_BOARD"]["today_pct"])
    with s2:
        st.markdown("**Top 12**")
        st.metric("Surfaced", source_summary["TOP12"]["today_total"])
        st.metric("HR Hit", source_summary["TOP12"]["today_hits"])
        st.metric("Hit Rate %", source_summary["TOP12"]["today_pct"])
    with s3:
        st.markdown("**Per-Game HR**")
        st.metric("Surfaced", source_summary["GAME_HR"]["today_total"])
        st.metric("HR Hit", source_summary["GAME_HR"]["today_hits"])
        st.metric("Hit Rate %", source_summary["GAME_HR"]["today_pct"])

    st.markdown("### Combo Section")
    cx1, cx2, cx3 = st.columns(3)
    cx1.metric("Today Combos", combo_summary["today_total"])
    cx2.metric("Today Full Hits", combo_summary["today_full_hits"])
    cx3.metric("Today Partial Hits", combo_summary["today_partial_hits"])

    st.divider()

    st.markdown("### All-Time by Section")
    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown("**Core Board**")
        st.metric("All Surfaced", source_summary["CORE_BOARD"]["all_total"])
        st.metric("All HR Hit", source_summary["CORE_BOARD"]["all_hits"])
        st.metric("All Hit Rate %", source_summary["CORE_BOARD"]["all_pct"])
    with a2:
        st.markdown("**Top 12**")
        st.metric("All Surfaced", source_summary["TOP12"]["all_total"])
        st.metric("All HR Hit", source_summary["TOP12"]["all_hits"])
        st.metric("All Hit Rate %", source_summary["TOP12"]["all_pct"])
    with a3:
        st.markdown("**Per-Game HR**")
        st.metric("All Surfaced", source_summary["GAME_HR"]["all_total"])
        st.metric("All HR Hit", source_summary["GAME_HR"]["all_hits"])
        st.metric("All Hit Rate %", source_summary["GAME_HR"]["all_pct"])

    st.divider()

    today_tracker = tracker[
        tracker["date"].astype("string").fillna("") == str(today_str())
    ].copy()

    if not today_tracker.empty:
        st.markdown("### Today's Split Tracker Tables")
        for section_name, source_key in [("Core Board", "CORE_BOARD"), ("Top 12", "TOP12"), ("Per-Game HR", "GAME_HR")]:
            section_df = today_tracker[today_tracker["tracker_source"].astype(str) == source_key].copy()
            st.markdown(f"**{section_name}**")
            if section_df.empty:
                st.caption("No tracked rows in this section today.")
            else:
                st.dataframe(
                    section_df.sort_values(
                        by=["hr_probability", "player"],
                        ascending=[False, True]
                    )[[
                        "player",
                        "team",
                        "game",
                        "hr_probability",
                        "hr_tier",
                        "tracker_source",
                        "hr_eligible",
                        "result",
                        "result_state",
                        "game_state",
                        "updated_at"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )

    if not combo_tracker.empty:
        st.divider()
        st.markdown("### Today's Combo Tracker")
        today_combo = combo_tracker[
            combo_tracker["date"].astype("string").fillna("") == str(today_str())
        ].copy()
        st.dataframe(
            today_combo.sort_values(
                by=["combo_size", "combined_score"],
                ascending=[True, False]
            )[[
                "combo_label",
                "combo_size",
                "avg_leg_probability",
                "combined_score",
                "legs_hit",
                "total_legs",
                "result_state",
                "updated_at"
            ]],
            use_container_width=True,
            hide_index=True
        )

    if not daily_summary.empty:
        st.divider()
        st.markdown("### Daily HR Prediction Accuracy History")
        st.dataframe(
            daily_summary,
            use_container_width=True,
            hide_index=True
        )

    if not combo_tracker.empty:
        st.divider()
        st.markdown("### Combo Tracker History")
        st.dataframe(
            combo_tracker.sort_values(
                by=["date", "combo_size", "combined_score"],
                ascending=[False, True, False]
            ),
            use_container_width=True,
            hide_index=True
        )

for idx, game in enumerate(schedule, start=8):
    with tabs[idx]:
        st.subheader(f"{game['game_key']} — {format_game_time_et(game.get('game_time', ''))}")
        st.caption(
            f"Start: {format_game_time_et(game.get('game_time', ''))}  |  "
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
            st.caption(f"Confirmed hitters: {game.get('away_confirmed_count', 0)}/9 | Pool status: {away_source}")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], away_team)
            if not team_hr.empty:
                st.markdown("**Best HR hitters**")
                st.dataframe(
                    team_hr[[
                        "Rank", "Player", "Lineup Spot", "Lineup Source", "Statcast Pass",
                        "Strict Statcast", "Recent Form Pass", "Pitcher Attackable", "HR Probability %",
                        "HR Tier", "GroundBall%", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%",
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
            st.caption(f"Confirmed hitters: {game.get('home_confirmed_count', 0)}/9 | Pool status: {home_source}")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], home_team)
            if not team_hr.empty:
                st.markdown("**Best HR hitters**")
                st.dataframe(
                    team_hr[[
                        "Rank", "Player", "Lineup Spot", "Lineup Source", "Statcast Pass",
                        "Strict Statcast", "Recent Form Pass", "Pitcher Attackable", "HR Probability %",
                        "HR Tier", "GroundBall%", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%",
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
