import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

# 1) Load raw data
@st.cache_data
def load_rules() -> pd.DataFrame:
    return pd.read_csv("rules_final.csv")

@st.cache_data
def load_sales_data() -> pd.DataFrame:
    return pd.read_csv("Filter.csv")

# 2) Aggregate sales data into per‐product summary
@st.cache_data
def aggregate_sales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]
    agg = (
        df.groupby("Description", as_index=False)
          .agg(
            Total_Items = ("Quantity", "sum"),
            Price       = ("UnitPrice", "mean"),
            Total_Spent = ("TotalSpent", "sum"),
          )
    )
    return agg

# 3) Merge rules with consequent‐level sales metrics
def merge_data(rules: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    return pd.merge(
        rules,
        sales,
        how="left",
        left_on="consequent",
        right_on="Description",
    ).drop(columns=["Description"])

# 4) Recommendation filtering
def get_recommendations(
    df, month, rule_type, min_conf, min_lift, min_supp,
    min_conseq_freq, sku_filter, keyword, bidirectional, top_n, sort_by
):
    d = df.copy()
    if month != "Any":
        d = d[d["Month"] == month]
    if rule_type != "All" and "type" in d.columns:
        d = d[d["type"] == rule_type]
    d = d[
        (d["confidence"] >= min_conf)
      & (d["lift"]       >= min_lift)
      & (d["support"]    >= min_supp)
    ].drop_duplicates(subset=["antecedent","consequent"])
    if sku_filter:
        d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    if "consequent_count" in d.columns:
        d = d[d["consequent_count"] >= min_conseq_freq]
    if keyword:
        d = d[d["consequent"].str.contains(keyword, case=False, na=False)]
    # find which antecedents have ≥ top_n distinct consequents
    counts = d["antecedent"].value_counts()
    good = counts[counts >= top_n].index.tolist()
    return d, sorted(good)

def filter_top(df, item, bidirectional, top_n, sort_by):
    if bidirectional:
        sel = df[(df["antecedent"] == item) | (df["consequent"] == item)]
    else:
        sel = df[df["antecedent"] == item]
    sel = sel[sel["antecedent"] != sel["consequent"]]
    return sel.sort_values(sort_by, ascending=False).head(top_n)

# ─── Streamlit UI ──────────────────────────────────────────────────────────
st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

with st.sidebar:
    st.header("🔧 Filters")
    month         = st.selectbox("📅 Month", ["Any"] + list(calendar.month_name)[1:])
    rule_type     = st.radio("🔀 Rule Type", ["All","color_swap","cross_category"])
    min_conf      = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift      = st.slider("📈 Min Lift",       1.0, 5.0, 1.2, 0.1)
    min_supp      = st.slider("📊 Min Support",    0.0, 0.1, 0.01, 0.005)
    min_conseq    = st.slider("🛒 Min Conseq Freq", 1, 100, 5)
    sku_filter    = st.text_input("🔍 SKU Contains")
    keyword       = st.text_input("🔍 Consequent Text")
    bidir         = st.checkbox("↔ Bidirectional", False)
    top_n         = st.slider("🔢 Top N Recs", 1, 20, 10)
    sort_by       = st.radio("📌 Sort By", ["confidence","lift"])

# Load & prep
rules   = load_rules()
sales   = load_sales_data()
agg     = aggregate_sales(sales)
merged  = merge_data(rules, agg)

# Prepare recommendations
filtered_df, products = get_recommendations(
    merged, month, rule_type, min_conf, min_lift, min_supp,
    min_conseq, sku_filter, keyword, bidir, top_n, sort_by
)
selected = st.selectbox("🛍️ Select a Product to Analyze", products)
top_rules = filter_top(filtered_df, selected, bidir, top_n, sort_by)

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"🔎 Top {len(top_rules)} Recs for `{selected}`")
    if top_rules.empty:
        st.warning("No recommendations match these filters.")
    else:
        st.dataframe(top_rules[[
            "consequent","support","confidence","lift",
            "Total_Items","Price","Total_Spent"
        ]])

        st.markdown("### 📘 Natural‐Language Rules")
        for _, r in top_rules.iterrows():
            qty  = int(r["Total_Items"])
            amt  = r["Total_Spent"]
            st.markdown(
                f"- If you buy **{r['antecedent']}**, "
                f"you also buy **{r['consequent']}** "
                f"(conf {r['confidence']:.2f}, lift {r['lift']:.2f}, "
                f"qty {qty:,}, spent ${amt:,.2f})"
            )

with col2:
    if not top_rules.empty:
        # Confidence bar chart
        st.markdown("### 📊 Confidence Bar Chart")
        fig, ax = plt.subplots(figsize=(4,3))
        br = top_rules.sort_values("confidence")
        ax.barh(br["consequent"], br["confidence"], color=plt.cm.Greens(br["confidence"]))
        ax.set_xlabel("Confidence")
        st.pyplot(fig)

        # Trend chart: one series per consequent, with unique Month index
        st.markdown("### 📈 Trend Chart")
        month_order = list(calendar.month_name)[1:]
        raw_trend   = merged[
            (merged["antecedent"]==selected)
          & (merged["consequent"].isin(top_rules["consequent"]))
        ]
        # collapse to one confidence per Month‐Consequent
        trend_base = (
            raw_trend.groupby(["Month","consequent"], as_index=False)
                     ["confidence"]
                     .mean()
        )
        fig, ax = plt.subplots(figsize=(4,3))
        for cons in top_rules["consequent"]:
            tmp = trend_base[trend_base["consequent"]==cons]
            ts  = tmp.set_index("Month")["confidence"].reindex(month_order)
            ax.plot(month_order, ts, marker="o", label=cons)
        ax.set_xticklabels(month_order, rotation=45, ha="right")
        ax.set_ylabel("Confidence")
        ax.legend(fontsize="small")
        st.pyplot(fig)

# allow downloading the merged rule+sales table
st.download_button(
    "📥 Download Full Merged Data",
    merged.to_csv(index=False),
    "merged_rules_sales.csv",
    mime="text/csv",
)
