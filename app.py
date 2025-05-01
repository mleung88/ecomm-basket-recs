import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar
import os

# Load rules
@st.cache_data
def load_rules():
    df = pd.read_csv("rules_final.csv")
    return df

# Load transaction data (sales data)
@st.cache_data
def load_sales_data():
    sales_df = pd.read_csv("Filter.csv")
    return sales_df
    
# Load the rules and sales data
rules_df = load_rules()
sales_data = load_sales_data()

# Merge the rules and sales data
merged_df = pd.merge(rules_df, sales_data[['Description', 'Total_Items', 'Price', 'Total_Spent']], 
                     left_on='antecedent', right_on='Description', how='left')

# Print merged data to check if the Total Items and Spend are correctly added
st.write(merged_df.head())  # This will show the merged data, which should include Total_Items and Total_Spent

# Filter the recommendations
filtered_df, available_items = get_recommendations(
    rules_df, None, month, rec_type, min_conf, min_lift, min_support,
    top_n, sort_by, bidirectional, sku_filter, min_conseq_freq
)

# Merge sales data for the selected item
item_sales = sales_data[sales_data['Description'] == selected_item]
if not item_sales.empty:
    total_items_sold = item_sales['Total_Items'].values[0]
    total_spent = item_sales['Total_Spent'].values[0]
else:
    total_items_sold = 0
    total_spent = 0

# Display the total items sold and total spent for the selected item
st.markdown(f"### 📊 Total Items Sold for `{selected_item}`: {total_items_sold}")
st.markdown(f"### 💰 Total Spent on `{selected_item}`: ${total_spent:,.2f}")

# Display the top recommendations
top_rules = filter_top_rules(filtered_df, selected_item, bidirectional, top_n, sort_by)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"🔎 Top Recommendations for `{selected_item}`")
    st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift', 'Total_Items', 'Total_Spent']])

    # Display rules in natural language
    if not top_rules.empty:
        st.markdown("### 📘 Natural Language Rules")
        for _, row in top_rules.iterrows():
            direction = "buys" if row['antecedent'] == selected_item else "is also bought with"
            st.markdown(f"- If someone **{direction}** `{selected_item}`, they often buy **{row['consequent']}** (conf: `{row['confidence']:.2f}`, lift: `{row['lift']:.2f}`)")

with col2:
    st.markdown("### 📊 Confidence Bar Chart")
    plot_data = top_rules.sort_values("confidence", ascending=True)
    fig, ax = plt.subplots()
    bars = ax.barh(plot_data["consequent"], plot_data["confidence"], color=plt.cm.Greens(plot_data["confidence"]))
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)

# Optional: Allow user to download the recommendations
if not top_rules.empty:
    st.download_button("📥 Download Recommendations CSV", top_rules.to_csv(index=False), "recommendations.csv")
else:
    st.warning("No recommendations available for this selection.")
