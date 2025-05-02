import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

st.set_page_config(page_title="E-commerce Recommendation Dashboard", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

@st.cache_data
def load_rules():
    return pd.read_csv("rules_final.csv")

@st.cache_data
def load_and_aggregate_sales():
    df = pd.read_csv("Filter.csv")
    # ensure TotalSpent
    if "TotalSpent" not in df.columns:
        df["TotalSpent"] = df["Quantity"] * df["UnitPrice"]
    summary = (
        df.groupby("Description")
          .agg(
              Total_Items = ("Quantity",  "sum"),
              Price       = ("UnitPrice", "mean"),
              Total_Spent = ("TotalSpent","sum"),
          )
          .reset_index()
    )
    return summary

@st.cache_data
def get_merged(rules, sales):
    # first merge antecedent → antecedent metrics
    m = rules.merge(
        sales.rename(columns={
            "Description":"Ant_Description",
            "Total_Items":"Ant_Total_Items",
            "Price":"Ant_Price",
            "Total_Spent":"Ant_Total_Spent"
        }),
        how="left",
        left_on="antecedent",
        right_on="Ant_Description"
    )
    # then merge consequent → consequent metrics
    m = m.merge(
        sales.rename(columns={
            "Description":"Con_Description",
            "Total_Items":"Total_Items",
            "Price":"Price",
            "Total_Spent":"Total_Spent"
        }),
        how="left",
        left_on="consequent",
        right_on="Con_Description"
    )
    # drop the helper description columns
    return m.drop(columns=["Ant_Description","Con_Description"], errors="ignore")

rules_df      = load_rules()
sales_summary = load_and_aggregate_sales()
merged_df     = get_merged(rules_df, sales_summary)

# ─── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("🔧 Filters")
    month     = st.selectbox("📅 Month", ["Any"] + list(calendar.month_name)[1:])
    rtype     = st.radio("🔀 Rule Type", ["All","color_swap","cross_category"])
    min_conf  = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift  = st.slider("📈 Min Lift",       1.0, 5.0, 1.2, 0.1)
    min_sup   = st.slider("📊 Min Support",    0.0, 0.1, 0.01, 0.005)
    min_cnt   = st.slider("🛒 Min Consequent Frequency", 1, 100, 5)
    sku_filt  = st.text_input("🔍 SKU contains")
    text_filt = st.text_input("🔍 Search Consequent")
    bidir     = st.checkbox("↔ Bidirectional")
    top_n     = st.slider("🔢 Top N", 1, 20, 10)
    sort_by   = st.radio("📌 Sort By", ["confidence","lift"])
    grp_by    = st.radio("🗂️ Group By", ["None","type","Month"])
    st.markdown("---")
    st.download_button(
        "📥 Download Merged Data",
        merged_df.to_csv(index=False),
        "merged_data.csv"
    )

# ─── Filtering & Recommendations ───────────────────────────────────────────────

def filter_rules(df):
    d = df.copy()
    if month!="Any":
        d = d[d["Month"]==month]
    if rtype!="All" and "type" in d.columns:
        d = d[d["type"]==rtype]
    d = d[
        (d["confidence"]>=min_conf)
        & (d["lift"]>=min_lift)
        & (d["support"]>=min_sup)
    ]
    d = d.drop_duplicates(["antecedent","consequent"])
    d["cons_count"] = d.groupby("antecedent")["consequent"].transform("count")
    d = d[d["cons_count"]>=min_cnt]
    if sku_filt:
        d = d[d["SKU"].astype(str).str.contains(sku_filt,case=False)]
    return d

filtered = filter_rules(merged_df)
ants      = sorted(filtered["antecedent"].unique())

st.subheader("🛍️ Select a Product")
selected = st.selectbox("", ants)

def top_for(item):
    d = filtered.copy()
    mask = (d["antecedent"]==item)
    if bidir:
        mask |= (d["consequent"]==item)
    top = d[mask & (d["antecedent"]!=d["consequent"])]
    top = top.sort_values(sort_by,ascending=False).head(top_n)
    if text_filt:
        top = top[top["consequent"].str.contains(text_filt,case=False,na=False)]
    return top

top_rules = top_for(selected)

# ─── Display ───────────────────────────────────────────────────────────────────

col1,col2 = st.columns([2,1])
with col1:
    if not top_rules.empty:
        st.subheader(f"🔎 Top {len(top_rules)} for {selected}")
        cols = ["consequent","support","confidence","lift","Total_Items","Price","Total_Spent"]
        if grp_by!="None":
            for g, grp in top_rules.groupby(grp_by):
                st.markdown(f"#### 🔸 {g}")
                st.dataframe(grp[cols])
        else:
            st.dataframe(top_rules[cols])

        st.markdown("### 📘 Natural Language")
        for _,r in top_rules.iterrows():
            st.markdown(
              f"- If you buy **{selected}**, you also buy **{r['consequent']}**  "
              f"(conf {r['confidence']:.2f}, lift {r['lift']:.2f}, "
              f"qty {int(r['Total_Items'])}, spent ${r['Total_Spent']:.2f})"
            )
    else:
        st.warning("No recs for these filters.")

with col2:
    if not top_rules.empty:
        st.markdown("### 📊 Confidence")
        fig,ax=plt.subplots()
        ax.barh(top_rules["consequent"],top_rules["confidence"],color=plt.cm.Greens(top_rules["confidence"]))
        st.pyplot(fig)

        st.markdown("### 📈 Trend")
        months = list(calendar.month_name)[1:]
        tr = (
            merged_df[
                (merged_df["antecedent"]==selected)
               &(merged_df["consequent"].isin(top_rules["consequent"]))
            ]
            .drop_duplicates(["Month","consequent"])
            .set_index("Month")
            .reindex(months)
            .reset_index()
        )
        if not tr.empty:
            fig,ax=plt.subplots()
            for cons in tr["consequent"].unique():
                tmp=tr[tr["consequent"]==cons]
                ax.plot(tmp["Month"],tmp["confidence"],marker="o",label=cons)
            ax.legend(fontsize="small", bbox_to_anchor=(1.05,1))
            plt.xticks(rotation=45)
            st.pyplot(fig)

if not top_rules.empty:
    st.download_button(
        "📥 Download Recommendations",
        top_rules.to_csv(index=False),
        "recommendations.csv"
    )
