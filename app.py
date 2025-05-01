# App starts
st.set_page_config(page_title="E-commerce Basket Recommender", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

# Sidebar filters
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

# Load rules and Filter data
rules_df, filter_df = load_rules()

# Merge the Filter data with the rules
aggregated_data = merge_data(rules_df, filter_df)

# Filter rules
filtered_df, available_items = get_recommendations(
    rules_df, None, month, rec_type, min_conf, min_lift, min_support,
    top_n, sort_by, bidirectional, sku_filter, min_conseq_freq
)

# Item selection
selected_item = st.selectbox("🛍️ Select a Product to Analyze", available_items)
top_rules = filter_top_rules(filtered_df, selected_item, bidirectional, top_n, sort_by)

# Keyword search
if keyword:
    top_rules = top_rules[top_rules['consequent'].str.contains(keyword, case=False, na=False)]

col1, col2 = st.columns([2, 1])

# Display the top recommendations
with col1:
    st.subheader(f"🔎 Top {len(top_rules)} Recommendations for `{selected_item}`")
    if group_by != "None" and group_by in top_rules.columns:
        for group, df_g in top_rules.groupby(group_by):
            st.markdown(f"### 🔸 {group}")
            st.dataframe(df_g[['consequent', 'support', 'confidence', 'lift']])
    else:
        st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift']])

    if not top_rules.empty:
        st.markdown("### 📘 Natural Language Rules")
        for _, row in top_rules.iterrows():
            direction = "buys" if row['antecedent'] == selected_item else "also bought with"
            st.markdown(f"- If someone **{direction}** `{selected_item}`, they often buy **{row['consequent']}** (confidence: `{row['confidence']:.2f}`, lift: `{row['lift']:.2f}`)")

# Show Total Spend and Quantity for the Selected Item
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
        trend_data = rules_df[(rules_df['antecedent'] == selected_item) & (rules_df['consequent'].isin(top_rules['consequent']))]
        if not trend_data.empty:
            fig, ax = plt.subplots()
            for cons in trend_data['consequent'].unique():
                temp = trend_data[trend_data['consequent'] == cons]
                temp = temp.set_index('Month').reindex(month_order).reset_index()
                ax.plot(temp['Month'], temp['confidence'], label=cons, marker='o')
            ax.set_ylabel("Confidence")
            ax.set_title(f"Monthly Confidence Trends for `{selected_item}`")
            ax.legend()
            st.pyplot(fig)

        # Show the Total Quantity and Total Spend for Each Recommended Item
        st.markdown("### 📊 Total Spend and Quantity for the Selected Item")
        agg_data = aggregated_data[aggregated_data['antecedent'] == selected_item]
        st.dataframe(agg_data[['consequent', 'total_quantity', 'total_spend']])

if not top_rules.empty:
    st.download_button("📥 Download Recommendations CSV", top_rules.to_csv(index=False), "recommendations.csv")
else:
    st.warning("No recommendations found for this item.")
