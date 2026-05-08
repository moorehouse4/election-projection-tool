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
#MainMenu, footer, header 

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

.hero h1 {
    color: white !important;
    font-size: 3rem;
    line-height: 1.05;
    margin-bottom: 0.8rem;
}

.hero p {
    color: white !important;
    font-size: 1.15rem;
    max-width: 760px;
}

h1, h2, h3, p, label, span {
    color: white !important;
    font-family: Arial, sans-serif;
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

/* Button */
.stButton > button {
    background: #00486e !important;
    color: white !important;
    border: 1px solid white !important;
    border-radius: 999px;
    padding: 0.75rem 1.5rem;
    font-weight: 800;
}

.stButton > button:hover {
    background: white !important;
    color: #00486e !important;
    border: 1px solid #00486e !important;
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

[data-testid="stDataFrame"] {
    background: white;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

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

    try:
        df = pd.read_excel(file, header=None)
    except Exception:
        file.seek(0)
        df = pd.read_excel(file, header=None, engine="xlrd")

    # remove completely empty rows/columns
    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")

    # reset column numbers back to 0,1,2,3...
    df = df.reset_index(drop=True)
    df.columns = range(df.shape[1])

    return df


def auto_detect_baseline(df):
    # Clean completely empty rows/columns
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df.columns = range(df.shape[1])

    # Find the first row that looks like booth data
    start_row = None
    for i in range(len(df)):
        row_text = " ".join([str(x).lower() for x in df.iloc[i].tolist()])
        if "blairgowrie" in row_text or "rosebud" in row_text or "dromana" in row_text:
            start_row = i
            break

    if start_row is None:
        st.error("Could not find the booth rows in the uploaded file.")
        st.stop()

    data = []

    for _, row in df.iloc[start_row:].iterrows():
        values = row.tolist()

        booth = None
        booth_index = None

        for idx, value in enumerate(values):
            text = str(value).strip()
            if text and text.lower() not in ["nan", "none"]:
                if not re.fullmatch(r"[\d,\.]+", text):
                    booth = text.lower().strip()
                    booth_index = idx
                    break

        if booth is None:
            continue

        nums = []
        for value in values:
            num = pd.to_numeric(value, errors="coerce")
            if pd.notna(num):
                nums.append(float(num))

        if len(nums) < 3:
            continue

        # Your VEC primary spreadsheet format:
        # independent candidate is before Liberal in the row.
        # For Nepean 2022, we use:
        # Independent = 5th numeric value after booth-ish data area
        # Liberal = 6th numeric value
        # Total = last numeric value
        try:
            a_votes = nums[4]
            b_votes = nums[5]
            total_votes = nums[-1]
        except IndexError:
            continue

        if total_votes <= 0 or (a_votes + b_votes) <= 0:
            continue

        data.append({
            "booth": booth,
            "a_pct": a_votes / (a_votes + b_votes) * 100,
            "b_pct": b_votes / (a_votes + b_votes) * 100,
            "votes": total_votes
        })

    baseline = pd.DataFrame(data).drop_duplicates(subset=["booth"], keep="first")

    if baseline.empty:
        st.error("Could not build baseline automatically from the uploaded file.")
        st.stop()

    return baseline

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

if uploaded_file is None:
    st.info("Upload a baseline results file to begin.")
    st.stop()

if not live_url:
    st.info("Paste a booth-level live results link to begin.")
    st.stop()

baseline = auto_detect_baseline(load_uploaded_file(uploaded_file))

if baseline.empty:
    st.error("Could not read the uploaded baseline file. Make sure it uses the same VEC-style format.")
    st.stop()

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

st.subheader("Booth-by-booth swing")

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
