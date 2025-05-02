import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

# ----------------- Data Loading & Aggregation -----------------
@st.cache_data
def load_rules():
    return pd.read_csv("rules_final.csv")

@st.cache_data
def load_sales_data():
    return pd.read_csv("Filter.csv")

@st.cache_data
def aggregate_sales_data(sales_df: pd.DataFrame) -> pd.DataFrame:
    # Ensure TotalSpent
    if 'TotalSpent' not in sales_df.columns:
        sales_df['TotalSpent'] = sales_df['Quantity'] * sales_df['UnitPrice']
    # Aggregate by Description
    agg = (
        sales_df
        .groupby('Description')
        .agg(
            Total_Items=('Quantity', 'sum'),
            Price=('UnitPrice', 'mean'),
            Total_Spent=('TotalSpent', 'sum')
        )
        .reset_index()
    )
    return agg

@st.cache_data
def merge_data(rules_df: pd.DataFrame, sales_agg: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(
        rules_df,
        sales_agg,
        how='left',
        left_on='antecedent',
        right_on='Description'
    )
    return merged

# ----------------- Recommendation Logic -----------------
def get_recommendations(
    df, month, rec_type, min_conf, min_lift, min_support,
    top_n, sort_by, bidirectional, sku_filter, min_conseq_freq
):
    sub = df.copy()
    if month != "Any":
        sub = sub[sub['Month'] == month]
    if 'type' in sub.columns and rec_type != 'All':
        sub = sub[sub['type'] == rec_type]
    sub = sub[(sub['confidence'] >= min_conf) &
              (sub['lift'] >= min_lift) &
              (sub['support'] >= min_support)]
    sub = sub.drop_duplicates(['antecedent','consequent'])
    if sku_filter:
        sub = sub[sub['SKU'].astype(str).str.contains(sku_filter, case=False)]
    if 'consequent_count' in sub.columns:
        sub = sub[sub['consequent_count'] >= min_conseq_freq]
    # items with at least top_n rules
    counts = sub['antecedent'].value_counts()
    available = sorted(counts[counts >= top_n].index.tolist())
    return sub, available


def filter_top_rules(df, item, bidirectional, top_n, sort_by):
    sub = df.copy()
    if bidirectional:
        sub = sub[(sub['antecedent']==item) | (sub['consequent']==item)]
    else:
        sub = sub[sub['antecedent']==item]
    sub = sub[sub['antecedent'] != sub['consequent']]
    return sub.sort_values(sort_by, ascending=False).head(top_n)

# ----------------- App Configuration -----------------
st.set_page_config(
    page_title="E-commerce Recommendation Dashboard",
    layout="wide",
)
st.title("📦 E-commerce Recommendation Dashboard")

# ----------------- Sidebar Filters -----------------
with st.sidebar:
    st.header("🔧 Filters")
    with st.expander("📊 Rule thresholds", expanded=True):
        month = st.selectbox(
            "📅 Filter by Month",
            options=["Any"] + list(calendar.month_name)[1:],
            help="Show rules only for the selected month"
        )
        rec_type = st.radio(
            "🔀 Rule Type",
            options=["All","color_swap","cross_category"],
            help="Filter by rule category"
        )
        min_conf = st.slider(
            "📉 Min Confidence", 0.0, 1.0, 0.4, 0.05,
            help="Minimum confidence threshold"
        )
        min_lift = st.slider(
            "📈 Min Lift", 1.0, 5.0, 1.2, 0.1,
            help="Minimum lift threshold"
        )
        min_support = st.slider(
            "📊 Min Support", 0.0, 0.1, 0.01, 0.005,
            help="Minimum support threshold"
        )
    with st.expander("🔍 Text & SKU search"):
        sku_filter = st.text_input(
            "🔍 SKU Contains (optional)",
            help="Filter only rules whose SKU contains this text"
        )
        keyword = st.text_input(
            "🔍 Search Consequent Text",
            help="Search within the consequent item name"
        )
    with st.expander("⚙️ Aggregation & Sorting"):        
        bidirectional = st.checkbox(
            "↔ Bidirectional Match", value=False,
            help="Include rules in both directions"
        )
        top_n = st.slider(
            "🔢 Top N Recs", 1, 20, 10,
            help="Number of recommendations to show"
        )
        sort_by = st.radio(
            "📌 Sort By", ["confidence","lift"],
            help="Sort recommendations by this metric"
        )
        group_by = st.radio(
            "🗂️ Group By", ["None","type","Month"],
            help="Group results in sections"
        )
        min_conseq_freq = st.slider(
            "🛒 Consequent Frequency ≥", 1, 100, 5,
            help="Minimum baskets for a consequent item"
        )

# ----------------- Data Preparation -----------------
rules_df      = load_rules()
sales_df      = load_sales_data()
sales_agg     = aggregate_sales_data(sales_df)
merged_df     = merge_data(rules_df, sales_agg)

# ----------------- Full Data Download -----------------
st.download_button(
    "📥 Download Full Merged Data",
    merged_df.to_csv(index=False),
    file_name="merged_rules_sales.csv",
    help="Download the entire merged rule+sales dataset"
)

# ----------------- Available Products & Selection -----------------
filtered_df, available_items = get_recommendations(
    merged_df,
    month, rec_type, min_conf, min_lift, min_support,
    top_n, sort_by, bidirectional, sku_filter, min_conseq_freq
)
selected_item = st.selectbox(
    "🛍️ Select a Product to Analyze",
    options=available_items,
    help="Pick the antecedent product you want recommendations for"
)

# ----------------- KPI Summary -----------------
item_data = merged_df[merged_df['antecedent']==selected_item]
k1, k2, k3 = st.columns(3)
k1.metric("Baskets",   f"{int(item_data['consequent_count'].sum())}")
k2.metric("Avg Conf",  f"{item_data['confidence'].mean():.2f}")
k3.metric("Revenue",   f"£{item_data['Total_Spent'].sum():,.0f}")

# ----------------- Build Recommendations -----------------
top_rules = filter_top_rules(
    filtered_df, selected_item,
    bidirectional, top_n, sort_by
)
if keyword:
    top_rules = top_rules[top_rules['consequent'].str.contains(keyword, case=False, na=False)]

# ----------------- Display Table -----------------
st.subheader(f"🔎 Top {len(top_rules)} Recommendations for `{selected_item}`")

if not top_rules.empty:
    styled = (
        top_rules[ ['consequent','support','confidence','lift','Total_Items','Total_Spent'] ]
        .style
        .background_gradient(subset=['confidence'], cmap='Greens')
        .background_gradient(subset=['lift'],       cmap='Oranges')
    )
    st.dataframe(styled, use_container_width=True)
else:
    st.warning("No recommendations available for this selection.")

# ----------------- Natural Language Rules -----------------
if not top_rules.empty:
    st.markdown("### 📘 Natural Language Rules")
    for _, r in top_rules.iterrows():
        direction = "buys" if r['antecedent']==selected_item else "is also bought with"
        st.markdown(
            f"- If someone **{direction}** `{selected_item}`, they often buy **{r['consequent']}** "
            f"(conf: `{r['confidence']:.2f}`, lift: `{r['lift']:.2f}`, "
            f"items: `{r['Total_Items']}`, spent: `£{r['Total_Spent']:.0f}`)"
        )

# ----------------- Confidence Bar & Trend Chart -----------------
col1, col2 = st.columns([2,1])
with col1:
    if not top_rules.empty:
        st.markdown("### 📊 Confidence Bar Chart")
        fig, ax = plt.subplots()
        plot_data = top_rules.sort_values('confidence', ascending=True)
        ax.barh(plot_data['consequent'], plot_data['confidence'], color=plt.cm.Greens(plot_data['confidence']))
        ax.set_xlabel('Confidence')
        ax.set_ylabel('Consequent Item')
        st.pyplot(fig)
with col2:
    if not top_rules.empty:
        st.markdown("### 📈 Trend Chart")
        month_order = list(calendar.month_name)[1:]
        trend = merged_df[
            (merged_df['antecedent']==selected_item) &
            (merged_df['consequent'].isin(top_rules['consequent']))
        ]
        trend = trend.drop_duplicates(['Month','consequent'])
        fig, ax = plt.subplots()
        for c in trend['consequent'].unique():
            temp = trend[trend['consequent']==c].set_index('Month').reindex(month_order).reset_index()
            ax.plot(temp['Month'], temp['confidence'], marker='o', label=c)
        ax.set_ylabel('Confidence')
        ax.set_title(f"Monthly confidence trends for '{selected_item}'")
        ax.legend(fontsize='small', bbox_to_anchor=(1.0,1.0))
        st.pyplot(fig)

# ----------------- Download Recommendations -----------------
if not top_rules.empty:
    st.download_button(
        "📥 Download Recommendations",
        top_rules.to_csv(index=False),
        file_name="recommendations.csv",
        use_container_width=True
    )
