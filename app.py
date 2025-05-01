import streamlit as st
from utils import load_rules, get_recommendations

st.set_page_config(page_title="Basket Recs", layout="wide")
st.title("🛒 E-Commerce Basket Recommendations")

# Load once
rules = load_rules()

# Sidebar controls
st.sidebar.header("Filter options")
all_products = sorted(rules["antecedent"].unique())
prod = st.sidebar.selectbox("Pick an antecedent product:", all_products)

months = ["All"] + list(rules["Month"].cat.categories)
month = st.sidebar.selectbox("Month:", months)

rec_type = st.sidebar.radio("Recommendation type:", ["cross", "variant"])
top_n = st.sidebar.slider("Number of recs:", min_value=5, max_value=20, value=10)

# Main panel
st.subheader(f"Top {top_n} {rec_type.title()}-sells for “{prod}” → {month}")
df = get_recommendations(rules, prod, month, top_n, rec_type)
st.dataframe(df[["Month","antecedent","consequent","support","confidence","lift"]])

# Optional: lift-over-time plot
if month == "All":
    try:
        pivot = rules[
            (rules["antecedent"] == prod) &
            (rules["type"] == rec_type)
        ].pivot_table(index="Month", values="lift", aggfunc="max").sort_index()
        st.line_chart(pivot)
    except Exception:
        st.write("No time-series data available for this selection.")
