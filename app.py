import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

#
# ─── DATA LOADING & MERGING ─────────────────────────────────────────────────────
#

@st.cache_data
def load_rules():
    return pd.read_csv("rules_final.csv")


@st.cache_data
def load_sales():
    df = pd.read_csv("Filter.csv")
    # compute TotalSpent if not present
    if "TotalSpent" not in df.columns:
        df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]
    # aggregate to one row per Description
    summary = (
        df.groupby("Description")
          .agg(
              Total_Items = ("Quantity", "sum"),
              Price       = ("UnitPrice", "mean"),
              Total_Spent = ("TotalSpent", "sum"),
          )
          .reset_index()
    )
    return summary


@st.cache_data
def merge_data(rules, sales):
    merged = pd.merge(
        rules, sales,
        how    = "left",
        left_on  = "antecedent",
        right_on = "Description",
    )
    return merged


rules_df = load_rules()
sales_df = load_sales()
merged_df = merge_data(rules_df, sales_df)

# let folks download the full merged table
with st.sidebar.expander("📥 Download Full Merged Data", expanded=False):
    st.download_button(
        label="Download CSV",
        data=merged_df.to_csv(index=False),
        file_name="merged_recommendations.csv",
    )


#
# ─── SIDEBAR FILTERS ──────────────────────────────────────────────────────────────
#

with st.sidebar:
    st.header("🔧 Filters")

    month         = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    rec_type      = st.radio("🔀 Rule Type", ["All", "color_swap", "cross_category"])
    min_conf      = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift      = st.slider("📈 Min Lift", 1.0, 5.0, 1.2, 0.1)
    min_support   = st.slider("📊 Min Support", 0.0, 0.1, 0.01, 0.005)
    min_baskets   = st.slider("🛒 Consequent Frequency ≥", 1, 100, 5)
    sku_filter    = st.text_input("🔍 SKU Contains (optional)")
    text_filter   = st.text_input("🔍 Search Consequent Text")
    bidir         = st.checkbox("↔ Bidirectional Match", value=False)
    top_n         = st.slider("🔢 Top N Recs", 1, 20, 10)
    sort_by       = st.radio("📌 Sort By", ["confidence", "lift"])
    group_by      = st.radio("🗂️ Group By", ["None", "type", "Month"])


#
# ─── RECOMMENDATION LOGIC ─────────────────────────────────────────────────────────
#

def get_recs(df):
    d = df.copy()
    # month filter
    if month != "Any":
        d = d[d["Month"] == month]
    # rule type filter
    if "type" in d.columns and rec_type != "All":
        d = d[d["type"] == rec_type]
    # numeric thresholds
    d = d[
        (d["confidence"] >= min_conf) &
        (d["lift"]       >= min_lift) &
        (d["support"]    >= min_support)
    ]
    # drop exact duplicates
    d = d.drop_duplicates(subset=["antecedent","consequent"])
    # compute how many consequents each antecedent has
    d["consequent_count"] = d.groupby("antecedent")["consequent"].transform("count")
    # basket size filter
    d = d[d["consequent_count"] >= min_baskets]
    # SKU substring filter
    if sku_filter:
        d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    return d

def filter_top(d, item):
    df0 = d[
        (d["antecedent"] == item) |
        (bidir & (d["consequent"] == item))
    ].copy()
    df0 = df0[df0["antecedent"] != df0["consequent"]]
    df0 = df0.sort_values(sort_by, ascending=False).head(top_n)
    if text_filter:
        df0 = df0[df0["consequent"].str.contains(text_filter, case=False, na=False)]
    return df0

# apply all rec filters and pull available antecedents
filtered_df = get_recs(merged_df)
available_items = sorted(filtered_df["antecedent"].unique())

#
# ─── MAIN UI ──────────────────────────────────────────────────────────────────────
#

st.subheader("🛍️ Select a Product to Analyze")
selected = st.selectbox("", available_items)

top_rules = filter_top(filtered_df, selected)

#
# ─── METRICS ──────────────────────────────────────────────────────────────────────
#

if top_rules.empty:
    st.warning("No recommendations match your filters.")
else:
    baskets = int(top_rules["consequent_count"].sum())
    st.metric("🧺 Total Potential Baskets", f"{baskets}")
    # you could also do: len(top_rules) if you just want count_of_rows

#
# ─── RECS TABLE ───────────────────────────────────────────────────────────────────
#

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"🔎 Top {len(top_rules)} Recommendations for `{selected}`")
    if group_by != "None" and group_by in top_rules.columns:
        for grp, sub in top_rules.groupby(group_by):
            st.markdown(f"#### 🔸 {grp}")
            st.dataframe(sub[
                ["consequent","support","confidence","lift",
                 "Total_Items","Price","Total_Spent"]
            ])
    else:
        st.dataframe(top_rules[[
            "consequent","support","confidence","lift",
            "Total_Items","Price","Total_Spent"
        ]])

    # natural language
    st.markdown("### 📘 Natural Language Rules")
    for _,r in top_rules.iterrows():
        dirn = "buys" if r["antecedent"] == selected else "also buys"
        st.markdown(
            f"- If someone **{dirn}** `{selected}`, they often buy **{r['consequent']}** "
            f"(conf: {r['confidence']:.2f}, lift: {r['lift']:.2f}, "
            f"items: {int(r['Total_Items'])}, spent: ${r['Total_Spent']:.2f})"
        )

with col2:
    # confidence bar chart
    st.markdown("### 📊 Confidence Bar Chart")
    fig,ax = plt.subplots()
    bars = ax.barh(
        top_rules["consequent"],
        top_rules["confidence"],
        color=plt.cm.Greens(top_rules["confidence"])
    )
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)

    # trend chart
    st.markdown("### 📈 Monthly Trend Chart")
    months = list(calendar.month_name)[1:]
    tr = merged_df[
        (merged_df["antecedent"] == selected) &
        (merged_df["consequent"].isin(top_rules["consequent"]))
    ].drop_duplicates(subset=["Month","consequent"])
    if not tr.empty:
        fig,ax = plt.subplots()
        for cons in tr["consequent"].unique():
            tmp = tr[tr["consequent"]==cons]
            tmp = tmp.set_index("Month").reindex(months).reset_index()
            ax.plot(tmp["Month"], tmp["confidence"], marker="o", label=cons)
        ax.set_ylabel("Confidence")
        ax.set_xticklabels(months, rotation=45, ha="right")
        ax.legend(fontsize="small", bbox_to_anchor=(1.05,1))
        st.pyplot(fig)

#
# ─── DOWNLOAD RECS ────────────────────────────────────────────────────────────────
#

if not top_rules.empty:
    st.download_button(
        "📥 Download Recommendations CSV",
        top_rules.to_csv(index=False),
        file_name="top_recommendations.csv"
    )
