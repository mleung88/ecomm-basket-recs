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
    """
    Load precomputed association rules.
    rules_final.csv must contain at least: antecedent, consequent, confidence, lift, support, type, Month.
    """
    return pd.read_csv("rules_final.csv")

@st.cache_data
def load_and_aggregate_sales():
    """
    Load raw sales data and build a summary by product Description.
    Produces: Description, Total_Items, Price, Total_Spent.
    """
    df = pd.read_csv("Filter.csv")

    # Compute total spent if missing
    if "TotalSpent" not in df.columns:
        df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]

    # Group by Description to summarize sales metrics
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
    """
    Merge rules with sales summary on antecedent Description.
    """
    merged = pd.merge(
        rules,
        sales_summary,
        how="left",
        left_on="antecedent",
        right_on="Description"
    )
    # Drop the joined Description column (from sales_summary)
    merged = merged.drop(columns=["Description"], errors="ignore")
    return merged

# Load data
rules_df      = load_rules()
sales_summary = load_and_aggregate_sales()
merged_df     = merge_rules_sales(rules_df, sales_summary)

# ─── 2) SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 Filters")
    month      = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    rec_type   = st.radio("🔀 Rule Type", ["All","color_swap","cross_category"])
    min_conf   = st.slider("📉 Min Confidence",  0.0, 1.0, 0.4, 0.05)
    min_lift   = st.slider("📈 Min Lift",        1.0, 5.0, 1.2, 0.1)
    min_sup    = st.slider("📊 Min Support",     0.0, 0.1, 0.01, 0.005)
    min_count  = st.slider("🛒 Consequent Frequency ≥", 1, 100, 5)
    sku_filter = st.text_input("🔍 SKU Contains (optional)")
    text_filt  = st.text_input("🔍 Search Consequent Text")
    bidir      = st.checkbox("↔ Bidirectional Match")
    top_n      = st.slider("🔢 Top N Recs", 1, 20, 10)
    sort_by    = st.radio("📌 Sort By", ["confidence","lift"])
    group_by   = st.radio("🗂️ Group By", ["None","type","Month"])
    st.markdown("---")
    st.download_button(
        "📥 Download Full Merged Data",
        merged_df.to_csv(index=False),
        "merged_data.csv"
    )

# ─── 3) RECOMMENDATION LOGIC ────────────────────────────────────────────────────
def get_filtered_rules(df):
    d = df.copy()
    # month filter
    if month != "Any":
        d = d[d["Month"] == month]
    # rule type filter
    if rec_type != "All" and "type" in d.columns:
        d = d[d["type"] == rec_type]
    # numeric thresholds
    d = d[
        (d["confidence"] >= min_conf) &
        (d["lift"]       >= min_lift) &
        (d["support"]    >= min_sup)
    ]
    # dedupe and count consequents per antecedent
    d = d.drop_duplicates(subset=["antecedent","consequent"]).copy()
    d["consequent_count"] = d.groupby("antecedent")["consequent"].transform("count")
    d = d[d["consequent_count"] >= min_count]
    # SKU substring filter (if your rules CSV has a SKU column)
    if sku_filter and "SKU" in d.columns:
        d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    return d


def get_top_for_item(d, selected):
    cond = (d["antecedent"] == selected)
    if bidir:
        cond |= (d["consequent"] == selected)

    top = d[cond].copy()
    top = top[top["antecedent"] != top["consequent"]]
    top = top.sort_values(sort_by, ascending=False).head(top_n)
    # text search filter
    if text_filt:
        top = top[top["consequent"].str.contains(text_filt, case=False, na=False)]

    # drop any pre-existing metric columns to avoid suffix conflicts
    top = top.drop(columns=["Total_Items","Price","Total_Spent","Description"], errors="ignore")

    # bring in consequent's sales metrics by Description
    top = (
        top
        .merge(
            sales_summary[["Description","Total_Items","Price","Total_Spent"]],
            how="left",
            left_on="consequent",
            right_on="Description"
        )
        .drop(columns=["Description"], errors="ignore")
    )
    return top

# generate recommendations from filtered rules
filtered_df     = get_filtered_rules(merged_df)
available_items = sorted(filtered_df["antecedent"].unique())

st.subheader("🛍️ Select a Product to Analyze")
selected_item   = st.selectbox("", available_items)

top_rules = get_top_for_item(filtered_df, selected_item)

# ─── 4) DISPLAY RESULTS ────────────────────────────────────────────────────────────
col1, col2 = st.columns([2,1])

with col1:
    if not top_rules.empty:
        st.subheader(f"🔎 Top {len(top_rules)} Recs for `{selected_item}`")
        display_cols = [
            "consequent","support","confidence","lift",
            "Total_Items","Price","Total_Spent"
        ]
        if group_by != "None" and group_by in top_rules.columns:
            for grp, grp_df in top_rules.groupby(group_by):
                st.markdown(f"#### 🔸 {grp}")
                st.dataframe(grp_df[display_cols])
        else:
            st.dataframe(top_rules[display_cols])

        st.markdown("### 📘 Natural Language")
        for _, r in top_rules.iterrows():
            st.markdown(
                f"- People who bought **{selected_item}** also buy **{r['consequent']}** "
                f"(conf: {r['confidence']:.2f}, lift: {r['lift']:.2f}, "
                f"items: {int(r['Total_Items'])}, spent: ${r['Total_Spent']:.2f})"
            )

with col2:
    if not top_rules.empty:
        st.markdown("### 📊 Confidence Bar Chart")
        fig, ax = plt.subplots()
        ax.barh(top_rules["consequent"], top_rules["confidence"], color=plt.cm.Greens(top_rules["confidence"]))
        ax.set_xlabel("Confidence"); ax.set_ylabel("Consequent Item")
        st.pyplot(fig)

        st.markdown("### 📈 Trend Chart")
month_order = list(calendar.month_name)[1:]
fig, ax = plt.subplots()
# plot each consequent individually to avoid duplicate-index reindex errors
for cons in top_rules["consequent"]:
    temp = (
        merged_df.loc[
            (merged_df["antecedent"] == selected_item) &
            (merged_df["consequent"] == cons)
        ]
        .drop_duplicates(subset=["Month","consequent"])
        .set_index("Month")
        .reindex(month_order)
    )
    ax.plot(month_order, temp["confidence"].fillna(0), marker="o", label=cons)
ax.set_ylabel("Confidence")
ax.set_xticklabels(month_order, rotation=45, ha="right")
ax.legend(fontsize="small", bbox_to_anchor=(1.05,1))
st.pyplot(fig)

# ─── 5) DOWNLOAD TOP RECS ────────────────────────────────────────────────────────
if not top_rules.empty:
    st.download_button(
        "📥 Download Recommendations CSV",
        top_rules.to_csv(index=False),
        "top_recommendations.csv"
    )
