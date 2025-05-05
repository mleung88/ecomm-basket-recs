import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

# ─── APP CONFIG ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

# ─── 1) LOAD & PREPARE DATA ────────────────────────────────────────────────────
@st.cache_data
def load_rules():
    rules = pd.read_csv("rules_final.csv")
    # Derive a 'type' column for color_swap vs cross_category
    def rule_type(row):
        a_base = row["antecedent"].split()[0]
        c_base = row["consequent"].split()[0]
        return "color_swap" if a_base == c_base else "cross_category"
    rules["type"] = rules.apply(rule_type, axis=1)
    return rules

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
    ).drop(columns=["Description"], errors="ignore")
    return merged

# load dataframes
rules_df      = load_rules()
sales_summary = load_and_aggregate_sales()
merged_df     = merge_rules_sales(rules_df, sales_summary)

# ─── 2) SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 Filters")

    # Month filter
    month = st.selectbox(
        "📅 Filter by Month",
        ["Any"] + list(calendar.month_name)[1:],
        key="month"
    )

    # Rule type filter
    rec_type = st.radio(
        "🔀 Rule Type",
        ["All", "color_swap", "cross_category"],
        key="type"
    )

    # Metric filters
    min_conf = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05, key="conf")
    min_lift = st.slider("📈 Min Lift",       1.0, 5.0, 1.2, 0.1, key="lift")
    min_sup  = st.slider("📊 Min Support",    0.0, 0.1, 0.01, 0.005, key="sup")

    # Consequent frequency slider with dynamic max
    consec_counts = merged_df.groupby("antecedent")["consequent"].nunique()
    max_consec = int(consec_counts.max())
    min_count = st.slider(
        "🛒 Consequent Frequency ≥",
        1,
        max_consec,
        5,
        key="count"
    )
    st.caption(f"Max consequents per antecedent = {max_consec}")

    # Antecedent text search
    antecedent_search = st.text_input(
        "🔍 Search Antecedent (optional)",
        key="ant_search"
    )

    # Consequent text search
    text_filt = st.text_input(
        "🔍 Search Consequent Text (optional)",
        key="text"
    )

    # Bidirectional match
    bidir = st.checkbox("↔ Bidirectional Match", key="bidir")

    # Top-N and sort
    top_n   = st.slider("🔢 Top N Recs", 1, 20, 10, key="topn")
    sort_by = st.radio("📌 Sort By", ["confidence", "lift"], key="sort")

    # Group by option
    group_by = st.radio("🗂️ Group By", ["None", "type", "Month"], key="group")

    st.markdown("---")
    st.download_button(
        "📥 Download Full Merged Data",
        merged_df.to_csv(index=False),
        "merged_data.csv"
    )

# ─── 3) HELPER FUNCTIONS ─────────────────────────────────────────────────────────
def get_filtered_rules(df):
    d = df.copy()

    # Month filter
    if month != "Any":
        d = d[d["Month"] == month]

    # Rule type filter
    if rec_type != "All" and "type" in d.columns:
        d = d[d["type"] == rec_type]

    # Support / confidence / lift filters
    d = d[
        (d["confidence"] >= min_conf) &
        (d["lift"] >= min_lift) &
        (d["support"] >= min_sup)
    ]

    # Drop duplicates and enforce min consequent count
    d = d.drop_duplicates(subset=["antecedent","consequent"])
    d["consequent_count"] = d.groupby("antecedent")["consequent"].transform("nunique")
    d = d[d["consequent_count"] >= min_count]

    # Antecedent text search
    if antecedent_search:
        d = d[d["antecedent"].str.contains(antecedent_search, case=False, na=False)]

    # Consequent text search
    if text_filt:
        d = d[d["consequent"].str.contains(text_filt, case=False, na=False)]

    return d

def get_top_for_item(df, selected):
    cond = df["antecedent"] == selected
    if bidir:
        cond |= df["consequent"] == selected

    top = df[cond].copy()
    top = top[top["antecedent"] != top["consequent"]]
    top = top.sort_values(sort_by, ascending=False).head(top_n)

    # Merge in sales summary for consequents
    top = (
        top
        .drop(columns=["Description","Total_Items","Price","Total_Spent"], errors="ignore")
        .merge(
            sales_summary[["Description","Total_Items","Price","Total_Spent"]],
            how="left",
            left_on="consequent",
            right_on="Description"
        )
        .drop(columns=["Description"], errors="ignore")
    )
    return top

# ─── 4) MAIN UI ─────────────────────────────────────────────────────────────────
filtered_df = get_filtered_rules(merged_df)

# If grouping is selected, show aggregated top-N per group
if group_by in ["Month", "type"]:
    st.subheader(f"🔎 Top {top_n} Rules by {group_by}")

    # Aggregate metrics per group + rule
    grp = (
        filtered_df
        .groupby([group_by, "antecedent", "consequent"], as_index=False)
        .agg(
            support    = ("support",    "mean"),
            confidence = ("confidence", "mean"),
            lift       = ("lift",       "mean"),
            Total_Spent= ("Total_Spent","sum")
        )
    )

    # Pick top-N within each group
    def top_n_rules(subdf):
        return subdf.nlargest(top_n, sort_by)

    top_per_group = grp.groupby(group_by, group_keys=False).apply(top_n_rules)

    st.dataframe(
        top_per_group[[
            group_by, "antecedent", "consequent",
            "support", "confidence", "lift", "Total_Spent"
        ]],
        use_container_width=True
    )
    st.stop()

# Otherwise, show single-product selector flow
available_items = sorted(filtered_df["antecedent"].unique())
st.subheader("🛍️ Select a Product to Analyze")
selected_item = st.selectbox("", available_items, key="select", label_visibility="hidden")

top_rules = get_top_for_item(filtered_df, selected_item)

if top_rules.empty:
    st.warning("No recommendations for these filters.")
else:
    # Recommendations table
    st.subheader(f"🔎 Top {len(top_rules)} Recs for “{selected_item}”")
    cols = ["consequent","support","confidence","lift","Total_Items","Price","Total_Spent"]
    st.dataframe(top_rules[cols], hide_index=True)

    # Natural-language insights
    with st.expander("📘 Natural Language Insights", expanded=True):
        for _, r in top_rules.iterrows():
            st.markdown(
                f"• People who bought **{selected_item}** also buy **{r['consequent']}**  "
                f"(conf: {r['confidence']:.2%}, lift: {r['lift']:.2f}, "
                f"items: {int(r['Total_Items'])}, spent: ${r['Total_Spent']:.2f})"
            )

    # Side-by-side charts
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("### 📊 Confidence Bar Chart")
        fig1, ax1 = plt.subplots(figsize=(6,4))
        ax1.barh(top_rules["consequent"], top_rules["confidence"], color=plt.cm.Greens(0.6))
        ax1.invert_yaxis()
        ax1.set_xlabel("Confidence")
        ax1.set_ylabel("Item")
        st.pyplot(fig1)

    with chart_col2:
        st.markdown("### 📈 Trend Chart")
        month_order = list(calendar.month_name)[1:]
        fig2, ax2 = plt.subplots(figsize=(6,4))
        for cons in top_rules["consequent"]:
            temp = (
                merged_df
                .loc[
                    (merged_df["antecedent"] == selected_item) &
                    (merged_df["consequent"]  == cons)
                ]
                .drop_duplicates(["Month","consequent"])
                .set_index("Month")
                .reindex(month_order)
            )
            ax2.plot(month_order, temp["confidence"].fillna(0), marker="o", label=cons)
        ax2.set_ylabel("Confidence")
        ax2.set_xticklabels(month_order, rotation=45, ha="right")
        ax2.legend(fontsize="small", bbox_to_anchor=(1.05,1))
        st.pyplot(fig2)

    # Download filtered recommendations
    st.download_button(
        "📥 Download Recommendations CSV",
        top_rules.to_csv(index=False),
        "top_recommendations.csv"
    )
