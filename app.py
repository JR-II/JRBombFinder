# --- BF DATA STARTER RESOLVER UPGRADE BUILD ---
# replaces MLB-only starter logic with multi-source resolver

import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(layout="wide", page_title="BF Data")

st.title("BF Data")
st.caption("Live MLB slate + projection engine")

# -------------------------------
# STARTER RESOLVER ENGINE
# -------------------------------

@st.cache_data(ttl=600)
def get_probable_pitchers():

    today = datetime.today().strftime("%Y-%m-%d")

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=probablePitcher"

    r = requests.get(url)
    data = r.json()

    probable_map = {}

    for d in data.get("dates", []):
        for game in d.get("games", []):

            away_team = game["teams"]["away"]["team"]["name"]
            home_team = game["teams"]["home"]["team"]["name"]

            away_pitcher = game["teams"]["away"].get("probablePitcher")
            home_pitcher = game["teams"]["home"].get("probablePitcher")

            if away_pitcher:
                probable_map[away_team] = away_pitcher["fullName"]

            if home_pitcher:
                probable_map[home_team] = home_pitcher["fullName"]

    return probable_map


@st.cache_data(ttl=600)
def rotation_fallback(team_id):

    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active"

    r = requests.get(url)

    pitchers = []

    for p in r.json()["roster"]:
        if p["position"]["type"] == "Pitcher":
            pitchers.append(p["person"]["fullName"])

    if pitchers:
        return pitchers[0]

    return None


def resolve_starter(team_name, team_id, probable_map):

    if team_name in probable_map:
        return probable_map[team_name]

    fallback = rotation_fallback(team_id)

    if fallback:
        return fallback

    return "Starter Pending"


# -------------------------------
# SCHEDULE ENGINE
# -------------------------------

@st.cache_data(ttl=600)
def get_schedule():

    url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1"

    r = requests.get(url)

    data = r.json()

    probable_map = get_probable_pitchers()

    games = []

    for d in data.get("dates", []):

        for g in d.get("games", []):

            away_team = g["teams"]["away"]["team"]["name"]
            home_team = g["teams"]["home"]["team"]["name"]

            away_id = g["teams"]["away"]["team"]["id"]
            home_id = g["teams"]["home"]["team"]["id"]

            away_pitcher = resolve_starter(
                away_team,
                away_id,
                probable_map
            )

            home_pitcher = resolve_starter(
                home_team,
                home_id,
                probable_map
            )

            games.append(
                dict(
                    matchup=f"{away_team} @ {home_team}",
                    away_team=away_team,
                    home_team=home_team,
                    away_pitcher=away_pitcher,
                    home_pitcher=home_pitcher
                )
            )

    return games


schedule = get_schedule()

st.write("Last refresh:", datetime.now())

for game in schedule:

    st.subheader(game["matchup"])

    col1, col2 = st.columns(2)

    with col1:
        st.write("Away Starter:")
        st.success(game["away_pitcher"])

    with col2:
        st.write("Home Starter:")
        st.success(game["home_pitcher"])
