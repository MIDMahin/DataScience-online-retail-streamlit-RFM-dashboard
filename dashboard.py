"""
Online Retail - 2-Page Streamlit Dashboard
Page 1: Business Overview | Page 2: RFM Customer Analysis
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Online Retail Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# Segment recommendations
SEGMENT_RECOMMENDATIONS = {
    "Champions": "• Reward with VIP program & exclusive offers\n• Encourage referrals & reviews\n• Prioritize inventory & support",
    "Loyal Customers": "• Cross-sell & upsell to grow spend\n• Introduce loyalty tiers",
    "Promising": "• Nurture with onboarding & product discovery\n• Incentivize 2nd purchase within 60 days",
    "New Customers": "• Onboarding flow\n• Cross-sell based on 1st purchase",
    "At Risk": "• Win-back campaign (We miss you!)\n• Personalized offer within 30 days",
    "Cant Lose": "• Urgent win-back with strong incentives\n• Check for pain points",
    "Hibernating": "• Reactivation campaign\n• Product-specific offers",
    "Lost": "• One low-cost win-back attempt\n• Deprioritize spend",
    "Others": "• Sub-segment for targeted campaigns",
}


@st.cache_data
def load_and_clean_data():
    """Load and clean data (same logic as notebooks)."""
    path = Path(__file__).parent / "Online Retail.xlsx"
    df = pd.read_excel(path)
    df_clean = df.copy()
    df_clean = df_clean.drop_duplicates()
    df_clean = df_clean.dropna(subset=["Description", "CustomerID"])
    df_clean = df_clean[~df_clean["InvoiceNo"].astype(str).str.startswith("C")]
    df_clean = df_clean[(df_clean["Quantity"] > 0) & (df_clean["UnitPrice"] > 0)]
    df_clean["Revenue"] = df_clean["Quantity"] * df_clean["UnitPrice"]
    return df, df_clean


@st.cache_data
def compute_rfm(df_clean):
    """Compute RFM metrics and segments."""
    ref_date = df_clean["InvoiceDate"].max() + pd.Timedelta(days=1)
    orders = df_clean.groupby(["CustomerID", "InvoiceNo"]).agg(
        Revenue=("Revenue", "sum"),
        InvoiceDate=("InvoiceDate", "max"),
    ).reset_index()
    rfm = orders.groupby("CustomerID").agg(
        Recency=("InvoiceDate", lambda x: (ref_date - x.max()).days),
        Frequency=("InvoiceNo", "nunique"),
        Monetary=("Revenue", "sum"),
    ).reset_index()
    rfm["R_Score"] = pd.qcut(rfm["Recency"], q=5, labels=[5, 4, 3, 2, 1], duplicates="drop")
    rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5], duplicates="drop")
    rfm["M_Score"] = pd.qcut(rfm["Monetary"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5], duplicates="drop")
    for col in ["R_Score", "F_Score", "M_Score"]:
        rfm[col] = rfm[col].astype(int)
    
    def assign_segment(row):
        r, f, m = row["R_Score"], row["F_Score"], row["M_Score"]
        if r >= 4 and f >= 4 and m >= 4: return "Champions"
        if r >= 4 and f >= 2 and m >= 2: return "Loyal Customers"
        if r >= 4 and f <= 1 and m <= 1: return "Promising"
        if r >= 3 and f <= 2 and m <= 2: return "New Customers"
        if r <= 2 and f >= 3 and m >= 3: return "At Risk"
        if r <= 2 and f >= 2 and m >= 2: return "Cant Lose"
        if r <= 2 and f <= 2 and m >= 3: return "Hibernating"
        if r <= 1 and f <= 1 and m <= 2: return "Lost"
        return "Others"
    
    rfm["Segment"] = rfm.apply(assign_segment, axis=1)
    return rfm, ref_date


def page_business_overview(df, df_clean):
    """Page 1: Business Overview."""
    st.title("📊 Business Overview")
    
    # Return rate from raw data (before cleaning)
    returns_count = len(df[(df["Quantity"] <= 0) | (df["UnitPrice"] <= 0)]) + len(df[df["InvoiceNo"].astype(str).str.startswith("C")])
    return_rate = 100 * returns_count / len(df) if len(df) > 0 else 0
    
    # Metrics
    total_revenue = df_clean["Revenue"].sum()
    n_customers = df_clean["CustomerID"].nunique()
    order_totals = df_clean.groupby("InvoiceNo")["Revenue"].sum()
    aov = order_totals.mean()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"£{total_revenue:,.0f}")
    col2.metric("Unique Customers", f"{n_customers:,}")
    col3.metric("AOV", f"£{aov:,.2f}")
    col4.metric("Return/Cancel Rate", f"{return_rate:.1f}%")
    
    st.divider()
    
    # Revenue trends (monthly)
    df_clean["Month"] = pd.to_datetime(df_clean["InvoiceDate"]).dt.to_period("M").astype(str)
    monthly = df_clean.groupby("Month").agg(
        Revenue=("Revenue", "sum"),
        Orders=("InvoiceNo", "nunique"),
    ).reset_index()
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=monthly["Month"], y=monthly["Revenue"], name="Revenue (£)", mode="lines+markers", line=dict(color="#2E86AB")))
    fig_trend.add_trace(go.Scatter(x=monthly["Month"], y=monthly["Orders"], name="Orders", yaxis="y2", mode="lines+markers", line=dict(color="#A23B72")))
    fig_trend.update_layout(
        title="Monthly Revenue & Order Trend",
        xaxis_title="Month",
        yaxis=dict(title=dict(text="Revenue (£)", font=dict(color="#2E86AB"))),
        yaxis2=dict(title=dict(text="Orders", font=dict(color="#A23B72")), overlaying="y", side="right"),
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    st.plotly_chart(fig_trend, width="stretch")
    
    # Geographic & Product
    col_geo, col_prod = st.columns(2)
    
    with col_geo:
        geo = df_clean.groupby("Country").agg(
            Revenue=("Revenue", "sum"),
            Orders=("InvoiceNo", "nunique"),
        ).reset_index()
        geo["AOV"] = geo["Revenue"] / geo["Orders"]
        geo_top = geo.nlargest(10, "Revenue").sort_values("Revenue", ascending=True)
        fig_geo = px.bar(geo_top, x="Revenue", y="Country", orientation="h", title="Revenue by Country (Top 10)", color="Revenue", color_continuous_scale="Blues")
        fig_geo.update_layout(showlegend=False, template="plotly_white", margin=dict(t=40))
        st.plotly_chart(fig_geo, width="stretch")
    
    with col_prod:
        top_prod = df_clean.groupby(["StockCode", "Description"]).agg(Revenue=("Revenue", "sum")).reset_index().nlargest(10, "Revenue")
        top_prod["Product"] = top_prod["StockCode"].astype(str) + ": " + top_prod["Description"].str[:35]
        top_prod = top_prod.sort_values("Revenue", ascending=True)
        fig_prod = px.bar(top_prod, x="Revenue", y="Product", orientation="h", title="Top 10 Products by Revenue", color="Revenue", color_continuous_scale="Teal")
        fig_prod.update_layout(showlegend=False, template="plotly_white", margin=dict(t=40), yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_prod, width="stretch")


def page_rfm_customer(df_clean, rfm, ref_date):
    """Page 2: RFM Customer Analysis."""
    st.title("👤 Customer RFM Analysis")
    
    # Merge rfm with country from df_clean (most common country per customer)
    cust_country = df_clean.groupby("CustomerID")["Country"].first().reset_index()
    rfm = rfm.merge(cust_country, on="CustomerID", how="left")
    
    # Customer selector: search + dropdown
    customer_options = [f"{int(cid)} - {seg}" for cid, seg in zip(rfm["CustomerID"], rfm["Segment"])]
    customer_map = {opt: float(opt.split(" - ")[0]) for opt in customer_options}
    
    st.subheader("Find a Customer")
    search = st.text_input("Search by Customer ID", placeholder="e.g. 12347", key="search_input")
    
    selected_opt = st.selectbox("Or select from dropdown:", customer_options, key="sel_dd")
    
    if search:
        try:
            cid_search = float(search.strip())
            matches = rfm[rfm["CustomerID"] == cid_search]
            if len(matches) > 0:
                cid = cid_search
            else:
                cid = customer_map[selected_opt]
        except ValueError:
            cid = customer_map[selected_opt]
    else:
        cid = customer_map[selected_opt]
    cust_rfm = rfm[rfm["CustomerID"] == cid].iloc[0]
    segment = cust_rfm["Segment"]
    
    # Segment badge & recommendations
    st.markdown("---")
    st.markdown(f"### 🏷️ Segment: **{segment}**")
    st.info(SEGMENT_RECOMMENDATIONS.get(segment, "No specific recommendations."))
    
    st.markdown("---")
    st.subheader("Customer Profile")
    
    # Get customer transaction data
    cust_df = df_clean[df_clean["CustomerID"] == cid]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Country", cust_rfm.get("Country", "N/A"))
    with col2:
        first_purchase = cust_df["InvoiceDate"].min()
        last_purchase = cust_df["InvoiceDate"].max()
        st.metric("First Purchase", first_purchase.strftime("%Y-%m-%d") if pd.notna(first_purchase) else "N/A")
    with col3:
        st.metric("Last Purchase", last_purchase.strftime("%Y-%m-%d") if pd.notna(last_purchase) else "N/A")
    
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Total Revenue", f"£{cust_rfm['Monetary']:,.2f}")
    with col5:
        n_orders = cust_rfm["Frequency"]
        st.metric("Transaction Count", f"{int(n_orders)}")
    with col6:
        cust_aov = cust_rfm["Monetary"] / cust_rfm["Frequency"] if cust_rfm["Frequency"] > 0 else 0
        st.metric("AOV", f"£{cust_aov:,.2f}")
    
    st.markdown("---")
    st.subheader("Purchase Behavior")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        top_prods = cust_df.groupby(["StockCode", "Description"]).agg(Revenue=("Revenue", "sum")).reset_index().nlargest(8, "Revenue")
        top_prods["Product"] = top_prods["StockCode"].astype(str) + ": " + top_prods["Description"].str[:30]
        fig_top = px.bar(top_prods, x="Revenue", y="Product", orientation="h", title="Top Products Purchased")
        fig_top.update_layout(template="plotly_white", margin=dict(t=40), yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig_top, width="stretch")
    
    with col_b:
        cust_df_copy = cust_df.copy()
        cust_df_copy["Category"] = cust_df_copy["Description"].str.strip().str.split().str[-1].str.upper()
        cat_rev = cust_df_copy.groupby("Category")["Revenue"].sum().reset_index().nlargest(8, "Revenue")
        fig_cat = px.pie(cat_rev, values="Revenue", names="Category", title="Product Categories Purchased")
        fig_cat.update_layout(template="plotly_white", margin=dict(t=40))
        st.plotly_chart(fig_cat, width="stretch")


def main():
    df, df_clean = load_and_clean_data()
    rfm, ref_date = compute_rfm(df_clean)
    
    st.sidebar.title("📊 Online Retail Dashboard")
    page = st.sidebar.radio("Navigation", ["Business Overview", "Customer RFM Analysis"])
    
    if page == "Business Overview":
        page_business_overview(df, df_clean)
    else:
        page_rfm_customer(df_clean, rfm, ref_date)


if __name__ == "__main__":
    main()
