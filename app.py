import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

#
# ─── DATA LOADING & AGGREGATION ─────────────────────────────────────────────────
#

@st.cache_data
def load_rules():
    return pd.read_csv("rules_final.csv")


@st.cache_data
def load_sales():
    df = pd.read_csv("Filter.csv")
    # Compute TotalSpent if not already present
    if "TotalSpent" not in df.columns:
        df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]
    # Aggregate to one row per Description
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
        how="left",
        left_on="antecedent",
        right_on="Description"
    )
    return merged


rules_df  = load_rules()
sales_df  = load_sales()
merged_df = merge_data(rules_df, sales_df)


#
# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────────
#

with st.sidebar:
    st.header("🔧 Filters")

    month       = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    rec_type    = st.radio("🔀 Rule Type", ["All", "color_swap", "cross_category"])
    min_conf    = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift    = st.slider("📈 Min Lift",      1.0, 5.0, 1.2, 0.1)
    min_sup     = st.slider("📊 Min Support",   0.0, 0.1, 0.01, 0.005)
    min_baskets = st.slider("🛒 Consequent Frequency ≥", 1, 100, 5)
    sku_filter  = st.text_input("🔍 SKU Contains (optional)")
    text_filt   = st.text_input("🔍 Search Consequent Text")
    bidir       = st.checkbox("↔ Bidirectional Match", value=False)
    top_n       = st.slider("🔢 Top N Recs", 1, 20, 10)
    sort_by     = st.radio("📌 Sort By", ["confidence", "lift"])
    group_by    = st.radio("🗂️ Group By", ["None", "type", "Month"])

    st.markdown("---")
    st.download_button(
        "📥 Download Full Merged Data",
        merged_df.to_csv(index=False),
        "merged_data.csv"
    )


#
# ─── RECOMMENDATION LOGIC ────────────────────────────────────────────────────────
#

def get_recs(df):
    d = df.copy()
    if month != "Any":
        d = d[d["Month"] == month]
    if "type" in d.columns and rec_type != "All":
        d = d[d["type"] == rec_type]
    d = d[
        (d["confidence"] >= min_conf) &
        (d["lift"]       >= min_lift) &
        (d["support"]    >= min_sup)
    ]
    d = d.drop_duplicates(subset=["antecedent","consequent"])
    d["consequent_count"] = d.groupby("antecedent")["consequent"].transform("count")
    d = d[d["consequent_count"] >= min_baskets]
    if sku_filter:
        d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    return d


def filter_top(d, item):
    # keep rows where item is antecedent, or if bidir, where item is consequent
    df0 = d[
        (d["antecedent"] == item) |
        (bidir & (d["consequent"] == item))
    ].copy()
    df0 = df0[df0["antecedent"] != df0["consequent"]]
    df0 = df0.sort_values(sort_by, ascending=False).head(top_n)
    if text_filt:
        df0 = df0[df0["consequent"].str.contains(text_filt, case=False, na=False)]
    return df0


filtered_df     = get_recs(merged_df)
available_items = sorted(filtered_df["antecedent"].unique())

st.subheader("🛍️ Select a Product to Analyze")
selected = st.selectbox("", available_items)

top_rules = filter_top(filtered_df, selected)


#
# ─── METRIC ──────────────────────────────────────────────────────────────────────
#

if not top_rules.empty:
    # total baskets = sum of consequent_count over these top rules
    metric_val = int(top_rules["consequent_count"].sum())
    st.metric("🧺 Total Possible Baskets", f"{metric_val}")
else:
    st.warning("No recommendations available for these filters.")


#
# ─── MAIN TABLE & NATURAL LANGUAGE ───────────────────────────────────────────────
#

col1, col2 = st.columns([2,1])
with col1:
    if not top_rules.empty:
        st.subheader(f"🔎 Top {len(top_rules)} Recommendations for `{selected}`")
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

        st.markdown("### 📘 Natural Language Rules")
        for _, r in top_rules.iterrows():
            st.markdown(
                f"- People who bought **{selected}** also often buy **{r['consequent']}**  "
                f"(conf: {r['confidence']:.2f}, lift: {r['lift']:.2f}, "
                f"items: {int(r['Total_Items'])}, spent: ${r['Total_Spent']:.2f})"
            )

with col2:
    if not top_rules.empty:
        st.markdown("### 📊 Confidence Bar Chart")
        fig, ax = plt.subplots()
        ax.barh(
            top_rules["consequent"],
            top_rules["confidence"],
            color=plt.cm.Greens(top_rules["confidence"])
        )
        ax.set_xlabel("Confidence")
        ax.set_ylabel("Consequent Item")
        st.pyplot(fig)

        st.markdown("### 📈 Trend Chart")
        months = list(calendar.month_name)[1:]
        tr = (
            merged_df
            .query("antecedent == @selected and consequent in @list(top_rules.consequent)")
            .drop_duplicates(subset=["Month","consequent"])
            .set_index("Month")
            .reindex(months)
            .reset_index()
        )
        if not tr.empty:
            fig, ax = plt.subplots()
            for cons in tr["consequent"].unique():
                temp = tr[tr["consequent"] == cons]
                ax.plot(temp["Month"], temp["confidence"], marker="o", label=cons)
            ax.set_ylabel("Confidence")
            ax.set_xticklabels(months, rotation=45, ha="right")
            ax.legend(fontsize="small", bbox_to_anchor=(1.05,1))
            st.pyplot(fig)


#
# ─── DOWNLOAD TOP RECS ───────────────────────────────────────────────────────────
#

if not top_rules.empty:
    st.download_button(
        "📥 Download Recommendations CSV",
        top_rules.to_csv(index=False),
        "top_recommendations.csv"
    )
