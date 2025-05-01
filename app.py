import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import calendar
import openai
import os

# Load rules
@st.cache_data
def load_rules():
    df = pd.read_csv("data/rules_final.csv")
    return df

def enrich_recommendation(text, model="gpt-3.5-turbo"):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": f"Write a one-sentence insight for this rule: {text}"}],
            temperature=0.5,
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(GPT Error: {e})"

def get_recommendations(df, item, month, rec_type, min_conf, min_lift, min_support, top_n, sort_by, bidirectional, sku_filter, min_conseq_freq):
    if month != "Any":
        df = df[df['Month'] == month]

    if "type" in df.columns and rec_type != "All":
        df = df[df['type'] == rec_type]

    df = df[(df['confidence'] >= min_conf) & (df['lift'] >= min_lift) & (df['support'] >= min_support)]
    df = df.drop_duplicates(subset=["antecedent", "consequent"], keep="first")

    if bidirectional:
        df = df[(df['antecedent'] == item) | (df['consequent'] == item)].copy()
    else:
        df = df[df['antecedent'] == item].copy()

    df = df[df['antecedent'] != df['consequent']]

    if sku_filter:
        df = df[df['SKU'].astype(str).str.contains(sku_filter, case=False)]

    if "consequent_count" in df.columns:
        df = df[df['consequent_count'] >= min_conseq_freq]

    return df.sort_values(sort_by, ascending=False).head(top_n)

# App starts
st.set_page_config(page_title="E-commerce Basket Recommender", layout="wide")
st.title("🛍️ E-commerce Basket Recommender")

openai_key = st.sidebar.text_input("🔐 OpenAI API Key", type="password")
if openai_key:
    openai.api_key = openai_key

enrich = st.sidebar.checkbox("💡 Use OpenAI for smart rule suggestions")

rules_df = load_rules()
month_order = list(calendar.month_name)[1:]  # January to December
months = ["Any"] + [m for m in month_order if m in rules_df['Month'].unique()]
# Step 1: Apply filters *before* selecting item
filtered_df = rules_df.copy()

if month != "Any":
    filtered_df = filtered_df[filtered_df['Month'] == month]

if "type" in filtered_df.columns and rec_type != "All":
    filtered_df = filtered_df[filtered_df['type'] == rec_type]

filtered_df = filtered_df[
    (filtered_df['confidence'] >= min_conf) &
    (filtered_df['lift'] >= min_lift) &
    (filtered_df['support'] >= min_support)
]

if "consequent_count" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['consequent_count'] >= min_conseq_freq]

# Step 2: Build list of valid antecedents (optional: include bidirectional logic here too)
valid_items = sorted(set(filtered_df['antecedent']))
selected_item = st.sidebar.selectbox("🛒 Choose an item", valid_items)


# Sidebar inputs
month = st.sidebar.selectbox("📅 Filter by Month", months)
selected_item = st.sidebar.selectbox("🛒 Choose an item", items)
rec_type = st.sidebar.radio("🔀 Rule Type", types)
min_conf = st.sidebar.slider("📉 Minimum Confidence", 0.0, 1.0, 0.4, 0.05)
min_lift = st.sidebar.slider("📈 Minimum Lift", 1.0, 5.0, 1.2, 0.1)
min_support = st.sidebar.slider("📊 Minimum Support", 0.0, 0.1, 0.01, 0.005)
min_conseq_freq = st.sidebar.slider("🛒 Consequent Min Frequency (baskets)", 1, 100, 5)
bidirectional = st.sidebar.checkbox("↔ Include item as consequent too")
top_n = st.sidebar.slider("🔢 Top N Recommendations", 1, 20, 10)
sort_by = st.sidebar.radio("📌 Sort By", ["confidence", "lift"])
group_by = st.sidebar.radio("📁 Group Results By", ["None", "type", "Month"])
keyword = st.sidebar.text_input("🔍 Search Consequent Contains")
sku_filter = st.sidebar.text_input("🔢 Filter by SKU (optional)")

# Get recommendations
top_rules = get_recommendations(
    rules_df, selected_item, month, rec_type, min_conf, min_lift, min_support,
    top_n, sort_by, bidirectional, sku_filter, min_conseq_freq
)

if keyword:
    top_rules = top_rules[top_rules['consequent'].str.contains(keyword, case=False, na=False)]

st.markdown(f"## Top {len(top_rules)} recs for `{selected_item}`")

if group_by != "None" and group_by in top_rules.columns:
    grouped = top_rules.groupby(group_by)
    for group, df_g in grouped:
        st.markdown(f"### 🔸 {group}")
        st.dataframe(df_g[['consequent', 'support', 'confidence', 'lift']])
else:
    st.dataframe(top_rules[['consequent', 'support', 'confidence', 'lift']])

if not top_rules.empty:
    st.markdown("### 🧾 Interpreted Recommendations")
    for _, row in top_rules.iterrows():
        direction = "buys" if row['antecedent'] == selected_item else "is also bought with"
        st.write(f"If someone **{direction}** `{selected_item}`, they’re likely to also buy **{row['consequent']}** (confidence: {row['confidence']:.2f}, lift: {row['lift']:.2f})")

        if enrich and openai_key:
            enriched = enrich_recommendation(f"{row['antecedent']} → {row['consequent']}, conf: {row['confidence']}, lift: {row['lift']}")
            st.caption(f"🤖 GPT: {enriched}")

    st.markdown("### 📊 Confidence Chart")
    plot_data = top_rules.sort_values("confidence", ascending=True)
    fig, ax = plt.subplots()
    bars = ax.barh(plot_data["consequent"], plot_data["confidence"], color=plt.cm.Greens(plot_data["confidence"]))
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Consequent Item")
    st.pyplot(fig)

    st.markdown("### 📈 Trend of Confidence Across Months")
    if 'Month' in rules_df.columns:
        trend_data = rules_df[(rules_df['antecedent'] == selected_item) & (rules_df['consequent'].isin(top_rules['consequent']))]
        if not trend_data.empty:
            fig, ax = plt.subplots()
            for cons in trend_data['consequent'].unique():
                temp = trend_data[trend_data['consequent'] == cons]
                temp = temp.set_index('Month').reindex(month_order).reset_index()
                ax.plot(temp['Month'], temp['confidence'], label=cons, marker='o')
            ax.set_ylabel("Confidence")
            ax.set_title(f"Monthly confidence trends for rules starting with '{selected_item}'")
            ax.legend()
            st.pyplot(fig)

    st.download_button("📥 Download These Recs", top_rules.to_csv(index=False), "recs.csv")
else:
    st.info("No recommendations found for this item.")
