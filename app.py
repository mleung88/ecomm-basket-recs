# app.py
import streamlit as st
import pandas as pd
import calendar

@st.cache_data
def load_rules(path="rules_by_month_abs30.csv"):
    df = pd.read_csv(path)
    month_order = list(calendar.month_name)[1:]
    df["Month"] = pd.Categorical(df["Month"], categories=month_order, ordered=True)
    return df

def get_recommendations(df, month, antecedent, rec_type, top_n):
    # filter by month
    if month != "Anytime":
        df = df[df["Month"] == month]
    # filter by rec type
    if rec_type != "All":
        df = df[df["type"] == rec_type]
    # filter by antecedent, sort & head
    return (
        df[df["antecedent"] == antecedent]
          .sort_values("lift", ascending=False)
          .head(top_n)
    )

def main():
    st.set_page_config(page_title="🛒 Basket Recs", layout="wide")
    st.title("🛍️ E-commerce Basket Recommender")

    rules = load_rules()

    # Sidebar controls
    month_opts = ["Anytime"] + list(rules["Month"].cat.categories)
    month = st.sidebar.selectbox("📅 Time window", month_opts)

    # recommendation type: All / variant / cross
    rec_type = st.sidebar.radio(
        "🔀 Recommendation type",
        ["All", "variant", "cross"]
    )

    # filter antecedent choices to whatever months/types selected
    df_choices = rules.copy()
    if month != "Anytime":
        df_choices = df_choices[df_choices["Month"] == month]
    if rec_type != "All":
        df_choices = df_choices[df_choices["type"] == rec_type]

    antecedent = st.sidebar.selectbox(
        "🛒 If they buy…",
        df_choices["antecedent"].unique()
    )

    top_n = st.sidebar.slider("🔢 How many recs?", 1, 20, 5)

    recs = get_recommendations(rules, month, antecedent, rec_type, top_n)

    if recs.empty:
        st.warning("No rules match that combination—try loosening the filters.")
    else:
        subtitle = f"Top {top_n} {rec_type if rec_type!='All' else ''} recs for **{antecedent}**"
        if month!="Anytime":
            subtitle += f" in **{month}**"
        st.subheader(subtitle)
        st.dataframe(
            recs[["consequent","support","confidence","lift"]],
            use_container_width=True
        )

    st.sidebar.markdown("---")
    st.sidebar.write(f"Loaded {len(rules)} rules total")

if __name__ == "__main__":
    main()
