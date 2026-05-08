import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="Election Projection Tool",
    page_icon="🗳️",
    layout="wide"
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}

* {
    font-family: "Zalando Sans Expanded Extra Bold", "Zalando Sans Expanded", Arial, sans-serif !important;
    font-weight: 800 !important;
}

.stApp {
    background: #3bc6e4;
}

.block-container {
    max-width: 1400px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.hero, .panel {
    background: #00486e;
    padding: 1.5rem;
    border-radius: 22px;
    box-shadow: 0 12px 30px rgba(0,0,0,0.15);
    margin-bottom: 1.2rem;
}

.hero {
    padding: 2.5rem;
}

.hero h1 {
    color: white !important;
    font-size: 3rem;
    line-height: 1.05;
    margin-bottom: 0.8rem;
}

.hero p, .panel p, .panel h2, .panel h3 {
    color: white !important;
}

h1, h2, h3, p, label, span {
    color: white !important;
}

[data-testid="stTextInput"],
[data-testid="stFileUploader"] {
    background: #00486e !important;
    border-radius: 18px;
    padding: 1rem;
    margin-bottom: 1rem;
}

input,
textarea,
[data-baseweb="input"] input {
    background: #00486e !important;
    color: white !important;
    border: 1px solid white !important;
    border-radius: 10px !important;
}

input::placeholder {
    color: rgba(255,255,255,0.75) !important;
}

[data-testid="stFileUploaderDropzone"] {
    background: #00486e !important;
    border: 1px solid white !important;
    border-radius: 12px;
}

[data-testid="stFileUploaderDropzone"] * {
    color: white !important;
}

[data-testid="stFileUploaderDropzone"] button {
    background: #00486e !important;
    color: white !important;
    border: 1px solid white !important;
}

[data-testid="stFileUploaderFile"] {
    background: #00486e !important;
    border: 1px solid white !important;
    border-radius: 12px !important;
}

[data-testid="stFileUploaderFile"] * {
    color: white !important;
    fill: white !important;
}

[data-testid="stFileUploaderDeleteBtn"] {
    background: #00486e !important;
    color: white !important;
}

[data-testid="stFileUploaderDeleteBtn"] * {
    color: white !important;
    fill: white !important;
}

.stButton > button {
    background: #00486e !important;
    color: white !important;
    border: 1px solid white !important;
    border-radius: 999px;
    padding: 0.8rem 1.6rem;
    font-weight: 800;
    width: 100%;
}

.stButton > button:hover,
[data-testid="stFileUploaderDropzone"] button:hover {
    background: #003554 !important;
    color: white !important;
    border: 1px solid white !important;
}

[data-testid="stAlert"] {
    background: #00486e !important;
    border-radius: 16px;
    border: 1px solid white;
}

[data-testid="stAlert"] * {
    color: white !important;
}

[data-testid="stMetric"] {
    background: #00486e;
    border-radius: 18px;
    padding: 1.2rem;
    border: 1px solid white;
}

[data-testid="stMetric"] * {
    color: white !important;
}

/* Dataframe/table */
[data-testid="stDataFrame"] {
    background: #00486e !important;
    border-radius: 12px;
    border: 1px solid white;
    overflow: hidden;
}

[data-testid="stDataFrame"] * {
    color: white !important;
}

/* Dataframe hover toolbar */
[data-testid="stElementToolbar"] {
    background: #00486e !important;
    border: 1px solid white !important;
    border-radius: 10px !important;
    box-shadow: 0 6px 18px rgba(0,0,0,0.18) !important;
}

[data-testid="stElementToolbar"] button {
    background: #00486e !important;
    border: 1px solid white !important;
    border-radius: 6px !important;
}

[data-testid="stElementToolbar"] svg,
[data-testid="stElementToolbar"] path {
    color: white !important;
    fill: white !important;
    stroke: white !important;
}

[data-testid="stElementToolbar"] button:hover {
    background: #003554 !important;
}

.small-note {
    color: rgba(255,255,255,0.85) !important;
    font-size: 0.95rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>Upload Election Results & Generate Live Projections</h1>
    <p>
        Upload a baseline election results file, paste a live booth-level results link,
        enter the candidate names, and click <b>Run projection</b> to estimate the live result
        using booth-by-booth swing modelling.
    </p>
</div>
""", unsafe_allow_html=True)


def clean_booth(x):
    return str(x).lower().strip()


def load_uploaded_file(file):
    file.seek(0)

    if file.name.endswith(".csv"):
        df = pd.read_csv(file, header=None)
    else:
        df = pd.read_excel(file, header=None)

    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = range(df.shape[1])

    return df


def auto_detect_baseline(df):
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = range(df.shape[1])

    if df.shape[1] >= 17:
        base = df.iloc[14:].copy()
        base = base[[1, 7, 8, 16]]
        base.columns = ["booth", "a_votes", "b_votes", "votes"]

    elif df.shape[1] == 6:
        base = df.copy()
        base = base[[0, 1, 2, 5]]
        base.columns = ["booth", "a_votes", "b_votes", "votes"]

    elif df.shape[1] == 4:
        base = df.copy()
        base.columns = ["booth", "a_votes", "b_votes", "votes"]

    else:
        st.error(
            f"The uploaded file has {df.shape[1]} columns. "
            "Upload the original VEC file, a 6-column cleaned file, or a 4-column file: booth, candidate A, candidate B, total votes."
        )
        st.stop()

    base = base.dropna(subset=["booth", "votes"])

    base["booth"] = base["booth"].astype(str).str.lower().str.strip()
    base["a_votes"] = pd.to_numeric(base["a_votes"], errors="coerce").fillna(0)
    base["b_votes"] = pd.to_numeric(base["b_votes"], errors="coerce").fillna(0)
    base["votes"] = pd.to_numeric(base["votes"], errors="coerce").fillna(0)

    base = base[base["votes"] > 0]
    base = base[(base["a_votes"] + base["b_votes"]) > 0]

    base["a_pct"] = base["a_votes"] / (base["a_votes"] + base["b_votes"]) * 100
    base["b_pct"] = 100 - base["a_pct"]

    if base.empty:
        st.error("Could not build baseline from the uploaded file.")
        st.stop()

    return base[["booth", "a_pct", "b_pct", "votes"]]


def fetch_live_page(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.text


def parse_live_results(html):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")

    rows = []

    pattern = re.compile(
        r"([A-Za-z][A-Za-z\s]+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"
    )

    for match in pattern.finditer(text):
        booth = clean_booth(match.group(1))

        skip = [
            "ordinary votes total",
            "absent votes",
            "early votes",
            "postal votes",
            "provisional votes",
            "marked as voted votes",
            "total votes",
            "percentage of formal vote polled by candidate",
        ]

        if booth in skip:
            continue

        b_votes = int(match.group(2))
        a_votes = int(match.group(3))
        total_votes = int(match.group(6))

        if total_votes <= 0 or (a_votes + b_votes) <= 0:
            continue

        rows.append({
            "booth": booth,
            "a_pct": a_votes / (a_votes + b_votes) * 100,
            "b_pct": b_votes / (a_votes + b_votes) * 100,
            "votes": total_votes
        })

    if not rows:
        return pd.DataFrame(columns=["booth", "a_pct", "b_pct", "votes"])

    return pd.DataFrame(rows).drop_duplicates(subset=["booth"], keep="first")


def project_result(live, baseline):
    merged = pd.merge(
        live,
        baseline,
        on="booth",
        suffixes=("_live", "_base")
    )

    if merged.empty:
        return None, merged

    merged["swing_to_a"] = merged["a_pct_live"] - merged["a_pct_base"]
    merged["swing_to_b"] = -merged["swing_to_a"]

    weighted_swing = (
        merged["swing_to_a"] * merged["votes_live"]
    ).sum() / merged["votes_live"].sum()

    projected = baseline.copy()
    projected["projected_a"] = projected["a_pct"] + weighted_swing

    total_votes = projected["votes"].sum()

    projected_a = (
        projected["projected_a"] * projected["votes"]
    ).sum() / total_votes

    projected_b = 100 - projected_a
    counted = live["votes"].sum() / total_votes

    return {
        "weighted_swing": weighted_swing,
        "projected_a": projected_a,
        "projected_b": projected_b,
        "counted": counted
    }, merged


left, right = st.columns([1, 2.2], gap="large")

with left:
    st.markdown(
        '<div class="panel"><h2>Inputs</h2><p class="small-note">Upload the baseline file and paste the live booth-level results link.</p></div>',
        unsafe_allow_html=True
    )

    uploaded_file = st.file_uploader(
        "Upload baseline results file",
        type=["xls", "xlsx", "csv"]
    )

    live_url = st.text_input(
        "Paste current booth-level results page link",
        placeholder="Paste booth-level results link here"
    )

    candidate_a_name = st.text_input("Candidate A name", "Independent")
    candidate_b_name = st.text_input("Candidate B name", "Liberal")

    run_button = st.button("Run projection")

    st.markdown("""
    <div class="panel">
        <h3>Accepted file formats</h3>
        <p class="small-note">
            Original VEC Excel file, cleaned 6-column file, or simple 4-column file:
            booth, candidate A votes, candidate B votes, total votes.
        </p>
    </div>
    """, unsafe_allow_html=True)

with right:
    if uploaded_file is None:
        st.info("Upload a baseline results file to begin.")
        st.stop()

    if not live_url:
        st.info("Paste a booth-level live results link to begin.")
        st.stop()

    if not run_button:
        st.info("Click Run projection when ready.")
        st.stop()

    baseline = auto_detect_baseline(load_uploaded_file(uploaded_file))

    try:
        html = fetch_live_page(live_url)
    except Exception as e:
        st.error(f"Could not fetch live results page: {e}")
        st.stop()

    live = parse_live_results(html)

    if live.empty:
        st.warning("No booth-level live results were parsed.")
        st.stop()

    result, merged = project_result(live, baseline)

    if result is None:
        st.error("Live booths were found, but none matched the baseline booth names.")
        st.stop()

    st.markdown('<div class="panel"><h2>Projection</h2></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.metric(f"Projected {candidate_a_name}", f"{result['projected_a']:.2f}%")
    c2.metric(f"Projected {candidate_b_name}", f"{result['projected_b']:.2f}%")

    c3, c4, c5 = st.columns(3)
    c3.metric("Matched booths", len(merged))
    c4.metric("Counted vs baseline", f"{result['counted'] * 100:.1f}%")

    swing_colour = "#ff4b4b" if result["weighted_swing"] < 0 else "white"
    c5.markdown(
        f"""
        <div style="
            background:#00486e;
            border:1px solid white;
            border-radius:18px;
            padding:1.2rem;
        ">
            <div style="color:white;font-size:0.9rem;">Swing to {candidate_a_name}</div>
            <div style="color:{swing_colour};font-size:2rem;font-weight:800;">
                {result['weighted_swing']:.2f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if result["projected_a"] > result["projected_b"]:
        st.success(f"Current projection: {candidate_a_name} ahead")
    else:
        st.error(f"Current projection: {candidate_b_name} ahead")

    st.subheader("Booth-by-booth swing")

    merged_display = merged[[
        "booth",
        "a_pct_base",
        "a_pct_live",
        "swing_to_a",
        "b_pct_base",
        "b_pct_live",
        "swing_to_b",
        "votes_live"
    ]].copy()

    merged_display.columns = [
        "Booth",
        f"{candidate_a_name} baseline %",
        f"{candidate_a_name} live %",
        f"Swing to {candidate_a_name}",
        f"{candidate_b_name} baseline %",
        f"{candidate_b_name} live %",
        f"Swing to {candidate_b_name}",
        "Live votes"
    ]

    styled_table = (
        merged_display
        .sort_values("Live votes", ascending=False)
        .style
        .set_properties(**{
            "background-color": "#00486e",
            "color": "white",
            "border-color": "white",
            "font-family": "Zalando Sans Expanded Extra Bold, Zalando Sans Expanded, Arial, sans-serif",
            "font-weight": "800",
        })
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("background-color", "#00486e"),
                    ("color", "white"),
                    ("border-color", "white"),
                    ("font-family", "Zalando Sans Expanded Extra Bold, Zalando Sans Expanded, Arial, sans-serif"),
                    ("font-weight", "800"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("background-color", "#00486e"),
                    ("color", "white"),
                    ("border-color", "white"),
                ],
            },
        ])
    )

    st.dataframe(styled_table, use_container_width=True)
