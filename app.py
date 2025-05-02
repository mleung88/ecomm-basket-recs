import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar
import os

# ─── 1) LOAD CSVs ────────────────────────────────────────────────────────────────
@st.cache_data
def load_rules(path="rules_final.csv"):
    return pd.read_csv(path)

@st.cache_data
def load_raw_sales(path="Filter.csv"):
    return pd.read_csv(path)

# ─── 2) AGGREGATE SALES ──────────────────────────────────────────────────────────
@st.cache_data
def aggregate_sales(raw):
    # ensure TotalSpent exists
    raw = raw.copy()
    raw["TotalSpent"] = raw["Quantity"] * raw["UnitPrice"]
    agg = (
        raw
        .groupby("Description", as_index=False)
        .agg(
            Total_Items = ("Quantity", "sum"),
            Price       = ("UnitPrice", "mean"),
            Total_Spent = ("TotalSpent", "sum"),
        )
    )
    return agg

# ─── 3) GET RECOMMENDATIONS ─────────────────────────────────────────────────────
def get_recommendations(df, month, rec_type, min_conf, min_lift, min_support, min_conseq_freq):
    d = df.copy()
    if month != "Any":
        d = d[d.Month == month]
    if "type" in d.columns and rec_type != "All":
        d = d[d.type == rec_type]
    d = d[
        (d.confidence >= min_conf) &
        (d.lift       >= min_lift) &
        (d.support    >= min_support)
    ]
    if "consequent_count" in d.columns:
        d = d[d.consequent_count >= min_conseq_freq]
    d = d.drop_duplicates(subset=["antecedent","consequent"])
    # items with at least one rule passing filters
    available = sorted(d.antecedent.unique())
    return d, available

def filter_top(df, item, bidir, top_n, sort_by):
    if bidir:
        sel = df[(df.antecedent==item)|(df.consequent==item)].copy()
    else:
        sel = df[df.antecedent==item].copy()
    sel = sel[sel.antecedent != sel.consequent]
    return sel.sort_values(sort_by, ascending=False).head(top_n)

# ─── 4) STREAMLIT APP ────────────────────────────────────────────────────────────
st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

# Sidebar filters
with st.sidebar:
    st.header("🔧 Filters")
    month        = st.selectbox("📅 Month", ["Any"] + list(calendar.month_name)[1:])
    rec_type     = st.radio("🔀 Rule Type", ["All","color_swap","cross_category"])
    min_conf     = st.slider("📉 Min Confidence", 0.0,1.0,0.4,0.05)
    min_lift     = st.slider("📈 Min Lift"      , 1.0,5.0,1.2,0.1)
    min_support  = st.slider("📊 Min Support"   , 0.0,0.1,0.01,0.005)
    min_confreq  = st.slider("🛒 Consequent Freq ≥",1,100,5)
    sku_filter   = st.text_input("🔍 SKU Contains")
    keyword      = st.text_input("🔍 Search Consequent")
    bidir        = st.checkbox("↔️ Bidirectional", value=False)
    top_n        = st.slider("🔢 Top N",1,20,10)
    sort_by      = st.radio("📌 Sort By",["confidence","lift"])
    group_by     = st.radio("🗂️ Group By",["None","type","Month"])

# Load & prep
rules     = load_rules()
raw_sales = load_raw_sales()
sales_agg = aggregate_sales(raw_sales)

# Merge each rule row’s consequent → its sales metrics
df = rules.merge(
    sales_agg,
    left_on="consequent", right_on="Description",
    how="left"
).drop(columns="Description")

# Filter down to the rule set & build item list
filtered, items = get_recommendations(
    df, month, rec_type, min_conf, min_lift, min_support, min_confreq
)

# Product selector
selected = st.selectbox("🛍️ Select a Product to Analyze", items)

# Top rules
top_rules = filter_top(filtered, selected, bidir, top_n, sort_by)
if keyword:
    top_rules = top_rules[top_rules.consequent.str.contains(keyword, case=False)]

# Merge in the sales metrics for the **consequents** themselves
top_rules = top_rules.merge(
    sales_agg,
    left_on="consequent", right_on="Description",
    how="left"
).drop(columns="Description")

# LAYOUT
col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"🔎 Top {len(top_rules)} Recommendations for `{selected}`")
    if group_by!="None" and group_by in top_rules.columns:
        for grp, dfg in top_rules.groupby(group_by):
            st.markdown(f"### 🔸 {grp}")
            st.dataframe(dfg[["consequent","support","confidence","lift","Total_Items","Price","Total_Spent"]])
    else:
        st.dataframe(top_rules[["consequent","support","confidence","lift","Total_Items","Price","Total_Spent"]])

    # natural‐language rules
    if not top_rules.empty:
        st.markdown("### 📘 Natural Language Rules")
        for _, r in top_rules.iterrows():
            direction = "buys" if r.antecedent==selected else "is also bought with"
            st.markdown(
                f"- If someone **{direction}** `{selected}`, they often buy **{r.consequent}** "
                f"(conf: `{r.confidence:.2f}`, lift: `{r.lift:.2f}`, "
                f"qty: `{int(r.Total_Items)}`, spent: `${r.Total_Spent:,.2f}`)"
            )

# download CSV
if not top_rules.empty:
    st.download_button(
        "📥 Download Recommendations (CSV)",
        top_rules.to_csv(index=False),
        "recommendations.csv",
        mime="text/csv"
    )
else:
    st.warning("No recommendations found for that product/filters.")
