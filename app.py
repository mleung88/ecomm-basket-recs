import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

# -- Data Loading & Caching --
@st.cache_data
def load_rules(path: str = "rules_final.csv") -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_sales(path: str = "Filter.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    # Compute total spent per row
    if "Quantity" in df.columns and "UnitPrice" in df.columns:
        df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]
    # Aggregate by Description
    agg = (
        df.groupby("Description")
          .agg(
            Total_Items=("Quantity", "sum"),
            Price=("UnitPrice", "mean"),
            Total_Spent=("TotalSpent", "sum")
          )
          .reset_index()
    )
    return agg

# -- Recommendation Logic --
def get_recommendations(df: pd.DataFrame, month: str, rule_type: str,
                        min_conf: float, min_lift: float, min_support: float,
                        min_freq: int) -> pd.DataFrame:
    # Month filter
    if month != "Any" and "Month" in df:
        df = df[df["Month"] == month]
    # Rule type filter
    if rule_type != "All" and "type" in df:
        df = df[df["type"] == rule_type]
    # Threshold filters
    df = df[(df["confidence"] >= min_conf) &
            (df["lift"] >= min_lift) &
            (df["support"] >= min_support)]
    # Consequent frequency filter
    if "consequent_count" in df:
        df = df[df["consequent_count"] >= min_freq]
    return df.drop_duplicates(["antecedent", "consequent"])

# -- UI Setup --
st.set_page_config(page_title="E‑commerce Recommendation", layout="wide")
st.title("📦 E‑commerce Recommendation Dashboard")

# Sidebar filters
with st.sidebar:
    st.header("🔧 Filters")
    month = st.selectbox("Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    rule_type = st.radio("Rule Type", ["All", "color_swap", "cross_category"])
    min_conf = st.slider("Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift = st.slider("Min Lift", 1.0, 5.0, 1.2, 0.1)
    min_support = st.slider("Min Support", 0.0, 0.1, 0.01, 0.005)
    min_freq = st.slider("Consequent Frequency ≥", 1, 100, 5)
    top_n = st.slider("Top N Recommendations", 1, 20, 10)
    sort_by = st.radio("Sort By", ["confidence", "lift"])

# Load data
rules_df = load_rules()
sales_df = load_sales()
# Merge on antecedent → Description
merged = rules_df.merge(sales_df, how="left", left_on="antecedent", right_on="Description")

# Get filtered rules
tf = get_recommendations(merged, month, rule_type, min_conf, min_lift, min_support, min_freq)

# Select product
available = sorted(tf["antecedent"].unique())
selected = st.selectbox("Select a Product to Analyze", available)

# Top recommendations for selected
mask = tf["antecedent"] == selected
top = tf[mask].sort_values(sort_by, ascending=False).head(top_n)

# Display table
st.subheader(f"🔎 Top {len(top)} Recommendations for `{selected}`")
st.dataframe(top[["consequent", "support", "confidence", "lift", "Total_Items", "Price", "Total_Spent"]])

# Natural language rules
if not top.empty:
    st.markdown("### 📘 Natural Language Rules")
    for _, r in top.iterrows():
        st.markdown(
            f"- If you buy **{r['antecedent']}**, you also buy **{r['consequent']}** "
            f"(conf {r['confidence']:.2f}, lift {r['lift']:.2f}, "
            f"qty {int(r['Total_Items'])}, spent ${r['Total_Spent']:.2f})"
        )

# Confidence bar chart
top_sorted = top.sort_values("confidence", ascending=True)
fig, ax = plt.subplots()
ax.barh(top_sorted["consequent"], top_sorted["confidence"])
ax.set_xlabel("Confidence")
ax.set_ylabel("Consequent Item")
st.markdown("### 📊 Confidence Bar Chart")
st.pyplot(fig)

# Download full merged data
st.sidebar.download_button(
    label="📥 Download Merged Data",
    data=merged.to_csv(index=False),
    file_name="merged_recommendations.csv"
)
