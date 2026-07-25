import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("🔥 Quant Trading Dashboard")

df = pd.read_csv("data/master_dashboard_pro.csv")

sector = st.selectbox("Select Sector", ["All"] + sorted(df["SECTOR"].dropna().unique()))

if sector != "All":
    df = df[df["SECTOR"] == sector]

top_n = st.slider("Top N Stocks", 10, 100, 20)

st.subheader("Top Opportunities")
st.dataframe(df.head(top_n))

st.subheader("Industry Leaders")
leaders = df[df["INDUSTRY_RANK"] == 1]
st.dataframe(leaders)

st.subheader("Score Distribution")
st.bar_chart(df["FINAL_SCORE"].value_counts())