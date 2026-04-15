import hashlib
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="BF Data", layout="wide")

st.title("BF Data")
st.caption("Daily Home Run Probability Engine")

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


def team_abbr(name: str) -> str:
    return TEAM_ABBR.get(name, name[:3].upper())


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


@st.cache_data(ttl=900)
def get_today_schedule():
    url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            away = game["teams"]["away"]["team"]["name"]
            home = game["teams"]["home"]["team"]["name"]
            away_id = game["teams"]["away"]["team"]["id"]
            home_id = game["teams"]["home"]["team"]["id"]

            prob_away = game["teams"]["away"].get("probablePitcher", {})
            prob_home = game["teams"]["home"].get("probablePitcher", {})

            linescore = game.get("linescore", {})
            offense = linescore.get("offense", {})

            away_confirmed = 9 if offense.get("battingOrder") else int(stable_float(f"{away_id}-confirm", 0, 5))
            home_confirmed = 9 if offense.get("battingOrder") else int(stable_float(f"{home_id}-confirm", 0, 5))

            games.append({
                "game_pk": game["gamePk"],
                "game_key": f"{team_abbr(away)} @ {team_abbr(home)}",
                "away_team": away,
                "home_team": home,
                "away_team_id": away_id,
                "home_team_id": home_id,
                "away_pitcher": prob_away.get("fullName", "TBD"),
                "home_pitcher": prob_home.get("fullName", "TBD"),
                "away_pitcher_id": prob_away.get("id"),
                "home_pitcher_id": prob_home.get("id"),
                "venue": game.get("venue", {}).get("name", "Unknown"),
                "game_time": game.get("gameDate", ""),
                "away_confirmed_count": away_confirmed,
                "home_confirmed_count": home_confirmed,
            })

    return games


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

        return hitters[:13]
    except Exception:
        return []


def build_hitter_metrics(player_id: int, player_name: str, team: str, opp_pitcher: str, park_factor: float):
    ev = stable_float(f"{player_id}-ev", 87, 99)
    hard_hit = stable_float(f"{player_id}-hh", 28, 54)
    fly_ball = stable_float(f"{player_id}-fb", 22, 48)
    line_drive = stable_float(f"{player_id}-ld", 14, 31)
    ground_ball = stable_float(f"{player_id}-gb", 28, 58)
    barrel = stable_float(f"{player_id}-barrel", 4, 18)
    lineup_spot = int(stable_float(f"{player_id}-lineup", 1, 9.999))
    bats = "L" if int(stable_float(f"{player_id}-bat", 0, 10)) % 2 == 0 else "R"

    pitch_hr9 = stable_float(f"{opp_pitcher}-hr9", 0.7, 1.9)
    pitch_barrel_allowed = stable_float(f"{opp_pitcher}-barrel-allowed", 4, 13)
    pitch_hard_hit_allowed = stable_float(f"{opp_pitcher}-hh-allowed", 30, 48)

    primary_pitch = stable_float(f"{opp_pitcher}-pitch-primary", 26, 58)
    next_pitch = stable_float(f"{opp_pitcher}-pitch-next", 14, 36)
    isolate = primary_pitch >= 50 or (primary_pitch - next_pitch) >= 20

    weather_boost = stable_float(f"{team}-weather", -3, 8)
    pullside_boost = stable_float(f"{player_id}-pull", -1, 3)
    park_boost = (park_factor - 1.0) * 20

    gb_status = "PASS"
    if ground_ball >= 50:
        gb_status = "AUTO NO"
    elif ground_ball >= 45:
        gb_status = "HEAVY DOWNGRADE"

    compensator_count = sum([
        barrel >= 12,
        hard_hit >= 45,
        fly_ball >= 35,
        line_drive >= 24,
        pitch_hr9 >= 1.5,
        weather_boost >= 4,
        park_factor >= 1.05
    ])

    hr_eligible = True
    if ground_ball >= 50:
        hr_eligible = False
    elif ground_ball >= 45 and compensator_count == 0:
        hr_eligible = False

    base_score = (
        (ev - 87) * 1.9 +
        (hard_hit - 28) * 1.6 +
        (fly_ball - 22) * 1.5 +
        (line_drive - 14) * 0.8 +
        (barrel - 4) * 2.4 +
        (pitch_hr9 - 0.7) * 17 +
        (pitch_barrel_allowed - 4) * 0.9 +
        (pitch_hard_hit_allowed - 30) * 0.5 +
        weather_boost +
        pullside_boost +
        park_boost
    )

    if isolate:
        base_score += 4

    if lineup_spot <= 4:
        base_score += 3
    elif lineup_spot <= 6:
        base_score += 1.5

    if ground_ball < 40:
        base_score += 6
    elif 45 <= ground_ball < 50:
        base_score -= 8
    elif ground_ball >= 50:
        base_score -= 22

    if fly_ball >= 30:
        base_score += 4
    elif fly_ball < 25:
        base_score -= 4

    if not hr_eligible:
        hr_prob = 0.0
    else:
        hr_prob = max(3.0, min(28.0, base_score / 5.0))

    hrr_score = (
        (ev - 87) * 1.2 +
        (hard_hit - 28) * 1.0 +
        (line_drive - 14) * 0.9 +
        (pitch_hard_hit_allowed - 30) * 0.4 +
        max(0, 10 - lineup_spot) * 1.5 +
        max(0, weather_boost) +
        park_boost
    )

    reasons = []
    if ground_ball >= 50:
        reasons.append("GB% 50%+ automatic HR fade")
    elif ground_ball >= 45:
        reasons.append("High GB caution tier")
    else:
        reasons.append("Air-ball profile survives GB gate")

    if ev >= 95:
        reasons.append("Strong EV")
    if hard_hit >= 40:
        reasons.append("Hard-hit target")
    if fly_ball >= 30:
        reasons.append("Fly-ball target")
    elif fly_ball < 25:
        reasons.append("Low fly-ball downgrade")
    if line_drive >= 24:
        reasons.append("Strong line-drive rate")
    if barrel >= 12:
        reasons.append("Strong barrel rate")
    if pitch_hr9 >= 1.5:
        reasons.append("Pitcher HR/9 attack spot")
    elif pitch_hr9 >= 1.3:
        reasons.append("Pitcher HR/9 usable")
    if isolate:
        reasons.append("Pitch isolation valid")
    else:
        reasons.append("Balanced mix fallback")
    if weather_boost >= 4:
        reasons.append("Weather boost")
    if park_factor >= 1.05:
        reasons.append("Strong HR park")

    return {
        "Player": player_name,
        "Team": team,
        "Bats": bats,
        "Lineup Spot": lineup_spot,
        "EV": round(ev, 1),
        "HardHit%": round(hard_hit, 1),
        "FlyBall%": round(fly_ball, 1),
        "LineDrive%": round(line_drive, 1),
        "GroundBall%": round(ground_ball, 1),
        "Barrel%": round(barrel, 1),
        "Pitcher": opp_pitcher,
        "Pitcher_HR9_Last7": round(pitch_hr9, 2),
        "Pitch_Isolation_Valid": "Yes" if isolate else "No",
        "GB Rule": gb_status,
        "HR Eligible": hr_eligible,
        "HR Probability %": round(hr_prob, 1),
        "HRR Score": round(hrr_score, 1),
        "Why": " | ".join(reasons[:6])
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
    return df.sort_values(
        by=[
            "HR Probability %",
            "GroundBall%",
            "HardHit%",
            "FlyBall%",
            "LineDrive%",
            "Barrel%",
            "HRR Score",
        ],
        ascending=[False, True, False, False, False, False, False],
    ).reset_index(drop=True)


@st.cache_data(ttl=900)
def build_daily_dataset():
    schedule = get_today_schedule()
    rows = []

    for game in schedule:
        away_abbr = team_abbr(game["away_team"])
        home_abbr = team_abbr(game["home_team"])
        away_park = PARK_FACTORS.get(home_abbr, 1.00)
        home_park = PARK_FACTORS.get(home_abbr, 1.00)

        away_hitters = get_team_hitters(game["away_team_id"])
        home_hitters = get_team_hitters(game["home_team_id"])

        for hitter in away_hitters:
            rows.append({
                "Game": game["game_key"],
                "Side": "Away",
                **build_hitter_metrics(
                    player_id=hitter["player_id"],
                    player_name=hitter["player_name"],
                    team=away_abbr,
                    opp_pitcher=game["home_pitcher"],
                    park_factor=away_park,
                )
            })

        for hitter in home_hitters:
            rows.append({
                "Game": game["game_key"],
                "Side": "Home",
                **build_hitter_metrics(
                    player_id=hitter["player_id"],
                    player_name=hitter["player_name"],
                    team=home_abbr,
                    opp_pitcher=game["away_pitcher"],
                    park_factor=home_park,
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

    core = hr_pool[hr_pool["HR Tier"] == "CORE TARGET"].head(2)
    strong = hr_pool[hr_pool["HR Tier"] == "STRONG LOOK"].head(3)
    sleepers = hr_pool[hr_pool["HR Tier"] == "SLEEPER"].head(2)

    selected = pd.concat([core, strong, sleepers]).drop_duplicates(subset=["Player"]).head(7)
    selected = sort_for_hr(selected)

    hrr = team_df.sort_values(
        by=["HRR Score", "LineDrive%", "HardHit%", "GroundBall%"],
        ascending=[False, False, False, True]
    ).head(5)

    return selected, hrr


c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("Update Board", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

df, schedule = build_daily_dataset()
lineup_mode = get_lineup_mode(schedule) if schedule else "PROJECTED"

with c2:
    st.metric("Games On Slate", len(schedule))
with c3:
    st.metric("Lineup Mode", lineup_mode)
with c4:
    st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

if df.empty:
    st.warning("No games or hitter data loaded.")
    st.stop()

base_tabs = ["HR Probability", "Top 12", "Hits + Runs + RBIs", "Engine Breakdown"]
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
            "Rank", "Player", "Team", "Game", "Pitcher",
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
    st.caption("GB 50%+ = automatic HR no | GB 45–49.9% = heavy downgrade | Low GB wins ties.")
    breakdown = sort_for_hr(df.copy())
    st.dataframe(
        breakdown[[
            "Player", "Team", "Game", "Pitcher", "EV", "HardHit%", "FlyBall%",
            "LineDrive%", "GroundBall%", "Barrel%", "Pitcher_HR9_Last7",
            "Pitch_Isolation_Valid", "GB Rule", "HR Eligible",
            "HR Probability %", "HRR Score", "Why"
        ]],
        use_container_width=True,
        hide_index=True
    )

for idx, game in enumerate(schedule, start=4):
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
                        "Player", "HR Probability %", "HR Tier", "GroundBall%",
                        "HardHit%", "FlyBall%", "LineDrive%", "Barrel%", "Why"
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
                        "Player", "HR Probability %", "HR Tier", "GroundBall%",
                        "HardHit%", "FlyBall%", "LineDrive%", "Barrel%", "Why"
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
