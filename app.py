# app.py
import streamlit as st
import pandas as pd
import calendar

@st.cache_data
def load_rules(path: str = "rules_by_month_abs30.csv") -> pd.DataFrame:
    """Load the CSV of pre-computed association rules."""
    df = pd.read_csv(path)
    # ensure Month is in calendar order
    month_order = list(calendar.month_name)[1:]
    df["Month"] = pd.Categorical(df["Month"], categories=month_order, ordered=True)
    return df

def get_recommendations(
    df: pd.DataFrame,
    month: str,
    antecedent: str,
    top_n: int = 5
) -> pd.DataFrame:
    """Filter to the chosen month + antecedent, sort by lift, and return top N."""
    sub = df[(df["Month"] == month) & (df["antecedent"] == antecedent)]
    return sub.sort_values("lift", ascending=False).head(top_n)

def main():
    st.set_page_config(page_title="🛒 Basket Recommender", layout="wide")
    st.title("🛍️ E-Commerce Basket Recommender")
    st.markdown(
        """
        Select a month and a product you've sold (the antecedent), 
        and see the top associated products (consequents), ranked by lift.
        """
    )

    # 1. Load once (cached)
    rules = load_rules()

    # 2. Sidebar controls
    months = rules["Month"].cat.categories
    month = st.sidebar.selectbox("📅 Month", months)
    month_df = rules[rules["Month"] == month]

    antecedents = month_df["antecedent"].unique()
    antecedent = st.sidebar.selectbox("🛒 If a customer buys…", antecedents)

    top_n = st.sidebar.slider("🔢 How many recommendations?", 1, 20, 5)

    # 3. Fetch and display
    recs = get_recommendations(rules, month, antecedent, top_n)
    if recs.empty:
        st.warning("No rules found for that combination. Try lowering the lift or confidence thresholds in your mining step.")
    else:
        st.subheader(f"Top {top_n} recommendations for **{antecedent}** in **{month}**")
        st.dataframe(
            recs[["consequent", "support", "confidence", "lift"]],
            use_container_width=True
        )

    # 4. Optional: show overall stats
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"Total rules loaded: **{len(rules)}**")

if __name__ == "__main__":
    main()
