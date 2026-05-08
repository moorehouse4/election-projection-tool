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

.stApp {
    background: #3bc6e4;
}

.block-container {
    max-width: 1150px;
    padding-top: 3rem;
    padding-bottom: 3rem;
}

.hero {
    background: #00486e;
    padding: 3rem;
    border-radius: 24px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.18);
    margin-bottom: 2rem;
}

.hero h1, .hero p {
    color: white;
}

h1, h2, h3, p, label, span {
    color: white !important;
}

/* make widgets transparent so no weird white boxes */
[data-testid="stTextInput"],
[data-testid="stFileUploader"],
[data-testid="stSelectbox"],
[data-testid="stNumberInput"] {
    background: #00486e !important;
    border-radius: 18px;
    padding: 1rem;
    margin-bottom: 1rem;
}

/* actual input fields */
input,
textarea,
[data-baseweb="input"] input {
    background: #00486e !important;
    color: white !important;
    border: 1px solid white !important;
    border-radius: 10px !important;
}

/* placeholder text */
input::placeholder {
    color: rgba(255,255,255,0.75) !important;
}

/* file uploader inner drop zone */
[data-testid="stFileUploaderDropzone"] {
    background: #00486e !important;
    border: 1px solid white !important;
    border-radius: 12px;
}

[data-testid="stFileUploaderDropzone"] * {
    color: white !important;
}

/* buttons */
.stButton > button {
    background: white;
    color: #00486e;
    border: none;
    border-radius: 999px;
    padding: 0.75rem 1.5rem;
    font-weight: 800;
}

.stButton > button:hover {
    background: #00486e;
    color: white;
    border: 2px solid white;
}

/* info/warning boxes */
[data-testid="stAlert"] {
    background: #00486e !important;
    border-radius: 16px;
    border: 1px solid white;
}

[data-testid="stAlert"] * {
    color: white !important;
}

/* metrics */
[data-testid="stMetric"] {
    background: #00486e;
    border-radius: 18px;
    padding: 1.2rem;
    border: 1px solid white;
}

[data-testid="stMetric"] * {
    color: white !important;
}

/* dataframes */
[data-testid="stDataFrame"] {
    background: white;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("""
<div class="hero">
    <h1>Election Projection Tool</h1>
    <p>
        Upload a baseline results file, paste a live booth-level results link,
        and estimate the projected result using booth-by-booth swing.
    </p>
</div>
""", unsafe_allow_html=True)


def clean_booth(x):
    return str(x).lower().strip()


def load_uploaded_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file, header=None)
    return pd.read_excel(file, header=None)


def normalise_baseline(df, booth_col, a_col, b_col, total_col, start_row):
    base = df.iloc[start_row:].copy()
    base = base[[booth_col, a_col, b_col, total_col]]
    base.columns = ["booth", "a_votes", "b_votes", "votes"]

    base = base.dropna(subset=["booth"])
    base["booth"] = base["booth"].apply(clean_booth)

    base["a_votes"] = pd.to_numeric(base["a_votes"], errors="coerce").fillna(0)
    base["b_votes"] = pd.to_numeric(base["b_votes"], errors="coerce").fillna(0)
    base["votes"] = pd.to_numeric(base["votes"], errors="coerce").fillna(0)

    base = base[base["votes"] > 0]
    base = base[(base["a_votes"] + base["b_votes"]) > 0]

    base["a_pct"] = base["a_votes"] / (base["a_votes"] + base["b_votes"]) * 100
    base["b_pct"] = 100 - base["a_pct"]

    return base[["booth", "a_pct", "b_pct", "votes"]]


def fetch_live_page(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.text


def parse_live_results(html, booth_names):
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


st.markdown('<div class="card">', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload baseline results file",
    type=["xls", "xlsx", "csv"]
)

live_url = st.text_input(
    "Paste current booth-level results page link",
    placeholder="https://www.vec.vic.gov.au/..."
)

candidate_a_name = st.text_input("Candidate A name", "Independent")
candidate_b_name = st.text_input("Candidate B name", "Liberal")

st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file is None:
    st.info("Upload a baseline results file to begin.")
    st.stop()

raw_df = load_uploaded_file(uploaded_file)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("1. Check uploaded file")
st.write("Preview the uploaded file and identify the row where real booth data begins.")
st.dataframe(raw_df.head(30), use_container_width=True)

columns = list(raw_df.columns)

start_row = st.number_input(
    "First row of real booth data",
    min_value=0,
    max_value=max(len(raw_df) - 1, 0),
    value=14,
    step=1
)

booth_col = st.selectbox(
    "Booth/location column",
    columns,
    index=1 if len(columns) > 1 else 0
)

a_col = st.selectbox(
    f"{candidate_a_name} votes column",
    columns,
    index=7 if len(columns) > 7 else 0
)

b_col = st.selectbox(
    f"{candidate_b_name} votes column",
    columns,
    index=8 if len(columns) > 8 else 0
)

total_col = st.selectbox(
    "Total votes column",
    columns,
    index=16 if len(columns) > 16 else 0
)

st.info(
    "For Nepean 2022: start row = 14, booth = column 1, "
    "Independent = column 7, Liberal = column 8, total votes = column 16."
)
st.markdown('</div>', unsafe_allow_html=True)

if st.button("Run projection"):
    if not live_url:
        st.error("Paste a current results URL first.")
        st.stop()

    baseline = normalise_baseline(
        raw_df,
        booth_col,
        a_col,
        b_col,
        total_col,
        start_row
    )

    if baseline.empty:
        st.error("Could not build baseline. Check the start row and selected columns.")
        st.stop()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("2. Baseline loaded")
    st.success(f"Loaded {len(baseline)} baseline booths.")
    st.dataframe(baseline, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    try:
        html = fetch_live_page(live_url)
    except Exception as e:
        st.error(f"Could not fetch live results page: {e}")
        st.stop()

    live = parse_live_results(html, baseline["booth"].tolist())

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("3. Live results parsed")

    if live.empty:
        st.warning("No booth-level live results were parsed.")
        st.stop()

    st.success(f"Parsed {len(live)} live booths.")
    st.dataframe(live, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    result, merged = project_result(live, baseline)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("4. Projection")

    if result is None:
        st.error("Live booths were found, but none matched the baseline booth names.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matched booths", len(merged))
    c2.metric("Counted vs baseline", f"{result['counted'] * 100:.1f}%")
    c3.metric(f"Projected {candidate_a_name}", f"{result['projected_a']:.2f}%")
    c4.metric(f"Projected {candidate_b_name}", f"{result['projected_b']:.2f}%")

    st.metric(f"Swing to {candidate_a_name}", f"{result['weighted_swing']:.2f}%")

    if result["projected_a"] > result["projected_b"]:
        st.success(f"Current projection: {candidate_a_name} ahead")
    else:
        st.error(f"Current projection: {candidate_b_name} ahead")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("5. Booth-by-booth swing")

    merged_display = merged[[
        "booth",
        "a_pct_base",
        "a_pct_live",
        "swing_to_a",
        "votes_live"
    ]].copy()

    merged_display.columns = [
        "Booth",
        f"{candidate_a_name} baseline %",
        f"{candidate_a_name} live %",
        f"Swing to {candidate_a_name}",
        "Live votes"
    ]

    st.dataframe(
        merged_display.sort_values("Live votes", ascending=False),
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
