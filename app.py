import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar
import numpy as np

# ─── APP CONFIG ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

# ─── 1) LOAD & PREPARE DATA ────────────────────────────────────────────────────
@st.cache_data
def load_rules():
    return pd.read_csv("rules_final.csv")

@st.cache_data
def load_and_aggregate_sales():
    df = pd.read_csv("Filter.csv")
    if "TotalSpent" not in df.columns:
        df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]
    summary = (
        df.groupby("Description", dropna=False)
          .agg(
             Total_Items = ("Quantity",   "sum"),
             Price       = ("UnitPrice",  "mean"),
             Total_Spent = ("TotalSpent", "sum"),
          )
          .reset_index()
    )
    return summary

@st.cache_data
def merge_rules_sales(rules, sales_summary):
    merged = pd.merge(
        rules,
        sales_summary,
        how="left",
        left_on="antecedent",
        right_on="Description"
    )
    return merged.drop(columns=["Description"], errors="ignore")

# Load and merge data
rules_df      = load_rules()
sales_summary = load_and_aggregate_sales()
merged_df     = merge_rules_sales(rules_df, sales_summary)

# ─── 2) SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 Filters")
    month      = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:], key="month")
    rec_type   = st.radio("🔀 Rule Type", ["All","color_swap","cross_category"], key="type")
    min_conf   = st.slider("📉 Min Confidence",  0.0, 1.0, 0.4, 0.05, key="conf")
    min_lift   = st.slider("📈 Min Lift",        1.0, 5.0, 1.2, 0.1, key="lift")
    min_sup    = st.slider("📊 Min Support",     0.0, 0.1, 0.01, 0.005, key="sup")
    min_count  = st.slider("🛒 Consequent Frequency ≥", 1, 100, 5, key="count")
    sku_filter = st.text_input("🔍 SKU Contains (optional)", key="sku")
    text_filt  = st.text_input("🔍 Search Consequent Text", key="text")
    bidir      = st.checkbox("↔ Bidirectional Match", key="bidir")
    top_n      = st.slider("🔢 Top N Recs", 1, 20, 10, key="topn")
    sort_by    = st.radio("📌 Sort By", ["confidence","lift"], key="sort")
    group_by   = st.radio("🗂️ Group By", ["None","type","Month"], key="group")
    st.markdown("---")
    st.download_button("📥 Download Full Merged Data", merged_df.to_csv(index=False), "merged_data.csv")

# ─── 3) RECOMMENDATION LOGIC ────────────────────────────────────────────────────
def get_filtered_rules(df):
    d = df.copy()
    if month != "Any": d = d[d["Month"] == month]
    if rec_type != "All" and "type" in d.columns: d = d[d["type"] == rec_type]
    d = d[(d["confidence"] >= min_conf) & (d["lift"] >= min_lift) & (d["support"] >= min_sup)]
    d = d.drop_duplicates(subset=["antecedent","consequent"]).copy()
    d["consequent_count"] = d.groupby("antecedent")["consequent"].transform("count")
    d = d[d["consequent_count"] >= min_count]
    if sku_filter: d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    return d


def get_top_for_item(df, selected):
    cond = df["antecedent"] == selected
    if bidir: cond |= df["consequent"] == selected
    top = df[cond].copy()
    top = top[top["antecedent"] != top["consequent"]]
    top = top.sort_values(sort_by, ascending=False).head(top_n)
    if text_filt: top = top[top["consequent"].str.contains(text_filt, case=False, na=False)]
    # Ensure fresh metrics merge
    top = top.drop(columns=["Total_Items","Price","Total_Spent","Description"], errors="ignore")
    top = (
        top.merge(
            sales_summary[ ["Description","Total_Items","Price","Total_Spent"] ],
            how="left", left_on="consequent", right_on="Description"
        )
        .drop(columns=["Description"], errors="ignore")
    )
    return top

# ─── 4) DISPLAY UI ──────────────────────────────────────────────────────────────
filtered_df     = get_filtered_rules(merged_df)
available_items = sorted(filtered_df["antecedent"].unique())

st.subheader("🛍️ Select a Product to Analyze")
selected_item = st.selectbox("", available_items, key="select", label_visibility="hidden")

top_rules = get_top_for_item(filtered_df, selected_item)

if top_rules.empty:
    st.warning("No recommendations for these filters.")
else:
    col1, col2 = st.columns([2,1])
    # Configure column display settings
    column_config = {
        "consequent": st.column_config.Column(header="Item", width="200px", text_align="left"),
        "support":    st.column_config.Column(format=".2%",  width="80px"),
        "confidence": st.column_config.Column(format=".2%",  width="80px"),
        "lift":       st.column_config.Column(format=".2f",  width="80px"),
        "Total_Items":st.column_config.Column(format="d",    width="80px"),
        "Price":      st.column_config.Column(format="$,.2f",width="80px"),
        "Total_Spent":st.column_config.Column(format="$,.2f",width="100px"),
    }
    with col1:
        st.subheader(f"🔎 Top {len(top_rules)} Recs for `{selected_item}`")
        cols = ["consequent","support","confidence","lift","Total_Items","Price","Total_Spent"]
        if group_by != "None" and group_by in top_rules.columns:
            for grp, grp_df in top_rules.groupby(group_by):
                st.markdown(f"#### 🔸 {grp}")
                st.dataframe(grp_df[cols], hide_index=True, column_config=column_config)
        else:
            st.dataframe(top_rules[cols], hide_index=True, column_config=column_config)

        st.markdown("### 📘 Natural Language")
        for _, r in top_rules.iterrows():
            st.markdown(
                f"- People who bought **{selected_item}** also buy **{r['consequent']}** "
                f"(conf: {r['confidence']:.2%}, lift: {r['lift']:.2f}, "
                f"items: {int(r['Total_Items'])}, spent: ${r['Total_Spent']:.2f})"
            )

    with col2:
        st.markdown("### 📊 Confidence Bar Chart")
        fig, ax = plt.subplots(figsize=(6,4))
        ax.barh(top_rules["consequent"], top_rules["confidence"], color=plt.cm.Greens(0.6))
        ax.set_xlabel("Confidence"); ax.set_ylabel("Item")
        ax.invert_yaxis()
        st.pyplot(fig)

        st.markdown("### 📈 Trend Chart")
        month_order = list(calendar.month_name)[1:]
        fig, ax = plt.subplots(figsize=(8,4))
        for cons in top_rules["consequent"]:
            temp = (
                merged_df[(merged_df["antecedent"]==selected_item)&(merged_df["consequent"]==cons)]
                    .drop_duplicates(["Month","consequent"]).set_index("Month").reindex(month_order)
            )
            ax.plot(month_order, temp["confidence"].fillna(0), marker="o", label=cons)
        ax.set_ylabel("Confidence")
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_xticklabels(month_order, rotation=45, ha="right")
        ax.legend(fontsize="small", bbox_to_anchor=(1.05,1))
        st.pyplot(fig)

    st.download_button("📥 Download Recommendations CSV", top_rules.to_csv(index=False), "top_recommendations.csv")
