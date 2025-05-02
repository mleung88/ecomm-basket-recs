import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar
import os

# Load rules
@st.cache_data
def load_rules():
    df = pd.read_csv("rules_final.csv")  # Ensure rules_final.csv is available
    return df

# Load transaction data (sales data)
@st.cache_data
def load_sales_data():
    sales_df = pd.read_csv("Filter.csv")  # Ensure Filter.csv is available
    return sales_df

# Add Total Spent
    sales_data['TotalSpent'] = sales_data['Quantity'] * sales_data['UnitPrice']
    sales_data = (
        sales_data
          .groupby('Description')
          .agg(
             Total_Items = ('Quantity',  'sum'),
             Price = ('UnitPrice', 'mean'),
             Total_Spent = ('TotalSpent', 'sum'), # Calculate Total_Spent using the existing TotalSpent column
          )
          .reset_index()
    )
# Merge rule data and sales data
def merge_data(rules_df, sales_df):
    merged_df = pd.merge(rules_df, sales_df, how="left", left_on="antecedent", right_on="Description")
    return merged_df

def get_recommendations(df, item, month, rec_type, min_conf, min_lift, min_support, top_n, sort_by, bidirectional, sku_filter, min_conseq_freq):
    if month != "Any":
        df = df[df['Month'] == month]

    if "type" in df.columns and rec_type != "All":
        df = df[df['type'] == rec_type]

    df = df[(df['confidence'] >= min_conf) & (df['lift'] >= min_lift) & (df['support'] >= min_support)]
    df = df.drop_duplicates(subset=["antecedent", "consequent"], keep="first")

    if sku_filter:
        df = df[df['SKU'].astype(str).str.contains(sku_filter, case=False)]

    if "consequent_count" in df.columns:
        df = df[df['consequent_count'] >= min_conseq_freq]

    filtered_items = df['antecedent'].value_counts()
    filtered_items = filtered_items[filtered_items >= top_n].index.tolist()
    filtered_items = sorted(filtered_items)

    return df, filtered_items

def filter_top_rules(df, item, bidirectional, top_n, sort_by):
    if bidirectional:
        df = df[(df['antecedent'] == item) | (df['consequent'] == item)].copy()
    else:
        df = df[df['antecedent'] == item].copy()

    df = df[df['antecedent'] != df['consequent']]
    return df.sort_values(sort_by, ascending=False).head(top_n)

# App starts
st.set_page_config(page_title="E-commerce Basket Recommender", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

with st.sidebar:
    st.header("🔧 Filters")
    month = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    rec_type = st.radio("🔀 Rule Type", ["All", "color_swap", "cross_category"])
    min_conf = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift = st.slider("📈 Min Lift", 1.0, 5.0, 1.2, 0.1)
    min_support = st.slider("📊 Min Support", 0.0, 0.1, 0.01, 0.005)
    min_conseq_freq = st.slider("🛒 Consequent Frequency ≥", 1, 100, 5)
    sku_filter = st.text_input("🔍 SKU Contains (optional)")
    keyword = st.text_input("🔍 Search Consequent Text")
    bidirectional = st.checkbox("↔ Bidirectional Match", value=False)
    top_n = st.slider("🔢 Top N Recs", 1, 20, 10)
    sort_by = st.radio("📌 Sort By", ["confidence", "lift"])
    group_by = st.radio("🗂️ Group By", ["None", "type", "Month"])

rules_df = load_rules()
sales_df = load_sales_data()

# Merge rule data and sales data
def merge_data(rules_df, sales_df):
    # First check if 'Total_Spent' exists in sales data
    if 'Total_Spent' not in sales_df.columns:
        sales_df['Total_Spent'] = sales_df['Quantity'] * sales_df['UnitPrice']  # Compute Total_Spent
        st.success("Total_Spent column successfully added!")
        
    # Perform merge
    merged_df = pd.merge(rules_df, sales_df, how="left", left_on="antecedent", right_on="Description")

    # Check if Total_Spent is in the merged data
    if 'Total_Spent' not in merged_df.columns:
        st.error("Total_Spent column is missing from the merged dataframe.")

    return merged_df

# Show the merged data (you can modify this line to display only the columns you need)
st.dataframe(merged_df[['consequent', 'support', 'confidence', 'lift', 'Total_Items', 'Total_Spent']])


filtered_df, available_items = get_recommendations(
    merged_data, None, month, rec_type, min_conf, min_lift, min_support,
    top_n, sort_by, bidirectional, sku_filter, min_conseq_freq
)

selected_item = st.selectbox("🛍️ Select a Product to Analyze", available_items)
top_rules = filter_top_rules(filtered_df, selected_item, bidirectional, top_n, sort_by)

if keyword:
    top_rules = top_rules[top_rules['consequent'].str.contains(keyword, case=False, na=False)]

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"🔎 Top {len(top_rules)} Recommendations for `{selected_item}`")
    if group_by != "None" and group_by in top_rules.columns:
        for group, df_g in top_rules.groupby(group_by):
            st.markdown(f"### 🔸 {group}")
            st.dataframe(df_g[['consequent', 'support', 'confidence', 'lift', 'Total_Items', 'Total_Spent']])
    else:
        st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift', 'Total_Items', 'Total_Spent']])

    if not top_rules.empty:
        st.markdown("### 📘 Natural Language Rules")
        for _, row in top_rules.iterrows():
            direction = "buys" if row['antecedent'] == selected_item else "is also bought with"
            st.markdown(f"- If someone **{direction}** `{selected_item}`, they often buy **{row['consequent']}** (conf: `{row['confidence']:.2f}`, lift: `{row['lift']:.2f}`, total items: `{row['Total_Items']}`, total spent: `{row['Total_Spent']}`)")

with col2:
    if not top_rules.empty:
        st.markdown("### 📊 Confidence Bar Chart")
        plot_data = top_rules.sort_values("confidence", ascending=True)
        fig, ax = plt.subplots()
        bars = ax.barh(plot_data["consequent"], plot_data["confidence"], color=plt.cm.Greens(plot_data["confidence"]))
        ax.set_xlabel("Confidence")
        ax.set_ylabel("Consequent Item")
        st.pyplot(fig)

        st.markdown("### 📈 Trend Chart")
        month_order = list(calendar.month_name)[1:]
        trend_data = merged_data[(merged_data['antecedent'] == selected_item) & (merged_data['consequent'].isin(top_rules['consequent']))]

    if not trend_data.empty:
        # Drop duplicates before reindexing to prevent errors
        trend_data = trend_data.drop_duplicates(subset=['Month', 'consequent'])

        fig, ax = plt.subplots()
        for cons in trend_data['consequent'].unique():
            temp = trend_data[trend_data['consequent'] == cons]
            temp = temp.set_index('Month').reindex(month_order).reset_index()
            ax.plot(temp['Month'], temp['confidence'], label=cons, marker='o')
        ax.set_ylabel("Confidence")
        ax.set_title(f"Monthly confidence trends for '{selected_item}'")
        ax.legend()
        st.pyplot(fig)

if not top_rules.empty:
    st.download_button("📥 Download CSV", top_rules.to_csv(index=False), "recommendations.csv")
else:
    st.warning("No recommendations available for this selection.")
