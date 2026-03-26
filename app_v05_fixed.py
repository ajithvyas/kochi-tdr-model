import streamlit as st
import pandas as pd
import altair as alt
import glob
import re
from pathlib import Path

# -------------------------
# PAGE SETUP
# -------------------------
st.set_page_config(page_title="Kochi TDR Policy Sandbox v05", layout="wide", page_icon="🏗️")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap');

        .block-container {
            padding-top: 1.0rem;
            padding-bottom: 0.5rem;
            max-width: 1500px;
        }

        section[data-testid="stSidebar"] {
            width: 290px !important;
            min-width: 290px !important;
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
        }

        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown h1,
        section[data-testid="stSidebar"] .stMarkdown h2,
        section[data-testid="stSidebar"] .stMarkdown h3,
        section[data-testid="stSidebar"] .stMarkdown h4,
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] span {
            color: #e8ecf3 !important;
        }

        section[data-testid="stSidebar"] .stCaption {
            color: #c9d3e6 !important;
            opacity: 1 !important;
        }

        h1, h2, h3 {
            font-family: 'DM Sans', sans-serif !important;
        }

        h1 {
            font-size: 2.55rem !important;
            line-height: 1.1 !important;
        }

        h2 {
            font-size: 2.0rem !important;
        }

        h3 {
            font-size: 1.55rem !important;
        }

        .stMetric label {
            font-family: 'Space Mono', monospace !important;
            font-size: 0.72rem !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .stMetric [data-testid="stMetricValue"] {
            font-family: 'DM Sans', sans-serif !important;
            font-weight: 700 !important;
        }

        div[data-testid="stExpander"] {
            border: 1px solid #e0e0e0;
            border-radius: 6px;
        }

        .soft-note {
            background: #f6f8fb;
            border: 1px solid #dbe4f0;
            border-radius: 8px;
            padding: 0.75rem 0.95rem;
            margin: 0.35rem 0 0.75rem 0;
            color: #334155;
            font-size: 0.95rem;
        }
    </style>
""", unsafe_allow_html=True)

# -------------------------
# HELPERS
# -------------------------

# IMPORTANT:
# Update these three lists to match your BehaviorSpace values exactly.
# The app will then adapt automatically to 3, 4, 5, or more levels.
PRICE_LEVELS = [1800, 2225, 2650, 3075, 3500]
GREEN_LEVELS = [2.5, 3.0, 3.5, 4.0]
TOD_LEVELS = [1.3, 1.5375, 1.775]

EXPECTED_RUNS = len(PRICE_LEVELS) * len(GREEN_LEVELS) * len(TOD_LEVELS)


def nearest_value(value, allowed):
    return min(allowed, key=lambda x: abs(x - value))


def safe_int(value, default=0):
    if pd.isna(value):
        return default
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def safe_delta(a, b):
    if pd.isna(a) or pd.isna(b):
        return None
    try:
        return safe_int(float(a) - float(b))
    except (TypeError, ValueError):
        return None


def safe_float_text(value, decimals=3, default='NA'):
    if pd.isna(value):
        return default
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return default


def run_id_from_params(price, green_p, tod_p):
    """Map 3 parameters to a sequential run ID using dynamic grid sizes."""
    p = nearest_value(price, PRICE_LEVELS)
    g = nearest_value(green_p, GREEN_LEVELS)
    t = nearest_value(tod_p, TOD_LEVELS)

    pi = PRICE_LEVELS.index(p)
    gi = GREEN_LEVELS.index(g)
    ti = TOD_LEVELS.index(t)

    # BehaviorSpace sequential: outer loop = price, middle = green, inner = tod
    run_id = ((pi * len(GREEN_LEVELS) + gi) * len(TOD_LEVELS)) + ti + 1
    return run_id, p, g, t


def params_from_run_id(run_id):
    idx = run_id - 1
    green_count = len(GREEN_LEVELS)
    tod_count = len(TOD_LEVELS)
    block = green_count * tod_count

    pi = idx // block
    rem = idx % block
    gi = rem // tod_count
    ti = rem % tod_count

    if pi < len(PRICE_LEVELS) and gi < len(GREEN_LEVELS) and ti < len(TOD_LEVELS):
        return PRICE_LEVELS[pi], GREEN_LEVELS[gi], TOD_LEVELS[ti]
    return None, None, None


@st.cache_data
def load_all_runs():
    """Load all KOCHI_v05_runN.csv files."""
    files = glob.glob("KOCHI_v05_run*.csv")
    data = {}

    for f in files:
        name = Path(f).name
        m = re.search(r"KOCHI_v05_run(\d+)\.csv", name)
        if m:
            run_id = int(m.group(1))
            df = pd.read_csv(f)
            df.columns = [c.strip() for c in df.columns]

            numeric_cols = [
                "tick", "total-developed", "total-transfers",
                "mean-density", "green-areas-protected",
                "heritage-areas-protected", "total-incentives-paid",
                "tdr-price", "developed-count", "conserved-count",
                "west-developed-count", "mean-land-value-receiving",
                "tdr-efficiency-ratio"
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            data[run_id] = df

    return data


def final_metrics(df):
    final = df.iloc[-1]
    return {
        "green": final.get("green-areas-protected", 0),
        "heritage": final.get("heritage-areas-protected", 0),
        "development": final.get("total-developed", 0),
        "transfers": final.get("total-transfers", 0),
        "density": final.get("mean-density", 0),
        "west_dev": final.get("west-developed-count", 0),
        "mean_lv": final.get("mean-land-value-receiving", 0),
        "tdr_eff": final.get("tdr-efficiency-ratio", 0),
        "incentives": final.get("total-incentives-paid", 0),
        "tdr_price": final.get("tdr-price", 0),
    }


def build_line_chart(df, y_col, title, color="#0f4c81", height=210):
    chart_df = df[["tick", y_col]].copy()
    chart = (
        alt.Chart(chart_df)
        .mark_area(
            line={"color": color, "strokeWidth": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color=color, offset=0),
                    alt.GradientStop(color="rgba(255,255,255,0)", offset=1),
                ],
                x1=0, x2=0, y1=0, y2=1,
            ),
            opacity=0.25,
        )
        .encode(
            x=alt.X("tick:Q", title="Tick"),
            y=alt.Y(f"{y_col}:Q", title=None),
            tooltip=["tick", y_col],
        )
        .properties(title=title, height=height)
    )
    line = (
        alt.Chart(chart_df)
        .mark_line(color=color, strokeWidth=2)
        .encode(
            x="tick:Q",
            y=f"{y_col}:Q",
        )
    )
    return chart + line


def build_compare_chart(df1, df2, y_col, title, label1, label2, height=210):
    a = df1[["tick", y_col]].copy()
    a["Scenario"] = label1
    b = df2[["tick", y_col]].copy()
    b["Scenario"] = label2
    merged = pd.concat([a, b], ignore_index=True)

    chart = (
        alt.Chart(merged)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("tick:Q", title="Tick"),
            y=alt.Y(f"{y_col}:Q", title=None),
            color=alt.Color("Scenario:N", title="Scenario",
                            scale=alt.Scale(range=["#0f4c81", "#e63946"])),
            strokeDash=alt.StrokeDash("Scenario:N"),
            tooltip=["tick", y_col, "Scenario"],
        )
        .properties(title=title, height=height)
    )
    return chart


# -------------------------
# LOAD DATA
# -------------------------
all_runs = load_all_runs()

# -------------------------
# HEADER
# -------------------------
st.markdown("# 🏗️ Kochi TDR Policy Sandbox")
st.markdown(
    f"<div style='margin-top:-6px; margin-bottom:16px; color:#6b7280; font-size:1.0rem;'>"
    f"Interactive exploration of TDR dynamics · v05 · {EXPECTED_RUNS}-run BehaviorSpace sweep over "
    f"<b>tdr-base-price</b> × <b>green-premium</b> × <b>tod-premium</b>"
    f"</div>",
    unsafe_allow_html=True,
)

if len(all_runs) != EXPECTED_RUNS:
    st.warning(
        f"The app is currently configured for {EXPECTED_RUNS} runs, but {len(all_runs)} run files were found. "
        "This is fine only if your level lists above have not yet been updated to match the new BehaviorSpace sweep."
    )

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.markdown("### 🎛️ Policy Controls")

comparison_mode = st.sidebar.checkbox("Enable Comparison Mode", value=False)

st.sidebar.markdown("#### Primary Scenario")
tdr_price = st.sidebar.select_slider(
    "TDR Base Price (₹/sqm FAR)",
    options=PRICE_LEVELS,
    value=PRICE_LEVELS[min(1, len(PRICE_LEVELS)-1)],
)
green_prem = st.sidebar.select_slider(
    "Green Premium",
    options=GREEN_LEVELS,
    value=GREEN_LEVELS[min(1, len(GREEN_LEVELS)-1)],
)
tod_prem = st.sidebar.select_slider(
    "TOD Premium",
    options=TOD_LEVELS,
    value=TOD_LEVELS[min(1, len(TOD_LEVELS)-1)],
)

primary_run_id, p_price, p_green, p_tod = run_id_from_params(tdr_price, green_prem, tod_prem)
primary_df = all_runs.get(primary_run_id)

if comparison_mode:
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Comparison Scenario")
    comp_price = st.sidebar.select_slider(
        "Comp. TDR Base Price",
        options=PRICE_LEVELS,
        value=PRICE_LEVELS[-1],
    )
    comp_green = st.sidebar.select_slider(
        "Comp. Green Premium",
        options=GREEN_LEVELS,
        value=GREEN_LEVELS[-1],
    )
    comp_tod = st.sidebar.select_slider(
        "Comp. TOD Premium",
        options=TOD_LEVELS,
        value=TOD_LEVELS[min(1, len(TOD_LEVELS)-1)] if len(TOD_LEVELS) > 1 else TOD_LEVELS[0],
    )
    comp_run_id, c_price, c_green, c_tod = run_id_from_params(comp_price, comp_green, comp_tod)
    comp_df = all_runs.get(comp_run_id)
else:
    comp_df = None
    comp_run_id = None
    c_price = c_green = c_tod = None

st.sidebar.markdown("---")
st.sidebar.markdown("#### Fixed Parameters")
st.sidebar.caption("These remain constant across the current BehaviorSpace sweep")
fixed_params = {
    "Heritage Premium": "1.75",
    "Corridor Premium": "1.6",
    "Number of Developers": "81",
    "Flood Friction": "0.4",
    "Incentive Per Unit": "1.5",
}
for k, v in fixed_params.items():
    st.sidebar.markdown(f"**{k}**: `{v}`")

# -------------------------
# SAFETY CHECK
# -------------------------
if primary_df is None:
    st.error(
        f"Run file for primary scenario not found (expected KOCHI_v05_run{primary_run_id}.csv). "
        f"Please ensure the BehaviorSpace output files are in the working directory."
    )
    st.info(f"Available runs: {sorted(all_runs.keys()) if all_runs else 'None found'}")
    st.stop()

if comparison_mode and comp_df is None:
    st.error(
        f"Run file for comparison scenario not found (expected KOCHI_v05_run{comp_run_id}.csv)."
    )
    st.stop()

# -------------------------
# METRICS
# -------------------------
pm = final_metrics(primary_df)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Green Protected", safe_int(pm["green"]))
m2.metric("Heritage Protected", safe_int(pm["heritage"]))
m3.metric("Total Development", safe_int(pm["development"]))
m4.metric("TDR Transfers", safe_int(pm["transfers"]))
m5.metric("West Kochi Dev", safe_int(pm["west_dev"]))
m6.metric("TDR Efficiency", safe_float_text(pm["tdr_eff"], decimals=3))

if comparison_mode:
    cm = final_metrics(comp_df)
    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("Green (Comp)", safe_int(cm["green"]), delta=safe_delta(cm["green"], pm["green"]))
    d2.metric("Heritage (Comp)", safe_int(cm["heritage"]), delta=safe_delta(cm["heritage"], pm["heritage"]))
    d3.metric("Development (Comp)", safe_int(cm["development"]), delta=safe_delta(cm["development"], pm["development"]))
    d4.metric("Transfers (Comp)", safe_int(cm["transfers"]), delta=safe_delta(cm["transfers"], pm["transfers"]))
    d5.metric("West Dev (Comp)", safe_int(cm["west_dev"]), delta=safe_delta(cm["west_dev"], pm["west_dev"]))
    d6.metric("TDR Eff (Comp)", safe_float_text(cm["tdr_eff"], decimals=3))

# -------------------------
# INSIGHT
# -------------------------
st.markdown("### Policy Insight")

if pm["transfers"] > 1200 and pm["green"] == 0:
    st.warning(
        "⚠️ Transfer activity is strong, but green-area protection remains absent. "
        "The green premium may be too low to incentivize conservation."
    )
elif pm["heritage"] > pm["green"] * 2 and pm["heritage"] > 5:
    st.info(
        "🏛️ Heritage protection is outpacing green conservation significantly. "
        "Consider raising the green premium to balance the policy."
    )
elif pm["west_dev"] > 10 and pm["development"] > 100:
    st.success(
        "🌊 West Kochi (Thoppumpady / Mattancherry) is seeing development activity. "
        "The receiving-tertiary zone and road connections are working."
    )
elif pm["development"] > 500 and pm["transfers"] > 1000:
    st.success(
        "🏗️ Strong development momentum with high transfer activity — the TDR market is active."
    )
elif pm["tdr_eff"] > 0.5:
    st.success(
        "✅ High TDR efficiency — each transfer is effectively generating conservation outcomes."
    )
else:
    st.info(
        "📊 Moderate system response. Development and protection are evolving together over time."
    )

# -------------------------
# CORE DYNAMICS
# -------------------------
st.markdown("### Core Dynamics")

primary_label = f"Run {primary_run_id} | ₹{p_price} | G={p_green} | TOD={p_tod}"
if comparison_mode:
    comp_label = f"Run {comp_run_id} | ₹{c_price} | G={c_green} | TOD={c_tod}"

c1, c2 = st.columns(2)

with c1:
    if comparison_mode:
        st.altair_chart(
            build_compare_chart(primary_df, comp_df, "mean-density",
                                "Mean Density Over Time", primary_label, comp_label),
            use_container_width=True,
        )
    else:
        st.altair_chart(
            build_line_chart(primary_df, "mean-density", "Mean Density Over Time"),
            use_container_width=True,
        )

with c2:
    if comparison_mode:
        st.altair_chart(
            build_compare_chart(primary_df, comp_df, "total-developed",
                                "Total Development", primary_label, comp_label),
            use_container_width=True,
        )
    else:
        st.altair_chart(
            build_line_chart(primary_df, "total-developed", "Total Development", color="#2a9d8f"),
            use_container_width=True,
        )

# -------------------------
# TRANSFER & PROTECTION
# -------------------------
st.markdown("### Transfer & Protection Dynamics")

c3, c4 = st.columns(2)

with c3:
    if comparison_mode:
        st.altair_chart(
            build_compare_chart(primary_df, comp_df, "total-transfers",
                                "TDR Transfers Over Time", primary_label, comp_label),
            use_container_width=True,
        )
    else:
        st.altair_chart(
            build_line_chart(primary_df, "total-transfers", "TDR Transfers Over Time", color="#e76f51"),
            use_container_width=True,
        )

with c4:
    if comparison_mode:
        p1 = primary_df[["tick", "green-areas-protected"]].copy()
        p1 = p1.rename(columns={"green-areas-protected": "value"})
        p1["Scenario"] = primary_label
        p1["Metric"] = "Green"

        p2 = primary_df[["tick", "heritage-areas-protected"]].copy()
        p2 = p2.rename(columns={"heritage-areas-protected": "value"})
        p2["Scenario"] = primary_label
        p2["Metric"] = "Heritage"

        q1 = comp_df[["tick", "green-areas-protected"]].copy()
        q1 = q1.rename(columns={"green-areas-protected": "value"})
        q1["Scenario"] = comp_label
        q1["Metric"] = "Green"

        q2 = comp_df[["tick", "heritage-areas-protected"]].copy()
        q2 = q2.rename(columns={"heritage-areas-protected": "value"})
        q2["Scenario"] = comp_label
        q2["Metric"] = "Heritage"

        protected_df = pd.concat([p1, p2, q1, q2], ignore_index=True)

        chart = (
            alt.Chart(protected_df)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X("tick:Q", title="Tick"),
                y=alt.Y("value:Q", title=None),
                color=alt.Color("Scenario:N", title="Scenario",
                                scale=alt.Scale(range=["#0f4c81", "#e63946"])),
                strokeDash=alt.StrokeDash("Metric:N", title="Protected Type"),
                tooltip=["tick", "value", "Scenario", "Metric"],
            )
            .properties(title="Protected Areas Over Time", height=210)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        p1 = primary_df[["tick", "green-areas-protected"]].copy()
        p1 = p1.rename(columns={"green-areas-protected": "value"})
        p1["Protected Type"] = "Green"

        p2 = primary_df[["tick", "heritage-areas-protected"]].copy()
        p2 = p2.rename(columns={"heritage-areas-protected": "value"})
        p2["Protected Type"] = "Heritage"

        protected_df = pd.concat([p1, p2], ignore_index=True)

        chart = (
            alt.Chart(protected_df)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X("tick:Q", title="Tick"),
                y=alt.Y("value:Q", title=None),
                color=alt.Color("Protected Type:N", title="Type",
                                scale=alt.Scale(range=["#2a9d8f", "#e9c46a"])),
                tooltip=["tick", "value", "Protected Type"],
            )
            .properties(title="Protected Areas Over Time", height=210)
        )
        st.altair_chart(chart, use_container_width=True)

# -------------------------
# v05 NEW: WEST KOCHI & ECONOMIC
# -------------------------
st.markdown("### West Kochi & Economic Indicators")

c5, c6 = st.columns(2)

with c5:
    if "west-developed-count" in primary_df.columns:
        if comparison_mode:
            st.altair_chart(
                build_compare_chart(primary_df, comp_df, "west-developed-count",
                                    "West Kochi Development", primary_label, comp_label),
                use_container_width=True,
            )
        else:
            st.altair_chart(
                build_line_chart(primary_df, "west-developed-count",
                                "West Kochi Development (Thoppumpady + Mattancherry)", color="#264653"),
                use_container_width=True,
            )
    else:
        st.info("West Kochi development data not available in this run.")

with c6:
    if "tdr-price" in primary_df.columns:
        if comparison_mode:
            st.altair_chart(
                build_compare_chart(primary_df, comp_df, "tdr-price",
                                    "Dynamic TDR Price (₹)", primary_label, comp_label),
                use_container_width=True,
            )
        else:
            st.altair_chart(
                build_line_chart(primary_df, "tdr-price", "Dynamic TDR Price (₹)", color="#f4a261"),
                use_container_width=True,
            )
    else:
        st.info("TDR price data not available in this run.")

# -------------------------
# POLICY HEATMAP
# -------------------------
if len(all_runs) >= min(9, EXPECTED_RUNS):
    st.markdown("### 📊 Policy Sensitivity Heatmap")
    st.caption(f"Final-tick metrics across the configured {EXPECTED_RUNS}-run policy grid")
    st.markdown(
        "<div class='soft-note'><b>How to read this:</b> each small box is one policy combination. "
        "Rows are <b>TDR Base Price</b>, columns are <b>Green Premium</b>, and each separate panel is a different <b>TOD Premium</b>. "
        "Darker-to-lighter color shows lower-to-higher values for the selected outcome metric.</div>",
        unsafe_allow_html=True,
    )

    heatmap_metric = st.selectbox(
        "Metric to visualize",
        [
            "total-developed", "total-transfers", "green-areas-protected",
            "heritage-areas-protected", "mean-density", "west-developed-count",
            "tdr-efficiency-ratio", "total-incentives-paid",
        ],
        index=0,
    )

    rows = []
    for rid, rdf in all_runs.items():
        if len(rdf) == 0:
            continue

        rp, rg, rt = params_from_run_id(rid)
        if rp is not None:
            final_row = rdf.iloc[-1]
            val = final_row.get(heatmap_metric, 0)
            rows.append({
                "tdr_price": rp,
                "green_premium": rg,
                "tod_premium": rt,
                "value": val,
                "run_id": rid,
            })

    if rows:
        hm_df = pd.DataFrame(rows)

        heat = (
            alt.Chart(hm_df)
            .mark_rect(cornerRadius=3)
            .encode(
                x=alt.X("green_premium:O", title="Green Premium"),
                y=alt.Y("tdr_price:O", title="TDR Price (₹)", sort="descending"),
                color=alt.Color("value:Q", title=heatmap_metric,
                                scale=alt.Scale(scheme="viridis")),
                tooltip=["run_id", "tdr_price", "green_premium", "tod_premium", "value"],
            )
            .facet(
                column=alt.Column("tod_premium:O", title="TOD Premium"),
            )
            .properties(title=f"{heatmap_metric} across policy grid")
        )
        st.altair_chart(heat, use_container_width=True)

# -------------------------
# DETAILS
# -------------------------
with st.expander("📋 Scenario Details"):
    st.write({
        "Configured Price Levels": PRICE_LEVELS,
        "Configured Green Levels": GREEN_LEVELS,
        "Configured TOD Levels": TOD_LEVELS,
        "Expected Run Count": EXPECTED_RUNS,
        "Detected Run Count": len(all_runs),
        "Primary Run ID": primary_run_id,
        "TDR Base Price": p_price,
        "Green Premium": p_green,
        "TOD Premium": p_tod,
        "Comparison Mode": comparison_mode,
        "Comparison Run ID": comp_run_id if comparison_mode else None,
    })

with st.expander("📁 Available Run Files"):
    st.write(sorted([f"KOCHI_v05_run{k}.csv" for k in all_runs.keys()]))

with st.expander("📖 About the Model"):
    st.markdown("""
    **Kochi TDR ABM v05** models Transfer of Development Rights policy for the Kochi urban region.

    **Key zones:**
    - **Receiving-Primary** (TOD corridor): Metro alignment with highest FSI bonus
    - **Receiving-Secondary** (Road corridors): Major road-adjacent development
    - **Receiving-Tertiary** (Thoppumpady): West Kochi fishing harbour node
    - **Sending-Green**: Wetland and canal-edge conservation areas
    - **Sending-Heritage**: Fort Kochi, Mattancherry heritage districts

    **v05 improvements over v04:**
    - Thoppumpady commercial node now correctly appears in west Kochi
    - Mattancherry spice-market node added
    - West Kochi connecting road (Thoppumpady bridge)
    - New metrics: west-developed-count, mean-land-value, TDR-efficiency
    - Enhanced BehaviorSpace: price × green × TOD grid, with app mapping driven by the configured level lists
    - Policy sensitivity heatmap across all runs
    """)
