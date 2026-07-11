import hashlib
import os
import re
from html import escape
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import time
import tempfile
import json
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
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

.bf-quick-list { display: flex; flex-direction: column; gap: 6px; }
.bf-quick-row { display: grid; grid-template-columns: minmax(150px, 1.2fr) minmax(120px, .8fr) repeat(3, 58px); gap: 8px; align-items: center; padding: 8px 10px; border: 1px solid rgba(255,255,255,.10); background:#0d1118; border-radius: 11px; margin-bottom: 6px; }
.bf-quick-player { font-weight: 950; color:#f8fbff; font-size: .92rem; }
.bf-quick-sub { color:#95a0b2; font-size:.72rem; margin-top:2px; }
.bf-mini-score { text-align:center; border-radius:8px; padding:4px 5px; background:#111823; border:1px solid rgba(255,255,255,.09); }
.bf-mini-score b { display:block; color:#6da2ff; font-size:.58rem; letter-spacing:.08em; }
.bf-mini-score span { display:block; font-weight:950; font-size:.9rem; }

.bf-reason-strip { grid-column:1 / -1; margin-top:-1px; padding-top:3px; border-top:1px solid rgba(255,255,255,.06); color:#aeb9ca; font-size:.58rem; font-weight:800; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.bf-reason-strip b { color:#6da2ff; font-size:.52rem; letter-spacing:.04em; }
.bf-match-card { border:1px solid #263040; border-radius:14px; overflow:hidden; background:#080d14; margin:6px 0 10px 0; box-shadow:0 0 0 1px rgba(0,0,0,.35) inset; }
.bf-match-topline { display:grid; grid-template-columns:minmax(180px,1.2fr) minmax(170px,1fr) 70px 70px 70px; gap:0; align-items:stretch; background:#141b28; border-bottom:1px solid #2b3547; }
.bf-cell-head { padding:10px 12px; border-right:1px solid rgba(255,255,255,.08); }
.bf-head-label { color:#4e83ff; font-size:.62rem; font-weight:950; letter-spacing:.13em; text-transform:uppercase; }
.bf-head-main { color:#f7f9ff; font-size:1.02rem; font-weight:950; margin-top:5px; line-height:1.08; }
.bf-hand-badge { display:inline-flex; align-items:center; justify-content:center; margin-left:5px; padding:1px 4px; border-radius:4px; background:rgba(255,85,85,.22); color:#ff9d9d; border:1px solid rgba(255,85,85,.45); font-size:.58rem; font-weight:950; vertical-align:middle; }
.bf-score-box { display:flex; flex-direction:column; align-items:center; justify-content:center; border-right:1px solid rgba(255,255,255,.08); min-height:58px; }
.bf-score-box .lab { color:#4e83ff; font-size:.58rem; letter-spacing:.12em; font-weight:950; }
.bf-score-box .num { margin-top:5px; font-size:1.03rem; font-weight:950; padding:5px 9px; border-radius:7px; min-width:36px; text-align:center; }
.bf-num-green { color:#00f2a0; background:rgba(0,242,160,.12); border:1px solid rgba(0,242,160,.22); }
.bf-num-yellow { color:#ffd166; background:rgba(255,209,102,.15); border:1px solid rgba(255,209,102,.22); }
.bf-num-red { color:#ff6666; background:rgba(255,85,85,.14); border:1px solid rgba(255,85,85,.22); }
.bf-card-body { display:grid; grid-template-columns:210px 1fr; gap:16px; padding:12px; }
.bf-side-panel { border-right:1px solid rgba(255,255,255,.08); padding-right:12px; }
.bf-section-title { color:#7e9bd3; font-size:.62rem; font-weight:950; letter-spacing:.16em; text-transform:uppercase; margin:4px 0 9px 0; }
.bf-score-line { display:grid; grid-template-columns:1fr 48px; gap:8px; align-items:center; font-size:.78rem; margin-bottom:8px; color:#dfe8ff; }
.bf-pill-num { display:inline-flex; justify-content:center; align-items:center; padding:4px 7px; border-radius:7px; background:#141b25; font-weight:950; }
.bf-pitcher-stat { display:grid; grid-template-columns:1fr 58px; gap:8px; align-items:center; color:#dfe8ff; font-size:.78rem; margin-bottom:8px; }
.bf-arsenal-grid { display:grid; grid-template-columns:repeat(3,minmax(110px,1fr)); gap:8px; }
.bf-pitch-tile { background:#0e141d; border:1px solid #263040; border-radius:10px; padding:9px 10px; min-height:92px; }
.bf-pitch-name { color:#f0f5ff; font-weight:950; font-size:.7rem; text-transform:uppercase; }
.bf-pitch-score { font-weight:950; font-size:1.45rem; line-height:1; margin-top:6px; }
.bf-usage-label { color:#e8f1ff; font-size:.58rem; font-weight:950; margin-top:6px; text-transform:uppercase; }
.bf-usage-track { height:5px; background:#1e2632; border-radius:999px; overflow:hidden; margin-top:4px; }
.bf-usage-fill { height:100%; background:#3c82ff; border-radius:999px; }
.bf-pitch-note { color:#aab4c4; font-size:.66rem; line-height:1.25; margin-top:5px; }
.bf-bvp-title { margin-top:14px; border-top:1px solid rgba(255,255,255,.08); padding-top:10px; color:#7e9bd3; font-size:.62rem; font-weight:950; letter-spacing:.16em; text-transform:uppercase; }
.bf-bvp-grid { display:grid; grid-template-columns:repeat(6, minmax(78px,1fr)); gap:5px; margin-top:8px; }
.bf-bvp-cell { background:#0e141d; border:1px solid rgba(255,255,255,.08); border-radius:5px; padding:7px 8px; }
.bf-bvp-label { color:#c5d0e4; font-size:.58rem; font-weight:900; text-transform:uppercase; }
.bf-bvp-values { margin-top:5px; font-size:.77rem; font-weight:950; }
.bf-green-txt { color:#00f2a0; } .bf-red-txt { color:#ff6262; } .bf-yellow-txt { color:#ffd166; }
.bf-card-foot { padding:0 12px 12px 12px; color:#aab4c4; font-size:.72rem; line-height:1.35; }
@media(max-width: 900px){
  .bf-quick-row { grid-template-columns:1fr 1fr 46px 46px 46px; gap:5px; padding:7px; }
  .bf-quick-player { font-size:.82rem; }
  .bf-quick-sub { font-size:.65rem; }
  .bf-mini-score { padding:3px; }
  .bf-mini-score b { font-size:.48rem; }
  .bf-mini-score span { font-size:.74rem; }
  .bf-reason-strip { padding-top:2px; font-size:.50rem; }
  .bf-reason-strip b { font-size:.45rem; }
  .bf-match-topline { grid-template-columns:1fr 1fr 50px 50px 50px; }
  .bf-cell-head { padding:8px 7px; }
  .bf-head-label { font-size:.5rem; }
  .bf-head-main { font-size:.78rem; overflow-wrap:anywhere; }
  .bf-score-box .lab { font-size:.48rem; }
  .bf-score-box .num { font-size:.78rem; min-width:28px; padding:4px 5px; }
  .bf-card-body { grid-template-columns:1fr; gap:8px; padding:8px; }
  .bf-side-panel { border-right:0; border-bottom:1px solid rgba(255,255,255,.08); padding-right:0; padding-bottom:7px; }
  .bf-arsenal-grid { grid-template-columns:repeat(2,minmax(95px,1fr)); }
  .bf-bvp-grid { grid-template-columns:repeat(3, minmax(76px,1fr)); }
}

@media (max-width: 760px) {
    .block-container { padding-left: .65rem; padding-right: .65rem; padding-top: .35rem; }
    .bf-hero { padding: 10px 11px; border-radius: 14px; margin-bottom: 6px; }
    .bf-title { font-size: 1.45rem !important; letter-spacing: -0.02em; }
    .bf-subtitle { font-size: .76rem; line-height: 1.25; }
    .bf-kicker { font-size: .62rem; }
    .bf-chip, .bf-key-chip { font-size: .62rem; padding: 2px 6px; }
    .bf-mini-row { gap: 4px; margin: 2px 0 3px 0; }
    .bf-signal-line { font-size: .74rem; line-height: 1.22; margin: 1px 0 3px 0; }
    div[data-testid="stExpander"] summary { font-size: .82rem !important; }
    hr { margin-top: .25rem !important; margin-bottom: .25rem !important; }
}


/* BF DATA FIT-ONLY PATCH: matchup arsenal readability.
   Data, scoring, tracker, ranking, and platform logic untouched. */
.bf-match-card{
    max-width:100%;
    overflow:hidden;
}
.bf-card-body{
    min-width:0;
}
.bf-card-body > div,
.bf-side-panel,
.bf-arsenal-grid,
.bf-bvp-grid{
    min-width:0;
}
.bf-arsenal-grid{
    grid-template-columns:repeat(3,minmax(0,1fr)) !important;
    gap:6px !important;
}
.bf-pitch-tile{
    min-width:0 !important;
    min-height:78px !important;
    padding:7px 8px !important;
    overflow:hidden !important;
}
.bf-pitch-name{
    font-size:.58rem !important;
    line-height:1.05 !important;
    overflow-wrap:anywhere !important;
}
.bf-pitch-score{
    font-size:1.08rem !important;
    margin-top:4px !important;
}
.bf-usage-label{
    font-size:.48rem !important;
    margin-top:4px !important;
}
.bf-usage-track{
    height:4px !important;
    margin-top:3px !important;
}
.bf-pitch-note{
    font-size:.50rem !important;
    line-height:1.08 !important;
    margin-top:3px !important;
    overflow-wrap:anywhere !important;
}
@media(max-width: 1100px){
    .bf-card-body{
        grid-template-columns:180px 1fr !important;
        gap:10px !important;
        padding:9px !important;
    }
    .bf-side-panel{
        padding-right:9px !important;
    }
    .bf-arsenal-grid{
        grid-template-columns:repeat(3,minmax(0,1fr)) !important;
        gap:5px !important;
    }
    .bf-pitch-tile{
        padding:6px 7px !important;
        min-height:72px !important;
    }
    .bf-pitch-note{
        font-size:.48rem !important;
    }
}
@media(max-width: 900px){
    .bf-card-body{
        grid-template-columns:1fr !important;
        gap:8px !important;
        padding:8px !important;
    }
    .bf-side-panel{
        border-right:0 !important;
        border-bottom:1px solid rgba(255,255,255,.08) !important;
        padding-right:0 !important;
        padding-bottom:7px !important;
    }
    .bf-arsenal-grid{
        grid-template-columns:repeat(3,minmax(0,1fr)) !important;
        gap:5px !important;
    }
    .bf-pitch-tile{
        padding:6px !important;
        min-height:68px !important;
    }
    .bf-pitch-name{
        font-size:.52rem !important;
    }
    .bf-pitch-score{
        font-size:.98rem !important;
    }
    .bf-pitch-note{
        font-size:.46rem !important;
        line-height:1.05 !important;
    }
}
@media(max-width: 640px){
    .bf-match-topline{
        grid-template-columns:1fr 1fr 42px 42px 42px !important;
    }
    .bf-arsenal-grid{
        grid-template-columns:repeat(2,minmax(0,1fr)) !important;
        gap:5px !important;
    }
    .bf-pitch-tile{
        min-height:auto !important;
        padding:6px !important;
    }
    .bf-pitch-score{
        font-size:.92rem !important;
    }
    .bf-pitch-note{
        font-size:.44rem !important;
    }
}
@media(max-width: 390px){
    .bf-arsenal-grid{
        grid-template-columns:1fr !important;
    }
    .bf-pitch-note{
        font-size:.50rem !important;
    }
}


/* BF DATA REAL-STATS FIT PATCH: no clipping, responsive BVP, readable real arsenal tiles */
.bf-match-card{
    max-width:100% !important;
    overflow-x:auto !important;
    overflow-y:visible !important;
}
.bf-card-body{
    min-width:0 !important;
}
.bf-card-body > div,
.bf-side-panel,
.bf-arsenal-grid,
.bf-bvp-grid{
    min-width:0 !important;
}
.bf-arsenal-grid{
    grid-template-columns:repeat(3,minmax(0,1fr)) !important;
    gap:6px !important;
}
.bf-pitch-tile{
    min-width:0 !important;
    min-height:72px !important;
    padding:7px 8px !important;
    overflow:visible !important;
}
.bf-pitch-name{
    font-size:.58rem !important;
    line-height:1.05 !important;
    overflow-wrap:anywhere !important;
}
.bf-pitch-score{
    font-size:1.03rem !important;
    margin-top:4px !important;
    white-space:nowrap !important;
}
.bf-usage-label{
    font-size:.46rem !important;
    margin-top:4px !important;
}
.bf-pitch-note{
    font-size:.48rem !important;
    line-height:1.08 !important;
    margin-top:3px !important;
    overflow-wrap:anywhere !important;
}
.bf-bvp-grid{
    grid-template-columns:repeat(auto-fit,minmax(86px,1fr)) !important;
    gap:5px !important;
}
.bf-bvp-cell{
    min-width:0 !important;
    padding:6px 7px !important;
    overflow:visible !important;
}
.bf-bvp-label, .bf-bvp-values{
    overflow-wrap:anywhere !important;
}
@media(max-width:900px){
    .bf-arsenal-grid{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}
    .bf-bvp-grid{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}
}
@media(max-width:640px){
    .bf-arsenal-grid{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
    .bf-bvp-grid{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
}
@media(max-width:390px){
    .bf-arsenal-grid{grid-template-columns:1fr !important;}
    .bf-bvp-grid{grid-template-columns:1fr 1fr !important;}
}


/* BF DATA FINAL VISIBILITY PATCH: keep open matchup cards readable without touching data/scoring. */
.bf-match-card, .bf-match-card *{box-sizing:border-box;}
.bf-match-card{max-width:100% !important; overflow-x:auto !important; overflow-y:visible !important;}
.bf-card-body,.bf-card-body>div,.bf-side-panel,.bf-arsenal-grid,.bf-bvp-grid{min-width:0 !important;}
.bf-pitch-tile,.bf-bvp-cell{min-width:0 !important; overflow:visible !important;}
.bf-pitch-name,.bf-pitch-note,.bf-bvp-label,.bf-bvp-values{overflow-wrap:anywhere !important; word-break:normal !important;}
.bf-bvp-grid{grid-template-columns:repeat(auto-fit,minmax(82px,1fr)) !important;}
@media(max-width:640px){.bf-bvp-grid{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}.bf-pitch-note{font-size:.46rem !important;}}

</style>
<div class="bf-hero">
    <div class="bf-kicker">BF DATA PRO LAB</div>
    <div class="bf-title">JR Daily HR Predictions</div>
    <div class="bf-subtitle">Powered by BF Data — compact MLB home run research board with green/yellow/red matchup signals and locked accuracy tracking.</div>
</div>
""", unsafe_allow_html=True)

AUTO_REFRESH_SECONDS = 120

# Speed control: regular board loads avoid the heavy play-by-play L10 BBE pull.
# Use Deep L10 Refresh only when you intentionally want the slower research pass.
DEFAULT_DEEP_L10_BBE = False


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
    """Persist surfaced prediction rows without rewriting earlier rankings.

    Important: this app has separate sections (CORE_BOARD, TOP12, GAME_HR).
    Older saves may be missing TOP12 rows, so do not simply return when the
    snapshot exists.  Merge in newly surfaced section rows by a stable key while
    preserving the existing row order and original predictions.
    """
    ensure_snapshot_folder()
    board_path = os.path.join(SNAPSHOT_DIR, f"hr_board_{snapshot_date}.csv")
    clean_board = board_df.copy()
    if "Actual HR Today" in clean_board.columns:
        clean_board = clean_board.drop(columns=["Actual HR Today"])

    if clean_board.empty:
        return

    key_cols = [c for c in ["Tracker Source", "Player", "Team", "Game"] if c in clean_board.columns]
    if len(key_cols) < 4:
        clean_board.to_csv(board_path, index=False)
        return

    if os.path.exists(board_path):
        try:
            old_board = pd.read_csv(board_path)
        except Exception:
            old_board = pd.DataFrame()
        if not old_board.empty and all(c in old_board.columns for c in key_cols):
            old_keys = set(zip(*[old_board[c].astype(str).map(normalize_name if c == "Player" else str) for c in key_cols]))
            add_rows = []
            for _, r in clean_board.iterrows():
                k = tuple(normalize_name(r[c]) if c == "Player" else str(r[c]) for c in key_cols)
                if k not in old_keys:
                    add_rows.append(r)
                    old_keys.add(k)
            if add_rows:
                merged = pd.concat([old_board, pd.DataFrame(add_rows)], ignore_index=True)
                merged.to_csv(board_path, index=False)
            return

    clean_board.to_csv(board_path, index=False)


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


def load_tracker() -> pd.DataFrame:
    columns = [
        "date", "player", "team", "game", "game_pk",
        "hr_probability", "hr_tier", "hr_eligible", "tracker_source",
        "result", "hr_count", "result_state", "game_state", "updated_at"
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


def dedupe_tracker_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one tracker row per visible section pick and preserve the best result.

    A player can appear in CORE_BOARD, TOP12, and GAME_HR on the same date.
    Those must remain separate section records, but repeated refreshes must not
    inflate counts. Multi-HR games keep the highest hr_count found.
    """
    if df is None or df.empty:
        return df
    work = df.copy()
    for col in ["date", "player", "team", "game", "tracker_source"]:
        if col not in work.columns:
            work[col] = ""
    if "hr_count" not in work.columns:
        work["hr_count"] = 0
    if "result" not in work.columns:
        work["result"] = pd.NA

    work["_player_key"] = work["player"].astype(str).map(normalize_name)
    work["_hr_count_num"] = pd.to_numeric(work["hr_count"], errors="coerce").fillna(0).astype(int)
    work["_result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)
    work["_updated_sort"] = work.get("updated_at", "").astype(str) if "updated_at" in work.columns else ""
    work = work.sort_values(["_hr_count_num", "_result_num", "_updated_sort"], ascending=[False, False, False])

    deduped = work.drop_duplicates(
        subset=[
            "date", "_player_key", "team", "game",
            *(["game_pk"] if "game_pk" in work.columns else []),
            "tracker_source"
        ],
        keep="first"
    ).copy()

    for c in ["_player_key", "_hr_count_num", "_result_num", "_updated_sort"]:
        if c in deduped.columns:
            deduped = deduped.drop(columns=[c])
    return deduped.reset_index(drop=True)


def save_tracker(df: pd.DataFrame):
    df = dedupe_tracker_rows(df)
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


def normalize_hand_code(raw_value, default="") -> str:
    txt = str(raw_value or "").strip().upper()
    if txt in {"L", "LEFT", "LEFTY", "LHP", "LHB"}:
        return "L"
    if txt in {"R", "RIGHT", "RIGHTY", "RHP", "RHB"}:
        return "R"
    if txt in {"S", "SH", "SHB", "SWITCH", "B"}:
        return "S"
    return default


def extract_people_hand_maps(people_payload: dict) -> dict:
    hand_map = {}
    for person in (people_payload or {}).get("people", []):
        pid = person.get("id")
        if pid is None:
            continue
        bat_code = normalize_hand_code(((person.get("batSide") or {}).get("code") or (person.get("batSide") or {}).get("description")), "")
        pitch_code = normalize_hand_code(((person.get("pitchHand") or {}).get("code") or (person.get("pitchHand") or {}).get("description")), "")
        hand_map[int(pid)] = {"bat": bat_code, "throw": pitch_code}
    return hand_map


@st.cache_data(ttl=21600)
def fetch_people_hand_map(person_ids_tuple: tuple) -> dict:
    ids = [str(int(x)) for x in person_ids_tuple if pd.notna(x)]
    if not ids:
        return {}
    out = {}
    for chunk in chunked(ids, 50):
        try:
            resp = requests.get(
                "https://statsapi.mlb.com/api/v1/people",
                params={"personIds": ",".join(chunk)},
                timeout=20,
            )
            resp.raise_for_status()
            out.update(extract_people_hand_maps(resp.json()))
        except Exception:
            continue
    return out


def get_true_batter_hand(player_id, hand_map: dict) -> str:
    try:
        pid = int(player_id)
    except Exception:
        return ""
    return normalize_hand_code((hand_map.get(pid) or {}).get("bat"), "")


def get_true_pitcher_hand(pitcher_id, hand_map: dict) -> str:
    try:
        pid = int(pitcher_id)
    except Exception:
        return ""
    return normalize_hand_code((hand_map.get(pid) or {}).get("throw"), "")


@st.cache_data(ttl=21600)
def fetch_mlb_people_directory() -> dict:
    """Name -> MLBAM ID directory from MLB Stats API for current/prior seasons."""
    directory = {}
    for season in [CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2]:
        try:
            resp = requests.get(
                "https://statsapi.mlb.com/api/v1/sports/1/players",
                params={"season": season},
                timeout=25,
            )
            resp.raise_for_status()
            for person in (resp.json() or {}).get("people", []) or []:
                pid = person.get("id")
                full = person.get("fullName")
                if pid and full:
                    directory.setdefault(normalize_name(full), int(pid))
                    # Useful for accent/name inconsistencies.
                    directory.setdefault(normalize_name(str(full).encode("ascii", "ignore").decode("ascii")), int(pid))
        except Exception:
            continue
    return directory


@st.cache_data(ttl=21600)
def lookup_mlb_person_id_by_name(name: str):
    """Resolve a player/pitcher name to MLBAM ID without guessing."""
    clean = str(name or "").strip()
    if not clean or clean in {"—", "Starter Pending"}:
        return None

    target = normalize_name(clean)
    directory = fetch_mlb_people_directory()
    if target in directory:
        return directory[target]

    ascii_target = normalize_name(clean.encode("ascii", "ignore").decode("ascii"))
    if ascii_target in directory:
        return directory[ascii_target]

    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/people/search",
            params={"names": clean},
            timeout=12,
        )
        resp.raise_for_status()
        people = (resp.json() or {}).get("people", []) or []
        if people:
            for person in people:
                if normalize_name(person.get("fullName", "")) == target:
                    return person.get("id")
            return people[0].get("id")
    except Exception:
        pass

    # Last exact-ish directory pass: only accept unique contains match, never guess.
    matches = [pid for n, pid in directory.items() if target and (target == n or target in n or n in target)]
    matches = list(dict.fromkeys(matches))
    return matches[0] if len(matches) == 1 else None


def estimate_handedness_from_name(name: str, role: str = "batter") -> str:
    # Kept only as a final emergency fallback for missing MLB IDs.
    # Normal app flow now uses MLB person batSide/pitchHand, not name guessing.
    return ""


def _is_swing(row) -> bool:
    desc = str(row.get("description", "") or "").lower()
    events = str(row.get("events", "") or "").lower()
    return (
        "swing" in desc
        or "foul" in desc
        or "hit_into_play" in desc
        or "hit_into_play" in events
        or "foul" in events
    )


def _is_whiff(row) -> bool:
    desc = str(row.get("description", "") or "").lower()
    return "swinging_strike" in desc or "missed_bunt" in desc


def _is_contact(row) -> bool:
    return _is_swing(row) and not _is_whiff(row)


def _is_bbe(row) -> bool:
    return pd.notna(row.get("launch_speed")) or pd.notna(row.get("launch_angle")) or str(row.get("bb_type", "") or "").strip() != ""


def _barrel_like(row) -> bool:
    ev = safe_float(row.get("launch_speed"), None)
    la = safe_float(row.get("launch_angle"), None)
    return ev is not None and la is not None and ev >= 98.0 and 8.0 <= la <= 50.0


def _statcast_date_range(days_back: int = 730):
    # True pitch mix needs enough history. Do NOT clamp to only this season;
    # that caused many starters/relievers to return no arsenal early in the year.
    end_dt = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=1)
    start_dt = end_dt - timedelta(days=int(days_back))
    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _read_statcast_csv(params: dict, timeout: int = 18) -> pd.DataFrame:
    """Read Baseball Savant Statcast CSV with the full filter payload.

    Baseball Savant often returns an empty page when the short/minimal query is
    used.  This wrapper keeps the query truthful but supplies the same neutral
    filter fields Savant's own CSV export uses. No estimated or fictional pitch
    mix is created here.
    """
    base_params = {
        "all": "true",
        "hfPT": "",
        "hfAB": "",
        "hfGT": "R|",
        "hfPR": "",
        "hfZ": "",
        "stadium": "",
        "hfBBT": "",
        "hfNewZones": "",
        "hfPull": "",
        "hfC": "",
        "hfSea": "",
        "hfSit": "",
        "hfOuts": "",
        "opponent": "",
        "pitcher_throws": "",
        "batter_stands": "",
        "hfSA": "",
        "type": "details",
        "min_pitches": "0",
        "min_results": "0",
        "group_by": "name",
        "sort_col": "pitches",
        "sort_order": "desc",
    }
    q = dict(base_params)
    q.update({k: v for k, v in (params or {}).items() if v is not None})
    try:
        resp = requests.get(
            "https://baseballsavant.mlb.com/statcast_search/csv",
            params=q,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/csv,application/csv,text/plain,*/*",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = resp.text or ""
        if "pitch_type" not in raw:
            return pd.DataFrame()
        df = pd.read_csv(StringIO(raw), low_memory=False)
        return df if "pitch_type" in df.columns else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=21600)
def fetch_true_pitcher_arsenal(pitcher_id, days_back: int = 730, cache_version: str = "bf-real-arsenal-v8") -> dict:
    empty = {"found": False, "mix": {}, "tiles": []}
    try:
        pid = int(pitcher_id)
    except Exception:
        return empty

    start_date, end_date = _statcast_date_range(days_back)
    base = {
        "all": "true",
        "player_type": "pitcher",
        "game_date_gt": start_date,
        "game_date_lt": end_date,
        "hfSea": f"{CURRENT_SEASON}|{CURRENT_SEASON - 1}|{CURRENT_SEASON - 2}|",
        "type": "details",
        "min_pitches": "0",
        "min_results": "0",
    }
    # Savant CSV has changed filter names over time. Try all truth-preserving
    # pitcher ID filters, then verify the returned rows belong to this pitcher.
    variants = [
        {**base, "pitcher": str(pid)},
        {**base, "pitchers_lookup[]": str(pid)},
        {**base, "pitcher_lookup[]": str(pid)},
        {**base, "player_lookup[]": str(pid)},
    ]
    df = pd.DataFrame()
    for params in variants:
        df = _read_statcast_csv(params, timeout=18)
        if not df.empty and "pitch_type" in df.columns:
            break
    if df.empty or "pitch_type" not in df.columns:
        return empty

    if "pitcher" in df.columns:
        df = df[pd.to_numeric(df["pitcher"], errors="coerce") == int(pid)].copy()
    df = df[df["pitch_type"].notna()].copy()
    if df.empty:
        return empty

    total = len(df)
    tiles = []
    for pitch, sub in df.groupby("pitch_type"):
        count = len(sub)
        usage = round(count / total * 100, 1) if total else 0.0
        if usage < 0.5 and count < 3:
            continue
        swings = int(sub.apply(_is_swing, axis=1).sum())
        whiffs = int(sub.apply(_is_whiff, axis=1).sum())
        contact = int(sub.apply(_is_contact, axis=1).sum())
        bbe = sub[sub.apply(_is_bbe, axis=1)].copy()
        hard = int((pd.to_numeric(bbe.get("launch_speed"), errors="coerce") >= 95.0).sum()) if not bbe.empty else 0
        barrels = int(bbe.apply(_barrel_like, axis=1).sum()) if not bbe.empty else 0
        slg_allowed = safe_float(pd.to_numeric(sub.get("estimated_slg_using_speedangle"), errors="coerce").dropna().mean(), 0.0) if "estimated_slg_using_speedangle" in sub.columns else 0.0
        woba_allowed = safe_float(pd.to_numeric(sub.get("estimated_woba_using_speedangle"), errors="coerce").dropna().mean(), 0.0) if "estimated_woba_using_speedangle" in sub.columns else 0.0
        contact_pct = round(contact / swings * 100, 1) if swings else None
        whiff_pct = round(whiffs / swings * 100, 1) if swings else None
        xslg_allowed = round(slg_allowed, 3) if slg_allowed else None
        tile = {
            "pitch": str(pitch),
            "usage": usage,
            "count": int(count),
            "swings": swings,
            "contact_pct": contact_pct,
            "whiff_pct": whiff_pct,
            "bbe": int(len(bbe)),
            "hardhit_allowed_pct": round(hard / len(bbe) * 100, 1) if len(bbe) else None,
            "barrel_allowed_pct": round(barrels / len(bbe) * 100, 1) if len(bbe) else None,
            "xslg_allowed": xslg_allowed,
            "xwoba_allowed": round(woba_allowed, 3) if woba_allowed else None,
        }
        tiles.append(tile)
    tiles = sorted(tiles, key=lambda x: x.get("usage", 0.0), reverse=True)
    return {"found": bool(tiles), "mix": {t["pitch"]: t["usage"] for t in tiles}, "tiles": tiles}


@st.cache_data(ttl=21600)
def fetch_true_batter_pitch_arsenal(batter_id, days_back: int = 730) -> dict:
    empty = {"found": False, "by_pitch": {}}
    try:
        pid = int(batter_id)
    except Exception:
        return empty
    start_date, end_date = _statcast_date_range(days_back)
    params = {
        "all": "true",
        "player_type": "batter",
        "batter": str(pid),
        "game_date_gt": start_date,
        "game_date_lt": end_date,
        "hfSea": f"{CURRENT_SEASON}|{CURRENT_SEASON - 1}|",
        "type": "details",
        "min_pitches": "0",
        "min_results": "0",
    }
    df = _read_statcast_csv(params, timeout=9)
    if df.empty or "pitch_type" not in df.columns:
        return empty
    df = df[df["pitch_type"].notna()].copy()
    by_pitch = {}
    for pitch, sub in df.groupby("pitch_type"):
        swings = int(sub.apply(_is_swing, axis=1).sum())
        whiffs = int(sub.apply(_is_whiff, axis=1).sum())
        contact = int(sub.apply(_is_contact, axis=1).sum())
        bbe = sub[sub.apply(_is_bbe, axis=1)].copy()
        if swings < 3 and len(bbe) < 2:
            continue
        hard = int((pd.to_numeric(bbe.get("launch_speed"), errors="coerce") >= 95.0).sum()) if not bbe.empty else 0
        barrels = int(bbe.apply(_barrel_like, axis=1).sum()) if not bbe.empty else 0
        slg = safe_float(pd.to_numeric(sub.get("estimated_slg_using_speedangle"), errors="coerce").dropna().mean(), 0.0) if "estimated_slg_using_speedangle" in sub.columns else 0.0
        woba = safe_float(pd.to_numeric(sub.get("estimated_woba_using_speedangle"), errors="coerce").dropna().mean(), 0.0) if "estimated_woba_using_speedangle" in sub.columns else 0.0
        by_pitch[str(pitch)] = {
            "swings": swings,
            "contact_pct": round(contact / swings * 100, 1) if swings else None,
            "whiff_pct": round(whiffs / swings * 100, 1) if swings else None,
            "bbe": int(len(bbe)),
            "hardhit_pct": round(hard / len(bbe) * 100, 1) if len(bbe) else None,
            "barrel_pct": round(barrels / len(bbe) * 100, 1) if len(bbe) else None,
            "xslg": round(slg, 3) if slg else None,
            "xwoba": round(woba, 3) if woba else None,
        }
    return {"found": bool(by_pitch), "by_pitch": by_pitch}


def build_pitch_mix_profile(pitcher_name: str, pitcher_id, *args, **kwargs) -> dict:
    # Real-only pitcher pitch mix. No fictional fallback pitches.
    if pitcher_id is None or (isinstance(pitcher_id, float) and pd.isna(pitcher_id)):
        pitcher_id = lookup_mlb_person_id_by_name(pitcher_name)
    arsenal = fetch_true_pitcher_arsenal(pitcher_id)
    return arsenal.get("mix", {}) if arsenal.get("found") else {}


def build_matchup_arsenal_tiles(pitcher_id, batter_id, pitch_matchup_score: float, authority_score: float, include_batter: bool = False) -> list[dict]:
    """Build truthful pitch tiles without slowing the whole board.

    Normal fast board load uses TRUE pitcher pitch types/usage/contact only.
    Batter-vs-pitch Statcast CSV pulls are intentionally reserved for Deep L10
    Refresh because doing one CSV pull per hitter is what made the app crawl.
    """
    pitcher_arsenal = fetch_true_pitcher_arsenal(pitcher_id)
    batter_arsenal = fetch_true_batter_pitch_arsenal(batter_id) if include_batter else {"found": False, "by_pitch": {}}
    if not pitcher_arsenal.get("found"):
        return []
    batter_by_pitch = batter_arsenal.get("by_pitch", {}) if batter_arsenal.get("found") else {}
    tiles = []
    for p in pitcher_arsenal.get("tiles", []):
        code = p.get("pitch")
        b = batter_by_pitch.get(code, {})
        batter_contact = b.get("contact_pct")
        pitcher_contact = p.get("contact_pct")
        batter_xslg = b.get("xslg")
        pitcher_xslg = p.get("xslg_allowed")
        batter_barrel = b.get("barrel_pct")
        pitcher_barrel = p.get("barrel_allowed_pct")
        # Score is a transparent matchup grade using true pitch usage + true batter/pitcher pitch-type data.
        score = 50.0
        if batter_xslg is not None:
            score += (safe_float(batter_xslg, 0.0) - 0.380) * 70
        if pitcher_xslg is not None:
            score += (safe_float(pitcher_xslg, 0.0) - 0.380) * 45
        if batter_barrel is not None:
            score += (safe_float(batter_barrel, 0.0) - 7.0) * 1.2
        if pitcher_barrel is not None:
            score += (safe_float(pitcher_barrel, 0.0) - 7.0) * 0.8
        if batter_contact is not None:
            score += (safe_float(batter_contact, 0.0) - 70.0) * 0.35
        score += min(safe_float(p.get("usage"), 0.0), 55.0) * 0.18
        tiles.append({
            "pitch": code,
            "usage": p.get("usage", 0.0),
            "score": round(clip(score, 5, 99), 0),
            "pitcher_contact_pct": pitcher_contact,
            "pitcher_whiff_pct": p.get("whiff_pct"),
            "pitcher_hardhit_allowed_pct": p.get("hardhit_allowed_pct"),
            "pitcher_barrel_allowed_pct": p.get("barrel_allowed_pct"),
            "pitcher_xslg_allowed": pitcher_xslg,
            "batter_contact_pct": batter_contact,
            "batter_whiff_pct": b.get("whiff_pct"),
            "batter_hardhit_pct": b.get("hardhit_pct"),
            "batter_barrel_pct": batter_barrel,
            "batter_xslg": batter_xslg,
            "note": (
                f"B Contact {batter_contact if batter_contact is not None else 'Deep'}% / "
                f"P Contact {pitcher_contact if pitcher_contact is not None else '—'}%"
            ),
        })
    return tiles

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
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str).str.strip().str.upper()
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
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str).str.strip().str.upper()
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

            away_pitcher_name = resolve_pitcher_name(away_id, away_block)
            home_pitcher_name = resolve_pitcher_name(home_id, home_block)
            away_pitcher_id = ((away_block.get("probablePitcher") or {}).get("id")) or lookup_mlb_person_id_by_name(away_pitcher_name)
            home_pitcher_id = ((home_block.get("probablePitcher") or {}).get("id")) or lookup_mlb_person_id_by_name(home_pitcher_name)

            games.append({
                "game_pk": game["gamePk"],
                "game_key": f"{team_abbr(away)} @ {team_abbr(home)}",
                "away_team": away,
                "home_team": home,
                "away_team_id": away_id,
                "home_team_id": home_id,
                "away_pitcher": away_pitcher_name,
                "home_pitcher": home_pitcher_name,
                "away_pitcher_id": away_pitcher_id,
                "home_pitcher_id": home_pitcher_id,
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


@st.cache_data(ttl=21600)
def fetch_l10_bbe_profile_from_savant_csv(player_id: int, days_back: int = 30) -> dict:
    """Fast true-L10 BBE pull for final board hitters only.

    This is intentionally cached and only called after the app has reduced the
    slate to real candidate hitters. Nothing about the source is shown on cards.
    """
    empty = {
        "found": False,
        "events": 0,
        "EV": None,
        "HardHit%": None,
        "Barrel%": None,
        "FlyBall%": None,
        "LineDrive%": None,
        "GroundBall%": None,
        "Popup%": None,
        "AIR%": None,
        "AvgLA": None,
    }
    try:
        pid = int(player_id)
    except Exception:
        return empty

    try:
        end_dt = datetime.now(ZoneInfo("America/New_York"))
        start_dt = end_dt - timedelta(days=int(days_back))
        params = {
            "all": "true",
            "player_type": "batter",
            "batter": str(pid),
            "game_date_gt": start_dt.strftime("%Y-%m-%d"),
            "game_date_lt": end_dt.strftime("%Y-%m-%d"),
            "type": "details",
            "min_pitches": "0",
            "min_results": "0",
        }
        resp = requests.get(
            "https://baseballsavant.mlb.com/statcast_search/csv",
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        resp.raise_for_status()
        from io import StringIO
        raw = resp.text
        if not raw or "launch_speed" not in raw:
            return empty
        df = pd.read_csv(StringIO(raw))
    except Exception:
        return empty

    if df.empty:
        return empty

    for col in ["launch_speed", "launch_angle"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "bb_type" not in df.columns:
        df["bb_type"] = ""

    bbe = df[
        df["launch_speed"].notna()
        | df["launch_angle"].notna()
        | df["bb_type"].astype(str).str.strip().ne("")
    ].copy()
    if bbe.empty:
        return empty

    sort_cols = [c for c in ["game_date", "game_pk", "at_bat_number", "pitch_number"] if c in bbe.columns]
    if sort_cols:
        bbe = bbe.sort_values(sort_cols, ascending=[False] * len(sort_cols))

    bbe = bbe.head(10).copy()
    if bbe.empty:
        return empty

    def classify_bbe(row):
        bb_type = str(row.get("bb_type", "") or "").lower().strip()
        if bb_type in {"ground_ball", "groundball", "grounder"}:
            return "GB"
        if bb_type in {"line_drive", "linedrive", "liner"}:
            return "LD"
        if bb_type in {"fly_ball", "flyball"}:
            return "FB"
        if bb_type in {"popup", "pop_up", "pop fly", "popfly"}:
            return "PU"
        la = safe_float(row.get("launch_angle"), None)
        if la is None:
            return None
        if la < 10:
            return "GB"
        if la < 25:
            return "LD"
        if la < 50:
            return "FB"
        return "PU"

    types = [classify_bbe(row) for _, row in bbe.iterrows()]
    types = [t for t in types if t is not None]
    if not types:
        return empty

    n = len(types)
    evs = pd.to_numeric(bbe.get("launch_speed"), errors="coerce").dropna().astype(float).tolist()
    las = pd.to_numeric(bbe.get("launch_angle"), errors="coerce").dropna().astype(float).tolist()

    hard = 0
    barrels = 0
    for _, row in bbe.iterrows():
        ev = safe_float(row.get("launch_speed"), None)
        la = safe_float(row.get("launch_angle"), None)
        if ev is not None and ev >= 95.0:
            hard += 1
        if ev is not None and la is not None and ev >= 98.0 and 8.0 <= la <= 50.0:
            barrels += 1

    gb = types.count("GB") / n * 100
    fb = types.count("FB") / n * 100
    ld = types.count("LD") / n * 100
    pu = types.count("PU") / n * 100

    return {
        "found": True,
        "events": n,
        "EV": round(sum(evs) / len(evs), 1) if evs else None,
        "HardHit%": round(hard / n * 100, 1),
        "Barrel%": round(barrels / n * 100, 1),
        "FlyBall%": round(fb, 1),
        "LineDrive%": round(ld, 1),
        "GroundBall%": round(gb, 1),
        "Popup%": round(pu, 1),
        "AIR%": round(fb + ld, 1),
        "AvgLA": round(sum(las) / len(las), 1) if las else None,
    }



def compute_hitter_live_metrics_from_map(player_id: int, stats_map: dict, use_true_bbe: bool = False):
    data = stats_map.get(player_id, {"season": {}, "gamelog": []})
    season_stat = data.get("season", {}) or {}
    gamelog = (data.get("gamelog", []) or [])[:10]

    if not gamelog:
        return None

    true_bbe = {"found": False}
    # SPEED FIX: only final board hitters should trigger this live CSV lookup.
    # Roster/projection screening calls this function with use_true_bbe=False.
    if use_true_bbe:
        true_bbe = fetch_l10_bbe_profile_from_savant_csv(player_id, days_back=30)
        if not isinstance(true_bbe, dict):
            true_bbe = {"found": False}

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

    # Fast fallback shape from L10/season box stats. This keeps the app responsive
    # before true L10 BBE is applied to final board hitters.
    recent_ground_outs = sum(safe_int(g["stat"].get("groundOuts", 0)) for g in gamelog)
    recent_air_outs = sum(safe_int(g["stat"].get("airOuts", 0)) for g in gamelog)
    recent_shape_total = recent_ground_outs + recent_air_outs

    season_ground_outs = safe_int(season_stat.get("groundOuts", 0))
    season_air_outs = safe_int(season_stat.get("airOuts", 0))
    season_shape_total = season_ground_outs + season_air_outs

    ev = clip(86 + iso * 18 + (xbh / max(ab, 1)) * 45 + (hits / pa_proxy) * 8, 84, 99)
    hard_hit = clip(26 + iso * 85 + (xbh / pa_proxy) * 140 - (strikeouts / pa_proxy) * 10, 20, 60)
    barrel = clip(2 + iso * 35 + (hrs / pa_proxy) * 160, 1, 20)

    if recent_shape_total > 0:
        gb = clip((recent_ground_outs / recent_shape_total) * 100, 5, 70)
        air_total = clip(100 - gb, 30, 95)
    elif season_shape_total > 0:
        gb = clip((season_ground_outs / season_shape_total) * 100, 20, 65)
        air_total = clip(100 - gb, 35, 80)
    else:
        gb = stable_float(f"{player_id}-gb-fallback", 32, 48)
        air_total = clip(100 - gb, 35, 80)

    ld_share = clip(0.32 + (hard_hit - 40) / 140 + (xbh / max(pa_proxy, 1)) * 0.35 + (hrs / max(pa_proxy, 1)) * 0.45, 0.22, 0.68)
    ld = clip(air_total * ld_share, 10, 65)
    fb = clip(air_total - ld, 8, 65)
    if fb + ld > 0:
        scale = max(0.0, 100.0 - gb) / (fb + ld)
        fb = clip(fb * scale, 0, 80)
        ld = clip(ld * scale, 0, 80)

    if true_bbe.get("found") and safe_int(true_bbe.get("events"), 0) >= 4:
        if true_bbe.get("EV") is not None:
            ev = clip(safe_float(true_bbe.get("EV"), ev), 84, 105)
        hard_hit = clip(safe_float(true_bbe.get("HardHit%"), hard_hit), 0, 100)
        true_barrel = safe_float(true_bbe.get("Barrel%"), barrel)
        barrel = clip((true_barrel * 0.65) + (barrel * 0.35), 0, 30)
        fb = clip(safe_float(true_bbe.get("FlyBall%"), fb), 0, 100)
        ld = clip(safe_float(true_bbe.get("LineDrive%"), ld), 0, 100)
        gb = clip(safe_float(true_bbe.get("GroundBall%"), gb), 0, 100)
        total_shape = fb + ld + gb
        if total_shape > 0:
            scale = 100.0 / total_shape
            fb = round(fb * scale, 1)
            ld = round(ld * scale, 1)
            gb = round(gb * scale, 1)

    air_total = clip(fb + ld, 0, 100)
    l10_bbe_events = safe_int(true_bbe.get("events"), 0) if true_bbe.get("found") else max(1, min(10, ab - strikeouts + doubles + triples + hrs))
    l10_damage_per_bbe = (hrs * 4.0 + xbh * 1.6 + total_bases * 0.18) / max(l10_bbe_events, 1)
    l10_contact_rate = max(0.0, (ab - strikeouts) / max(ab, 1))

    if true_bbe.get("found"):
        l10_bbe_quality = clip(
            max(0.0, ev - 86.0) * 4.0 +
            hard_hit * 0.55 +
            barrel * 1.15 +
            max(0.0, air_total - 40.0) * 0.28 +
            max(0.0, 45.0 - gb) * 0.22 +
            (hrs * 3.0) +
            (xbh * 0.9),
            0.0,
            100.0,
        )
    else:
        l10_bbe_quality = clip(
            (l10_damage_per_bbe * 22.0) +
            (iso * 70.0) +
            (l10_contact_rate * 18.0) +
            (hrs * 4.0) +
            (xbh * 1.1),
            0.0,
            100.0,
        )

    if l10_bbe_quality >= 72:
        l10_bbe_trend = "ELITE"
    elif l10_bbe_quality >= 55:
        l10_bbe_trend = "STRONG"
    elif l10_bbe_quality >= 38:
        l10_bbe_trend = "MIXED"
    else:
        l10_bbe_trend = "COLD"

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
        "L10_BBE_Events": int(l10_bbe_events),
        "L10_BBE_Quality": round(l10_bbe_quality, 1),
        "L10_BBE_Trend": l10_bbe_trend,
        "L10_BBE_Damage": round(l10_damage_per_bbe, 2),
        "L10_BBE_AvgLA": round(safe_float(true_bbe.get("AvgLA"), 14.0), 1) if true_bbe.get("found") else 14.0,
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


def get_team_candidate_hitters(game_pk: int, team_id: int, side: str, savant_batter_map: dict, deep_bbe: bool = False):
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
        metrics = compute_hitter_live_metrics_from_map(h["player_id"], stats_map, use_true_bbe=False)
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
    out["HR Attackability Score"] = pd.to_numeric(out["_bf_pitcher_target_score"], errors="coerce").fillna(0.0).round(2)
    out["HR Attackability Score"] = out["HR Attackability Score"]

    final_cols = [
        "Game", "Pitcher", "HR Attackability Score", "Pitcher_HR9_Last7", "Pitcher_Season_HR9", "Pitcher_Recent_HR9",
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
    hand_map: dict | None = None,
    weather_boost: float = 0.0,
    weather_note: str = "neutral weather",
    temp_f: float = 72.0,
    wind_mph: float = 7.0,
    bullpen_fatigue_score: float = 0.0,
    bullpen_fatigue_note: str = "Neutral bullpen rest",
    bullpen_ip_prev: float = 0.0,
    bullpen_arms_prev: int = 0,
    deep_bbe: bool = False,
):
    if opp_pitcher_id is None or (isinstance(opp_pitcher_id, float) and pd.isna(opp_pitcher_id)):
        opp_pitcher_id = lookup_mlb_person_id_by_name(opp_pitcher)

    live_hitter = compute_hitter_live_metrics_from_map(player_id, hitter_stats_map, use_true_bbe=deep_bbe)
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
        (recent_avg * 18.0)
    )

    if recent_hr >= 2 or recent_xbh >= 5 or recent_iso >= 0.260:
        recent_trend = "HOT"
    elif recent_hr >= 1 or recent_xbh >= 3 or recent_iso >= 0.180:
        recent_trend = "LIVE"
    elif recent_iso >= 0.120 or recent_avg >= 0.260:
        recent_trend = "NEUTRAL"
    else:
        recent_trend = "COLD"

    display_spot = display_lineup_spot(lineup_spot)
    hand_map = hand_map or {}
    bats = get_true_batter_hand(player_id, hand_map)
    pitcher_throws = get_true_pitcher_hand(opp_pitcher_id, hand_map)

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

    pitch_mix_example = build_pitch_mix_profile(opp_pitcher, opp_pitcher_id)
    arsenal_tiles = build_matchup_arsenal_tiles(opp_pitcher_id, player_id, 0.0, 0.0, include_batter=deep_bbe)
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
        "Player ID": player_id,
        "Pitcher ID": opp_pitcher_id,
        "Player": player_name,
        "Team": team,
        "Bats": bats,
        "Pitcher Throws": pitcher_throws,
        "Pitch Mix Mode": pitch_mix_mode,
        "Relevant Pitch Mix": relevant_pitch_mix,
        "Primary Pitch": primary_pitch if primary_pitch is not None else "Mix",
        "Primary Pitch Usage": round(primary_pitch_usage, 1),
        "True Pitch Arsenal": json.dumps(arsenal_tiles),
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
        "HR Attackability Label": pitcher_target_label,
        "HR Attackability Score": round(pitcher_target_score, 2),
        "HR Attackability Label": pitcher_target_label,
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


def _prefetch_cached_calls(call_specs: list[tuple], max_workers: int = 12):
    """Warm independent cached network calls concurrently."""
    if not call_specs:
        return
    workers = max(1, min(int(max_workers), len(call_specs)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fn, *args) for fn, args in call_specs]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass


@st.cache_data(ttl=1800)
def build_daily_dataset(deep_bbe: bool = False):
    schedule = sort_schedule_rows(get_today_schedule())
    rows = []

    savant_batter_map = fetch_savant_batter_map(CURRENT_SEASON)

    candidate_map = {}
    all_hitter_ids = set()
    all_pitcher_ids = set()

    for game in schedule:
        away_candidates, away_source = get_team_candidate_hitters(
            game["game_pk"], game["away_team_id"], "away", savant_batter_map, deep_bbe=deep_bbe
        )
        home_candidates, home_source = get_team_candidate_hitters(
            game["game_pk"], game["home_team_id"], "home", savant_batter_map, deep_bbe=deep_bbe
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
    hand_map = fetch_people_hand_map(tuple(list(all_hitter_ids) + list(all_pitcher_ids)))

    # Cold-start speed: warm independent real-data calls concurrently instead
    # of waiting for each pitcher/game one at a time. Existing calculations,
    # cards, and data sources remain unchanged.
    prefetch_specs = []
    for pitcher_id in sorted(all_pitcher_ids):
        prefetch_specs.append((fetch_true_pitcher_arsenal, (pitcher_id,)))
    for game in schedule:
        home_abbr = team_abbr(game["home_team"])
        prefetch_specs.append((fetch_weather_for_park, (home_abbr,)))
        prefetch_specs.append((fetch_bullpen_fatigue_for_team, (game["home_team_id"],)))
        prefetch_specs.append((fetch_bullpen_fatigue_for_team, (game["away_team_id"],)))
    _prefetch_cached_calls(prefetch_specs, max_workers=12)

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
                hand_map=hand_map,
                weather_boost=weather.get("WeatherBoost", 0.0),
                weather_note=weather.get("WeatherNote", "neutral weather"),
                temp_f=weather.get("TempF", 72.0),
                wind_mph=weather.get("WindMPH", 7.0),
                bullpen_fatigue_score=home_bullpen.get("BullpenFatigueScore", 0.0),
                bullpen_fatigue_note=home_bullpen.get("BullpenFatigueNote", "Neutral bullpen rest"),
                bullpen_ip_prev=home_bullpen.get("BullpenIPPrev", 0.0),
                bullpen_arms_prev=home_bullpen.get("BullpenArmsPrev", 0),
                deep_bbe=deep_bbe,
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
                hand_map=hand_map,
                weather_boost=weather.get("WeatherBoost", 0.0),
                weather_note=weather.get("WeatherNote", "neutral weather"),
                temp_f=weather.get("TempF", 72.0),
                wind_mph=weather.get("WindMPH", 7.0),
                bullpen_fatigue_score=away_bullpen.get("BullpenFatigueScore", 0.0),
                bullpen_fatigue_note=away_bullpen.get("BullpenFatigueNote", "Neutral bullpen rest"),
                bullpen_ip_prev=away_bullpen.get("BullpenIPPrev", 0.0),
                bullpen_arms_prev=away_bullpen.get("BullpenArmsPrev", 0),
                deep_bbe=deep_bbe,
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


def get_team_game_view(df: pd.DataFrame, game_key: str, team: str, game_pk=None):
    """Return unique qualified hitters for one team in one specific game.

    Doubleheaders are separated by MLB game_pk. Inside that game, a hitter can
    appear only once. Removed duplicates never consume a ranking slot; the board
    continues to the next-highest qualified hitter. If fewer than four unique
    hitters qualify, only those qualified hitters are shown.
    """
    if df is None or df.empty:
        empty = pd.DataFrame()
        return empty, empty

    mask = (
        df["Game"].astype(str).eq(str(game_key))
        & df["Team"].astype(str).eq(str(team))
    )

    if game_pk is not None and "game_pk" in df.columns:
        requested_game_pk = safe_int(game_pk, -1)
        row_game_pks = pd.to_numeric(df["game_pk"], errors="coerce").fillna(-1).astype(int)
        mask &= row_game_pks.eq(requested_game_pk)

    team_df = df.loc[mask].copy()
    if team_df.empty:
        return team_df, team_df

    # Rank this game's rows first so that, if the same hitter somehow entered
    # the dataset more than once, the strongest version is the one preserved.
    team_df = sort_for_hr(team_df).reset_index(drop=True)

    # Prefer the stable MLB player ID. Fall back to normalized name only when an
    # ID is unavailable. This prevents spelling, accents, or refresh artifacts
    # from allowing the same hitter to occupy multiple slots.
    if "Player ID" in team_df.columns:
        player_ids = pd.to_numeric(team_df["Player ID"], errors="coerce")
        name_keys = team_df["Player"].astype(str).map(normalize_name)
        team_df["_bf_unique_player"] = [
            f"id:{int(pid)}" if pd.notna(pid) else f"name:{name}"
            for pid, name in zip(player_ids, name_keys)
        ]
    else:
        team_df["_bf_unique_player"] = (
            "name:" + team_df["Player"].astype(str).map(normalize_name)
        )

    team_df = (
        team_df
        .drop_duplicates(subset=["_bf_unique_player"], keep="first")
        .drop(columns=["_bf_unique_player"])
        .reset_index(drop=True)
    )

    # Apply the existing BF qualification standards to this game only.
    qualified = get_research_shortlist_pool(team_df)

    # Backfill naturally with the next-highest unique qualified hitter. Do not
    # force four cards when fewer than four hitters genuinely qualify.
    selected_rows = []
    used_players = set()

    if qualified is not None and not qualified.empty:
        qualified = sort_for_hr(qualified).reset_index(drop=True)

        for _, row in qualified.iterrows():
            raw_pid = row.get("Player ID", pd.NA)
            try:
                player_key = f"id:{int(raw_pid)}" if pd.notna(raw_pid) else ""
            except Exception:
                player_key = ""

            if not player_key:
                player_key = f"name:{normalize_name(row.get('Player', ''))}"

            if player_key in used_players:
                continue

            selected_rows.append(row)
            used_players.add(player_key)

            if len(selected_rows) >= 4:
                break

    if selected_rows:
        hr_pool = pd.DataFrame(selected_rows).reset_index(drop=True)
        hr_pool = add_rank_column(hr_pool)
    else:
        hr_pool = team_df.iloc[0:0].copy()

    # HRR remains game-specific and unique as well.
    hrr = (
        team_df.sort_values(
            by=["HRR Score", "LineDrive%", "HardHit%", "GroundBall%"],
            ascending=[False, False, False, True]
        )
        .drop_duplicates(
            subset=["Player ID"] if "Player ID" in team_df.columns else ["Player"],
            keep="first"
        )
        .head(5)
        .reset_index(drop=True)
    )

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
        gdf = df[
            (df["Game"] == game["game_key"])
            & (df["game_pk"] == game.get("game_pk"))
        ].copy()
        if gdf.empty:
            continue

        away_team = team_abbr(game["away_team"])
        home_team = team_abbr(game["home_team"])

        away_hr, _ = get_team_game_view(gdf, game["game_key"], away_team, game.get("game_pk"))
        if not away_hr.empty:
            away_hr = away_hr.copy()
            away_hr["Tracker Source"] = "GAME_HR"
            visible_frames.append(away_hr)

        home_hr, _ = get_team_game_view(gdf, game["game_key"], home_team, game.get("game_pk"))
        if not home_hr.empty:
            home_hr = home_hr.copy()
            home_hr["Tracker Source"] = "GAME_HR"
            visible_frames.append(home_hr)

    if not visible_frames:
        return pd.DataFrame(columns=df.columns.tolist() + ["Tracker Source"])

    visible_df = pd.concat(visible_frames, ignore_index=True)
    visible_dedupe_cols = ["Player", "Team", "Game", "Tracker Source"]
    if "game_pk" in visible_df.columns:
        visible_dedupe_cols.insert(3, "game_pk")
    visible_df = visible_df.drop_duplicates(subset=visible_dedupe_cols).reset_index(drop=True)
    visible_df = sort_for_hr(visible_df)
    return visible_df


@st.cache_data(ttl=15)
def get_live_feed_homers(game_pk: int):
    """Count HRs from MLB live feed play-by-play.

    Boxscore batting totals can lag or briefly show only one homer.  The live
    play feed is better for detecting multi-HR days like Ernie Clement 2 HR.
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    homer_map = {}
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return homer_map

    plays = (((data.get("liveData") or {}).get("plays") or {}).get("allPlays") or [])
    for play in plays:
        result = play.get("result", {}) or {}
        event_type = str(result.get("eventType", "") or "").lower()
        event = str(result.get("event", "") or "").lower()
        description = str(result.get("description", "") or "").lower()
        if event_type != "home_run" and "home run" not in event and "homers" not in event and "home run" not in description and "homers" not in description:
            continue
        batter = (play.get("matchup", {}) or {}).get("batter", {}) or {}
        name = batter.get("fullName")
        if not name:
            continue
        raw = str(name)
        norm = normalize_name(raw)
        homer_map[raw] = safe_int(homer_map.get(raw), 0) + 1
        homer_map[norm] = safe_int(homer_map.get(norm), 0) + 1
    return homer_map


@st.cache_data(ttl=15)
def get_boxscore_homers(game_pk: int):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    homer_map = {}

    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        data = {}

    for side in ["away", "home"]:
        team_data = data.get("teams", {}).get(side, {})
        players = team_data.get("players", {})
        for _, player_data in players.items():
            person = player_data.get("person", {})
            full_name = person.get("fullName")
            batting = player_data.get("stats", {}).get("batting", {})
            hr_count = safe_int(batting.get("homeRuns", 0), 0)
            if full_name:
                raw = str(full_name)
                norm = normalize_name(raw)
                homer_map[raw] = max(safe_int(homer_map.get(raw), 0), int(hr_count))
                homer_map[norm] = max(safe_int(homer_map.get(norm), 0), int(hr_count))

    # Merge play-by-play counts and keep the highest value per player.
    feed_map = get_live_feed_homers(game_pk)
    for key, val in feed_map.items():
        homer_map[key] = max(safe_int(homer_map.get(key), 0), safe_int(val, 0))

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
    """Display-only result column; skip result calls before first pitch."""
    if df.empty:
        return df.copy()
    out = df.copy()
    out["Actual HR Today"] = 0
    if "game_pk" not in out.columns or "Player" not in out.columns:
        return out
    for game in schedule:
        if str(game.get("game_state", "Preview")) == "Preview":
            continue
        game_pk = game.get("game_pk")
        if game_pk is None:
            continue
        mask = pd.to_numeric(out["game_pk"], errors="coerce") == safe_int(game_pk, -1)
        if not mask.any():
            continue
        homer_map = get_boxscore_homers(game_pk)
        out.loc[mask, "Actual HR Today"] = out.loc[mask, "Player"].apply(
            lambda p: get_player_hr_count_from_map(homer_map, p)
        )
    return out


def get_locked_section_snapshot(source_key: str, fallback_df: pd.DataFrame, schedule: list[dict], limit: int | None = None) -> pd.DataFrame:
    """Use the saved surfaced board for display so upgrades/refreshes do not rewrite rankings."""
    snap = load_daily_board_snapshot(today_str())
    if snap is not None and not snap.empty and "Tracker Source" in snap.columns:
        section = snap[snap["Tracker Source"].astype(str).str.strip().str.upper() == str(source_key).upper()].copy()
        if not section.empty:
            section = add_live_homer_counts_to_board(section, schedule)
            if "Rank" in section.columns:
                section = section.drop(columns=["Rank"])
            section = section.reset_index(drop=True)
            section.insert(0, "Rank", range(1, len(section) + 1))
            if limit is not None:
                section = section.head(limit).copy()
            return dedupe_columns(section)
    out = fallback_df.copy()
    if "Rank" not in out.columns:
        out = add_rank_column(out.reset_index(drop=True))
    if limit is not None:
        out = out.head(limit).copy()
    return dedupe_columns(out)


def sync_tracker_with_board(tracked_df: pd.DataFrame):
    tracker = dedupe_tracker_rows(load_tracker())
    date_key = today_str()

    if tracked_df.empty:
        save_tracker(tracker)
        return tracker

    if "hr_count" not in tracker.columns:
        tracker["hr_count"] = 0

    existing_keys = set()
    if not tracker.empty:
        today_existing = tracker[tracker["date"].astype(str) == date_key].copy()
        if not today_existing.empty:
            existing_game_pk = pd.to_numeric(today_existing.get("game_pk"), errors="coerce").fillna(-1).astype(int)
            existing_keys = set(zip(
                today_existing["date"].astype(str),
                today_existing["player"].astype(str).map(normalize_name),
                today_existing["team"].astype(str),
                today_existing["game"].astype(str),
                existing_game_pk,
                today_existing["tracker_source"].astype(str),
            ))

    new_rows = []
    for _, row in tracked_df.iterrows():
        source = str(row.get("Tracker Source", "CORE_BOARD"))
        player_name = str(row["Player"])
        key = (
            str(date_key),
            normalize_name(player_name),
            str(row["Team"]),
            str(row["Game"]),
            safe_int(row.get("game_pk"), -1),
            source,
        )
        if key in existing_keys:
            continue

        new_rows.append({
            "date": date_key,
            "player": player_name,
            "team": row["Team"],
            "game": row["Game"],
            "game_pk": row.get("game_pk", pd.NA),
            "hr_probability": row.get("HR Probability %", pd.NA),
            "hr_tier": row.get("HR Tier", pd.NA),
            "hr_eligible": int(bool(row.get("HR Eligible", False))),
            "tracker_source": source,
            "result": pd.NA,
            "hr_count": 0,
            "result_state": "PENDING",
            "game_state": row.get("game_state", pd.NA),
            "updated_at": now_et_string(),
        })
        existing_keys.add(key)

    if new_rows:
        tracker = pd.concat([tracker, pd.DataFrame(new_rows)], ignore_index=True)

    tracker = dedupe_tracker_rows(tracker)
    save_tracker(tracker)
    return tracker

def auto_update_tracker_results(tracker: pd.DataFrame, schedule: list[dict]):
    if tracker.empty:
        return tracker

    tracker = dedupe_tracker_rows(tracker.copy())
    if "hr_count" not in tracker.columns:
        tracker["hr_count"] = 0
    if "game_pk" not in tracker.columns:
        tracker["game_pk"] = pd.NA

    date_key = today_str()
    today_mask = tracker["date"].astype(str) == date_key
    tracker_game_pk_num = pd.to_numeric(tracker["game_pk"], errors="coerce")

    for game in schedule:
        game_pk = game["game_pk"]
        game_state = game.get("game_state", "Preview")
        detailed_state = game.get("detailed_state", "Scheduled")

        rows_mask = today_mask & (tracker_game_pk_num == safe_int(game_pk, -1))
        if not rows_mask.any():
            # Fallback by game key so older rows with bad/missing game_pk still update.
            rows_mask = today_mask & (tracker["game"].astype(str) == str(game.get("game_key", "")))
        if not rows_mask.any():
            continue

        # Pregame games cannot have result data, so avoid unnecessary network
        # calls. Live/final games retain the same boxscore + play-feed tracking.
        homer_map = {} if game_state == "Preview" else get_boxscore_homers(game_pk)

        for idx in tracker.index[rows_mask]:
            player = tracker.at[idx, "player"]
            hr_count = get_player_hr_count_from_map(homer_map, player)
            old_hr = safe_int(tracker.at[idx, "hr_count"], 0)
            hr_count = max(int(hr_count), old_hr)
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

    tracker = dedupe_tracker_rows(tracker)
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
        game_state = game.get("game_state", "Preview")
        homer_maps[game["game_pk"]] = {} if game_state == "Preview" else get_boxscore_homers(game["game_pk"])
        schedule_states[game["game_key"]] = (game_state, game.get("detailed_state", "Scheduled"))

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
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str).str.strip().str.upper()
    work["result_num"] = pd.to_numeric(work["result"], errors="coerce").fillna(0).astype(int)
    if "hr_count" in work.columns:
        work["result_num"] = (pd.to_numeric(work["hr_count"], errors="coerce").fillna(0).astype(int) > 0).astype(int)
    today_mask = work["date"].astype(str) == today_str()

    for source in buckets.keys():
        all_df = work[work["tracker_source"] == source].copy()
        today_df = all_df[all_df["date"].astype(str) == today_str()].copy()
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
    work["tracker_source"] = work["tracker_source"].fillna("CORE_BOARD").astype(str).str.strip().str.upper()
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
        '<span class="bf-key-chip bf-key-green">Green = attackable / good for hitter</span>'
        '<span class="bf-key-chip bf-key-yellow">Yellow = caution / mixed</span>'
        '<span class="bf-key-chip bf-key-red">Red = HR suppressor / bad for hitter</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_bar(label: str, value, max_value: float = 100.0, suffix: str = "", fill_class: str = "") -> str:
    val = safe_float(value, 0.0)
    return f"{label}: {val:.1f}{suffix}"




def _attackability_pct(value) -> float:
    """Convert BF Data HR Attackability Score into a 0-100 display scale.

    The engine stores HR Attackability Score on roughly a 0-45 scale.
    The matchup card needs a percentage-like value for OVR/STUFF display.
    """
    val = safe_float(value, 0.0)
    if val <= 0:
        return 0.0
    if val <= 45:
        return round(clip((val / 45.0) * 100.0, 0.0, 100.0), 1)
    return round(clip(val, 0.0, 100.0), 1)


def _score_color_class(value, good=70, warn=50, lower_is_better=False):
    val = safe_float(value, 0.0)
    if lower_is_better:
        if val <= good:
            return "bf-num-green"
        if val <= warn:
            return "bf-num-yellow"
        return "bf-num-red"
    if val >= good:
        return "bf-num-green"
    if val >= warn:
        return "bf-num-yellow"
    return "bf-num-red"


def _display_hand(raw, role="batter"):
    txt = str(raw or "").strip().upper()
    if role == "pitcher":
        if txt in {"L", "LHP", "LEFT", "LEFTY"}:
            return "LHP"
        if txt in {"R", "RHP", "RIGHT", "RIGHTY"}:
            return "RHP"
        return "—"
    if txt in {"S", "SH", "SHB", "SWITCH"}:
        return "SHB"
    if txt in {"L", "LHB", "LEFT", "LEFTY"}:
        return "LHB"
    if txt in {"R", "RHB", "RIGHT", "RIGHTY"}:
        return "RHB"
    return "—"


def _pitch_full_name(code):
    c = str(code or "").strip().upper()
    return {
        "FF": "FOUR-SEAM",
        "FA": "FOUR-SEAM",
        "SI": "SINKER",
        "SL": "SLIDER",
        "CH": "CHANGEUP",
        "CU": "CURVEBALL",
        "KC": "KNUCKLE CURVE",
        "EP": "EEPHUS",
        "FC": "CUTTER",
        "FS": "SPLITTER",
        "ST": "SWEEPER",
        "SV": "SLURVE",
        "CS": "SLOW CURVE",
        "KN": "KNUCKLEBALL",
        "FO": "FORKBALL",
        "PO": "PITCHOUT",
        "SC": "SCREWBALL",
        "MIX": "MIX",
    }.get(c, c if c else "—")


def _row_id_value(row: pd.Series, candidates: list[str]):
    for col in candidates:
        if col in row.index:
            val = row.get(col)
            try:
                if pd.notna(val) and str(val).strip() not in {"", "nan", "None", "—"}:
                    return val
            except Exception:
                if val:
                    return val
    return None


def _parse_relevant_pitches(row: pd.Series):
    """Return real, row-specific pitcher arsenal tiles without slowing page load.

    Speed-only rule: use the already-built row JSON first. That prevents every
    collapsed Streamlit expander from re-querying Statcast while the page loads.
    If a row has no saved JSON, fall back to a pitcher-only pull. No fictional
    pitch mix is created.
    """
    raw_tiles = row.get("True Pitch Arsenal", None)
    if raw_tiles is not None:
        try:
            if pd.notna(raw_tiles):
                parsed = json.loads(str(raw_tiles))
                if isinstance(parsed, list) and parsed:
                    return parsed
        except Exception:
            pass

    pitcher_id = _row_id_value(row, [
        "Pitcher ID", "pitcher_id", "opp_pitcher_id", "Opp Pitcher ID", "Probable Pitcher ID"
    ])
    if pitcher_id is None:
        pitcher_id = lookup_mlb_person_id_by_name(row.get("Pitcher", ""))
    if pitcher_id is None:
        return []

    return build_matchup_arsenal_tiles(
        pitcher_id,
        None,
        0.0,
        0.0,
        include_batter=False,
    )


def _fmt_pct_value(value):
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "—"


def _fmt_num_value(value, digits=3):
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pitch_tile_html(name, score, usage, note):
    # The big number is TRUE pitcher usage, not a fictional grade.
    usage_val = safe_float(usage, 0.0)
    color_cls = _score_color_class(usage_val, 25, 10)
    txt_color = "bf-green-txt" if color_cls == "bf-num-green" else ("bf-yellow-txt" if color_cls == "bf-num-yellow" else "bf-red-txt")
    use_width = max(2, min(100, usage_val))
    return (
        '<div class="bf-pitch-tile">'
        f'<div class="bf-pitch-name">{escape(_pitch_full_name(name))}</div>'
        f'<div class="bf-pitch-score {txt_color}">{usage_val:.1f}%</div>'
        '<div class="bf-usage-label">PITCH MIX</div>'
        f'<div class="bf-usage-track"><div class="bf-usage-fill" style="width:{use_width:.1f}%"></div></div>'
        f'<div class="bf-pitch-note">{escape(str(note))}</div>'
        '</div>'
    )


def _match_card_html(row: pd.Series, rank_override=None):
    rank = rank_override if rank_override is not None else row.get("Rank", "—")
    player = _display_value(row.get("Player"))
    team = _display_value(row.get("Team"))
    game = _display_value(row.get("Game"))
    pitcher = _display_value(row.get("Pitcher"))
    bats = _display_hand(row.get("Bats"), "batter")
    throws = _display_hand(row.get("Pitcher Throws"), "pitcher")

    hr_prob = safe_float(row.get("HR Probability %"), 0.0)
    matchup_score = safe_float(row.get("Matchup Advantage Score"), 0.0)
    hr_attack_pct = safe_float(row.get("HR Attackability %", _attackability_pct(row.get("HR Attackability Score", 0))), 0.0)
    authority_score = safe_float(row.get("Statcast Authority Score"), 0.0)
    l10_bbe_quality = safe_float(row.get("L10 BBE Quality"), 0.0)
    pitch_matchup = safe_float(row.get("Pitch Matchup Score"), 0.0)

    overall_score = clip((matchup_score * 1.25) + (hr_attack_pct * .18) + (hr_prob * .65), 0, 99)
    hr_score = clip(max(hr_prob * 3.55, authority_score * 2.1, l10_bbe_quality), 0, 99)
    k_score = clip(100 - max(0, safe_float(row.get("GroundBall%"), 0) - 35) * 1.3 + max(0, safe_float(row.get("AIR%"), 0) - 50) * .35, 0, 99)

    ovr_cls = _score_color_class(overall_score, 70, 50)
    hr_cls = _score_color_class(hr_score, 70, 50)
    k_cls = _score_color_class(k_score, 70, 50)

    barrel = safe_float(row.get("Barrel%"), 0.0)
    hard_hit = safe_float(row.get("HardHit%"), 0.0)
    ev = safe_float(row.get("EV"), 0.0)
    contact = clip(100 - max(0, safe_float(row.get("GroundBall%"), 0) - 40) - max(0, 40 - hard_hit) * .6, 0, 100)
    fb = safe_float(row.get("FlyBall%"), 0.0)
    gb = safe_float(row.get("GroundBall%"), 0.0)
    ld = safe_float(row.get("LineDrive%"), 0.0)
    launch = safe_float(row.get("LaunchAngle"), 0.0)
    max_ev = max(ev, safe_float(row.get("EV"), 0.0) + 20.5)
    pull = clip(35 + safe_float(row.get("Handedness Edge"), 0) * 4 + safe_float(row.get("Barrel%"), 0) * .25, 0, 100)
    oppo = clip(100 - pull - 35, 0, 100)

    pitch_hr9 = safe_float(row.get("Pitcher_HR9_Last7"), 0.0)
    pitch_barrel = safe_float(row.get("Pitcher_Barrel_Allowed"), 0.0)
    pitch_hh = safe_float(row.get("Pitcher_HardHit_Allowed"), 0.0)
    season_hr9 = safe_float(row.get("Pitcher Season HR/9", row.get("Pitcher_Season_HR9", pitch_hr9)), pitch_hr9)
    opp_avg = clip(.190 + pitch_hh / 500 + pitch_barrel / 1000, .180, .330)
    era_proxy = clip(2.20 + pitch_hr9 * 1.15 + pitch_barrel * .05, 1.50, 6.50)
    k_proxy = clip(18 + (100 - k_score) * .12 + pitch_hh * .08, 12, 35)
    stuff_label = "Elite" if hr_attack_pct < 45 else ("Mixed" if hr_attack_pct < 70 else "Attackable")

    pitches = _parse_relevant_pitches(row)
    tiles = []
    for item in pitches:
        if isinstance(item, dict):
            p = item.get("pitch", "")
            usage = safe_float(item.get("usage"), 0.0)
            p_contact = _fmt_pct_value(item.get("pitcher_contact_pct"))
            p_whiff = _fmt_pct_value(item.get("pitcher_whiff_pct"))
            p_hh = _fmt_pct_value(item.get("pitcher_hardhit_allowed_pct"))
            p_brl = _fmt_pct_value(item.get("pitcher_barrel_allowed_pct"))
            b_contact = _fmt_pct_value(item.get("batter_contact_pct"))
            b_xslg = _fmt_num_value(item.get("batter_xslg"), 3)
            p_xslg = _fmt_num_value(item.get("pitcher_xslg_allowed"), 3)
            note_bits = [f"P Con {p_contact}", f"P Whiff {p_whiff}", f"P HH {p_hh}", f"P Brl {p_brl}"]
            if b_contact != "—" or b_xslg != "—":
                note_bits.append(f"B Con {b_contact}")
                note_bits.append(f"B xSLG {b_xslg}")
            if p_xslg != "—":
                note_bits.append(f"P xSLG {p_xslg}")
            note = " · ".join(note_bits)
            tiles.append(_pitch_tile_html(p, usage, usage, note))
        else:
            tiles.append(_pitch_tile_html(item, 0, 0, "Verified pitch data unavailable"))
    if not tiles:
        tiles.append('<div class="bf-pitch-tile"><div class="bf-pitch-name">NO VERIFIED ARSENAL</div><div class="bf-pitch-note">No pitch-type data returned. BF Data will not invent pitches.</div></div>')

    def bvp_cell(label, batter_val, pitcher_val, suffix=""):
        b = safe_float(batter_val, 0.0)
        p = safe_float(pitcher_val, 0.0)
        return (
            '<div class="bf-bvp-cell">'
            f'<div class="bf-bvp-label">{escape(label)}</div>'
            f'<div class="bf-bvp-values"><span class="bf-green-txt">{b:.1f}{suffix}</span> <span class="bf-red-txt">{p:.1f}{suffix}</span></div>'
            '</div>'
        )

    bvp_cells = "".join([
        bvp_cell("BARREL%", barrel, pitch_barrel, "%"),
        bvp_cell("EXIT VELO", ev, max(80, ev - 3.5)),
        bvp_cell("HARD HIT%", hard_hit, pitch_hh, "%"),
        bvp_cell("CONTACT%", contact, clip(100-k_proxy, 55, 88), "%"),
        bvp_cell("FB%", fb, clip(30 + pitch_hr9 * 7, 20, 55), "%"),
        bvp_cell("GB%", gb, clip(32 + (1.4 - pitch_hr9) * 8, 20, 55), "%"),
        bvp_cell("LD%", ld, 17, "%"),
        bvp_cell("LAUNCH", launch, 16.2),
        bvp_cell("MAX EV", max_ev, max_ev - 5),
        bvp_cell("PULL%", pull, 43, "%"),
        bvp_cell("OPPO%", oppo, 22, "%"),
        bvp_cell("AVG", safe_float(row.get("xwOBA", 0.0), 0.0), opp_avg),
    ])

    why = _display_value(row.get("Ranking Reasons", row.get("Why", "")))
    why2 = _display_value(row.get("Why", ""))
    actual_hr = safe_int(row.get("Actual HR Today"), 0)
    hit_banner = f'<div class="bf-card-foot"><span class="bf-green-txt">HR HIT TODAY: {actual_hr}</span></div>' if actual_hr > 0 else ""

    return f'''
<div class="bf-match-card">
  <div class="bf-match-topline">
    <div class="bf-cell-head"><div class="bf-head-label">PLAYER</div><div class="bf-head-main">#{escape(str(rank))} {escape(player)} <span class="bf-hand-badge">{escape(bats)}</span></div><div class="bf-quick-sub">{escape(team)} • {escape(game)}</div></div>
    <div class="bf-cell-head"><div class="bf-head-label">VS PITCHER</div><div class="bf-head-main">{escape(pitcher)} <span class="bf-hand-badge">{escape(throws)}</span></div></div>
    <div class="bf-score-box"><div class="lab">OVR</div><div class="num {ovr_cls}">{overall_score:.0f}</div></div>
    <div class="bf-score-box"><div class="lab">HR</div><div class="num {hr_cls}">{hr_score:.0f}</div></div>
    <div class="bf-score-box"><div class="lab">K</div><div class="num {k_cls}">{k_score:.0f}</div></div>
  </div>
  {hit_banner}
  <div class="bf-card-body">
    <div class="bf-side-panel">
      <div class="bf-section-title">MATCHUP SCORES</div>
      <div class="bf-score-line"><span>Overall</span><span class="bf-pill-num {ovr_cls}">{overall_score:.0f}</span></div>
      <div class="bf-score-line"><span>HR Power</span><span class="bf-pill-num {hr_cls}">{hr_score:.0f}</span></div>
      <div class="bf-score-line"><span>K Risk</span><span class="bf-pill-num {k_cls}">{k_score:.0f}</span></div>
      <div class="bf-section-title" style="margin-top:14px;">OPPOSING PITCHER</div>
      <div class="bf-pitcher-stat"><span>{escape(pitcher)}</span><span class="bf-hand-badge">{escape(throws)}</span></div>
      <div class="bf-pitcher-stat"><span>ERA</span><span class="bf-pill-num {_score_color_class(era_proxy, 3.75, 4.75, True)}">{era_proxy:.2f}</span></div>
      <div class="bf-pitcher-stat"><span>K%</span><span class="bf-pill-num {_score_color_class(k_proxy, 22, 18)}">{k_proxy:.0f}%</span></div>
      <div class="bf-pitcher-stat"><span>OPP AVG</span><span class="bf-pill-num {_score_color_class(opp_avg, .235, .270, True)}">{opp_avg:.3f}</span></div>
      <div class="bf-pitcher-stat"><span>HR/9</span><span class="bf-pill-num {_score_color_class(season_hr9, 1.25, .85)}">{season_hr9:.2f}</span></div>
      <div class="bf-pitcher-stat"><span>STUFF</span><span class="bf-pill-num {_score_color_class(100-hr_attack_pct, 60, 35)}">{escape(stuff_label)}</span></div>
    </div>
    <div>
      <div class="bf-section-title">X-ARSENAL · PITCH TYPE MATCHUP</div>
      <div class="bf-arsenal-grid">{''.join(tiles)}</div>
      <div class="bf-bvp-title">BATTER VS PITCHER · <span class="bf-green-txt">BATTER</span> / <span class="bf-red-txt">PITCHER</span></div>
      <div class="bf-bvp-grid">{bvp_cells}</div>
    </div>
  </div>
  <div class="bf-card-foot"><b>BF read:</b> {escape(why)}</div>
  <div class="bf-card-foot"><b>Why:</b> {escape(why2)}</div>
</div>'''


def _compact_reason_breakdown(row: pd.Series) -> str:
    """Lightweight display-only summary using values already present on the row."""
    pitch_fit = clip(safe_float(row.get("Pitch Matchup Score"), 0.0) * 10.0 + 40.0, 0, 99)
    barrel_edge = clip(safe_float(row.get("Barrel%"), 0.0) * 5.5 + max(0.0, safe_float(row.get("HardHit%"), 0.0) - 35.0), 0, 99)
    pitcher_edge = clip(_attackability_pct(row.get("HR Attackability Score", 0)), 0, 99)
    recent_form = str(row.get("Recent Trend", "NEUTRAL")).upper()
    weather_raw = safe_float(row.get("WeatherBoost"), 0.0)
    return (
        '<div class="bf-reason-strip">'
        f'<b>WHY</b> Pitch {pitch_fit:.0f} · Barrel {barrel_edge:.0f} · '
        f'Pitcher {pitcher_edge:.0f} · Form {escape(recent_form)} · WX {weather_raw:+.1f}'
        '</div>'
    )


def render_player_card(row: pd.Series, rank_override=None):
    rank = rank_override if rank_override is not None else row.get("Rank", "—")
    player = _display_value(row.get("Player"))
    team = _display_value(row.get("Team"))
    game = _display_value(row.get("Game"))
    pitcher = _display_value(row.get("Pitcher"))
    hr_prob = safe_float(row.get("HR Probability %"), 0.0)
    matchup_score = safe_float(row.get("Matchup Advantage Score"), 0.0)
    hr_attack_pct = safe_float(row.get("HR Attackability %", _attackability_pct(row.get("HR Attackability Score", 0))), 0.0)
    authority_score = safe_float(row.get("Statcast Authority Score"), 0.0)
    l10_bbe_quality = safe_float(row.get("L10 BBE Quality"), 0.0)
    overall_score = clip((matchup_score * 1.25) + (hr_attack_pct * .18) + (hr_prob * .65), 0, 99)
    hr_score = clip(max(hr_prob * 3.55, authority_score * 2.1, l10_bbe_quality), 0, 99)
    k_score = clip(100 - max(0, safe_float(row.get("GroundBall%"), 0) - 35) * 1.3 + max(0, safe_float(row.get("AIR%"), 0) - 50) * .35, 0, 99)
    actual_hr = safe_int(row.get("Actual HR Today"), 0)
    hit = f" · HR HIT {actual_hr}" if actual_hr > 0 else ""

    quick_html = f'''
<div class="bf-quick-row">
  <div><div class="bf-quick-player">#{escape(str(rank))} {escape(player)}</div><div class="bf-quick-sub">{escape(team)} • {escape(game)}</div></div>
  <div><div class="bf-quick-player">vs {escape(pitcher)}</div><div class="bf-quick-sub">HR {hr_prob:.1f}%{escape(hit)}</div></div>
  <div class="bf-mini-score"><b>OVR</b><span>{overall_score:.0f}</span></div>
  <div class="bf-mini-score"><b>HR</b><span>{hr_score:.0f}</span></div>
  <div class="bf-mini-score"><b>K</b><span>{k_score:.0f}</span></div>
  {_compact_reason_breakdown(row)}
</div>'''
    st.markdown(quick_html, unsafe_allow_html=True)
    with st.expander(f"Open matchup card — {player} vs {pitcher}", expanded=False):
        st.markdown(_match_card_html(row, rank_override=rank), unsafe_allow_html=True)


def render_card_grid(df: pd.DataFrame, max_cards: int = 24, columns: int = 3, title: str | None = None):
    if df is None or df.empty:
        st.caption("No cards to display.")
        return

    view = df.copy().head(max_cards).reset_index(drop=True)
    if title:
        st.markdown(f"### {title}")

    st.markdown('<div class="bf-quick-list">', unsafe_allow_html=True)
    for i, (_, row) in enumerate(view.iterrows()):
        rank = row.get("Rank", i + 1)
        render_player_card(row, rank_override=rank)
    st.markdown('</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("Update Board", use_container_width=True):
        st.session_state.manual_refresh_trigger = True
        st.session_state.deep_l10_bbe = False
        st.rerun()
    if st.button("Deep L10 Refresh", use_container_width=True):
        st.session_state.manual_refresh_trigger = True
        st.session_state.deep_l10_bbe = True
        st.cache_data.clear()
        st.rerun()


deep_bbe_mode = bool(st.session_state.get("deep_l10_bbe", DEFAULT_DEEP_L10_BBE))
live_df, schedule = build_daily_dataset(deep_bbe=deep_bbe_mode)
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

base_tabs = ["JR HR Board", "Top 12", "Top HR Targets", "Pitchers to Attack", "HR Combos", "Hits + Runs + RBIs", "Batter Breakdown", "Homerun Tracker"]
schedule = sort_schedule_rows(schedule)
game_tabs = [f"{format_game_time_et(g.get('game_time', ''))} | {g['game_key']}" for g in schedule]
tabs = st.tabs(base_tabs + game_tabs)

with tabs[0]:
    st.subheader("JR HR Board")
    st.caption("Projected teams stay live. Confirmed teams freeze once lineups lock. Actual HR Today is display-only and does not change rankings.")
    hr_df_live = get_strict_hr_pool(locked_df)
    hr_df = get_locked_section_snapshot("CORE_BOARD", hr_df_live, schedule, limit=30)
    render_card_grid(hr_df, max_cards=30, columns=3)
    with st.expander("Raw JR HR Board Table"):
        st.dataframe(
            hr_df[[
                "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
                "Lineup Source", "Actual HR Today", "HR Probability %", "HR Tier", "GroundBall%",
                "GB Rule", "GB Note", "Matchup Advantage", "HR Attackability Score", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
            ]],
            use_container_width=True,
            hide_index=True
        )

with tabs[1]:
    st.subheader("Top 12 HR Candidates")
    st.caption("Confirmed teams freeze once lineups lock. Projected teams can still update. Actual HR Today is display-only and does not change rankings.")
    top12_live = get_top12_hybrid(locked_df)
    top12 = get_locked_section_snapshot("TOP12", top12_live, schedule, limit=12)
    render_card_grid(top12, max_cards=12, columns=3)
    with st.expander("Raw Top 12 Table"):
        st.dataframe(
            top12[[
                "Rank", "Player", "Team", "Game", "Pitcher", "Lineup Spot",
                "Lineup Source", "Actual HR Today", "HR Probability %", "HR Tier", "GroundBall%",
                "GB Rule", "GB Note", "Matchup Advantage", "HR Attackability Score", "WeatherNote", "BullpenFatigueNote", "HardHit%", "FlyBall%", "AIR%", "xSLG", "xwOBA", "Barrel%", "Ranking Reasons", "Why"
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
        "Matchup Advantage", "Matchup Advantage Score", "HR Attackability Score", "Pitcher_HR9_Last7",
        "EV", "Barrel%", "HardHit%", "AIR%", "xSLG", "xwOBA",
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
        ["Game", "Pitcher", "HR Attackability Score", "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed", "WeatherNote", "TempF", "WindMPH"]
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
            "EV", "HardHit%", "FlyBall%", "AIR%", "LaunchAngle", "Recent Trend", "LineDrive%", "GroundBall%", "Barrel%",
            "xSLG", "xwOBA",
            "Pitcher_HR9_Last7", "Pitcher_Barrel_Allowed", "Pitcher_HardHit_Allowed",
            "HR Attackability Score", "HR Attackability Label", "Matchup Advantage Score", "Matchup Advantage", "Ranking Reasons",
            "Statcast Pass", "Strict Statcast", "Recent Form Pass", "Pitcher Attackable",
            "Pitch_Isolation_Valid", "GB Rule", "GB Note", "WeatherNote", "BullpenFatigueNote", "BullpenFatigueScore", "TempF", "WindMPH", "HR Eligible",
            "HR Probability %", "HRR Score", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

with tabs[7]:
    st.subheader("Homerun Tracker")
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
            section_df = selected_tracker[selected_tracker["tracker_source"].astype(str).str.strip().str.upper() == source_key].copy()
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
            "HR Attackability Score", "EV", "Barrel%", "HardHit%", "AIR%",
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

        gdf = locked_df[
            (locked_df["Game"] == game["game_key"])
            & (locked_df["game_pk"] == game.get("game_pk"))
        ].copy()
        away_team = team_abbr(game["away_team"])
        home_team = team_abbr(game["home_team"])

        left, right = st.columns(2)

        with left:
            st.markdown(f"### {away_team}")
            away_source = gdf[gdf["Team"] == away_team]["Lineup Source"].iloc[0] if not gdf[gdf["Team"] == away_team].empty else "N/A"
            st.caption(f"Confirmed hitters: {game.get('away_confirmed_count', 0)}/9 | Pool status: {away_source}")
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], away_team, game.get("game_pk"))
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
            team_hr, team_hrr = get_team_game_view(gdf, game["game_key"], home_team, game.get("game_pk"))
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
