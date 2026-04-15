from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from config import APP_LAYOUT, APP_SUBTITLE, APP_TITLE, TIMEZONE
from data.schedule_data import get_today_schedule
from data.weather_data import get_weather_for_games
from data.park_data import get_park_factors
from data.lineup_data import get_lineups_for_slate, resolve_lineup_mode
from data.pitcher_data import get_pitchers_for_slate
from data.hitter_data import get_hitter_pool
from engine.environment_engine import score_environment
from engine.pitcher_engine import score_pitcher_vulnerability
from engine.hitter_engine import score_hitter_power, score_recent_form
from engine.split_engine import score_handedness_split
from engine.pitch_isolation import check_pitch_isolation_eligibility, score_pitch_match
from engine.hr_score_engine import calculate_final_hr_score, convert_hr_score_to_probability, assign_hr_tier, build_hr_reason_summary
from engine.hrrbi_engine import score_hrrbi_profile
from engine.longshot_engine import is_longshot_candidate
from engine.ranking_engine import build_hr_board, build_top12_board, build_hrrbi_board
from engine.game_tab_builder import build_game_tab_data
from tracking.history_store import save_daily_snapshot
from tracking.accuracy_tracker import build_accuracy_bundle
from utils.constants import CORE_TABS
from utils.formatting import format_percent


st.set_page_config(page_title=APP_TITLE, layout=APP_LAYOUT)


def load_styles() -> None:
    css_path = Path(__file__).resolve().parent / "assets" / "styles.css"
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def init_session_state() -> None:
    st.session_state.setdefault("board", None)


def build_daily_board() -> dict:
    schedule_df = get_today_schedule()
    weather_df = get_weather_for_games(schedule_df)
    park_df = get_park_factors()
    lineup_df = get_lineups_for_slate(schedule_df)
    pitcher_df = get_pitchers_for_slate(schedule_df)
    hitter_df = get_hitter_pool(schedule_df, lineup_df)

    games_df = schedule_df.merge(weather_df, on="game_key", how="left").merge(park_df, on="venue", how="left")
    games_df["park_hr_factor"] = games_df["park_hr_factor"].fillna(1.0)

    env_map: dict[str, dict] = {}
    for _, g in games_df.iterrows():
        env_score, env_grade, env_reason = score_environment(g)
        row = g.to_dict()
        row.update({"environment_score": env_score, "environment_grade": env_grade, "environment_reason": env_reason})
        env_map[g["game_key"]] = row

    scored_rows = []
    for _, hitter in hitter_df.iterrows():
        game = env_map[hitter["game_key"]]
        pitcher = pitcher_df[pitcher_df["team"] == hitter["opponent"]].iloc[0]
        hitter_power_score, gb_bonus, hitter_reason = score_hitter_power(hitter)
        pitcher_vulnerability_score, pitcher_reason = score_pitcher_vulnerability(pitcher)
        split_score, split_reason = score_handedness_split(hitter, pitcher)
        isolation_valid, isolated_pitch, isolation_reason = check_pitch_isolation_eligibility(pitcher["pitch_mix"])
        pitch_match_score, pitch_match_reason = score_pitch_match(hitter, pitcher, isolated_pitch if isolation_valid else None)
        lineup_context_score = max(35.0, 100.0 - (float(hitter["lineup_spot"]) - 1) * 10)
        recent_form_score = score_recent_form(hitter)
        component_scores = {
            "hitter_power": hitter_power_score,
            "pitcher_vulnerability": pitcher_vulnerability_score,
            "environment": game["environment_score"],
            "split": split_score,
            "pitch_match": pitch_match_score,
            "lineup_context": lineup_context_score,
            "recent_form": recent_form_score,
            "groundball_bonus": gb_bonus * 5,
        }
        final_hr_score = calculate_final_hr_score(component_scores)
        hr_probability = convert_hr_score_to_probability(final_hr_score)
        hr_tier = assign_hr_tier(hr_probability)
        hrrbi_score, hrrbi_confidence, hrrbi_reason = score_hrrbi_profile(hitter, pitcher, game["environment_score"])
        reason = build_hr_reason_summary([
            game["environment_reason"],
            pitcher_reason,
            hitter_reason,
            split_reason,
            isolation_reason,
            pitch_match_reason,
        ])
        row = {
            "date": game["date"],
            "game_key": hitter["game_key"],
            "team": hitter["team"],
            "opponent": hitter["opponent"],
            "player": hitter["player"],
            "pitcher": pitcher["pitcher"],
            "lineup_spot": hitter["lineup_spot"],
            "lineup_status": hitter["lineup_status"],
            "hitter_power_score": hitter_power_score,
            "groundball_bonus_score": gb_bonus,
            "pitcher_vulnerability_score": pitcher_vulnerability_score,
            "environment_score": game["environment_score"],
            "environment_grade": game["environment_grade"],
            "split_score": split_score,
            "pitch_match_score": pitch_match_score,
            "lineup_context_score": lineup_context_score,
            "recent_form_score": recent_form_score,
            "final_hr_score": final_hr_score,
            "hr_probability": hr_probability,
            "hr_tier": hr_tier,
            "hrrbi_score": hrrbi_score,
            "hrrbi_confidence": hrrbi_confidence,
            "why_summary": reason,
            "hrrbi_reason": hrrbi_reason,
            "environment_reason": game["environment_reason"],
            "isolation_reason": isolation_reason,
        }
        longshot_flag, longshot_reason = is_longshot_candidate(row)
        row["longshot_flag"] = longshot_flag
        row["longshot_reason"] = longshot_reason
        scored_rows.append(row)

    scored_df = pd.DataFrame(scored_rows)
    hr_board = build_hr_board(scored_df)
    top12 = build_top12_board(hr_board)
    hrrbi_board = build_hrrbi_board(scored_df)
    game_tabs = {}
    for _, game in games_df.iterrows():
        row = env_map[game["game_key"]]
        game_tabs[game["game_key"]] = build_game_tab_data(game["game_key"], hr_board, row)

    snapshot = {
        "top12": top12[["rank", "player", "team", "hr_probability", "hr_tier"]].to_dict("records"),
        "updated_at": datetime.now().isoformat(),
    }
    save_daily_snapshot(str(datetime.now().date()), snapshot)
    return {
        "meta": {
            "updated_at": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            "lineup_mode": resolve_lineup_mode(lineup_df),
            "games": int(len(games_df)),
            "timezone": TIMEZONE,
        },
        "hr_board": hr_board,
        "top12": top12,
        "hrrbi_board": hrrbi_board,
        "engine_breakdown": hr_board.copy(),
        "game_tabs": game_tabs,
        "accuracy": build_accuracy_bundle(),
    }


def refresh_board() -> None:
    st.session_state.board = build_daily_board()


def render_header(meta: dict) -> None:
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)
    st.markdown(
        f"<span class='metric-chip'>Updated: {meta['updated_at']}</span>"
        f"<span class='metric-chip'>Lineup Mode: {meta['lineup_mode']}</span>"
        f"<span class='metric-chip'>Games: {meta['games']}</span>"
        f"<span class='metric-chip'>Timezone: {meta['timezone']}</span>",
        unsafe_allow_html=True,
    )


def render_hr_probability_tab(df: pd.DataFrame) -> None:
    show = df[["rank", "player", "team", "opponent", "pitcher", "lineup_spot", "lineup_status", "hr_probability", "hr_tier", "longshot_flag", "why_summary"]].copy()
    show["hr_probability"] = show["hr_probability"].map(format_percent)
    show = show.rename(columns={"hr_probability": "HR %", "hr_tier": "Tier", "lineup_spot": "Spot", "lineup_status": "Status", "longshot_flag": "Long Shot", "why_summary": "Why"})
    st.dataframe(show, use_container_width=True, hide_index=True)


def render_top12_tab(df: pd.DataFrame) -> None:
    cols = st.columns(3)
    for idx, (_, row) in enumerate(df.iterrows()):
        with cols[idx % 3]:
            st.markdown(f"**#{int(row['rank'])} {row['player']}**")
            st.write(f"{row['team']} vs {row['pitcher']}")
            st.write(f"HR %: {format_percent(row['hr_probability'])}")
            st.write(f"Tier: {row['hr_tier']}")
            st.caption(row['why_summary'][:180] + ("..." if len(row['why_summary']) > 180 else ""))
            st.markdown("---")


def render_hrrbi_tab(df: pd.DataFrame) -> None:
    show = df[["rank", "player", "team", "opponent", "lineup_spot", "hrrbi_score", "hrrbi_confidence", "hrrbi_reason"]].copy()
    show = show.rename(columns={"lineup_spot": "Spot", "hrrbi_score": "H+R+RBI Score", "hrrbi_confidence": "Confidence", "hrrbi_reason": "Why"})
    st.dataframe(show, use_container_width=True, hide_index=True)


def render_engine_breakdown_tab(df: pd.DataFrame) -> None:
    show = df[["player", "team", "hitter_power_score", "groundball_bonus_score", "pitcher_vulnerability_score", "environment_score", "split_score", "pitch_match_score", "lineup_context_score", "recent_form_score", "final_hr_score", "isolation_reason", "why_summary"]].copy()
    st.dataframe(show, use_container_width=True, hide_index=True)


def render_accuracy_tracker_tab(bundle: dict) -> None:
    metrics = bundle["metrics"]
    cols = st.columns(4)
    for i, (k, v) in enumerate(metrics.items()):
        cols[i].metric(k, v)
    if not bundle["log"].empty:
        st.dataframe(bundle["log"], use_container_width=True, hide_index=True)
    else:
        st.info("Accuracy history will populate as daily snapshots are logged.")


def _render_team_section(team: str, bundle: dict) -> None:
    st.subheader(team)
    for row in bundle["hr_main"]:
        st.markdown(f"**#{row['player']} — {format_percent(row['hr_probability'])}**")
        st.caption(row["hr_tier"])
        st.write(row["why_summary"][:240] + ("..." if len(row["why_summary"]) > 240 else ""))
    for row in bundle["hr_longshots"]:
        st.markdown(f"🎯 **Long Shot: {row['player']} — {format_percent(row['hr_probability'])}**")
        st.caption(row["longshot_reason"])
    st.markdown("**Best Hits + Runs + RBIs**")
    for row in bundle["hrrbi"]:
        st.write(f"- {row['player']} ({row['hrrbi_confidence']})")


def render_game_tab(game_key: str, game_data: dict) -> None:
    header = game_data["header"]
    st.subheader(game_key)
    st.caption(f"{header['start_time']} • {header['venue']} • {header['environment_grade']}")
    st.write(f"Weather: {header['temperature']}° | Wind: {header['wind_speed']} mph {header['wind_direction']} | Roof: {header['roof_status']}")
    cols = st.columns(2)
    away, home = game_data["teams"]
    with cols[0]:
        _render_team_section(away, game_data[away])
    with cols[1]:
        _render_team_section(home, game_data[home])
    st.markdown("**Quick matchup notes**")
    for note in game_data["notes"]:
        st.write(f"- {note}")


def main() -> None:
    load_styles()
    init_session_state()
    if st.session_state.board is None:
        refresh_board()
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("Update Board", use_container_width=True):
            refresh_board()
    with c2:
        render_header(st.session_state.board["meta"])
    board = st.session_state.board
    tab_names = CORE_TABS + list(board["game_tabs"].keys())
    tabs = st.tabs(tab_names)
    with tabs[0]:
        render_hr_probability_tab(board["hr_board"])
    with tabs[1]:
        render_top12_tab(board["top12"])
    with tabs[2]:
        render_hrrbi_tab(board["hrrbi_board"])
    with tabs[3]:
        render_engine_breakdown_tab(board["engine_breakdown"])
    with tabs[4]:
        render_accuracy_tracker_tab(board["accuracy"])
    for idx, game_key in enumerate(board["game_tabs"].keys(), start=5):
        with tabs[idx]:
            render_game_tab(game_key, board["game_tabs"][game_key])


if __name__ == "__main__":
    main()
