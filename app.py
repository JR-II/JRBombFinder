import streamlit as st
import pandas as pd
import requests
import hashlib
from datetime import datetime

st.set_page_config(page_title="BF Data", layout="wide")

st.title("BF Data")
st.caption("Live MLB slate + roster engine | Contact-quality scoring layer (model-driven until Statcast integration)")

# -----------------------------
# TEAM ABBREVIATIONS
# -----------------------------

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
    "Washington Nationals": "WSH"
}

# -----------------------------
# STABLE FLOAT (MODEL SEED)
# -----------------------------

def stable_float(key, low, high):
    digest = hashlib.md5(key.encode()).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


# -----------------------------
# LIVE MLB SCHEDULE
# -----------------------------

@st.cache_data(ttl=600)
def get_schedule():

    url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1"

    data = requests.get(url).json()

    games = []

    for date in data.get("dates", []):

        for game in date.get("games", []):

            away = game["teams"]["away"]["team"]["name"]
            home = game["teams"]["home"]["team"]["name"]

            away_pitcher = game["teams"]["away"].get("probablePitcher", {}).get("fullName")
            home_pitcher = game["teams"]["home"].get("probablePitcher", {}).get("fullName")

            games.append({
                "game_key": f"{TEAM_ABBR.get(away, away[:3])} @ {TEAM_ABBR.get(home, home[:3])}",
                "away": away,
                "home": home,
                "away_pitcher": away_pitcher if away_pitcher else "Starter Pending",
                "home_pitcher": home_pitcher if home_pitcher else "Starter Pending",
                "away_id": game["teams"]["away"]["team"]["id"],
                "home_id": game["teams"]["home"]["team"]["id"]
            })

    return games


# -----------------------------
# LIVE TEAM ROSTER (HITTERS ONLY)
# -----------------------------

@st.cache_data(ttl=1800)
def get_hitters(team_id):

    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active"

    data = requests.get(url).json()

    hitters = []

    for player in data.get("roster", []):

        if player["position"]["type"] != "Pitcher":

            hitters.append(player["person"]["fullName"])

    return hitters[:13]


# -----------------------------
# HR ENGINE CORE MODEL
# -----------------------------

def build_metrics(player, pitcher):

    EV = stable_float(player, 88, 99)
    HardHit = stable_float(player + "hh", 30, 52)
    FlyBall = stable_float(player + "fb", 24, 44)
    LineDrive = stable_float(player + "ld", 18, 28)

    GroundBall = 100 - FlyBall - LineDrive

    Barrel = stable_float(player + "barrel", 5, 16)

    pitcher_hr9 = stable_float(pitcher, .9, 1.8)

    # -----------------------------
    # GB FILTER
    # -----------------------------

    if GroundBall >= 50:

        eligible = False
        gb_rule = "AUTO NO"

    elif GroundBall >= 45:

        eligible = Barrel >= 12 or HardHit >= 45
        gb_rule = "DOWNGRADE"

    else:

        eligible = True
        gb_rule = "PASS"

    # -----------------------------
    # SCORING ENGINE
    # -----------------------------

    score = (
        (EV - 88) * 1.6 +
        (HardHit - 30) * 1.5 +
        (FlyBall - 25) * 1.4 +
        (LineDrive - 18) * .9 +
        (Barrel - 5) * 2.2 +
        pitcher_hr9 * 12
    )

    if FlyBall >= 30:
        score += 4

    if GroundBall < 40:
        score += 5

    hr_prob = 0 if not eligible else min(28, max(4, score / 5))

    return {

        "EV": round(EV,1),
        "HardHit%": round(HardHit,1),
        "FlyBall%": round(FlyBall,1),
        "LineDrive%": round(LineDrive,1),
        "GroundBall%": round(GroundBall,1),
        "Barrel%": round(Barrel,1),

        "Pitcher_HR9_Last7": round(pitcher_hr9,2),

        "HR Eligible": eligible,
        "GB Rule": gb_rule,

        "HR Probability %": round(hr_prob,1)

    }


# -----------------------------
# BUILD DATASET
# -----------------------------

@st.cache_data(ttl=600)
def build_dataset():

    schedule = get_schedule()

    rows = []

    for game in schedule:

        away_hitters = get_hitters(game["away_id"])
        home_hitters = get_hitters(game["home_id"])

        for hitter in away_hitters:

            metrics = build_metrics(hitter, game["home_pitcher"])

            rows.append({

                "Player": hitter,
                "Team": TEAM_ABBR[game["away"]],
                "Game": game["game_key"],
                "Pitcher": game["home_pitcher"],

                **metrics

            })

        for hitter in home_hitters:

            metrics = build_metrics(hitter, game["away_pitcher"])

            rows.append({

                "Player": hitter,
                "Team": TEAM_ABBR[game["home"]],
                "Game": game["game_key"],
                "Pitcher": game["away_pitcher"],

                **metrics

            })

    df = pd.DataFrame(rows)

    df = df.sort_values(

        by=[

            "HR Probability %",
            "GroundBall%",
            "HardHit%",
            "FlyBall%",
            "LineDrive%",
            "Barrel%"

        ],

        ascending=[False, True, False, False, False, False]

    )

    return df, schedule


# -----------------------------
# LOAD DATA
# -----------------------------

df, schedule = build_dataset()

st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

# -----------------------------
# MAIN BOARD
# -----------------------------

st.subheader("HR Probability Board")

board = df[df["HR Eligible"]]

st.dataframe(

    board[

        [

            "Player",
            "Team",
            "Game",
            "Pitcher",
            "HR Probability %",
            "GroundBall%",
            "HardHit%",
            "FlyBall%",
            "LineDrive%",
            "Barrel%",
            "Pitcher_HR9_Last7",
            "GB Rule"

        ]

    ],

    use_container_width=True,
    hide_index=True

)
