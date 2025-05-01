import pandas as pd
import streamlit as st

@st.cache_data
def load_rules(path="data/rules_by_month_abs30_pruned.csv"):
    df = pd.read_csv(path)
    # ensure types
    df["Month"] = pd.Categorical(
        df["Month"],
        categories=["January","February","March","April","May","June",
                    "July","August","September","October","November","December"],
        ordered=True
    )
    return df

def get_recommendations(rules, antecedent, month=None, top_n=10, rec_type="cross"):
    """
    Filter rules by:
      - antecedent product
      - optional month
      - optional rec_type ("cross" or "variant")
      - sorted by lift desc
    """
    df = rules[rules["antecedent"] == antecedent]
    if month and month != "All":
        df = df[df["Month"] == month]
    df = df[df["type"] == rec_type]
    return df.sort_values("lift", ascending=False).head(top_n)
