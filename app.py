import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# -----------------------------
# PAGE SETTINGS
# -----------------------------

st.set_page_config(
    page_title="BF Data",
    layout="wide"
)

st.title("BF Data")
st.caption("Daily Home Run Probability Engine")

# -----------------------------
# UPDATE BUTTON
# -----------------------------

if st.button("Update Board"):
    st.rerun()

# -----------------------------
# MLB SCHEDULE CONNECTOR
# -----------------------------

def get_today_games():

    try:
        url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1"
        data = requests.get(url).json()

        games = []

        for date in data["dates"]:
            for game in date["games"]:

                away = game["teams"]["away"]["team"]["name"]
                home = game["teams"]["home"]["team"]["name"]

                games.append(f"{away} @ {home}")

        return games

    except:

        return [
            "Tigers @ Cubs",
            "Dodgers @ Padres"
        ]

# -----------------------------
# SAMPLE HR ENGINE
# (temporary until Statcast layer plugs in)
# -----------------------------

def build_hr_board():

    players = [
        "Aaron Judge",
        "Shohei Ohtani",
        "Matt Olson",
        "Kyle Schwarber",
        "Pete Alonso",
        "Juan Soto",
        "Ronald Acuna",
        "Corey Seager"
    ]

    probabilities = [
        .24,
        .22,
        .20,
        .19,
        .18,
        .17,
        .16,
        .15
    ]

    df = pd.DataFrame({

        "Player": players,
        "HR Probability %": [round(x * 100,2) for x in probabilities]

    })

    return df.sort_values("HR Probability %", ascending=False)


# -----------------------------
# TABS
# -----------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "HR Probability",
    "Top 12",
    "Games",
    "Hits + Runs + RBIs"
])


# -----------------------------
# TAB 1
# -----------------------------

with tab1:

    st.subheader("HR Probability Board")

    df = build_hr_board()

    st.dataframe(df, use_container_width=True)


# -----------------------------
# TAB 2
# -----------------------------

with tab2:

    st.subheader("Top 12 HR Candidates")

    df = build_hr_board().head(12)

    st.dataframe(df, use_container_width=True)


# -----------------------------
# TAB 3
# -----------------------------

with tab3:

    st.subheader("Game Tabs")

    games = get_today_games()

    for game in games:

        with st.expander(game):

            st.write("Top hitters from this matchup will appear here")


# -----------------------------
# TAB 4
# -----------------------------

with tab4:

    st.subheader("Hits + Runs + RBIs Board")

    df = build_hr_board()

    df["HRR Score"] = df["HR Probability %"] * 1.35

    st.dataframe(df.sort_values("HRR Score", ascending=False))
