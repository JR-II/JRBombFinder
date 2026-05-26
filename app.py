import hashlib
import os
import glob
import shutil
import re
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import time 
st.set_page_config(page_title="BF Data", layout="wide")

st.markdown("""
<style>
:root {
    --bf-bg: #050608;
    --bf-panel: #0e1116;
    --bf-panel-2: #151922;
    --bf-border: rgba(255,255,255,0.10);
    --bf-border-strong: rgba(255,255,255,0.18);
    --bf-text: #f5f5f5;
    --bf-muted: #a8adb5;
    --bf-red: #ff5555;
    --bf-yellow: #ffd166;
    --bf-green: #35d07f;
}
.stApp { background: linear-gradient(180deg, #050608 0%, #090b10 54%, #050608 100%); color: var(--bf-text); }
.block-container { padding-top: .75rem; padding-bottom: 2rem; max-width: 1560px; }
[data-testid="stMetric"] { background: #10141b; border: 1px solid var(--bf-border); border-radius: 12px; padding: 7px 10px; box-shadow: none; }
[data-testid="stMetricLabel"] p { color: var(--bf-muted) !important; font-size: .76rem !important; }
[data-testid="stMetricValue"] { color: #fff !important; font-size: 1.12rem !important; font-weight: 850; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { background: #0f131a; border: 1px solid var(--bf-border); border-radius: 999px; padding: 7px 11px; }
.stTabs [aria-selected="true"] { background: #151922 !important; border-color: rgba(255,209,102,.65) !important; color: #ffffff !important; font-weight: 850; }
.bf-hero { border: 1px solid var(--bf-border-strong); border-radius: 18px; padding: 14px 16px; margin-bottom: 10px; background: #0f1319; box-shadow: none; }
.bf-kicker { color: var(--bf-yellow); font-size: .72rem; font-weight: 850; letter-spacing: .15em; text-transform: uppercase; }
.bf-title { font-size: clamp(1.45rem, 3vw, 2.85rem); font-weight: 950; line-height: 1; margin: 5px 0 5px 0; }
.bf-subtitle { color: var(--bf-muted); font-size: .9rem; max-width: 900px; }
.bf-key { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 6px; margin-top: 2px; margin-bottom: 3px; }
.bf-chip, .bf-key-chip { display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 8px; font-size: .72rem; font-weight: 800; border: 1px solid rgba(255,255,255,.12); background: rgba(255,255,255,.035); color: #ececec; white-space: nowrap; }
.bf-chip-green, .bf-key-green { color: #bcffd6; border-color: rgba(53,208,127,.55); background: rgba(53,208,127,.09); }
.bf-chip-yellow, .bf-key-yellow { color: #ffe4a3; border-color: rgba(255,209,102,.55); background: rgba(255,209,102,.10); }
.bf-chip-red, .bf-key-red { color: #ffb8b8; border-color: rgba(255,85,85,.55); background: rgba(255,85,85,.09); }
.bf-chip-gray { color: #c4c8cf; border-color: rgba(255,255,255,.12); background: rgba(255,255,255,.04); }
.bf-mini-row { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; margin: 4px 0 5px 0; }
.bf-signal-line { font-size: .82rem; line-height: 1.3; margin: 3px 0 5px 0; color: #e9e9e9; }
.bf-signal-line strong { color: #ffffff; }
.bf-signal-value-green { color: var(--bf-green); font-weight: 900; }
.bf-signal-value-yellow { color: var(--bf-yellow); font-weight: 900; }
.bf-signal-value-red { color: var(--bf-red); font-weight: 900; }
.bf-bar-wrap { margin: 7px 0 9px 0; }
.bf-bar-head { display: flex; justify-content: space-between; gap: 8px; font-size: .78rem; font-weight: 850; color: #e8e8e8; margin-bottom: 4px; }
.bf-track { height: 8px; border-radius: 999px; overflow: hidden; background: #252a33; border: 1px solid rgba(255,255,255,.08); }
.bf-fill { height: 100%; border-radius: 999px; }
.bf-fill-green { background: var(--bf-green); }
.bf-fill-yellow { background: var(--bf-yellow); }
.bf-fill-red { background: var(--bf-red); }
div[data-testid="stDataFrame"] { border: 1px solid rgba(255,255,255,.12); border-radius: 14px; overflow:hidden; }
div[data-testid="stExpander"] { background: rgba(255,255,255,.018); border-radius: 12px; }
hr { margin-top: .38rem !important; margin-bottom: .38rem !important; }
</style>
<div class="bf-hero">
    <div class="bf-kicker">BF DATA PRO LAB</div>
    <div class="bf-title">Daily Home Run Probability Engine</div>
    <div class="bf-subtitle">Matte dark board, compact player cards, green/yellow/red HR attackability signals, and transparent tracking built around the actual surfaced picks.</div>
</div>
""", unsafe_allow_html=True)

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
    if tracker_df is None or tracker_df.empty:
        return
    tracker_path = os.path.join(SNAPSHOT_DIR, f"hr_tracker_{snapshot_date}.csv")
    atomic_write_csv(tracker_df.copy(), tracker_path)


def save_daily_board_snapshot(board_df: pd.DataFrame, snapshot_date: str):
    """Persist surfaced HR board history without rewriting old predictions.

    If new visible players appear later from confirmed lineups or per-game boards,
    append them to the saved snapshot while preserving the original rows already stored.
    """
    ensure_snapshot_folder()
    if board_df is None or board_df.empty:
        return

    board_path = os.path.join(SNAPSHOT_DIR, f"hr_board_{snapshot_date}.csv")
    clean_board = board_df.copy()
    if "Actual HR Today" in clean_board.columns:
        clean_board = clean_board.drop(columns=["Actual HR Today"])

    key_cols = [c for c in ["Tracker Source", "Player", "Team", "Game"] if c in clean_board.columns]

    if os.path.exists(board_path):
        try:
            existing = pd.read_csv(board_path)
        except Exception:
            existing = pd.DataFrame()

        if not existing.empty and key_cols and all(c in existing.columns for c in key_cols):
            existing_keys = set(
                tuple(str(row.get(c, "")) for c in key_cols)
                for _, row in existing.iterrows()
            )
            add_rows = []
            for _, row in clean_board.iterrows():
                key = tuple(str(row.get(c, "")) for c in key_cols)
                if key not in existing_keys:
                    add_rows.append(row)
            if add_rows:
                merged = pd.concat([existing, pd.DataFrame(add_rows)], ignore_index=True)
                merged = dedupe_columns(merged) if "dedupe_columns" in globals() else merged.loc[:, ~merged.columns.duplicated()]
                atomic_write_csv(merged, board_path)
            return

    atomic_write_csv(clean_board, board_path)


def load_daily_board_snapshot(snapshot_date: str) -> pd.DataFrame:
    ensure_snapshot_folder()
    board_path = os.path.join(SNAPSHOT_DIR, f"hr_board_{snapshot_date}.csv")
    if os.path.exists(board_path):
        try:
            return pd.read_csv(board_path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def available_tracker_dates(tracker_df: pd.DataFrame) -> list[str]:
    dates = set()
    if tracker_df is not None and not tracker_df.empty and "date" in tracker_df.columns:
        dates.update(tracker_df["date"].dropna().astype(str).tolist())
    if os.path.exists(SNAPSHOT_DIR):
        for name in os.listdir(SNAPSHOT_DIR):
            m = re.match(r"hr_board_(\d{4}-\d{2}-\d{2})\.csv", name)
            if m:
                dates.add(m.group(1))
    dates.add(today_str())
    return sorted(dates, reverse=True)


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


def atomic_write_csv(df: pd.DataFrame, path: str):
    """Write CSV safely so refreshes do not leave half-written tracker files."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = f"{path}.tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, path)


def backup_csv_file(path: str):
    """Keep a local rolling backup before overwriting tracker files."""
    if not os.path.exists(path):
        return
    ensure_snapshot_folder()
    base = os.path.basename(path).replace(".csv", "")
    backup_path = os.path.join(SNAPSHOT_DIR, f"{base}_backup.csv")
    try:
        shutil.copy2(path, backup_path)
    except Exception:
        pass


def load_tracker_snapshots() -> pd.DataFrame:
    """Recover tracker history from daily snapshot files if the main tracker CSV is incomplete."""
    ensure_snapshot_folder()
    frames = []
    for snap_path in sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "hr_tracker_*.csv"))):
        try:
            snap = pd.read_csv(snap_path)
            if not snap.empty:
                frames.append(snap)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def normalize_tracker_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date", "player", "team", "game", "game_pk",
        "hr_probability", "hr_tier", "hr_eligible", "tracker_source",
        "result", "hr_count", "result_state", "game_state", "updated_at"
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = pd.NA
    return work[columns]


def load_tracker() -> pd.DataFrame:
    frames = []
    if os.path.exists(TRACKER_FILE):
        try:
            frames.append(pd.read_csv(TRACKER_FILE))
        except Exception:
            pass

    snap_df = load_tracker_snapshots()
    if not snap_df.empty:
        frames.append(snap_df)

    if os.path.exists(os.path.join(SNAPSHOT_DIR, "hr_tracker_backup.csv")):
        try:
            frames.append(pd.read_csv(os.path.join(SNAPSHOT_DIR, "hr_tracker_backup.csv")))
        except Exception:
            pass

    if not frames:
        return normalize_tracker_columns(pd.DataFrame())

    merged = normalize_tracker_columns(pd.concat(frames, ignore_index=True))
    if not merged.empty:
        key_cols = ["date", "player", "team", "game", "tracker_source"]
        merged["_norm_player"] = merged["player"].astype(str).map(normalize_name)
        merged["_has_result"] = pd.to_numeric(merged["hr_count"], errors="coerce").fillna(0).astype(int)
        merged["_has_result"] = merged["_has_result"] + pd.to_numeric(merged["result"], errors="coerce").fillna(0).astype(int)
        merged = merged.sort_values(by=["date", "_has_result", "updated_at"], ascending=[True, True, True])
        merged = merged.drop_duplicates(
            subset=["date", "_norm_player", "team", "game", "tracker_source"],
            keep="last"
        ).drop(columns=["_norm_player", "_has_result"])
    return normalize_tracker_columns(merged.reset_index(drop=True))


def save_tracker(df: pd.DataFrame):
    backup_csv_file(TRACKER_FILE)
    clean = normalize_tracker_columns(df)
    atomic_write_csv(clean, TRACKER_FILE)
    try:
        for date_key, day_df in clean.groupby(clean["date"].astype(str)):
            if date_key and date_key != "nan":
                save_daily_tracker_snapshot(day_df.copy(), date_key)
    except Exception:
        pass


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
    backup_csv_file(COMBO_TRACKER_FILE)
    atomic_write_csv(df.copy(), COMBO_TRACKER_FILE)


def load_board_locks() -> pd.DataFrame:
    if os.path.exists(LOCK_FILE):
        try:
            return pd.read_csv(LOCK_FILE)
        except Exception:
            pass
    return pd.DataFrame()


def save_board_locks(df: pd.DataFrame):
    backup_csv_file(LOCK_FILE)
    atomic_write_csv(df.copy(), LOCK_FILE)


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
    if "hr_count" in work.columns:
        work["result_num"] = (pd.to_numeric(work["hr_count"], errors="coerce").fillna(0).astype(int) > 0).astype(int)

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
    if "hr_count" in work.columns:
        work["result_num"] = (pd.to_numeric(work["hr_count"], errors="coerce").fillna(0).astype(int) > 0).astype(int)
    else:
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


def compute_l10_bbe_profile(live_metrics: dict, savant_values: dict) -> dict:
    """Recent batted-ball profile weighted toward the hitter's last 10 live games.

    MLB StatsAPI does not expose every individual batted-ball event in this lightweight app,
    so this builds a stable L10 BBE-style view by blending recent game damage with Savant
    batted-ball baselines. The scoring engine favors this recent profile over full-season rates.
    """
    if not live_metrics:
        return {
            "L10_BBE_EV": 0.0,
            "L10_BBE_HardHit%": 0.0,
            "L10_BBE_Barrel%": 0.0,
            "L10_BBE_AIR%": 0.0,
            "L10_BBE_GB%": 0.0,
            "L10_BBE_Score": 0.0,
            "L10_BBE_Trend": "UNKNOWN",
        }

    sav_ev = safe_float(savant_values.get("Savant_EV"), live_metrics.get("EV", 0.0))
    sav_hh = safe_float(savant_values.get("Savant_HardHit%"), live_metrics.get("HardHit%", 0.0))
    sav_brl = safe_float(savant_values.get("Savant_Barrel%"), live_metrics.get("Barrel%", 0.0))
    sav_fb = safe_float(savant_values.get("Savant_FB%"), live_metrics.get("FlyBall%", 0.0))
    sav_ld = safe_float(savant_values.get("Savant_LD%"), live_metrics.get("LineDrive%", 0.0))
    sav_air = safe_float(savant_values.get("Savant_AIR%"), max(0.0, sav_fb + sav_ld))
    sav_gb = safe_float(savant_values.get("Savant_GB%"), live_metrics.get("GroundBall%", 0.0))

    recent_ev = safe_float(live_metrics.get("EV"), sav_ev)
    recent_hh = safe_float(live_metrics.get("HardHit%"), sav_hh)
    recent_brl = safe_float(live_metrics.get("Barrel%"), sav_brl)
    recent_air = safe_float(live_metrics.get("FlyBall%"), 0.0) + safe_float(live_metrics.get("LineDrive%"), 0.0)
    recent_gb = safe_float(live_metrics.get("GroundBall%"), sav_gb)

    # Weight recent L10 form heavier than season-long Savant baselines.
    l10_ev = (recent_ev * 0.68) + (sav_ev * 0.32)
    l10_hh = (recent_hh * 0.68) + (sav_hh * 0.32)
    l10_brl = (recent_brl * 0.70) + (sav_brl * 0.30)
    l10_air = (recent_air * 0.66) + (sav_air * 0.34)
    l10_gb = (recent_gb * 0.66) + (sav_gb * 0.34)

    score = (
        max(0.0, l10_ev - 87.0) * 2.0 +
        max(0.0, l10_hh - 35.0) * 1.25 +
        max(0.0, l10_brl - 7.0) * 3.6 +
        max(0.0, l10_air - 48.0) * 0.9 -
        max(0.0, l10_gb - 48.0) * 1.4 +
        safe_float(live_metrics.get("recent_hr"), 0.0) * 7.0 +
        safe_float(live_metrics.get("recent_xbh"), 0.0) * 2.2
    )
    score = round(clip(score, 0.0, 100.0), 1)

    if score >= 70:
        trend = "L10 BBE HOT"
    elif score >= 50:
        trend = "L10 BBE LIVE"
    elif score >= 32:
        trend = "L10 BBE MIXED"
    else:
        trend = "L10 BBE COLD"

    return {
        "L10_BBE_EV": round(l10_ev, 1),
        "L10_BBE_HardHit%": round(l10_hh, 1),
        "L10_BBE_Barrel%": round(l10_brl, 1),
        "L10_BBE_AIR%": round(l10_air, 1),
        "L10_BBE_GB%": round(l10_gb, 1),
        "L10_BBE_Score": score,
        "L10_BBE_Trend": trend,
    }


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
    """HR-focused pitcher damage profile.

    This intentionally answers: can this pitcher be taken deep?
    It blends season HR leakage with the recent starter window so a pitcher who
    is generally good but still allows HR damage does not get incorrectly marked
    as a poor target.
    """
    if pd.isna(pitcher_id):
        return None

    data = stats_map.get(pitcher_id, {"season": {}, "gamelog": []})
    season_stat = data.get("season", {}) or {}
    gamelog = data.get("gamelog", []) or []

    season_ip = ip_to_float(season_stat.get("inningsPitched", 0))
    season_hr_allowed = safe_int(season_stat.get("homeRuns", 0))
    season_hits_allowed = safe_int(season_stat.get("hits", 0))
    season_walks_allowed = safe_int(season_stat.get("baseOnBalls", 0))

    season_hr9 = (season_hr_allowed * 9 / season_ip) if season_ip > 0 else stable_float(f"{pitcher_name}-season-hr9-fallback", 0.8, 1.6)
    season_hit9 = (season_hits_allowed * 9 / season_ip) if season_ip > 0 else stable_float(f"{pitcher_name}-season-hit9-fallback", 6.5, 10.5)
    season_whip = ((season_hits_allowed + season_walks_allowed) / season_ip) if season_ip > 0 else stable_float(f"{pitcher_name}-season-whip-fallback", 1.0, 1.5)

    if gamelog:
        starts_only = [g for g in gamelog if safe_int(g["stat"].get("gamesStarted", 0)) > 0]
        use_logs = starts_only[:7] if starts_only else gamelog[:7]
    else:
        use_logs = []

    if use_logs:
        recent_ip = sum(ip_to_float(g["stat"].get("inningsPitched", 0)) for g in use_logs)
        recent_hr_allowed = sum(safe_int(g["stat"].get("homeRuns", 0)) for g in use_logs)
        recent_hits_allowed = sum(safe_int(g["stat"].get("hits", 0)) for g in use_logs)
        recent_walks_allowed = sum(safe_int(g["stat"].get("baseOnBalls", 0)) for g in use_logs)

        recent_hr9 = (recent_hr_allowed * 9 / recent_ip) if recent_ip > 0 else season_hr9
        recent_hit9 = (recent_hits_allowed * 9 / recent_ip) if recent_ip > 0 else season_hit9
        recent_whip = ((recent_hits_allowed + recent_walks_allowed) / recent_ip) if recent_ip > 0 else season_whip
    else:
        recent_hr9 = season_hr9
        recent_hit9 = season_hit9
        recent_whip = season_whip

    # Blend recent with season. Use the higher HR leakage when it is meaningfully above the blend,
    # because HR props care about damage allowed more than real-life run prevention.
    blended_hr9 = (recent_hr9 * 0.55) + (season_hr9 * 0.45)
    hr9 = max(blended_hr9, season_hr9 * 0.92, recent_hr9 * 0.85)
    hit9 = (recent_hit9 * 0.50) + (season_hit9 * 0.50)
    whip = (recent_whip * 0.50) + (season_whip * 0.50)

    barrel_allowed = clip(2.2 + hr9 * 4.8 + (hit9 - 6) * 0.55, 3, 16)
    hard_hit_allowed = clip(25 + hr9 * 9.2 + (whip - 1.0) * 18, 25, 52)

    return {
        "Pitcher_HR9_Last7": round(hr9, 2),
        "Pitcher_Season_HR9": round(season_hr9, 2),
        "Pitcher_Recent_HR9": round(recent_hr9, 2),
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



def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Streamlit/Arrow crashes if a dataframe has duplicate column names."""
    if df is None or df.empty:
        return df
    return df.loc[:, ~df.columns.duplicated()].copy()


def display_existing_columns(df: pd.DataFrame, columns: list[str], **kwargs):
    """Safely display only columns that exist, with duplicate column protection."""
    if df is None or df.empty:
        st.caption("No rows to display.")
        return
    safe_df = dedupe_columns(df)
    cols = [c for c in columns if c in safe_df.columns]
    if not cols:
        st.dataframe(safe_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(safe_df[cols], use_container_width=True, hide_index=True)


def compute_pitcher_target_score(
    pitch_hr9: float,
    pitch_barrel_allowed: float,
    pitch_hard_hit_allowed: float,
    park_factor: float,
    weather_boost: float,
) -> tuple[float, str]:
    """HR Attackability score.

    Green/high means GOOD for the hitter because the pitcher leaks HR damage.
    Red/low means the pitcher is suppressing the HR profile.
    """
    score = 0.0
    bits = []

    # HR/9 is the anchor. A pitcher around 1.25+ HR/9 is attackable for HR props.
    if pitch_hr9 >= 2.00:
        score += 22.0
        bits.append("elite HR leak")
    elif pitch_hr9 >= 1.60:
        score += 17.0
        bits.append("high HR/9 leak")
    elif pitch_hr9 >= 1.25:
        score += 12.0
        bits.append("attackable HR/9")
    elif pitch_hr9 >= 1.05:
        score += 7.0
        bits.append("mild HR leakage")
    elif pitch_hr9 >= 0.85:
        score += 3.0
        bits.append("below-target HR/9")
    else:
        bits.append("HR suppressor")

    # Barrel / hard-contact allowed should push a pitcher into target range even if ERA looks fine.
    if pitch_barrel_allowed >= 11:
        score += 12.0
        bits.append("barrel-prone pitcher")
    elif pitch_barrel_allowed >= 8:
        score += 8.0
        bits.append("allows barrels")
    elif pitch_barrel_allowed >= 6.5:
        score += 4.0
        bits.append("some barrel leakage")
    else:
        bits.append("low barrel leak")

    if pitch_hard_hit_allowed >= 44:
        score += 9.0
        bits.append("hard contact allowed")
    elif pitch_hard_hit_allowed >= 40:
        score += 6.0
        bits.append("contact damage allowed")
    elif pitch_hard_hit_allowed >= 36:
        score += 3.0
        bits.append("some hard contact")
    else:
        bits.append("contact suppressor")

    park_boost = (park_factor - 1.0) * 20
    if park_boost >= 1.0:
        score += park_boost
        bits.append("HR-friendly park")
    elif park_boost <= -1.0:
        score += park_boost * 0.6
        bits.append("park suppresses HR")

    if weather_boost >= 1.5:
        score += weather_boost * 2.0
        bits.append("carry weather")
    elif weather_boost <= -1.0:
        score += weather_boost * 0.9
        bits.append("weather suppresses carry")

    score = clip(score, 0.0, 45.0)

    if score >= 24:
        label = "STRONG HR ATTACK"
    elif score >= 13:
        label = "MIXED / ATTACKABLE"
    else:
        label = "POOR HR TARGET"

    return round(score, 2), f"{label}: " + " | ".join(bits[:4])



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
        reasons.append("great air-ball shape")
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

    try:
        if lineup_spot is not None and str(lineup_spot) != "—":
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
        reasons = ["ranked by blended matchup score"]

    return round(score, 2), label, " | ".join(reasons[:7])


def get_best_hr_matchups(df: pd.DataFrame, limit: int = 25) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    board = df.copy()
    if "Matchup Advantage Score" not in board.columns:
        board["Matchup Advantage Score"] = safe_numeric_series(board, "Model Rank Score", 0.0)
    if "HR Attackability Score" not in board.columns:
        board["HR Attackability Score"] = safe_numeric_series(board, "Pitcher_HR9_Last7", 0.0) * 10
    if "HR Attackability Score" not in board.columns:
        board["HR Attackability Score"] = board["HR Attackability Score"]

    eligible = board[board["HR Eligible"].astype(bool)].copy()
    if eligible.empty:
        eligible = board.copy()

    eligible["_global_score"] = (
        safe_numeric_series(eligible, "Matchup Advantage Score", 0.0) * 1.35
        + safe_numeric_series(eligible, "HR Attackability Score", 0.0) * 1.10
        + safe_numeric_series(eligible, "Statcast Authority Score", 0.0) * 0.85
        + safe_numeric_series(eligible, "Model Rank Score", 0.0) * 0.05
        + safe_numeric_series(eligible, "HR Probability %", 0.0) * 1.4
    )

    eligible = eligible.sort_values("_global_score", ascending=False).drop(columns=["_global_score"]).head(limit)
    return add_rank_column(dedupe_columns(eligible.reset_index(drop=True)))


def get_pitchers_to_target(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    for col in [
        "Game", "Pitcher", "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed",
        "Pitcher_HardHit_Allowed", "Pitcher_Season_HR9", "Pitcher_Recent_HR9", "TempF", "WindMPH", "WeatherNote", "WeatherBoost"
    ]:
        if col not in work.columns:
            work[col] = pd.NA

    if "HR Attackability Score" in work.columns:
        work["_bf_pitcher_target_score"] = safe_numeric_series(work, "HR Attackability Score", 0.0)
    else:
        work["_bf_pitcher_target_score"] = (
            safe_numeric_series(work, "Pitcher_HR9_Last7", 0.0) * 8
            + safe_numeric_series(work, "Pitcher_Barrel_Allowed", 0.0) * 1.3
            + safe_numeric_series(work, "Pitcher_HardHit_Allowed", 0.0) * 0.55
            + safe_numeric_series(work, "WeatherBoost", 0.0) * 2.5
        ).clip(0, 45)

    out = (
        work.sort_values("_bf_pitcher_target_score", ascending=False)
        .drop_duplicates(subset=["Game", "Pitcher"])
        .head(15)
        .copy()
    )
    out["HR Attackability Score"] = pd.to_numeric(out["_bf_pitcher_target_score"], errors="coerce").fillna(0.0).round(2)
    out["HR Attackability %"] = out["HR Attackability Score"].apply(_attackability_pct)
    out["HR Attackability Status"] = out["HR Attackability %"].apply(lambda v: _attackability_bucket(v, already_pct=True)[0])
    out["Pitcher HR Profile"] = out["HR Attackability %"].apply(lambda v: _attackability_note(v, already_pct=True))

    final_cols = [
        "Game", "Pitcher", "HR Attackability %", "HR Attackability Status", "Pitcher HR Profile",
        "HR Attackability %", "HR Attackability Status", "HR Attackability Score", "Pitcher_HR9_Last7", "Pitcher_Season_HR9", "Pitcher_Recent_HR9",
        "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed",
        "WeatherNote", "TempF", "WindMPH"
    ]
    out = out[[c for c in final_cols if c in out.columns]].copy()
    return dedupe_columns(out.reset_index(drop=True))



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
    weather_boost: float = 0.0,
    weather_note: str = "neutral weather",
    temp_f: float = 72.0,
    wind_mph: float = 7.0,
    bullpen_fatigue_score: float = 0.0,
    bullpen_fatigue_note: str = "Neutral bullpen rest",
    bullpen_ip_prev: float = 0.0,
    bullpen_arms_prev: int = 0,
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
    launch_angle = safe_float(sav.get("Savant_LA"), 14.0)
    xslg = safe_float(sav.get("Savant_xSLG"), 0.0)
    xwoba = safe_float(sav.get("Savant_xwOBA"), 0.0)
    xiso = safe_float(sav.get("Savant_xISO"), live_hitter["recent_iso"])

    l10_bbe = compute_l10_bbe_profile(live_hitter, sav)

    # Recent BBE view is the hitter engine's primary authority input.
    # Season Savant still stabilizes the number, but L10 form drives the model.
    ev = round((l10_bbe["L10_BBE_EV"] * 0.72) + (ev * 0.28), 1)
    hard_hit = round((l10_bbe["L10_BBE_HardHit%"] * 0.72) + (hard_hit * 0.28), 1)
    barrel = round((l10_bbe["L10_BBE_Barrel%"] * 0.74) + (barrel * 0.26), 1)
    air_pct = round((l10_bbe["L10_BBE_AIR%"] * 0.70) + (air_pct * 0.30), 1)
    ground_ball = round((l10_bbe["L10_BBE_GB%"] * 0.70) + (ground_ball * 0.30), 1)

    recent_hr = live_hitter["recent_hr"]
    recent_xbh = live_hitter["recent_xbh"]
    recent_iso = live_hitter["recent_iso"]
    recent_avg = live_hitter["recent_avg"]
    recent_rbi = live_hitter["recent_rbi"]
    recent_runs = live_hitter["recent_runs"]
    recent_pa = live_hitter["recent_pa"]

    recent_damage_score = (
        (recent_hr * 9.0) +
        (recent_xbh * 3.0) +
        (recent_iso * 65.0) +
        (recent_avg * 18.0) +
        (l10_bbe["L10_BBE_Score"] * 0.16)
    )

    if recent_hr >= 2 or recent_xbh >= 5 or recent_iso >= 0.260 or l10_bbe["L10_BBE_Score"] >= 72:
        recent_trend = "HOT"
    elif recent_hr >= 1 or recent_xbh >= 3 or recent_iso >= 0.180 or l10_bbe["L10_BBE_Score"] >= 52:
        recent_trend = "LIVE"
    elif recent_iso >= 0.120 or recent_avg >= 0.260 or l10_bbe["L10_BBE_Score"] >= 34:
        recent_trend = "NEUTRAL"
    else:
        recent_trend = "COLD"

    display_spot = display_lineup_spot(lineup_spot)
    bats = estimate_handedness_from_name(player_name, "batter")
    pitcher_throws = estimate_handedness_from_name(opp_pitcher, "pitcher")

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
    weather_score_boost = weather_boost * 1.6
    bullpen_fatigue_boost = bullpen_fatigue_score * 1.8

    pitch_mix_example = build_pitch_mix_profile(
        opp_pitcher,
        opp_pitcher_id,
        pitch_hr9,
        pitch_barrel_allowed,
        pitch_hard_hit_allowed,
        pitcher_throws,
    )
    pitch_context = compute_relevant_pitch_matchup(
        pitch_mix_example,
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
    pitch_mix_mode = pitch_context["mode"]
    relevant_pitch_mix = pitch_context["label"]
    primary_pitch = pitch_context["primary_pitch"]
    primary_pitch_usage = pitch_context["usage"]
    pitch_gap = pitch_context["gap"]
    pitch_matchup_score = pitch_context["score"]
    pitch_matchup_label = pitch_context["reason"]
    handedness_edge = pitch_context["handedness_edge"]

    pitch_isolation_bonus = -2.5
    pitch_isolation_valid = "No"

    elite_statcast_profile = (
        (
            barrel >= 10
            and hard_hit >= 45
            and air_pct >= 55
            and ground_ball <= 50
        )
        or (
            barrel >= 11
            and xslg >= 0.500
            and xwoba >= 0.340
            and 10 <= launch_angle <= 24
        )
    )

    weak_pitch_shape = (
        barrel < 9 and hard_hit < 39 and xslg < 0.430 and air_pct < 52
    )

    statcast_authority_score, statcast_authority_multiplier, statcast_authority_tier = compute_statcast_authority(
        ev,
        barrel,
        hard_hit,
        air_pct,
        launch_angle,
        xslg,
        ground_ball,
    )

    multi_pitch_authority_score = compute_multi_pitch_authority_score(
        pitch_mix_mode,
        pitch_matchup_score,
        barrel,
        hard_hit,
        air_pct,
        xslg,
        ev,
        lineup_spot,
        recent_trend,
    )

    pitcher_target_score, pitcher_target_label = compute_pitcher_target_score(
        pitch_hr9,
        pitch_barrel_allowed,
        pitch_hard_hit_allowed,
        park_factor,
        weather_boost,
    )

    matchup_advantage_score, matchup_advantage_tier, ranking_reasons = compute_matchup_advantage_score(
        ev=ev,
        barrel=barrel,
        hard_hit=hard_hit,
        air_pct=air_pct,
        xslg=xslg,
        xwoba=xwoba,
        ground_ball=ground_ball,
        pitch_matchup_score=pitch_matchup_score,
        pitch_hr9=pitch_hr9,
        pitch_barrel_allowed=pitch_barrel_allowed,
        pitch_hard_hit_allowed=pitch_hard_hit_allowed,
        handedness_edge=handedness_edge,
        lineup_spot=lineup_spot,
        recent_trend=recent_trend,
        statcast_authority_tier=statcast_authority_tier,
        pitch_mix_mode=pitch_mix_mode,
        primary_pitch_usage=primary_pitch_usage,
        park_factor=park_factor,
        weather_boost=weather_boost,
    )

    elite_hr_flag = elite_hr_look(pd.Series({
        "Barrel%": barrel,
        "HardHit%": hard_hit,
        "AIR%": air_pct,
        "xSLG": xslg,
        "EV": ev,
        "GroundBall%": ground_ball,
    }))

    if pitch_mix_mode == "HARD" and primary_pitch is not None:
        pitch_isolation_valid = "Yes"
        pitch_isolation_bonus = pitch_matchup_score
    elif pitch_mix_mode == "SOFT":
        if weak_pitch_shape and not elite_statcast_profile:
            pitch_isolation_valid = "Soft No Edge"
            pitch_isolation_bonus = min(pitch_matchup_score - 2.0, -0.75)
        else:
            pitch_isolation_valid = "Soft Isolate"
            pitch_isolation_bonus = pitch_matchup_score * 0.96
    elif pitch_mix_mode == "BALANCED":
        if weak_pitch_shape and not elite_statcast_profile and not (barrel >= 10 or hard_hit >= 42 or xslg >= 0.470):
            pitch_isolation_valid = "Balanced No Edge"
            pitch_isolation_bonus = min(pitch_matchup_score - 2.0, -1.0)
        else:
            pitch_isolation_valid = "Balanced Mix"
            pitch_isolation_bonus = pitch_matchup_score * 0.92
    elif elite_statcast_profile:
        pitch_isolation_valid = "Elite Statcast Override"
        pitch_isolation_bonus = 2.25

    if pitch_isolation_valid != "No":
        if pitch_isolation_valid == "Elite Statcast Override":
            pitch_isolation_bonus = pitch_isolation_bonus * max(statcast_authority_multiplier, 0.75)
        else:
            pitch_isolation_bonus = pitch_isolation_bonus * statcast_authority_multiplier

    if statcast_authority_tier == "FAIL" and pitch_mix_mode != "HARD" and not elite_statcast_profile:
        pitch_isolation_bonus = min(pitch_isolation_bonus, -3.5)
    elif statcast_authority_tier == "WEAK" and pitch_mix_mode == "BALANCED" and not elite_statcast_profile:
        pitch_isolation_bonus = min(pitch_isolation_bonus, -2.0)

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

    confirmed_keep_override = bool(
        lineup_source == "CONFIRMED"
        and lineup_spot is not None
        and lineup_spot <= 4
        and pitch_mix_mode == "HARD"
        and pitch_matchup_score >= 5.0
    )

    confirmed_authority_fail = bool(
        lineup_source == "CONFIRMED"
        and statcast_authority_tier in {"FAIL", "WEAK"}
        and ev < 90.0
        and barrel < 12.0
        and hard_hit < 40.0
        and xslg < 0.450
        and not elite_override
    )

    confirmed_blend_fail = bool(
        lineup_source == "CONFIRMED"
        and pitch_mix_mode != "HARD"
        and ev < 90.0
        and barrel < 11.0
        and hard_hit < 41.0
        and xslg < 0.455
        and air_pct < 55.0
        and not elite_override
    )

    if (confirmed_authority_fail or confirmed_blend_fail) and not confirmed_keep_override:
        hr_eligible = False

    base_score = (
        (barrel - 4) * 4.2 +
        (hard_hit - 28) * 2.5 +
        (air_pct - 45) * 1.2 +
        (ev - 87) * 1.1 +
        (xslg * 100) * 1.2 +
        (xiso * 100) * 0.7 +
        (xwoba * 100) * 0.45 +
        pitch_isolation_bonus +
        handedness_edge +
        (pitch_hr9 - 0.7) * 10.0 +
        (pitch_barrel_allowed - 4) * 0.9 +
        (pitch_hard_hit_allowed - 30) * 0.4 +
        (recent_hr * 3.2) +
        (recent_xbh * 1.5) +
        (recent_iso * 24.0) +
        (recent_damage_score * 0.22) +
        (l10_bbe["L10_BBE_Score"] * 0.18) +
        pullside_boost +
        park_boost +
        weather_score_boost +
        bullpen_fatigue_boost +
        (pitcher_target_score * 0.35) +
        (matchup_advantage_score * 0.28)
    )

    if statcast_authority_tier == "ELITE":
        base_score += 4.5
    elif statcast_authority_tier == "STRONG":
        base_score += 2.0
    elif statcast_authority_tier == "MEDIUM":
        base_score -= 0.5
    elif statcast_authority_tier == "WEAK":
        base_score -= 4.0
    else:
        base_score -= 8.0

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

    if 12 <= launch_angle <= 22:
        base_score += 3.0
    elif 8 <= launch_angle < 12 or 22 < launch_angle <= 28:
        base_score += 1.0
    else:
        base_score -= 2.0

    if barrel >= 14:
        base_score += 6.0
    elif barrel < 8:
        base_score -= 7.0

    if hard_hit >= 45:
        base_score += 5.0
    elif hard_hit < 35:
        base_score -= 7.0

    if pitch_mix_mode == "HARD" and primary_pitch_usage >= 50:
        base_score += 2.8
    elif pitch_mix_mode == "HARD" and pitch_gap > 20:
        base_score += 1.8
    elif pitch_mix_mode == "SOFT":
        base_score += 0.9

    if not pitcher_attackable:
        base_score -= 4.0
    if weak_recent_profile:
        base_score -= 10.0
    if awful_hr_shape:
        base_score -= 14.0
    if recent_trend == "HOT":
        base_score += 4.0
    elif recent_trend == "LIVE":
        base_score += 2.0
    elif recent_trend == "COLD":
        base_score -= 4.0
    if lineup_source == "PROJECTED" and lineup_spot is None:
        if (
            statcast_authority_tier in {"ELITE", "STRONG"}
            or barrel >= 10.0
            or xslg >= 0.470
            or hard_hit >= 42.0
            or recent_trend in {"HOT", "LIVE"}
            or pitch_mix_mode in {"HARD", "SOFT"}
            or pitch_matchup_score >= 4.5
        ):
            base_score -= 1.25
        else:
            base_score -= 4.0
    if elite_override and ground_ball < 55:
        base_score += 2.5

    if not hr_eligible and elite_hr_flag and lineup_source == "PROJECTED":
        hr_prob = max(7.5, min(18.0, base_score / 7.0))
    elif not hr_eligible:
        hr_prob = 0.0
    else:
        hr_prob = max(3.0, min(28.0, (base_score + multi_pitch_authority_score * 2.2) / 6.6))

    if elite_hr_flag and hr_prob < 10.5:
        hr_prob = 10.5

    hrr_score = (
        (ev - 87) * 1.1 +
        (hard_hit - 28) * 1.0 +
        (line_drive - 14) * 0.9 +
        (pitch_hard_hit_allowed - 30) * 0.4 +
        park_boost +
        (recent_runs * 0.7) +
        (recent_rbi * 0.7) +
        (recent_avg * 15) +
        (weather_boost * 0.8) +
        (bullpen_fatigue_score * 0.7)
    )
    if lineup_spot is not None:
        hrr_score += max(0, 10 - lineup_spot) * 1.5

    gb_note = get_gb_explanation(ground_ball, barrel, air_pct, xslg)

    reasons = []
    reasons.append(f"{lineup_source} lineup pool")
    reasons.append("Statcast damage pass" if statcast_pass else "Failed Statcast damage")
    reasons.append("Pitcher attackable" if pitcher_attackable else "Pitcher less attackable")
    reasons.append("Recent damage form" if recent_form_pass else "Weak recent form")

    if pitch_isolation_valid == "Yes" and elite_statcast_profile:
        reasons.append("Elite + isolation combo")
    elif pitch_isolation_valid in ["Yes", "Soft Isolate", "Balanced Mix"]:
        reasons.append(pitch_matchup_label)
    elif multi_pitch_authority_score >= 3.5:
        reasons.append("Multi-pitch authority path")
    elif pitch_isolation_valid == "Elite Statcast Override":
        reasons.append("Elite Statcast override")
    else:
        reasons.append("No pitch edge")

    if recent_trend == "HOT":
        reasons.append("Hot recent trend")
    elif recent_trend == "LIVE":
        reasons.append("Live recent trend")
    elif recent_trend == "COLD":
        reasons.append("Cold recent trend")
    else:
        reasons.append("Neutral recent trend")

    if weather_boost >= 1.5:
        reasons.append("Weather carry boost")
    elif weather_boost <= -1.0:
        reasons.append("Weather suppression")
    else:
        reasons.append("Neutral weather")

    if statcast_authority_tier == "ELITE":
        reasons.append("Elite Statcast authority")
    elif statcast_authority_tier == "STRONG":
        reasons.append("Strong Statcast authority")
    elif statcast_authority_tier == "MEDIUM":
        reasons.append("Moderate Statcast authority")
    elif statcast_authority_tier == "WEAK":
        reasons.append("Weak Statcast authority")
    else:
        reasons.append("Statcast authority fail")

    if bullpen_fatigue_score >= 2.0:
        reasons.append("Bullpen fatigue boost")
    elif bullpen_fatigue_score >= 0.8:
        reasons.append("Bullpen slightly taxed")
    else:
        reasons.append("Bullpen rested")

    if ground_ball >= 50:
        reasons.append("Heavy GB downgrade")
    elif ground_ball >= 45:
        reasons.append("Borderline GB caution")
    else:
        reasons.append("Clean launch shape")

    if barrel >= 12:
        reasons.append("Strong barrel")
    elif hard_hit >= 40:
        reasons.append("Hard-hit target")
    elif air_pct >= 55:
        reasons.append("Air-ball target")

    model_rank_score = (
        (barrel * 5.6) +
        (hard_hit * 3.0) +
        (air_pct * 1.5) +
        (xslg * 145) +
        (xwoba * 72) +
        (max(0, 24 - abs(launch_angle - 18)) * 1.5) +
        (pitch_hr9 * 8.0) +
        (pitch_barrel_allowed * 1.1) +
        (recent_hr * 5.0) +
        (recent_xbh * 1.8) +
        (recent_iso * 24.0) +
        (recent_damage_score * 0.35) +
        (l10_bbe["L10_BBE_Score"] * 0.42) +
        (pitch_matchup_score * 2.1) +
        (handedness_edge * 1.7) +
        (weather_boost * 4.0) +
        (bullpen_fatigue_score * 4.8) +
        (statcast_authority_score * 1.55) +
        (multi_pitch_authority_score * 3.0) +
        (pitcher_target_score * 1.15) +
        (matchup_advantage_score * 1.05)
    )

    if pitch_isolation_valid == "Yes":
        model_rank_score += 7.5
    elif pitch_isolation_valid == "Elite Statcast Override":
        model_rank_score += 5.0

    if pitch_mix_mode == "HARD" and primary_pitch_usage >= 50:
        model_rank_score += 4.0
    elif pitch_mix_mode == "HARD" and pitch_gap > 20:
        model_rank_score += 2.0
    elif pitch_mix_mode == "SOFT":
        model_rank_score += 1.5
    elif pitch_mix_mode == "BALANCED" and elite_hr_flag:
        model_rank_score += 3.0

    if recent_trend == "HOT":
        model_rank_score += 6.0
    elif recent_trend == "LIVE":
        model_rank_score += 3.0
    elif recent_trend == "COLD":
        model_rank_score -= 5.0

    if ground_ball >= 55:
        model_rank_score -= 18.0
    elif ground_ball >= 50:
        model_rank_score -= 10.0
    elif ground_ball >= 45:
        model_rank_score -= 4.0

    if lineup_spot is not None:
        if lineup_spot <= 4:
            model_rank_score += 5.0
        elif lineup_spot <= 6:
            model_rank_score += 2.0

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
        "Pitcher Throws": pitcher_throws,
        "Pitch Mix Mode": pitch_mix_mode,
        "Relevant Pitch Mix": relevant_pitch_mix,
        "Primary Pitch": primary_pitch if primary_pitch is not None else "Mix",
        "Primary Pitch Usage": round(primary_pitch_usage, 1),
        "Pitch Gap": round(pitch_gap, 1),
        "Pitch Matchup Score": round(pitch_matchup_score, 2),
        "Handedness Edge": round(handedness_edge, 2),
        "Lineup Spot": display_spot,
        "Lineup Source": lineup_source,
        "EV": round(ev, 1),
        "HardHit%": round(hard_hit, 1),
        "FlyBall%": round(fly_ball, 1),
        "LineDrive%": round(line_drive, 1),
        "GroundBall%": round(ground_ball, 1),
        "Barrel%": round(barrel, 1),
        "AIR%": round(air_pct, 1),
        "LaunchAngle": round(launch_angle, 1),
        "L10 BBE EV": l10_bbe["L10_BBE_EV"],
        "L10 BBE HardHit%": l10_bbe["L10_BBE_HardHit%"],
        "L10 BBE Barrel%": l10_bbe["L10_BBE_Barrel%"],
        "L10 BBE AIR%": l10_bbe["L10_BBE_AIR%"],
        "L10 BBE GB%": l10_bbe["L10_BBE_GB%"],
        "L10 BBE Score": l10_bbe["L10_BBE_Score"],
        "L10 BBE Trend": l10_bbe["L10_BBE_Trend"],
        "Recent Trend": recent_trend,
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
        "Elite HR Look": "Yes" if elite_hr_flag else "No",
        "Multi Pitch Authority Score": round(multi_pitch_authority_score, 2),
        "HR Probability %": round(hr_prob, 1),
        "HRR Score": round(hrr_score, 1),
        "Model Rank Score": round(model_rank_score, 2),
        "TempF": round(temp_f, 1),
        "WindMPH": round(wind_mph, 1),
        "WeatherBoost": round(weather_boost, 2),
        "WeatherNote": weather_note,
        "BullpenFatigueScore": round(bullpen_fatigue_score, 2),
        "BullpenFatigueNote": bullpen_fatigue_note,
        "BullpenIPPrev": round(bullpen_ip_prev, 1),
        "BullpenArmsPrev": int(bullpen_arms_prev),
        "Statcast Authority Score": round(statcast_authority_score, 2),
        "Statcast Authority Tier": statcast_authority_tier,
        "HR Attackability Score": round(pitcher_target_score, 2),
        "HR Attackability %": _attackability_pct(pitcher_target_score),
        "HR Attackability Label": pitcher_target_label,
        "HR Attackability Status": _attackability_bucket(pitcher_target_score)[0],
        "Pitcher HR Profile": _attackability_note(pitcher_target_score),
        "Pitcher Season HR/9": live_pitcher.get("Pitcher_Season_HR9", round(pitch_hr9, 2)) if live_pitcher else round(pitch_hr9, 2),
        "Pitcher Recent HR/9": live_pitcher.get("Pitcher_Recent_HR9", round(pitch_hr9, 2)) if live_pitcher else round(pitch_hr9, 2),
        "Matchup Advantage Score": round(matchup_advantage_score, 2),
        "Matchup Advantage": matchup_advantage_tier,
        "Ranking Reasons": ranking_reasons,
        "Why": " | ".join(reasons[:6]),
    }



def safe_numeric_series(df: pd.DataFrame, col_name: str, default=0.0) -> pd.Series:
    if col_name in df.columns:
        return pd.to_numeric(df[col_name], errors="coerce").fillna(default)
    return pd.Series([default] * len(df), index=df.index, dtype="float64")

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
    sortable["_lineup_sort"] = safe_numeric_series(sortable, "Lineup Spot", 99)
    sortable["_model_rank_sort"] = safe_numeric_series(sortable, "Model Rank Score", 0.0)
    sortable["_hr_prob_sort"] = safe_numeric_series(sortable, "HR Probability %", 0.0)
    sortable["_barrel_sort"] = safe_numeric_series(sortable, "Barrel%", 0.0)
    sortable["_hh_sort"] = safe_numeric_series(sortable, "HardHit%", 0.0)
    sortable["_air_sort"] = safe_numeric_series(sortable, "AIR%", 0.0)
    sortable["_fb_sort"] = safe_numeric_series(sortable, "FlyBall%", 0.0)
    sortable["_ld_sort"] = safe_numeric_series(sortable, "LineDrive%", 0.0)
    sortable["_air_edge_sort"] = sortable["_fb_sort"] + sortable["_ld_sort"] - safe_numeric_series(sortable, "GroundBall%", 999.0)
    sortable["_xslg_sort"] = safe_numeric_series(sortable, "xSLG", 0.0)
    sortable["_gb_sort"] = safe_numeric_series(sortable, "GroundBall%", 999.0)
    sortable["_pitch_hr9_sort"] = safe_numeric_series(sortable, "Pitcher_HR9_Last7", 0.0)
    sortable["_pitch_barrel_sort"] = safe_numeric_series(sortable, "Pitcher_Barrel_Allowed", 0.0)
    sortable["_pitch_matchup_sort"] = safe_numeric_series(sortable, "Pitch Matchup Score", 0.0)
    sortable["_handedness_sort"] = safe_numeric_series(sortable, "Handedness Edge", 0.0)
    sortable["_usage_sort"] = safe_numeric_series(sortable, "Primary Pitch Usage", 0.0)
    sortable["_mix_mode_sort"] = sortable.get("Pitch Mix Mode", pd.Series(["BALANCED"] * len(sortable), index=sortable.index)).map({"HARD": 3, "SOFT": 2, "BALANCED": 1}).fillna(1)
    sortable["_authority_sort"] = safe_numeric_series(sortable, "Statcast Authority Score", 0.0)
    sortable["_authority_tier_sort"] = sortable.get("Statcast Authority Tier", pd.Series(["MEDIUM"] * len(sortable), index=sortable.index)).map({"ELITE": 4, "STRONG": 3, "MEDIUM": 2, "WEAK": 1, "FAIL": 0}).fillna(2)
    sortable["_la_sort"] = safe_numeric_series(sortable, "LaunchAngle", 0.0)
    sortable["_trend_sort"] = sortable.get("Recent Trend", pd.Series(["NEUTRAL"] * len(sortable), index=sortable.index)).map({"HOT": 3, "LIVE": 2, "NEUTRAL": 1, "COLD": 0}).fillna(1)
    sortable["_hrr_sort"] = safe_numeric_series(sortable, "HRR Score", 0.0)
    sortable["_multi_pitch_sort"] = safe_numeric_series(sortable, "Multi Pitch Authority Score", 0.0)
    sortable["_elite_hr_sort"] = sortable.get("Elite HR Look", pd.Series(["No"] * len(sortable), index=sortable.index)).map({"Yes": 1, "No": 0}).fillna(0)
    sortable["_pitcher_target_sort"] = safe_numeric_series(sortable, "HR Attackability Score", safe_numeric_series(sortable, "HR Attackability Score", 0.0).iloc[0] if len(sortable) else 0.0) if "HR Attackability Score" in sortable.columns else safe_numeric_series(sortable, "HR Attackability Score", 0.0)
    sortable["_matchup_adv_sort"] = safe_numeric_series(sortable, "Matchup Advantage Score", 0.0)

    sortable = sortable.sort_values(
        by=[
            "_matchup_adv_sort",
            "_pitcher_target_sort",
            "_elite_hr_sort",
            "_authority_tier_sort",
            "_authority_sort",
            "_multi_pitch_sort",
            "_barrel_sort",
            "_hh_sort",
            "_air_edge_sort",
            "_fb_sort",
            "_ld_sort",
            "_air_sort",
            "_xslg_sort",
            "_pitch_matchup_sort",
            "_hr_prob_sort",
            "_model_rank_sort",
            "_lineup_sort",
            "_usage_sort",
            "_mix_mode_sort",
            "_gb_sort",
            "_pitch_hr9_sort",
            "_pitch_barrel_sort",
            "_handedness_sort",
            "_la_sort",
            "_trend_sort",
            "_hrr_sort",
        ],
        ascending=[False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, True, False, False, False, False, False, False],
    ).reset_index(drop=True)
    return sortable.drop(columns=[
        "_lineup_sort",
        "_model_rank_sort",
        "_hr_prob_sort",
        "_barrel_sort",
        "_hh_sort",
        "_air_sort",
        "_fb_sort",
        "_ld_sort",
        "_air_edge_sort",
        "_xslg_sort",
        "_gb_sort",
        "_pitch_hr9_sort",
        "_pitch_barrel_sort",
        "_pitch_matchup_sort",
        "_handedness_sort",
        "_usage_sort",
        "_mix_mode_sort",
        "_authority_sort",
        "_authority_tier_sort",
        "_la_sort",
        "_trend_sort",
        "_hrr_sort",
        "_multi_pitch_sort",
        "_elite_hr_sort",
        "_pitcher_target_sort",
        "_matchup_adv_sort",
    ])


@st.cache_data(ttl=900)
def build_daily_dataset():
    schedule = sort_schedule_rows(get_today_schedule())
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
        weather = fetch_weather_for_park(home_abbr)
        home_bullpen = fetch_bullpen_fatigue_for_team(game["home_team_id"])
        away_bullpen = fetch_bullpen_fatigue_for_team(game["away_team_id"])

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
                weather_boost=weather.get("WeatherBoost", 0.0),
                weather_note=weather.get("WeatherNote", "neutral weather"),
                temp_f=weather.get("TempF", 72.0),
                wind_mph=weather.get("WindMPH", 7.0),
                bullpen_fatigue_score=home_bullpen.get("BullpenFatigueScore", 0.0),
                bullpen_fatigue_note=home_bullpen.get("BullpenFatigueNote", "Neutral bullpen rest"),
                bullpen_ip_prev=home_bullpen.get("BullpenIPPrev", 0.0),
                bullpen_arms_prev=home_bullpen.get("BullpenArmsPrev", 0),
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
                weather_boost=weather.get("WeatherBoost", 0.0),
                weather_note=weather.get("WeatherNote", "neutral weather"),
                temp_f=weather.get("TempF", 72.0),
                wind_mph=weather.get("WindMPH", 7.0),
                bullpen_fatigue_score=away_bullpen.get("BullpenFatigueScore", 0.0),
                bullpen_fatigue_note=away_bullpen.get("BullpenFatigueNote", "Neutral bullpen rest"),
                bullpen_ip_prev=away_bullpen.get("BullpenIPPrev", 0.0),
                bullpen_arms_prev=away_bullpen.get("BullpenArmsPrev", 0),
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


def get_research_shortlist_pool(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    pool = df[df["HR Eligible"]].copy()
    if pool.empty:
        return pool

    lineup_num = safe_numeric_series(pool, "Lineup Spot", 99)
    barrel = safe_numeric_series(pool, "Barrel%", 0.0)
    hard_hit = safe_numeric_series(pool, "HardHit%", 0.0)
    air_pct = safe_numeric_series(pool, "AIR%", 0.0)
    xslg = safe_numeric_series(pool, "xSLG", 0.0)
    gb = safe_numeric_series(pool, "GroundBall%", 999.0)
    pitch_score = safe_numeric_series(pool, "Pitch Matchup Score", 0.0)
    hr_prob = safe_numeric_series(pool, "HR Probability %", 0.0)
    trend_score = safe_numeric_series(pool, "Model Rank Score", 0.0)
    recent_trend = pool.get("Recent Trend", pd.Series(["NEUTRAL"] * len(pool), index=pool.index)).astype(str)
    authority_tier = pool.get("Statcast Authority Tier", pd.Series(["MEDIUM"] * len(pool), index=pool.index)).astype(str)
    mix_mode = pool.get("Pitch Mix Mode", pd.Series(["BALANCED"] * len(pool), index=pool.index)).astype(str)
    lineup_source = pool.get("Lineup Source", pd.Series(["PROJECTED"] * len(pool), index=pool.index)).astype(str).str.upper()

    authority_keep = authority_tier.isin(["ELITE", "STRONG"])
    hot_keep = recent_trend.isin(["HOT", "LIVE"])
    elite_shape = (barrel >= 12.0) | (xslg >= 0.500) | ((hard_hit >= 45.0) & (air_pct >= 54.0))
    starter_attack = (pitch_score >= 4.4) | (hr_prob >= 12.5)

    hard_shape_gate = (
        ((barrel >= 8.5) & (hard_hit >= 40.0) & (air_pct >= 49.0))
        | ((barrel >= 10.0) & (xslg >= 0.460))
        | ((hard_hit >= 44.0) & (air_pct >= 50.0))
        | elite_shape
        | authority_keep
    )

    gb_keep = (
        (gb <= 47.5)
        | elite_shape
        | authority_keep
        | ((gb <= 50.0) & (barrel >= 11.0) & (xslg >= 0.485))
    )

    projected_keep = (
        lineup_source.eq("PROJECTED")
        & (
            elite_shape
            | authority_keep
            | (hot_keep & starter_attack)
            | ((barrel >= 10.5) & (xslg >= 0.475))
        )
    )

    mixed_pitch_keep = (
        mix_mode.eq("HARD")
        | authority_keep
        | projected_keep
        | (mix_mode.eq("SOFT") & (starter_attack | hot_keep | elite_shape))
        | (mix_mode.eq("BALANCED") & (elite_shape | authority_keep | (hot_keep & (pitch_score >= 4.8))))
    )

    score_gate = (
        (hr_prob >= 9.2)
        | authority_keep
        | elite_shape
        | ((barrel >= 10.8) & (hard_hit >= 42.0))
        | (trend_score >= 455)
    )

    playable_lineup = (lineup_num <= 6) | authority_keep | projected_keep | hot_keep

    fade_cold = ~(
        recent_trend.eq("COLD")
        & (barrel < 11.5)
        & (xslg < 0.485)
        & (pitch_score < 5.2)
        & ~authority_keep
    )

    projected_unknown_fade = ~(
        lineup_num.eq(99)
        & lineup_source.eq("PROJECTED")
        & ~(projected_keep | authority_keep | elite_shape)
    )

    shortlist = pool[
        hard_shape_gate
        & gb_keep
        & mixed_pitch_keep
        & score_gate
        & playable_lineup
        & fade_cold
        & projected_unknown_fade
    ].copy()

    if shortlist.empty:
        shortlist = sort_for_hr(pool).head(28).copy()
        return shortlist.reset_index(drop=True)

    shortlist = sort_for_hr(shortlist).head(30).reset_index(drop=True)
    return shortlist


def get_strict_hr_pool(df: pd.DataFrame) -> pd.DataFrame:
    hr_pool = get_research_shortlist_pool(df)
    if hr_pool.empty:
        return hr_pool
    return add_rank_column(hr_pool)


def get_top12_hybrid(df: pd.DataFrame) -> pd.DataFrame:
    hr_pool = get_research_shortlist_pool(df)
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

    hr_pool = get_research_shortlist_pool(team_df)
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

    core_board = get_research_shortlist_pool(df).copy()
    if not core_board.empty:
        core_board = sort_for_hr(core_board).head(30)
        core_board["Tracker Source"] = "CORE_BOARD"
        visible_frames.append(core_board)

    top12 = get_top12_hybrid(df).copy()
    if not top12.empty:
        top12["Tracker Source"] = "TOP12"
        visible_frames.append(top12)

    # Match tracker entries to the actual per-game HR boards the user sees.
    # If BF Data surfaces a hitter in a visible per-game HR table, that hitter must be tracked.
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
    visible_df = sort_for_hr(visible_df)
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
            hr_count = safe_int(batting.get("homeRuns", 0), 0)
            if full_name:
                homer_map[str(full_name)] = int(hr_count)
                homer_map[normalize_name(full_name)] = int(hr_count)
    return homer_map


def get_player_hr_count_from_map(homer_map: dict, player_name: str) -> int:
    if not homer_map or not player_name:
        return 0
    raw = str(player_name)
    if raw in homer_map:
        return safe_int(homer_map.get(raw), 0)
    norm = normalize_name(raw)
    if norm in homer_map:
        return safe_int(homer_map.get(norm), 0)
    for key, val in homer_map.items():
        if normalize_name(key) == norm:
            return safe_int(val, 0)
    return 0


def add_live_homer_counts_to_board(df: pd.DataFrame, schedule: list[dict]) -> pd.DataFrame:
    """Display-only result column. This must NEVER be used to rank or rewrite predictions."""
    if df.empty:
        return df.copy()
    out = df.copy()
    out["Actual HR Today"] = 0
    if "game_pk" not in out.columns or "Player" not in out.columns:
        return out
    for game in schedule:
        game_pk = game.get("game_pk")
        if game_pk is None:
            continue
        homer_map = get_boxscore_homers(game_pk)
        mask = out["game_pk"] == game_pk
        if mask.any():
            out.loc[mask, "Actual HR Today"] = out.loc[mask, "Player"].apply(
                lambda p: get_player_hr_count_from_map(homer_map, p)
            )
    return out


def sync_tracker_with_board(tracked_df: pd.DataFrame):
    tracker = load_tracker()
    date_key = today_str()

    if tracked_df.empty:
        return tracker

    if "hr_count" not in tracker.columns:
        tracker["hr_count"] = 0

    existing_keys = set()
    if not tracker.empty:
        today_existing = tracker[tracker["date"].astype(str) == date_key].copy()
        if not today_existing.empty:
            existing_keys = set(zip(
                today_existing["date"].astype(str),
                today_existing["player"].astype(str).map(normalize_name),
                today_existing["team"].astype(str),
                today_existing["game"].astype(str),
                today_existing["tracker_source"].astype(str),
            ))

    new_rows = []
    for _, row in tracked_df.iterrows():
        source = str(row.get("Tracker Source", "CORE_BOARD"))
        player_name = str(row["Player"])
        key = (str(date_key), normalize_name(player_name), str(row["Team"]), str(row["Game"]), source)
        if key in existing_keys:
            continue

        new_rows.append({
            "date": date_key,
            "player": player_name,
            "team": row["Team"],
            "game": row["Game"],
            "game_pk": row["game_pk"],
            "hr_probability": row["HR Probability %"],
            "hr_tier": row["HR Tier"],
            "hr_eligible": int(bool(row["HR Eligible"])),
            "tracker_source": source,
            "result": pd.NA,
            "hr_count": 0,
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
    if "hr_count" not in tracker.columns:
        tracker["hr_count"] = 0

    date_key = today_str()
    today_mask = tracker["date"].astype(str) == date_key

    for game in schedule:
        game_pk = game["game_pk"]
        game_state = game.get("game_state", "Preview")
        detailed_state = game.get("detailed_state", "Scheduled")

        rows_mask = today_mask & (tracker["game_pk"] == game_pk)
        if not rows_mask.any():
            continue

        # Always read boxscore. Some MLB schedule states lag or stay weird while boxscore already has HR data.
        homer_map = get_boxscore_homers(game_pk)

        for idx in tracker.index[rows_mask]:
            player = tracker.at[idx, "player"]
            hr_count = get_player_hr_count_from_map(homer_map, player)
            tracker.at[idx, "hr_count"] = int(hr_count)

            if hr_count > 0:
                tracker.at[idx, "result"] = 1
                tracker.at[idx, "result_state"] = "HOMERED" if hr_count == 1 else f"HOMERED_{hr_count}X"
            else:
                if game_state == "Preview":
                    if pd.isna(tracker.at[idx, "result"]):
                        tracker.at[idx, "result_state"] = "PREGAME"
                elif game_state == "Final":
                    tracker.at[idx, "result"] = 0
                    tracker.at[idx, "result_state"] = "FINAL_NO_HR"
                else:
                    tracker.at[idx, "result_state"] = "LIVE"

            tracker.at[idx, "game_state"] = detailed_state
            tracker.at[idx, "updated_at"] = now_et_string()

    save_tracker(tracker)
    return tracker


def _combo_signature(players: list[str]) -> str:
    return " | ".join(sorted(players))


def _pick_combo_rows(candidates: pd.DataFrame, size: int, max_combos: int, global_usage: dict) -> list[dict]:
    from itertools import combinations

    if candidates.empty or len(candidates) < size:
        return []

    ranked = candidates.reset_index(drop=True).copy()
    combos = []
    for idxs in combinations(ranked.index.tolist(), size):
        rows = ranked.loc[list(idxs)].copy()
        players = rows["Player"].tolist()
        games = rows["Game"].tolist()
        teams = rows["Team"].tolist()
        if len(set(players)) != size:
            continue
        if size >= 3 and len(set(games)) < size - 1:
            continue
        if len(set(teams)) < max(2, size - 1):
            continue

        avg_prob = rows["HR Probability %"].mean()
        total_prob = rows["HR Probability %"].sum()
        total_model = rows["Model Rank Score"].sum()
        diversity_bonus = len(set(games)) * 2.4 + len(set(teams)) * 1.2
        same_game_penalty = max(0, size - len(set(games))) * 6.0
        score = total_prob + (total_model * 0.08) + diversity_bonus - same_game_penalty
        combos.append({
            "players": players,
            "games": games,
            "rows": rows,
            "score": round(score, 2),
            "avg_prob": round(avg_prob, 2),
        })

    combos = sorted(combos, key=lambda x: (x["score"], x["avg_prob"]), reverse=True)

    selected = []
    seen = set()
    for combo in combos:
        sig = _combo_signature(combo["players"])
        if sig in seen:
            continue
        if any(global_usage.get(p, 0) >= 3 for p in combo["players"]):
            continue
        if any(len(set(combo["players"]) & set(existing["players"])) > max(1, size // 2) for existing in selected):
            continue
        selected.append(combo)
        seen.add(sig)
        for p in combo["players"]:
            global_usage[p] = global_usage.get(p, 0) + 1
        if len(selected) >= max_combos:
            break
    return selected


def build_combo_board(df: pd.DataFrame) -> pd.DataFrame:
    shortlist = get_research_shortlist_pool(df)
    top12 = get_top12_hybrid(df)
    if shortlist.empty and top12.empty:
        return pd.DataFrame()

    candidate_pool = pd.concat([top12, shortlist], ignore_index=True)
    candidate_pool = candidate_pool.drop_duplicates(subset=["Player", "Team", "Game"])
    candidate_pool = sort_for_hr(candidate_pool).head(14).reset_index(drop=True)

    global_usage = {}
    rows = []
    combo_counts = {2: 5, 3: 4, 4: 3, 5: 2}
    for size in [2, 3, 4, 5]:
        selected = _pick_combo_rows(candidate_pool, size, combo_counts[size], global_usage)
        for idx, combo in enumerate(selected, start=1):
            players = combo["players"]
            games = combo["games"]
            labels = [f"{p} ({t})" for p, t in zip(combo["players"], combo["rows"]["Team"].tolist())]
            rows.append({
                "Combo Type": f"{size}-Leg",
                "Combo #": idx,
                "Combo Label": " + ".join(labels),
                "Players": " | ".join(players),
                "Games": " | ".join(games),
                "Avg Leg HR %": round(combo["avg_prob"], 2),
                "Combined Score": combo["score"],
                "Source Pool": "TOP12+CORE",
            })
    return pd.DataFrame(rows)


def sync_combo_tracker_with_board(combo_df: pd.DataFrame):
    tracker = load_combo_tracker()
    date_key = today_str()
    if combo_df.empty:
        return tracker

    existing_ids = set()
    if not tracker.empty:
        existing_today = tracker[tracker["date"].astype(str) == date_key].copy()
        if not existing_today.empty and "combo_id" in existing_today.columns:
            existing_ids = set(existing_today["combo_id"].astype(str).tolist())

    new_rows = []
    for _, row in combo_df.iterrows():
        combo_id = f"{date_key}-{row['Combo Type']}-{int(row['Combo #'])}"
        if combo_id in existing_ids:
            continue
        legs = str(row["Players"]).split(" | ")
        new_rows.append({
            "date": date_key,
            "combo_id": combo_id,
            "combo_label": row["Combo Label"],
            "combo_size": int(str(row["Combo Type"]).split("-")[0]),
            "legs": row["Players"],
            "games": row["Games"],
            "avg_leg_probability": row["Avg Leg HR %"],
            "combined_score": row["Combined Score"],
            "source_pool": row["Source Pool"],
            "result": pd.NA,
            "result_state": "PENDING",
            "legs_hit": 0,
            "total_legs": len(legs),
            "updated_at": now_et_string(),
        })

    if new_rows:
        tracker = pd.concat([tracker, pd.DataFrame(new_rows)], ignore_index=True)
        save_combo_tracker(tracker)
    return tracker


def auto_update_combo_tracker_results(combo_tracker: pd.DataFrame, schedule: list[dict]):
    if combo_tracker.empty:
        return combo_tracker

    combo_tracker = combo_tracker.copy()
    date_key = today_str()
    today_mask = combo_tracker["date"].astype(str) == date_key

    homer_maps = {}
    schedule_states = {}
    for game in schedule:
        homer_maps[game["game_pk"]] = get_boxscore_homers(game["game_pk"])
        schedule_states[game["game_key"]] = (game.get("game_state", "Preview"), game.get("detailed_state", "Scheduled"))

    for idx in combo_tracker.index[today_mask]:
        legs = [x.strip() for x in str(combo_tracker.at[idx, "legs"]).split("|") if x.strip()]
        games = [x.strip() for x in str(combo_tracker.at[idx, "games"]).split("|") if x.strip()]
        legs_hit = 0
        any_live = False
        all_final = True
        for leg, game_key in zip(legs, games):
            game_state, detailed = schedule_states.get(game_key, ("Preview", "Scheduled"))
            if game_state != "Final":
                all_final = False
            if game_state not in ["Preview", "Final"]:
                any_live = True
            # find matching homer map by game key via schedule lookup
            matched = False
            for game in schedule:
                if game["game_key"] == game_key:
                    if get_player_hr_count_from_map(homer_maps.get(game["game_pk"], {}), leg) > 0:
                        legs_hit += 1
                    matched = True
                    break
            if not matched:
                all_final = False

        combo_tracker.at[idx, "legs_hit"] = legs_hit
        combo_tracker.at[idx, "total_legs"] = len(legs)
        combo_tracker.at[idx, "updated_at"] = now_et_string()
        if legs_hit == len(legs) and len(legs) > 0:
            combo_tracker.at[idx, "result"] = 1
            combo_tracker.at[idx, "result_state"] = "FULL_HIT"
        elif all_final:
            combo_tracker.at[idx, "result"] = 0
            combo_tracker.at[idx, "result_state"] = "PARTIAL_HIT" if legs_hit > 0 else "FINAL_MISS"
        elif any_live:
            combo_tracker.at[idx, "result_state"] = "LIVE" if legs_hit == 0 else f"LIVE_{legs_hit}_HIT"
        else:
            combo_tracker.at[idx, "result_state"] = "PREGAME"

    save_combo_tracker(combo_tracker)
    return combo_tracker



def summarize_tracker_sources(df: pd.DataFrame) -> dict:
    buckets = {
        "CORE_BOARD": {"today_total": 0, "today_hits": 0, "today_pct": 0.0, "all_total": 0, "all_hits": 0, "all_pct": 0.0},
        "TOP12": {"today_total": 0, "today_hits": 0, "today_pct": 0.0, "all_total": 0, "all_hits": 0, "all_pct": 0.0},
        "GAME_HR": {"today_total": 0, "today_hits": 0, "today_pct": 0.0, "all_total": 0, "all_hits": 0, "all_pct": 0.0},
    }
    if df.empty:
        return buckets

    work = df.copy()
    if "tracker_source" not in work.columns:
        work["tracker_source"] = "CORE_BOARD"
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str)
    if "hr_count" in work.columns:
        work["result_num"] = (pd.to_numeric(work["hr_count"], errors="coerce").fillna(0).astype(int) > 0).astype(int)
    else:
        work["result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)
    today_mask = work["date"].astype(str) == today_str()

    for source in buckets.keys():
        all_df = work[work["tracker_source"] == source].copy()
        today_df = all_df[today_mask].copy()
        all_total = len(all_df)
        all_hits = int(all_df["result_num"].sum()) if all_total else 0
        today_total = len(today_df)
        today_hits = int(today_df["result_num"].sum()) if today_total else 0
        buckets[source] = {
            "today_total": today_total,
            "today_hits": today_hits,
            "today_pct": round((today_hits / today_total) * 100, 2) if today_total else 0.0,
            "all_total": all_total,
            "all_hits": all_hits,
            "all_pct": round((all_hits / all_total) * 100, 2) if all_total else 0.0,
        }

    return buckets


def summarize_tracker_sources_for_date(df: pd.DataFrame, date_key: str) -> dict:
    buckets = {
        "CORE_BOARD": {"total": 0, "hits": 0, "pct": 0.0, "misses": 0},
        "TOP12": {"total": 0, "hits": 0, "pct": 0.0, "misses": 0},
        "GAME_HR": {"total": 0, "hits": 0, "pct": 0.0, "misses": 0},
    }
    if df.empty:
        return buckets

    work = df.copy()
    if "tracker_source" not in work.columns:
        work["tracker_source"] = "CORE_BOARD"
    if "hr_count" not in work.columns:
        work["hr_count"] = pd.to_numeric(work.get("result", 0), errors="coerce").fillna(0)
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str)
    work["result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)
    work["hr_count_num"] = pd.to_numeric(work["hr_count"], errors="coerce").fillna(0).astype(int)
    day = work[work["date"].astype(str) == str(date_key)].copy()

    for source in buckets:
        sub = day[day["tracker_source"] == source].copy()
        total = len(sub)
        hits = int((sub["hr_count_num"] > 0).sum()) if total else 0
        if hits == 0 and total:
            hits = int(sub["result_num"].sum())
        buckets[source] = {
            "total": total,
            "hits": hits,
            "misses": max(total - hits, 0),
            "pct": round((hits / total) * 100, 2) if total else 0.0,
        }
    return buckets


def summarize_combo_tracker(df: pd.DataFrame) -> dict:
    summary = {
        "today_total": 0, "today_full_hits": 0, "today_partial_hits": 0,
        "all_total": 0, "all_full_hits": 0, "all_partial_hits": 0,
    }
    if df.empty:
        return summary
    work = df.copy()
    today_df = work[work["date"].astype(str) == today_str()]
    summary["today_total"] = len(today_df)
    summary["today_full_hits"] = int((today_df["result_state"].astype(str) == "FULL_HIT").sum())
    summary["today_partial_hits"] = int(today_df["legs_hit"].fillna(0).astype(int).gt(0).sum())
    summary["all_total"] = len(work)
    summary["all_full_hits"] = int((work["result_state"].astype(str) == "FULL_HIT").sum())
    summary["all_partial_hits"] = int(work["legs_hit"].fillna(0).astype(int).gt(0).sum())
    return summary


def _display_value(value, default="—"):
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    if value is None:
        return default
    txt = str(value)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = txt.replace("[", "(").replace("]", ")")
    return txt.strip() if txt.strip() else default


def _pct_width(value, max_value):
    try:
        val = float(value)
    except Exception:
        val = 0.0
    try:
        max_val = float(max_value)
    except Exception:
        max_val = 100.0
    if max_val <= 0:
        max_val = 100.0
    return max(0, min(100, (val / max_val) * 100))


def _attackability_pct(score) -> float:
    """Convert internal HR attackability into a stricter 0-100 meter.

    This deliberately compresses the top end so 90+ is rare. A strong HR-leak pitcher
    will usually land 70-85 instead of everything turning bright green.
    """
    raw = safe_float(score, 0.0)
    pct = (raw / 52.0) * 100.0
    if raw > 43.0:
        pct += (raw - 43.0) * 2.0
    return round(clip(pct, 0.0, 96.0), 1)


def _attackability_bucket(score_or_pct, already_pct: bool = False) -> tuple[str, str]:
    """Green/yellow/red meaning is from the batter's perspective."""
    pct = safe_float(score_or_pct, 0.0) if already_pct else _attackability_pct(score_or_pct)
    if pct >= 88:
        return "ELITE TARGET", "green"
    if pct >= 72:
        return "STRONG TARGET", "green"
    if pct >= 58:
        return "ATTACKABLE", "green"
    if pct >= 45:
        return "MODERATE", "yellow"
    return "SUPPRESSIVE", "red"


def _attackability_note(score_or_pct, already_pct: bool = False) -> str:
    pct = safe_float(score_or_pct, 0.0) if already_pct else _attackability_pct(score_or_pct)
    if pct >= 88:
        return "Elite HR target for hitters"
    if pct >= 72:
        return "Strong HR target for hitters"
    if pct >= 58:
        return "Attackable HR profile"
    if pct >= 45:
        return "Mixed / moderate HR environment"
    return "Suppressive HR profile"


def _signal_from_value(value, good_at, warn_at=None, lower_is_better=False):
    val = safe_float(value, 0.0)
    if warn_at is None:
        warn_at = good_at * 0.65
    if lower_is_better:
        if val <= good_at:
            return "STRONG", "green"
        if val <= warn_at:
            return "CAUTION", "yellow"
        return "POOR", "red"
    if val >= good_at:
        return "STRONG", "green"
    if val >= warn_at:
        return "CAUTION", "yellow"
    return "POOR", "red"


def _chip_html(text, color="gray"):
    safe = escape(_display_value(text))
    color = color if color in {"green", "yellow", "red", "gray"} else "gray"
    return f'<span class="bf-chip bf-chip-{color}">{safe}</span>'


def _tier_color(tier: str):
    tier = str(tier).upper()
    if tier in {"CORE TARGET", "STRONG LOOK"}:
        return "green"
    if tier == "SLEEPER":
        return "yellow"
    return "gray"


def _matchup_color(matchup: str):
    matchup = str(matchup).upper()
    if matchup == "HIGH":
        return "green"
    if matchup == "MED":
        return "yellow"
    return "red"


def _gb_color(ground_ball: float):
    if ground_ball >= 50:
        return "red"
    if ground_ball >= 45:
        return "yellow"
    return "green"


def _value_span(value, color):
    color = color if color in {"green", "yellow", "red"} else "yellow"
    return f'<span class="bf-signal-value-{color}">{escape(str(value))}</span>'


def _signal_bar_html(label: str, value, max_value: float = 100.0, suffix: str = "", good_at: float | None = None, warn_at: float | None = None, lower_is_better: bool = False):
    val = safe_float(value, 0.0)
    pct = _pct_width(val, max_value)
    if good_at is None:
        good_at = max_value * 0.67
    if warn_at is None:
        warn_at = max_value * 0.42
    signal, color = _signal_from_value(val, good_at=good_at, warn_at=warn_at, lower_is_better=lower_is_better)
    pretty = f"{val:.1f}{suffix}"
    return (
        '<div class="bf-bar-wrap">'
        f'<div class="bf-bar-head"><span>{escape(str(label))}</span><span>{signal} · {_value_span(pretty, color)}</span></div>'
        f'<div class="bf-track"><div class="bf-fill bf-fill-{color}" style="width:{pct:.1f}%"></div></div>'
        '</div>'
    )


def render_board_key():
    st.markdown(
        '<div class="bf-key">'
        '<span class="bf-key-chip bf-key-green">Green 58–100 = pitcher attackable / hitter edge</span>'
        '<span class="bf-key-chip bf-key-yellow">Yellow 45–57 = mixed / caution</span>'
        '<span class="bf-key-chip bf-key-red">Red 0–44 = suppressive / avoid</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_bar(label: str, value, max_value: float = 100.0, suffix: str = "", fill_class: str = "") -> str:
    val = safe_float(value, 0.0)
    return f"{label}: {val:.1f}{suffix}"


def render_player_card(row: pd.Series, rank_override=None):
    rank = rank_override if rank_override is not None else row.get("Rank", "—")
    player = _display_value(row.get("Player"))
    team = _display_value(row.get("Team"))
    game = _display_value(row.get("Game"))
    pitcher = _display_value(row.get("Pitcher"))
    tier = _display_value(row.get("HR Tier"))
    lineup = _display_value(row.get("Lineup Spot"))
    lineup_source = _display_value(row.get("Lineup Source"))
    matchup = _display_value(row.get("Matchup Advantage"))
    gb_rule = _display_value(row.get("GB Rule"))
    recent = _display_value(row.get("Recent Trend"))
    weather = _display_value(row.get("WeatherNote"))
    pitch_mix = _display_value(row.get("Relevant Pitch Mix"))
    pitch_mode = _display_value(row.get("Pitch Mix Mode"))
    why = _display_value(row.get("Ranking Reasons", row.get("Why", "")))
    why2 = _display_value(row.get("Why", ""))

    hr_prob = safe_float(row.get("HR Probability %"), 0.0)
    matchup_score = safe_float(row.get("Matchup Advantage Score"), 0.0)
    hr_attackability = safe_float(row.get("HR Attackability Score", 0.0), 0.0)
    hr_attack_pct = safe_float(row.get("HR Attackability %", _attackability_pct(hr_attackability)), 0.0)
    hr_attack_status = _display_value(row.get("HR Attackability Status", _attackability_bucket(hr_attack_pct, already_pct=True)[0]))
    pitcher_profile = _display_value(row.get("Pitcher HR Profile", _attackability_note(hr_attack_pct, already_pct=True)))
    pitcher_label = _display_value(row.get("HR Attackability Label", ""))
    pitch_hr9_l7 = safe_float(row.get("Pitcher_HR9_Last7"), 0.0)
    pitch_hr9_season = safe_float(row.get("Pitcher Season HR/9", row.get("Pitcher_Season_HR9", 0.0)), 0.0)
    pitch_hr9_recent = safe_float(row.get("Pitcher Recent HR/9", row.get("Pitcher_Recent_HR9", 0.0)), 0.0)
    pitch_barrel_allowed = safe_float(row.get("Pitcher_Barrel_Allowed"), 0.0)
    pitch_hh_allowed = safe_float(row.get("Pitcher_HardHit_Allowed"), 0.0)
    authority_score = safe_float(row.get("Statcast Authority Score"), 0.0)
    l10_bbe_score = safe_float(row.get("L10 BBE Score"), 0.0)
    l10_bbe_trend = _display_value(row.get("L10 BBE Trend", "—"))
    l10_bbe_ev = safe_float(row.get("L10 BBE EV"), 0.0)
    l10_bbe_brl = safe_float(row.get("L10 BBE Barrel%"), 0.0)
    l10_bbe_hh = safe_float(row.get("L10 BBE HardHit%"), 0.0)
    l10_bbe_air = safe_float(row.get("L10 BBE AIR%"), 0.0)
    l10_bbe_gb = safe_float(row.get("L10 BBE GB%"), 0.0)
    barrel = safe_float(row.get("Barrel%"), 0.0)
    hard_hit = safe_float(row.get("HardHit%"), 0.0)
    air_pct = safe_float(row.get("AIR%"), 0.0)
    ground_ball = safe_float(row.get("GroundBall%"), 0.0)
    xslg = safe_float(row.get("xSLG"), 0.0)
    actual_hr = safe_int(row.get("Actual HR Today"), 0)

    st.markdown(f"**#{rank} {player}**  \n`{team}` • {game}")
    st.caption(f"vs {pitcher}")

    chip_row = "".join([
        _chip_html(tier, _tier_color(tier)),
        _chip_html(f"LU {lineup}", "gray"),
        _chip_html(lineup_source, "gray"),
        _chip_html(f"Matchup {matchup}", _matchup_color(matchup)),
        _chip_html(f"GB {gb_rule}", _gb_color(ground_ball)),
    ])
    st.markdown(f'<div class="bf-mini-row">{chip_row}</div>', unsafe_allow_html=True)

    hr_signal, hr_color = _signal_from_value(hr_prob, good_at=14, warn_at=9)
    matchup_signal, matchup_color = _signal_from_value(matchup_score, good_at=55, warn_at=38)
    attack_signal, attack_color = _signal_from_value(hr_attack_pct, good_at=58, warn_at=45)
    authority_signal, authority_color = _signal_from_value(authority_score, good_at=30, warn_at=17)

    st.markdown(
        '<div class="bf-signal-line">'
        f'<strong>HR</strong> {hr_signal} {_value_span(f"{hr_prob:.1f}%", hr_color)} · '
        f'<strong>Matchup</strong> {matchup_signal} {_value_span(f"{matchup_score:.1f}", matchup_color)} · '
        f'<strong>Pitcher</strong> {hr_attack_status} {_value_span(f"{hr_attack_pct:.0f}%", attack_color)} · '
        f'<strong>Auth</strong> {authority_signal} {_value_span(f"{authority_score:.1f}", authority_color)}'
        '</div>',
        unsafe_allow_html=True,
    )

    if actual_hr > 0:
        st.success(f"HR HIT TODAY: {actual_hr}")

    with st.expander("Bars + matchup details", expanded=False):
        st.markdown(_signal_bar_html("HR Probability", hr_prob, 28, "%", good_at=14, warn_at=9), unsafe_allow_html=True)
        st.markdown(_signal_bar_html("Matchup Score", matchup_score, 75, good_at=55, warn_at=38), unsafe_allow_html=True)
        st.markdown(_signal_bar_html("Pitcher HR Attackability", hr_attack_pct, 100, "%", good_at=58, warn_at=45), unsafe_allow_html=True)
        st.caption(f"Pitcher profile: {pitcher_profile} | L7 HR/9: {pitch_hr9_l7:.2f} | Season HR/9: {pitch_hr9_season:.2f} | Recent HR/9: {pitch_hr9_recent:.2f} | Barrels allowed: {pitch_barrel_allowed:.1f} | Hard-hit allowed: {pitch_hh_allowed:.1f}")
        if pitcher_label:
            st.caption(f"Attackability detail: {pitcher_label}")
        st.markdown(_signal_bar_html("L10 BBE Power", l10_bbe_score, 100, good_at=52, warn_at=34), unsafe_allow_html=True)
        st.caption(f"L10 BBE profile: {l10_bbe_trend} | EV {l10_bbe_ev:.1f} | Barrel {l10_bbe_brl:.1f}% | Hard-hit {l10_bbe_hh:.1f}% | Air {l10_bbe_air:.1f}% | GB {l10_bbe_gb:.1f}%")
        st.markdown(_signal_bar_html("Statcast Authority", authority_score, 55, good_at=30, warn_at=17), unsafe_allow_html=True)
        st.markdown(_signal_bar_html("Barrel", barrel, 20, "%", good_at=11, warn_at=8), unsafe_allow_html=True)
        st.markdown(_signal_bar_html("Hard Hit", hard_hit, 60, "%", good_at=42, warn_at=35), unsafe_allow_html=True)
        st.markdown(_signal_bar_html("Air Ball", air_pct, 75, "%", good_at=55, warn_at=48), unsafe_allow_html=True)
        st.markdown(_signal_bar_html("Ground Ball Risk", ground_ball, 60, "%", good_at=44, warn_at=50, lower_is_better=True), unsafe_allow_html=True)

        st.caption(f"Pitch Mix: {pitch_mode} • {pitch_mix} | xSLG: {xslg:.3f} | Trend: {recent}")
        st.caption(f"Weather: {weather}")
        st.write(f"Why: {why}")
        if why2 and why2 != why:
            st.caption(why2)

    st.divider()


def render_card_grid(df: pd.DataFrame, max_cards: int = 24, columns: int = 3, title: str | None = None):
    if df is None or df.empty:
        st.caption("No cards to display.")
        return

    view = df.copy().head(max_cards).reset_index(drop=True)
    if title:
        st.markdown(f"### {title}")

    try:
        columns = int(columns)
    except Exception:
        columns = 3

    if columns >= 3:
        columns = 4
    columns = max(1, min(columns, 4))

    col_objs = st.columns(columns)
    for i, (_, row) in enumerate(view.iterrows()):
        rank = row.get("Rank", i + 1)
        with col_objs[i % columns]:
            render_player_card(row, rank_override=rank)


c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("Update Board", use_container_width=True):
        st.session_state.manual_refresh_trigger = True
        st.cache_data.clear()
        st.rerun()


live_df, schedule = build_daily_dataset()
locked_df_raw = ensure_daily_board_lock(live_df, schedule)

lineup_mode = get_lineup_mode(schedule) if schedule else "PROJECTED"

# Build and save the prediction/tracker pool BEFORE adding live results.
# This prevents post-HR result data from rewriting the prediction board.
tracked_df = build_visible_tracker_pool(locked_df_raw, schedule)
save_daily_board_snapshot(tracked_df, today_str())

tracker = sync_tracker_with_board(tracked_df)
combo_board = build_combo_board(locked_df_raw)
combo_tracker = sync_combo_tracker_with_board(combo_board)

# Always update results every run. Refresh/update should not be required for HR counts to move off zero.
tracker = auto_update_tracker_results(tracker, schedule)
combo_tracker = auto_update_combo_tracker_results(combo_tracker, schedule)
st.session_state.manual_refresh_trigger = False

# Display-only live result column.
locked_df = add_live_homer_counts_to_board(locked_df_raw, schedule)

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

render_board_key()

base_tabs = ["HR Probability", "Top 12", "Top HR Targets", "Pitchers to Attack", "HR Combos", "Hits + Runs + RBIs", "Batter Breakdown", "Accuracy Tracker"]
schedule = sort_schedule_rows(schedule)
game_tabs = [f"{format_game_time_et(g.get('game_time', ''))} | {g['game_key']}" for g in schedule]
tabs = st.tabs(base_tabs + game_tabs)

with tabs[0]:
    st.subheader("HR Probability Board")
    st.caption("Projected teams stay live. Confirmed teams freeze once lineups lock. Actual HR Today is display-only and does not change rankings.")
    hr_df = get_strict_hr_pool(locked_df)
    render_card_grid(hr_df, max_cards=30, columns=3)
    with st.expander("Raw HR Probability Table"):
        st.dataframe(
            hr_df[[
                "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
                "Lineup Source", "Actual HR Today", "HR Probability %", "HR Tier", "GroundBall%",
                "GB Rule", "GB Note", "Matchup Advantage", "HR Attackability Score", "HR Attackability %", "HR Attackability Status", "WeatherNote", "BullpenFatigueNote", "L10 BBE Score", "L10 BBE Trend", "L10 BBE EV", "L10 BBE Barrel%", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
            ]],
            use_container_width=True,
            hide_index=True
        )

with tabs[1]:
    st.subheader("Top 12 HR Candidates")
    st.caption("Confirmed teams freeze once lineups lock. Projected teams can still update. Actual HR Today is display-only and does not change rankings.")
    top12 = get_top12_hybrid(locked_df)
    render_card_grid(top12, max_cards=12, columns=3)
    with st.expander("Raw Top 12 Table"):
        st.dataframe(
            top12[[
                "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
                "Lineup Source", "Actual HR Today", "HR Probability %", "HR Tier", "GroundBall%",
                "GB Rule", "GB Note", "Matchup Advantage", "HR Attackability Score", "HR Attackability %", "HR Attackability Status", "WeatherNote", "BullpenFatigueNote", "L10 BBE Score", "L10 BBE Trend", "L10 BBE EV", "L10 BBE Barrel%", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
            ]],
            use_container_width=True,
            hide_index=True
        )

with tabs[2]:
    st.subheader("Top HR Targets — Slate-Wide Top 25")
    st.caption("Global slate ranking based on hitter authority, EV/ISO-style power, pitch exposure, pitcher HR/9 vulnerability, weather, park, and matchup advantage.")
    top_targets = get_best_hr_matchups(locked_df, 25)
    target_cols = [
        "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot", "Lineup Source",
        "Matchup Advantage", "Matchup Advantage Score", "HR Attackability %", "HR Attackability Status", "HR Attackability Score", "Pitcher_HR9_Last7",
        "EV", "L10 BBE Score", "L10 BBE Trend", "L10 BBE EV", "L10 BBE Barrel%", "Barrel%", "HardHit%", "AIR%", "xSLG", "xwOBA",
        "Pitch Mix Mode", "Relevant Pitch Mix", "Primary Pitch Usage",
        "Actual HR Today", "HR Probability %", "HR Tier", "Ranking Reasons"
    ]
    render_card_grid(top_targets, max_cards=25, columns=3)
    with st.expander("Raw Top HR Targets Table"):
        display_existing_columns(top_targets, target_cols)

with tabs[3]:
    st.subheader("Pitchers to Attack Today")
    st.caption("Attackability board emphasizing HR/9, barrel allowed, hard contact allowed, park/weather carry, and matchup vulnerability.")
    pitcher_targets = get_pitchers_to_target(locked_df)
    display_existing_columns(
        pitcher_targets,
        ["Game", "Pitcher", "HR Attackability %", "HR Attackability Status", "HR Attackability Score", "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed", "WeatherNote", "TempF", "WindMPH"]
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
            dedupe_columns(combo_tracker.sort_values(by=["date", "combo_size", "combined_score"], ascending=[False, True, False])),
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
            "EV", "L10 BBE Score", "L10 BBE Trend", "L10 BBE EV", "L10 BBE Barrel%", "Barrel%", "HardHit%", "AIR%", "xSLG", "xwOBA",
        "Pitch Mix Mode"
            "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed",
            "HR Attackability Score", "HR Attackability %", "HR Attackability Status", "Pitcher HR Profile", "HR Attackability Label", "Matchup Advantage Score", "Matchup Advantage", "Ranking Reasons",
            "Statcast Pass", "Strict Statcast", "Recent Form Pass", "Pitcher Attackable",
            "Pitch_Isolation_Valid", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "BullpenFatigueScore", "TempF", "WindMPH", "HR Eligible",
            "HR Probability %", "HRR Score", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[7]:
    st.subheader("Accuracy Tracker")
    st.caption("Tracker is broken into separate sections. Newly surfaced per-game picks are now added instead of being blocked after the first tracker write.")

    date_options = available_tracker_dates(tracker)
    selected_tracker_date = st.selectbox("Review slate date", options=date_options, index=0)

    selected_source_summary = summarize_tracker_sources_for_date(tracker, selected_tracker_date)
    selected_tracker = tracker[
        tracker["date"].astype("string").fillna("") == str(selected_tracker_date)
    ].copy()
    if "hr_count" not in selected_tracker.columns:
        selected_tracker["hr_count"] = pd.to_numeric(selected_tracker.get("result", 0), errors="coerce").fillna(0).astype(int)

    st.markdown(f"### {selected_tracker_date} by Section")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown("**Core Board**")
        st.metric("Surfaced", selected_source_summary["CORE_BOARD"]["total"])
        st.metric("HR Hit", selected_source_summary["CORE_BOARD"]["hits"])
        st.metric("Hit Rate %", selected_source_summary["CORE_BOARD"]["pct"])
    with s2:
        st.markdown("**Top 12**")
        st.metric("Surfaced", selected_source_summary["TOP12"]["total"])
        st.metric("HR Hit", selected_source_summary["TOP12"]["hits"])
        st.metric("Hit Rate %", selected_source_summary["TOP12"]["pct"])
    with s3:
        st.markdown("**Per-Game HR**")
        st.metric("Surfaced", selected_source_summary["GAME_HR"]["total"])
        st.metric("HR Hit", selected_source_summary["GAME_HR"]["hits"])
        st.metric("Hit Rate %", selected_source_summary["GAME_HR"]["pct"])

    st.markdown("### Today Combo Section")
    cx1, cx2, cx3 = st.columns(3)
    cx1.metric("Today Combos", combo_summary["today_total"])
    cx2.metric("Today Full Hits", combo_summary["today_full_hits"])
    cx3.metric("Today Partial Hits", combo_summary["today_partial_hits"])

    st.divider()

    if not selected_tracker.empty:
        st.markdown("### Selected Date Split Tracker Tables")
        for section_name, source_key in [("Core Board", "CORE_BOARD"), ("Top 12", "TOP12"), ("Per-Game HR", "GAME_HR")]:
            section_df = selected_tracker[selected_tracker["tracker_source"].astype(str) == source_key].copy()
            st.markdown(f"**{section_name}**")
            if section_df.empty:
                st.caption("No tracked rows in this section for selected date.")
            else:
                section_df["hr_count"] = pd.to_numeric(section_df["hr_count"], errors="coerce").fillna(0).astype(int)
                st.dataframe(
                    dedupe_columns(section_df.sort_values(
                        by=["hr_count", "result", "hr_probability", "player"],
                        ascending=[False, False, False, True]
                    )[[
                        "player", "team", "game", "hr_probability", "hr_tier",
                        "tracker_source", "hr_eligible", "result", "hr_count",
                        "result_state", "game_state", "updated_at"
                    ]]),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.caption("No tracker rows for selected date.")

    selected_board_snapshot = load_daily_board_snapshot(selected_tracker_date)
    if not selected_board_snapshot.empty:
        st.divider()
        st.markdown("### Saved Board Snapshot for Selected Date")
        snapshot_cols = [
            "Tracker Source", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
            "HR Probability %", "HR Tier", "Actual HR Today", "Matchup Advantage",
            "HR Attackability Score", "HR Attackability %", "L10 BBE Score", "L10 BBE Trend", "EV", "Barrel%", "HardHit%", "AIR%",
            "Ranking Reasons", "Why"
        ]
        display_existing_columns(selected_board_snapshot, snapshot_cols)
    else:
        st.caption("No saved board snapshot found for selected date.")

    if not combo_tracker.empty:
        st.divider()
        st.markdown("### Combo Tracker")
        combo_view = combo_tracker[combo_tracker["date"].astype("string").fillna("") == str(selected_tracker_date)].copy()
        if combo_view.empty:
            st.caption("No combos tracked for selected date.")
        else:
            st.dataframe(
                dedupe_columns(combo_view.sort_values(
                    by=["combo_size", "combined_score"],
                    ascending=[True, False]
                )[[
                    "combo_label", "combo_size", "avg_leg_probability",
                    "combined_score", "legs_hit", "total_legs",
                    "result_state", "updated_at"
                ]]),
                use_container_width=True,
                hide_index=True
            )

    if not daily_summary.empty:
        st.divider()
        st.markdown("### Daily HR Prediction Accuracy History")
        st.dataframe(dedupe_columns(daily_summary), use_container_width=True, hide_index=True)

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
                render_card_grid(team_hr, max_cards=4, columns=1)
                with st.expander("Raw team HR table"):
                    st.dataframe(
                        team_hr[[
                            "Rank", "Player", "Lineup Spot", "Lineup Source", "Statcast Pass",
                            "Strict Statcast", "Recent Form Pass", "Pitcher Attackable", "Actual HR Today", "HR Probability %",
                            "HR Tier", "GroundBall%", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%",
                            "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
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
                render_card_grid(team_hr, max_cards=4, columns=1)
                with st.expander("Raw team HR table"):
                    st.dataframe(
                        team_hr[[
                            "Rank", "Player", "Lineup Spot", "Lineup Source", "Statcast Pass",
                            "Strict Statcast", "Recent Form Pass", "Pitcher Attackable", "Actual HR Today", "HR Probability %",
                            "HR Tier", "GroundBall%", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%",
                            "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
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
