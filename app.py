import hashlib
from datetime import datetime
import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="BF Data", layout="wide")

st.title("BF Data")
st.caption("Daily Home Run Probability Engine")

TRACKER_FILE = "hr_tracker.csv"


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        return pd.read_csv(TRACKER_FILE)
    return pd.DataFrame(columns=["date", "player", "team", "result"])


def save_tracker(df):
    df.to_csv(TRACKER_FILE, index=False)


def tracker_summary(df):
    if df.empty:
        return 0, 0, 0
    total = len(df)
    hits = df["result"].sum()
    pct = round((hits / total) * 100, 2)
    return total, hits, pct


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
    "ARI": 1.02, "ATL": 1.04, "BAL": 0.99, "BOS": 1.03,
    "CHC": 1.01, "CWS": 1.02, "CIN": 1.08, "CLE": 0.97,
    "COL": 1.20, "DET": 0.95, "HOU": 1.01, "KC": 0.96,
    "LAA": 0.99, "LAD": 1.01, "MIA": 0.94, "MIL": 1.03,
    "MIN": 1.00, "NYM": 0.98, "NYY": 1.05, "ATH": 0.93,
    "PHI": 1.06, "PIT": 0.95, "SD": 0.98, "SF": 0.92,
    "SEA": 0.95, "STL": 1.00, "TB": 0.97, "TEX": 1.07,
    "TOR": 1.04, "WSH": 1.00,
}


def stable_float(key, low, high):
    digest = hashlib.md5(key.encode()).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


def team_abbr(name):
    return TEAM_ABBR.get(name, name[:3].upper())


@st.cache_data(ttl=300)
def get_today_schedule():

    today = datetime.now().strftime("%Y-%m-%d")

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=probablePitcher"

    data = requests.get(url).json()

    games = []

    for d in data.get("dates", []):
        for g in d.get("games", []):

            away = g["teams"]["away"]["team"]["name"]
            home = g["teams"]["home"]["team"]["name"]

            away_pitcher = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "Starter Pending")
            home_pitcher = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "Starter Pending")

            games.append(dict(
                game_key=f"{team_abbr(away)} @ {team_abbr(home)}",
                away_team=away,
                home_team=home,
                away_pitcher=away_pitcher,
                home_pitcher=home_pitcher
            ))

    return games


schedule = get_today_schedule()

st.divider()

st.subheader("Accuracy Tracker")

tracker = load_tracker()

total, hits, pct = tracker_summary(tracker)

c1, c2, c3 = st.columns(3)

c1.metric("Tracked Picks", total)
c2.metric("Correct HR", hits)
c3.metric("Hit Rate %", pct)

st.divider()

tabs = st.tabs(["Accuracy Tracker"] + [g["game_key"] for g in schedule])

with tabs[0]:

    st.caption("Check Top-12 winners daily")

    example_players = ["Example Player A", "Example Player B"]

    results = []

    for player in example_players:

        result = st.checkbox(player)

        results.append(dict(
            date=datetime.today().date(),
            player=player,
            team="N/A",
            result=int(result)
        ))

    if st.button("Save Results"):
        tracker = pd.concat([tracker, pd.DataFrame(results)])
        save_tracker(tracker)
        st.success("Saved ✅")
