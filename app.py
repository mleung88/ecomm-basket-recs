import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt  # still used for color maps
import calendar

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

# ─── 2) LOAD & MERGE DATA ────────────────────────────────────────────────────────
rules_df      = load_rules()
sales_summary = load_and_aggregate_sales()
merged_df     = merge_rules_sales(rules_df, sales_summary)

# ─── 3) SIDEBAR FILTERS ─────────────────────────────────────────────────────────
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

# ─── 4) RECOMMENDATION HELPER FUNCTIONS ─────────────────────────────────────────
def get_filtered_rules(df):
    d = df.copy()
    if month != "Any": d = d[d["Month"] == month]
    if rec_type != "All" and "type" in d.columns: d = d[d["type"] == rec_type]
    d = d[(d["confidence"] >= min_conf) & (d["lift"] >= min_lift) & (d["support"] >= min_sup)]
    d = d.drop_duplicates(subset=["antecedent","consequent"])  
    d["consequent_count"] = d.groupby("antecedent")["consequent"].transform("count")
    d = d[d["consequent_count"] >= min_count]
    if sku_filter and "SKU" in d.columns:
        d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    return d


def get_top_for_item(df, selected):
    cond = df["antecedent"] == selected
    if bidir: cond |= df["consequent"] == selected
    top = df[cond].copy()
    top = top[top["antecedent"] != top["consequent"]]
    top = top.sort_values(sort_by, ascending=False).head(top_n)
    if text_filt:
        top = top[top["consequent"].str.contains(text_filt, case=False, na=False)]
    top = top.drop(columns=["Description","Total_Items","Price","Total_Spent"], errors="ignore")
    top = (
        top.merge(
            sales_summary[["Description","Total_Items","Price","Total_Spent"]],
            how="left", left_on="consequent", right_on="Description"
        )
        .drop(columns=["Description"], errors="ignore")
    )
    return top

# ─── 5) UI: SELECTION & DISPLAY ─────────────────────────────────────────────────
filtered_df     = get_filtered_rules(merged_df)
available_items = sorted(filtered_df["antecedent"].unique())

st.subheader("🛍️ Select a Product to Analyze")
selected_item = st.selectbox("", available_items, key="select", label_visibility="hidden")

top_rules = get_top_for_item(filtered_df, selected_item)

if top_rules.empty:
    st.warning("No recommendations for these filters.")
else:
    col1, col2 = st.columns([2,1])
    # Display recommendations table
    with col1:
        st.subheader(f"🔎 Top {len(top_rules)} Recs for `{selected_item}`")
        cols = ["consequent","support","confidence","lift","Total_Items","Price","Total_Spent"]
        st.dataframe(top_rules[cols], hide_index=True)

        # Wrap natural language insights in an expander for collapsibility
        with st.expander("📘 Natural Language Insights", expanded=True):
            for _, r in top_rules.iterrows():
                st.markdown(
                    f"• People who bought **{selected_item}** also buy **{r['consequent']}**  "
                    f"(conf: {r['confidence']:.2%}, lift: {r['lift']:.2f}, "
                    f"items: {int(r['Total_Items'])}, spent: ${r['Total_Spent']:.2f})"
                )

    # Display charts
    with col2:
        st.markdown("### 📊 Confidence Bar Chart")
        bar_fig = px.bar(
            top_rules,
            x="confidence",
            y="consequent",
            orientation="h",
            text=top_rules["confidence"],
            labels={"consequent":"Item","confidence":"Confidence"},
            color_discrete_sequence=[plt.cm.Greens(0.6)],
        )
        bar_fig.update_layout(yaxis_categoryorder="total ascending", height=400)
        st.plotly_chart(bar_fig, use_container_width=True)

        st.markdown("### 📈 Trend Chart")
        month_order = list(calendar.month_name)[1:]
        trend_df = (
            merged_df.loc[
                (merged_df["antecedent"] == selected_item)
                & (merged_df["consequent"].isin(top_rules["consequent"]))
            ]
            .drop_duplicates(subset=["Month","consequent"] )
            .assign(Month=lambda d: pd.Categorical(d["Month"], categories=month_order, ordered=True))
        )
        trend_fig = px.line(
            trend_df,
            x="Month",
            y="confidence",
            color="consequent",
            markers=True,
            labels={"confidence":"Confidence"},
        )
        trend_fig.update_layout(xaxis_tickangle=45, height=450)
        st.plotly_chart(trend_fig, use_container_width=True)

    st.download_button("📥 Download Recommendations CSV", top_rules.to_csv(index=False), "top_recommendations.csv")
