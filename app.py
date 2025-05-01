import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Load rules
@st.cache_data
def load_rules():
    df = pd.read_csv("rules_by_month_abs30.csv")
    return df

def get_recommendations(df, item, month, top_n=10):
    # Optional month filter
    if month != "Any":
        df = df[df['Month'] == month]

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

# Sidebar inputs
month = st.selectbox("Filter by Month", months)
selected_item = st.selectbox("Choose an item to get recommendations", items)

# Get recommendations
top_rules = get_recommendations(rules_df, selected_item, month, top_n=10)

# Show results
st.markdown(f"## Top {len(top_rules)} recs for ` {selected_item} `")
st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift']])

# Bonus: Recommendation strength plot
if not top_rules.empty:
    st.markdown("### 📈 Recommendation Strength (by Confidence)")
    plot_data = top_rules.sort_values("confidence", ascending=True)
    fig, ax = plt.subplots()
    ax.barh(plot_data["consequent"], plot_data["confidence"], color="#4caf50")
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)
else:
    st.info("No recommendations found for this item.")
