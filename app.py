# app.py
import streamlit as st
import pandas as pd

# === Load rules ===
@st.cache_data

def load_rules():
    return pd.read_csv("rules_by_month_abs30.csv")

# === UI ===
st.set_page_config(page_title="E-commerce Recommender")
st.title("🏍️ E-commerce Basket Recommender")

rules = load_rules()
months = ["Any"] + sorted(rules["Month"].dropna().unique().tolist())
selected_month = st.selectbox("Filter by Month", months)

# === Filter by month ===
if selected_month != "Any":
    df = rules[rules["Month"] == selected_month].copy()
else:
    df = rules.copy()
    df = df.drop_duplicates(subset=["antecedent", "consequent"], keep="first")

# === Select an item ===
candidates = sorted(df["antecedent"].unique().tolist())
user_selected_item = st.selectbox("Choose an item to get recommendations", candidates)

# === Get and process matching recommendations ===
df_choices = df[df["antecedent"] == user_selected_item]
df_choices = df_choices.sort_values("confidence", ascending=False)
df_choices = df_choices.drop_duplicates(subset=["consequent"], keep="first")
df_choices = df_choices.head(5)

# === Display ===
st.markdown(f"### Top {len(df_choices)} recs for `{user_selected_item}`")
st.dataframe(df_choices[["consequent", "support", "confidence", "lift"]], use_container_width=True)
