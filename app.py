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
/* FINAL FIX: kill Streamlit's messy upload button */
[data-testid="stFileUploaderDropzone"] button {
    display: none !important;
}

/* Make the dropzone itself act as the upload area */
[data-testid="stFileUploaderDropzone"] {
    cursor: pointer !important;
}

/* Add one clean instruction instead */
[data-testid="stFileUploaderDropzone"]::before {
    content: "Click here to upload baseline file";
    display: block;
    background: white;
    color: #00486e;
    padding: 0.7rem 1rem;
    border-radius: 10px;
    width: fit-content;
    margin-bottom: 1rem;
}

/* Hide any leftover duplicated upload text */
[data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}

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

[data-testid="stTextInput"] {
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

/* File uploader */
[data-testid="stFileUploader"] {
    background: #00486e !important;
    border-radius: 18px;
    padding: 1rem;
    margin-bottom: 1rem;
}

[data-testid="stFileUploaderDropzone"] {
    background: #00486e !important;
    border: 1px solid white !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

/* Keep uploader label text white */
[data-testid="stFileUploader"] label,
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] p {
    color: white !important;
}

/* DO NOT style the internal upload button */

/* Uploaded file row */
[data-testid="stFileUploaderFile"] {
    background: white !important;
    border-radius: 10px !important;
    border: 1px solid white !important;
}

[data-testid="stFileUploaderFile"] * {
    color: #00486e !important;
    fill: #00486e !important;
    font-size: 0.85rem !important;
}

/* Run button */
.stButton > button {
    background: #00486e !important;
    color: white !important;
    border: 1px solid white !important;
    border-radius: 999px;
    padding: 0.8rem 1.6rem;
    width: 100%;
}

.stButton > button:hover {
    background: #003554 !important;
    color: white !important;
    border: 1px solid white !important;
}

/* Alerts */
[data-testid="stAlert"] {
    background: #00486e !important;
    border-radius: 16px;
    border: 1px solid white;
}

[data-testid="stAlert"] * {
    color: white !important;
}

/* Metrics */
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
    <h1>Election Projection Tool</h1>
    <p>
        This tool is made for Community Indpendent Candidates running an election campaign is state and federal elections in Australia. This tool helps predict 2 candidate preferred results by comparing the previous election results. The tool only looks at data and makes a reasonable prediction and should not be taken as an offical results. This site is not authorised by the VEC/AEC and was made by an independent private individual.
        Upload a baseline results file, paste a live booth-level results link,
        and estimate the projected result using booth-by-booth swing.
    </p>
</div>
""", unsafe_allow_html=True)


def clean_booth(x):
    return str(x).lower().strip()


def classify_vote_type(name):
    name = clean_booth(name)

    if "early" in name or "pre-poll" in name or "pre poll" in name:
        return "early"
    if "postal" in name:
        return "postal"
    if "absent" in name:
        return "absent"
    if "provisional" in name:
        return "provisional"
    if "marked as voted" in name:
        return "marked_as_voted"

    return "ordinary"


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


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
    base["vote_type"] = base["booth"].apply(classify_vote_type)

    if base.empty:
        st.error("Could not build baseline from the uploaded file.")
        st.stop()

    return base[["booth", "vote_type", "a_pct", "b_pct", "votes"]]


def fetch_live_page(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.text


def parse_live_results(html):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")

    rows = []

    pattern = re.compile(
        r"([A-Za-z][A-Za-z\s\-]+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"
    )

    for match in pattern.finditer(text):
        booth = clean_booth(match.group(1))

        skip = [
            "two candidate preferred votes",
            "candidate",
            "party",
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
            "vote_type": classify_vote_type(booth),
            "a_votes": a_votes,
            "b_votes": b_votes,
            "a_pct": a_votes / (a_votes + b_votes) * 100,
            "b_pct": b_votes / (a_votes + b_votes) * 100,
            "votes": total_votes
        })

    if not rows:
        return pd.DataFrame(columns=[
            "booth", "vote_type", "a_votes", "b_votes", "a_pct", "b_pct", "votes"
        ])

    return pd.DataFrame(rows).drop_duplicates(subset=["booth"], keep="first")


def project_result(live, baseline):
    baseline = baseline.copy()
    live = live.copy()

    live["a_votes"] = live["a_pct"] / 100 * live["votes"]
    live["b_votes"] = live["b_pct"] / 100 * live["votes"]

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
    merged["vote_type"] = merged["vote_type_live"]

    total_baseline_votes = baseline["votes"].sum()
    matched_baseline_votes = merged["votes_base"].sum()

    raw_overall_swing = (
        merged["swing_to_a"] * merged["votes_live"]
    ).sum() / merged["votes_live"].sum()

    count_share = matched_baseline_votes / total_baseline_votes
    confidence = min(1.0, max(0.25, count_share * 2.5))
    regressed_overall_swing = raw_overall_swing * confidence

    type_swings = {}

    for vote_type, group in merged.groupby("vote_type"):
        raw_type_swing = (
            group["swing_to_a"] * group["votes_live"]
        ).sum() / group["votes_live"].sum()

        baseline_type_votes = baseline[baseline["vote_type"] == vote_type]["votes"].sum()

        if baseline_type_votes > 0:
            type_count_share = group["votes_base"].sum() / baseline_type_votes
        else:
            type_count_share = count_share

        type_confidence = min(1.0, max(0.25, type_count_share * 2.5))
        type_swings[vote_type] = raw_type_swing * type_confidence

    live_lookup = live.set_index("booth").to_dict("index")

    projected_rows = []

    for _, row in baseline.iterrows():
        booth = row["booth"]
        vote_type = row["vote_type"]

        if booth in live_lookup:
            live_row = live_lookup[booth]

            projected_rows.append({
                "booth": booth,
                "vote_type": vote_type,
                "status": "counted",
                "a_votes": live_row["a_votes"],
                "b_votes": live_row["b_votes"],
                "votes": live_row["votes"]
            })

        else:
            swing = type_swings.get(vote_type, regressed_overall_swing)

            estimated_a_pct = clamp(row["a_pct"] + swing)
            estimated_b_pct = 100 - estimated_a_pct

            projected_rows.append({
                "booth": booth,
                "vote_type": vote_type,
                "status": "estimated",
                "a_votes": estimated_a_pct / 100 * row["votes"],
                "b_votes": estimated_b_pct / 100 * row["votes"],
                "votes": row["votes"]
            })

    projection = pd.DataFrame(projected_rows)

    total_a = projection["a_votes"].sum()
    total_b = projection["b_votes"].sum()
    total_votes = total_a + total_b

    projected_a = total_a / total_votes * 100
    projected_b = 100 - projected_a

    counted_votes = projection[projection["status"] == "counted"]["votes"].sum()
    counted = counted_votes / projection["votes"].sum()

    return {
        "weighted_swing": regressed_overall_swing,
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

    candidate_a_name = st.text_input(
        "Candidate A name (challenger)",
        placeholder="Enter candidate A name"
    )

    candidate_b_name = st.text_input(
        "Candidate B name (incumbent)",
        placeholder="Enter candidate B name"
    )

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
else:
    candidate_a_display = candidate_a_name or "Candidate A"
    candidate_b_display = candidate_b_name or "Candidate B"

    baseline = auto_detect_baseline(load_uploaded_file(uploaded_file))

    # keep the rest of your projection code indented under this else

    candidate_a_display = candidate_a_name or "Candidate A"
    candidate_b_display = candidate_b_name or "Candidate B"

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

    
    def result_card(label, value, colour="white"):
        st.markdown(
        f"""
        <div style="
            background:#00486e;
            border:1px solid white;
            border-radius:18px;
            padding:1.2rem;
            min-height:120px;
        ">
            <div style="color:white;font-size:0.9rem;">{label}</div>
            <div style="color:{colour};font-size:2rem;font-weight:800;">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


candidate_a_colour = "#21c45d" if result["projected_a"] >= 50 else "#ff4b4b"
candidate_b_colour = "#21c45d" if result["projected_b"] >= 50 else "#ff4b4b"
swing_colour = "#ff4b4b" if result["weighted_swing"] < 0 else "#21c45d"

c1, c2 = st.columns(2)

with c1:
    result_card(
        f"Projected {candidate_a_display}",
        f"{result['projected_a']:.2f}%",
        candidate_a_colour
    )

with c2:
    result_card(
        f"Projected {candidate_b_display}",
        f"{result['projected_b']:.2f}%",
        candidate_b_colour
    )

c3, c4, c5 = st.columns(3)

with c3:
    result_card("Matched booths", len(merged), "white")

with c4:
    result_card(
        "Counted vs baseline",
        f"{result['counted'] * 100:.1f}%",
        "white"
    )

with c5:
    result_card(
        f"Swing to {candidate_a_display}",
        f"{result['weighted_swing']:.2f}%",
        swing_colour
    )
    
    if result["projected_a"] > result["projected_b"]:
        st.success(f"Current projection: {candidate_a_display} ahead")
    else:
        st.error(f"Current projection: {candidate_b_display} ahead")

    st.subheader("Booth-by-booth swing")

    merged_display = merged[[
        "booth",
        "vote_type",
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
        "Vote type",
        f"{candidate_a_display} baseline %",
        f"{candidate_a_display} live %",
        f"Swing to {candidate_a_display}",
        f"{candidate_b_display} baseline %",
        f"{candidate_b_display} live %",
        f"Swing to {candidate_b_display}",
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
