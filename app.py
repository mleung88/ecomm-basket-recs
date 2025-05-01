# app.py
import streamlit as st
import pandas as pd
import calendar

@st.cache_data
def load_rules(path: str = "rules_by_month_abs30.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    # enforce calendar ordering
    month_order = list(calendar.month_name)[1:]
    df["Month"] = pd.Categorical(df["Month"], categories=month_order, ordered=True)
    return df

def get_recommendations(
    df: pd.DataFrame,
    month: str,
    antecedent: str,
    top_n: int = 5
) -> pd.DataFrame:
    # if “Anytime”, don’t filter by Month
    if month != "Anytime":
        df = df[df["Month"] == month]
    return (
        df[df["antecedent"] == antecedent]
          .sort_values("lift", ascending=False)
          .head(top_n)
    )

def main():
    st.set_page_config(page_title="🛒 Basket Recommender", layout="wide")
    st.title("🛍️ E-Commerce Basket Recommender")
    st.markdown(
        """
        Pick a time window and a product, then see top associated
        products sorted by lift.
        """
    )

    rules = load_rules()

    # build our month selector with an “Anytime” option first
    month_cats = list(rules["Month"].cat.categories)
    month_option = st.sidebar.selectbox(
        "📅 Time window", ["Anytime"] + month_cats
    )

    # filter the rules to whichever months we're looking at
    if month_option == "Anytime":
        filtered = rules.copy()
    else:
        filtered = rules[rules["Month"] == month_option]

    # now pick your antecedent from that subset
    antecedent = st.sidebar.selectbox(
        "🛒 If they buy…",
        filtered["antecedent"].unique()
    )

    top_n = st.sidebar.slider(
        "🔢 Number of recommendations", 1, 20, 5
    )

    recs = get_recommendations(rules, month_option, antecedent, top_n)

    if recs.empty:
        st.warning("No rules found for that choice. Try a different product or increase the pool (e.g. lower your lift threshold when mining).")
    else:
        title = f"Top {top_n} recs for **{antecedent}**"
        if month_option != "Anytime":
            title += f" in **{month_option}**"
        st.subheader(title)
        st.dataframe(
            recs[["consequent","support","confidence","lift"]],
            use_container_width=True
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"Total rules loaded: **{len(rules)}**")

if __name__ == "__main__":
    main()
