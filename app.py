import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

# 1) LOAD & CACHE RULES
@st.cache_data
def load_rules():
    return pd.read_csv("rules_final.csv")

# 2) LOAD & AGGREGATE SALES
@st.cache_data
def load_and_aggregate_sales():
    df = pd.read_csv("Filter.csv")
    df["Total_Spent_Row"] = df["Quantity"] * df["UnitPrice"]
    agg = (
        df
        .groupby("Description", as_index=False)
        .agg(
            Total_Items=("Quantity", "sum"),
            Price=("UnitPrice", "mean"),
            Total_Spent=("Total_Spent_Row", "sum"),
        )
    )
    return agg

# 3) FILTERING & TOP-N
def get_recommendations(df, month, rec_type, min_conf, min_lift, min_sup, min_freq, top_n, bidir, sku_filter):
    d = df.copy()
    if month != "Any":
        d = d[d["Month"] == month]
    if rec_type != "All" and "type" in d:
        d = d[d["type"] == rec_type]
    d = d[
        (d["confidence"] >= min_conf) &
        (d["lift"]       >= min_lift) &
        (d["support"]    >= min_sup)
    ]
    if sku_filter:
        d = d[d["SKU"].astype(str).str.contains(sku_filter, case=False)]
    if "consequent_count" in d:
        d = d[d["consequent_count"] >= min_freq]
    d = d.drop_duplicates(["antecedent","consequent"])
    cnt = d["antecedent"].value_counts()
    valid = cnt[cnt >= top_n].index.sort_values().tolist()
    return d, valid

def filter_top_rules(df, selected, top_n, sort_by, bidir):
    d = df.copy()
    if bidir:
        d = d[(d["antecedent"]==selected)|(d["consequent"]==selected)]
    else:
        d = d[d["antecedent"]==selected]
    d = d[d["antecedent"] != d["consequent"]]
    return d.sort_values(sort_by, ascending=False).head(top_n)

# 4) BUILD UI
st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

with st.sidebar:
    st.header("⚙️ Rule thresholds")
    month       = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    rec_type    = st.radio("🔀 Rule Type", ["All","color_swap","cross_category"])
    min_conf    = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift    = st.slider("📈 Min Lift",       1.0, 5.0, 1.2, 0.1)
    min_sup     = st.slider("📊 Min Support",    0.0, 0.1, 0.01,0.005)
    min_freq    = st.slider("🛒 Consequent Frequency ≥", 1,100,5)
    sku_filter  = st.text_input("🔍 SKU Contains (opt.)")
    bidir       = st.checkbox("↔ Bidirectional Match", value=False)
    top_n       = st.slider("🔢 Top N Recs", 1,20,10)
    sort_by     = st.radio("📌 Sort By", ["confidence","lift"])

rules_df  = load_rules()
sales_agg = load_and_aggregate_sales()

# merge metrics onto each consequent
rules_with_sales = pd.merge(
    rules_df,
    sales_agg,
    left_on="consequent",
    right_on="Description",
    how="left"
).drop(columns=["Description"])

filtered_df, products = get_recommendations(
    rules_with_sales,
    month, rec_type, min_conf, min_lift, min_sup,
    min_freq, top_n, bidir, sku_filter
)

selected = st.selectbox("🛍️ Select a Product to Analyze", products)
top_rules = filter_top_rules(filtered_df, selected, top_n, sort_by, bidir)

if not top_rules.empty:
    # ensure each consequent carries its own sales metrics
    top_with_sales = pd.merge(
        top_rules,
        sales_agg,
        left_on="consequent",
        right_on="Description",
        how="left"
    ).drop(columns=["Description"])
else:
    top_with_sales = top_rules.copy()

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"🔎 Top {len(top_with_sales)} Recommendations for `{selected}`")
    st.dataframe(
        top_with_sales[[
            "consequent","support","confidence","lift",
            "Total_Items","Price","Total_Spent"
        ]]
    )
    if not top_with_sales.empty:
        st.markdown("### 📘 Natural Language Rules")
        for _, r in top_with_sales.iterrows():
            dir_ = "buys" if r["antecedent"]==selected else "is also bought with"
            st.markdown(
                f"- If someone **{dir_}** `{selected}`, they often buy **{r['consequent']}** "
                f"(conf: `{r['confidence']:.2f}`, lift: `{r['lift']:.2f}`, "
                f"qty: `{int(r['Total_Items'])}`, spent: `${r['Total_Spent']:.2f}`)"
            )

with col2:
    if not top_with_sales.empty:
        st.markdown("### 📊 Confidence Bar Chart")
        fig, ax = plt.subplots()
        top_with_sales.sort_values("confidence").plot.barh(
            x="consequent", y="confidence", legend=False, ax=ax
        )
        ax.set_xlabel("Confidence")
        st.pyplot(fig)

        st.markdown("### 📈 Monthly Confidence Trend")
        months = list(calendar.month_name)[1:]
        trend_df = rules_with_sales[
            (rules_with_sales["antecedent"]==selected)
            & (rules_with_sales["consequent"].isin(top_with_sales["consequent"]))
        ]
        if not trend_df.empty:
            # pivot_table with max to collapse duplicates
            pivot = (
                trend_df
                .pivot_table(
                    index="Month",
                    columns="consequent",
                    values="confidence",
                    aggfunc="max"
                )
                .reindex(months)
            )
            fig, ax = plt.subplots()
            for col in pivot.columns:
                series = pivot[col].dropna()
                if not series.empty:
                    ax.plot(series.index, series.values, marker="o", label=col)
            ax.set_ylabel("Confidence")
            ax.set_xticklabels(months, rotation=45)
            ax.legend(fontsize="small", bbox_to_anchor=(1.02,1))
            st.pyplot(fig)

if not top_with_sales.empty:
    st.download_button(
        "📥 Download Recommendations (CSV)",
        top_with_sales.to_csv(index=False),
        "recommendations.csv",
        mime="text/csv"
    )
