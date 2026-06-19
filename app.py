import datetime
import urllib.request
import pandas as pd
import streamlit as st
import yfinance as yf

# Set up Page Config
st.set_page_config(
    page_title="Passive Endgame Monitor", page_icon="📊", layout="wide"
)

st.title("📊 Mike Green's Passive Endgame Monitor")
st.markdown(
    """
This dashboard tracks the structural health, liquidity flows, and systemic risks of the U.S. stock market 
under the **Passive Investing Endgame Hypothesis**. When passive inflows turn to outflows, structural cracks appear.
"""
)
st.markdown("---")


# Helper function to grab FRED data safely bypassing bot blocks
@st.cache_data(ttl=3600)  # Cache data for 1 hour to prevent constant reloading
def fetch_fred_csv(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        # Bypasses the FRED block by mimicking a standard web browser request
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req) as response:
            df = pd.read_csv(response, parse_dates=["DATE"], index_col="DATE")

        # Ensure data is numeric
        df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
        df = df.dropna()
        return df
    except Exception as e:
        st.error(f"Error fetching FRED series {series_id}: {e}")
        return pd.DataFrame()


# Helper function to grab Yahoo Finance data
@st.cache_data(ttl=3600)
def fetch_mkt_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)
    data = yf.download(
        ["SPY", "RSP"], start=start_date, end=end_date, progress=False
    )
    close_prices = data["Close"]
    close_prices["Ratio"] = close_prices["SPY"] / close_prices["RSP"]
    return close_prices


# Load data
with st.spinner("Fetching latest market and macro plumbing metrics..."):
    df_icsa = fetch_fred_csv("ICSA")  # Initial Claims
    df_ccsa = fetch_fred_csv("CCSA")  # Continuing Claims
    df_spread = fetch_fred_csv("BAMLH0A0HYM2")  # High Yield Spread
    df_mkt = fetch_mkt_data()

# Check if dataframes loaded properly before calculating metrics
if not df_icsa.empty and not df_ccsa.empty and not df_spread.empty:

    # -----------------------------------------------------------------------------
    # PHASE 1: METRICS DISPLAY
    # -----------------------------------------------------------------------------
    st.header("🚨 Systemic Threshold Alerts")

    col1, col2, col3, col4 = st.columns(4)

    # Initial Claims
    latest_icsa = df_icsa["ICSA"].iloc[-1]
    prev_icsa = df_icsa["ICSA"].iloc[-2]
    icsa_delta = latest_icsa - prev_icsa
    with col1:
        st.metric(
            label="Initial Unemployment Claims",
            value=f"{latest_icsa:,.0f}",
            delta=f"{icsa_delta:,.0f} vs last week",
            delta_color="inverse",
        )
        if latest_icsa > 250000:
            st.error("⚠️ Over Trigger Threshold (> 250k)")
        else:
            st.success("🟢 Safe Range (< 250k)")

    # Continuing Claims
    latest_ccsa = df_ccsa["CCSA"].iloc[-1]
    prev_ccsa = df_ccsa["CCSA"].iloc[-2]
    ccsa_delta = latest_ccsa - prev_ccsa
    with col2:
        st.metric(
            label="Continuing Claims",
            value=f"{latest_ccsa:,.0f}",
            delta=f"{ccsa_delta:,.0f} vs last week",
            delta_color="inverse",
        )
        if latest_ccsa > 1900000:
            st.error("⚠️ Over Trigger Threshold (> 1.9M)")
        else:
            st.success("🟢 Safe Range (< 1.9M)")

    # High Yield Spread
    latest_spread = df_spread["BAMLH0A0HYM2"].iloc[-1]
    prev_spread = df_spread["BAMLH0A0HYM2"].iloc[-2]
    spread_delta = round(latest_spread - prev_spread, 2)
    with col3:
        st.metric(
            label="High Yield Credit Spread",
            value=f"{latest_spread}%",
            delta=f"{spread_delta}% vs yesterday",
            delta_color="inverse",
        )
        if latest_spread > 4.5:
            st.error("⚠️ Credit Stress Alert (> 4.5%)")
        else:
            st.success("🟢 Normal Credit Environment")

    # SPY / RSP Ratio
    latest_ratio = df_mkt["Ratio"].iloc[-1]
    prev_ratio = df_mkt["Ratio"].iloc[-5]  # 5 days ago
    ratio_delta = round(latest_ratio - prev_ratio, 3)
    with col4:
        st.metric(
            label="SPY / RSP Inelasticity Ratio",
            value=f"{latest_ratio:.3f}",
            delta=f"{ratio_delta:.3f} (5d change)",
        )
        st.info("Higher ratio = Higher Concentration")

    st.markdown("---")

    # -----------------------------------------------------------------------------
    # PHASE 2: CHARTS & EXPLANATIONS
    # -----------------------------------------------------------------------------
    st.header("📈 Data Visualizations")

    tab1, tab2, tab3 = st.tabs(
        ["Market Inelasticity", "Labor Market Flows", "Credit Health"]
    )

    with tab1:
        st.subheader("SPY (Market-Cap Weighted) vs RSP (Equal Weighted) Ratio")
        st.markdown(
            "**Why it matters:** When this ratio rises aggressively, it indicates blind passive flows are disproportionately forcing capital into mega-cap stocks regardless of valuation."
        )
        st.line_chart(df_mkt["Ratio"])

    with tab2:
        st.subheader("Weekly Initial Jobless Claims")
        st.markdown(
            "**Why it matters:** Job losses disrupt automatic, recurring payroll contributions into retirement accounts—the exact engine powering passive index fund buying."
        )
        st.line_chart(df_icsa.tail(104)["ICSA"])  # Show last 2 years

    with tab3:
        st.subheader("ICE BofA High Yield Option-Adjusted Spread")
        st.markdown(
            "**Why it matters:** Credit markets are overwhelmingly actively managed. Spreads widen when economic conditions decay under the surface, acting as an early warning indicator for overall liquidity stress."
        )
        st.line_chart(df_spread.tail(260)["BAMLH0A0HYM2"])  # Show last 5 years

else:
    st.warning(
        "Waiting for data pipelines to initialize. If this message persists, check your network connections to FRED."
    )

st.sidebar.title("Dashboard Info")
st.sidebar.info(
    """
**Estimated Passive Market Share:** ~54%
\n**Mathematical Crash Threshold:** 83% 
\n*Data dynamically aggregates from Yahoo Finance and the Federal Reserve Bank of St. Louis (FRED).*
"""
)
