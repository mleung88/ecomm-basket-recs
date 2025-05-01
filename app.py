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


top_rules_plot = top_rules.sort_values("confidence", ascending=True)
if not top_rules.empty:
    st.markdown("### 📈 Recommendation Strength (by Confidence)")
    
    top_rules_plot = top_rules.sort_values("confidence", ascending=True)

    fig, ax = plt.subplots()
    ax.barh(top_rules_plot["consequent"], top_rules_plot["confidence"], color="#4caf50")
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)
else:
    st.info("No recommendations found for this item.")


import matplotlib.pyplot as plt

st.subheader("📈 Recommendation Strength (by Confidence)")
fig, ax = plt.subplots()
top_rules_plot = top_rules.sort_values("confidence", ascending=True)
ax.barh(top_rules_plot["consequent"], top_rules_plot["confidence"], color="#1f77b4")
ax.set_xlabel("Confidence")
ax.set_ylabel("Consequent Item")
st.pyplot(fig)

import networkx as nx

G = nx.DiGraph()
for _, row in top_rules.iterrows():
    G.add_edge(row["antecedent"], row["consequent"], weight=row["lift"])

plt.figure(figsize=(8,6))
pos = nx.spring_layout(G, k=0.5, seed=42)
edges = G.edges(data=True)
weights = [e[2]["weight"] for e in edges]
nx.draw(G, pos, with_labels=True, node_color="skyblue", node_size=1500,
        edge_color=weights, edge_cmap=plt.cm.viridis, width=2)
st.pyplot(plt)

st.markdown(f"**Average Confidence:** {top_rules['confidence'].mean():.2f}")
st.markdown(f"**Average Lift:** {top_rules['lift'].mean():.2f}")

