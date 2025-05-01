st.set_page_config(page_title="E-commerce Basket Recommender", layout="wide")
st.title("📦 E-commerce Recommendation Dashboard")

# Sidebar filters
with st.sidebar:
    st.header("🔧 Filters")
    selected_item = st.selectbox("🛍️ Select a Product to Analyze", available_items)
    month = st.selectbox("📅 Filter by Month", ["Any"] + list(calendar.month_name)[1:])
    min_conf = st.slider("📉 Min Confidence", 0.0, 1.0, 0.4, 0.05)
    min_lift = st.slider("📈 Min Lift", 1.0, 5.0, 1.2, 0.1)
    min_support = st.slider("📊 Min Support", 0.0, 0.1, 0.01, 0.005)
    min_conseq_freq = st.slider("🛒 Consequent Frequency ≥", 1, 100, 5)
    sku_filter = st.text_input("🔍 SKU Contains (optional)")
    top_n = st.slider("🔢 Top N Recs", 1, 20, 10)
    group_by = st.radio("🗂️ Group By", ["None", "type", "Month"])

# Load the rules
rules_df = load_rules()

# Filter recommendations
filtered_df, available_items = get_recommendations(
    rules_df, selected_item, month, min_conf, min_lift, min_support,
    top_n, sku_filter, min_conseq_freq
)

# Filter the top rules
top_rules = filter_top_rules(filtered_df, selected_item)

# Display recommendations in main area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"🔎 Top Recommendations for `{selected_item}`")
    if group_by != "None":
        for group, df_g in top_rules.groupby(group_by):
            st.markdown(f"### 🔸 {group}")
            st.dataframe(df_g[['consequent', 'support', 'confidence', 'lift']])
    else:
        st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift']])

with col2:
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
        ax.set_title(f"Monthly confidence trends for '{selected_item}'")
        ax.legend()
        st.pyplot(fig)

# Download button
if not top_rules.empty:
    st.download_button("📥 Download CSV", top_rules.to_csv(index=False), "recommendations.csv")
else:
    st.warning("No recommendations available for this selection.")
