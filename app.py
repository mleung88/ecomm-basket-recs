import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Load rules
@st.cache_data
def load_rules():
    df = pd.read_csv("rules_by_month_abs30.csv")
    return df

def get_recommendations(df, item, month, rec_type, min_conf, min_lift, top_n=10):
    if month != "Any":
        df = df[df['Month'] == month]

    # Filter by type if available
    if "type" in df.columns and rec_type != "All":
        df = df[df['type'] == rec_type]

    # Apply thresholds
    df = df[(df['confidence'] >= min_conf) & (df['lift'] >= min_lift)]

    # Drop duplicates across months
    df = df.drop_duplicates(subset=["antecedent", "consequent"], keep="first")

    # Filter by selected item
    df = df[df['antecedent'] == item].copy()

    # Sort by confidence or lift
    df_sorted = df.sort_values("confidence", ascending=False).head(top_n)
    return df_sorted

# App starts
st.set_page_config(page_title="E-commerce Basket Recommender", layout="wide")
st.title("🛒 E-commerce Basket Recommender")

# Load rules once
rules_df = load_rules()
months = ["Any"] + sorted(rules_df['Month'].dropna().unique().tolist())
items = sorted(rules_df['antecedent'].unique())
types = ["All"] + (rules_df['type'].dropna().unique().tolist() if "type" in rules_df.columns else [])

# Sidebar inputs
month = st.sidebar.selectbox("📅 Filter by Month", months)
selected_item = st.sidebar.selectbox("🛒 Choose an item", items)
rec_type = st.sidebar.radio("🔀 Rule Type", types)
min_conf = st.sidebar.slider("📉 Minimum Confidence", 0.0, 1.0, 0.4, 0.05)
min_lift = st.sidebar.slider("📈 Minimum Lift", 1.0, 5.0, 1.2, 0.1)
top_n = st.sidebar.slider("🔢 Top N Recommendations", 1, 20, 10)

# Get recommendations
top_rules = get_recommendations(rules_df, selected_item, month, rec_type, min_conf, min_lift, top_n=top_n)

# Show results
st.markdown(f"## Top {len(top_rules)} recs for `{selected_item}`")
st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift']])

# Summary interpretations
if not top_rules.empty:
    st.markdown("### 🧾 Interpreted Recommendations")
    for _, row in top_rules.iterrows():
        st.write(f"If someone buys **{row['antecedent']}**, they're likely to also buy **{row['consequent']}** "
                 f"(confidence: {row['confidence']:.2f}, lift: {row['lift']:.2f})")

    st.markdown("### 📊 Confidence Chart")
    plot_data = top_rules.sort_values("confidence", ascending=True)
    fig, ax = plt.subplots()
    ax.barh(plot_data["consequent"], plot_data["confidence"], color="#4caf50")
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)
else:
    st.info("No recommendations found for this item.")
