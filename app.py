import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar

# Load rules
@st.cache_data
def load_rules():
    df = pd.read_csv("data/rules_final.csv")
    return df

def get_recommendations(df, item, month, rec_type, min_conf, min_lift, min_support, top_n, sort_by, bidirectional):
    if month != "Any":
        df = df[df['Month'] == month]

    if "type" in df.columns and rec_type != "All":
        df = df[df['type'] == rec_type]

    # Apply thresholds
    df = df[(df['confidence'] >= min_conf) & (df['lift'] >= min_lift) & (df['support'] >= min_support)]

    # Drop duplicate pairs across months
    df = df.drop_duplicates(subset=["antecedent", "consequent"], keep="first")

    # Filter by item, directionally or bidirectionally
    if bidirectional:
        df = df[(df['antecedent'] == item) | (df['consequent'] == item)].copy()
    else:
        df = df[df['antecedent'] == item].copy()

    # Remove self-loops
    df = df[df['antecedent'] != df['consequent']]

    return df.sort_values(sort_by, ascending=False).head(top_n)

# App starts
st.set_page_config(page_title="E-commerce Basket Recommender", layout="wide")
st.title("🛍️ E-commerce Basket Recommender")

rules_df = load_rules()
month_order = list(calendar.month_name)[1:]  # January to December
months = ["Any"] + [m for m in month_order if m in rules_df['Month'].unique()]
items = sorted(set(rules_df['antecedent']).union(set(rules_df['consequent'])))
types = ["All"] + (rules_df['type'].dropna().unique().tolist() if "type" in rules_df.columns else [])

# Sidebar inputs
month = st.sidebar.selectbox("📅 Filter by Month", months)
selected_item = st.sidebar.selectbox("🛒 Choose an item", items)
rec_type = st.sidebar.radio("🔀 Rule Type", types)
min_conf = st.sidebar.slider("📉 Minimum Confidence", 0.0, 1.0, 0.4, 0.05)
min_lift = st.sidebar.slider("📈 Minimum Lift", 1.0, 5.0, 1.2, 0.1)
min_support = st.sidebar.slider("📊 Minimum Support", 0.0, 0.1, 0.01, 0.005)
bidirectional = st.sidebar.checkbox("↔ Include item as consequent too")
top_n = st.sidebar.slider("🔢 Top N Recommendations", 1, 20, 10)
sort_by = st.sidebar.radio("📌 Sort By", ["confidence", "lift"])

# Get recommendations
top_rules = get_recommendations(
    rules_df, selected_item, month, rec_type, min_conf, min_lift, min_support, top_n, sort_by, bidirectional
)

# Show results
st.markdown(f"## Top {len(top_rules)} recs for `{selected_item}`")
st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift']])

if not top_rules.empty:
    st.markdown("### 🧾 Interpreted Recommendations")
    for _, row in top_rules.iterrows():
        direction = "buys" if row['antecedent'] == selected_item else "is also bought with"
        st.write(f"If someone **{direction}** `{selected_item}`, they’re likely to also buy **{row['consequent']}** (confidence: {row['confidence']:.2f}, lift: {row['lift']:.2f})")

    st.markdown("### 📊 Confidence Chart")
    plot_data = top_rules.sort_values("confidence", ascending=True)
    fig, ax = plt.subplots()
    ax.barh(plot_data["consequent"], plot_data["confidence"], color="#4caf50")
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)

    st.download_button("📥 Download These Recs", top_rules.to_csv(index=False), "recs.csv")
else:
    st.info("No recommendations found for this item.")
