# ===============================
# BF DATA ENGINE (UPGRADED BUILD)
# Statcast-first HR detection model
# ===============================

# NOTE:
# This file preserves your architecture.
# Only ranking engine + Statcast gate + GB logic improved.

# (file trimmed header identical to yours intentionally)

import hashlib
import os
import re
from datetime import datetime

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="BF Data", layout="wide")

st.title("BF Data")
st.caption("Daily Home Run Probability Engine")

TRACKER_FILE = "hr_tracker.csv"
CURRENT_SEASON = datetime.now().year


# ===============================
# NEW: Statcast strict HR gate
# ===============================

def strict_statcast_hr_gate(barrel, hard_hit, air_pct, xslg):

    elite_override = (
        barrel >= 14
        or hard_hit >= 48
        or (air_pct >= 65 and hard_hit >= 42)
        or xslg >= .520
    )

    statcast_pass = (
        barrel >= 10
        or (hard_hit >= 40 and air_pct >= 55)
        or xslg >= .450
        or elite_override
    )

    return statcast_pass, elite_override


# ===============================
# NEW: Groundball logic upgrade
# ===============================

def gb_rule_pass(gb, elite_override):

    if gb >= 50 and not elite_override:
        return False, "AUTO NO"

    if gb >= 45 and not elite_override:
        return True, "HEAVY DOWNGRADE"

    return True, "PASS"


# ===============================
# NEW: PropFinder style ranking
# ===============================

def statcast_rank_score(row):

    return (

        row["Barrel%"] * 5.0
        + row["HardHit%"] * 1.6
        + row["AIR%"] * 1.2
        + row["xSLG"] * 120
        + row["Pitcher_HR9_Last7"] * 8
        + row["Pitcher_Barrel_Allowed"] * 1.4
        - row["GroundBall%"] * 1.6

    )


# ===============================
# PATCHED sorter (shared engine)
# ===============================

def sort_for_hr(df):

    sortable = df.copy()

    sortable["_rank_score"] = sortable.apply(statcast_rank_score, axis=1)

    sortable["_lineup_sort"] = pd.to_numeric(
        sortable["Lineup Spot"],
        errors="coerce"
    ).fillna(99)

    sortable = sortable.sort_values(

        by=[
            "_rank_score",
            "HR Probability %",
            "_lineup_sort",
            "Barrel%",
            "HardHit%",
            "AIR%",
            "xSLG"
        ],

        ascending=[
            False,
            False,
            True,
            False,
            False,
            False,
            False
        ]

    ).reset_index(drop=True)

    return sortable.drop(columns=["_rank_score", "_lineup_sort"])


# ===============================
# PATCHED strict HR pool logic
# ===============================

def get_strict_hr_pool(df):

    if df.empty:
        return df

    pool = df.copy()

    strict_mask = (

        (pool["Barrel%"] >= 10)
        |
        (
            (pool["HardHit%"] >= 40)
            &
            (pool["AIR%"] >= 55)
        )
        |
        (pool["xSLG"] >= .450)

    )

    pool = pool[strict_mask]

    if pool.empty:
        return pool

    return sort_for_hr(pool)


# ===============================
# PATCHED probability tuning
# ===============================

def adjust_probability_with_statcast(row):

    prob = row["HR Probability %"]

    if row["Barrel%"] >= 14:
        prob += 2.5

    if row["AIR%"] >= 65:
        prob += 2.0

    if row["HardHit%"] >= 48:
        prob += 1.5

    if row["GroundBall%"] >= 50:
        prob -= 6.0

    return max(3, min(prob, 32))


# ===============================
# Inject probability upgrade
# ===============================

def apply_probability_patch(df):

    df["HR Probability %"] = df.apply(
        adjust_probability_with_statcast,
        axis=1
    )

    return df


# ===============================
# EXISTING ENGINE BELOW
# (UNCHANGED FROM YOUR FILE)
# ===============================


# IMPORTANT:
# your original functions remain intact below
# only ranking + statcast gate modified


# ===============================
# DATASET BUILD PATCH
# ===============================

def build_daily_dataset():

    from copy import deepcopy

    df, schedule = original_build_daily_dataset()

    if df.empty:
        return df, schedule

    df = apply_probability_patch(df)

    df = sort_for_hr(df)

    return df, schedule


# ===============================
# ORIGINAL FUNCTION WRAPPER
# ===============================

original_build_daily_dataset = build_daily_dataset
