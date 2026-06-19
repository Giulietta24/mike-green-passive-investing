import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import requests

# Set up Page Config
st.set_page_config(
    page_title="Passive Endgame Framework Monitor", page_icon="📊", layout="wide"
)

st.title("📊 Passive Endgame Framework Monitor")
st.markdown(
    """
This dashboard monitors macroeconomic parameters and concentration spreads as a tool to evaluate the 
**Passive Investing Endgame Hypothesis** (pioneered by researchers like Mike Green). 
This framework explores whether mechanical, index-driven inflows reduce market elasticity and alter price discovery. 
*Note: The relationships displayed here represent an economic hypothesis under observation, not established causal certainties.*
"""
)
st.divider()

# -----------------------------------------------------------------------------
# API KEY RESOLUTION 
# -----------------------------------------------------------------------------
fred_key = None
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
else:
    fred_key = st.sidebar.text_input(
        "🔑 Enter Free FRED API Key:", 
        type="password",
        help="Get a free key instantly from https://fred.stlouisfed.org/docs/api/api_key.html"
    )

if not fred_key:
    st.warning("⚠️ Please input your free FRED API Key in the sidebar to populate macroeconomic observations.")


# Helper function to fetch data using FRED's official JSON endpoint
@st.cache_data(ttl=3600)
def fetch_fred_api(series_id, api_key):
    if not api_key:
        return pd.DataFrame()
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    try:
        response = requests.get(url, timeout=10).json()
        if "observations" not in response:
            return pd.DataFrame()
        df = pd.DataFrame(response["observations"])
        df["DATE"] = pd.to_datetime(df["date"])
        df[series_id] = pd.to_numeric(df["value"], errors="coerce")
        df = df.set_index("DATE")[[series_id]].dropna()
        return df
    except Exception:
        return pd.DataFrame()


# Helper function to grab Yahoo Finance data & strictly align dates
@st.cache_data(ttl=3600)
def fetch_mkt_data():
    # Use explicit dates to minimize exchange-time zone overlap edge cases
    today = datetime.datetime.now()
    start_date = today - datetime.timedelta(days=365)
    try:
        spy_ticker = yf.Ticker("SPY").history(start=start_date, end=today)
        rsp_ticker = yf.Ticker("RSP").history(start=start_date, end=today)
        
        if spy_ticker.empty or rsp_ticker.empty:
            return pd.DataFrame()
        
        # Pull close values and clean up indices to prevent mismatch mapping
        spy_close = spy_ticker["Close"].rename("SPY")
        rsp_close = rsp_ticker["Close"].rename("RSP")
        
        # Concat with an inner join to strictly align on matching trading dates only
        df = pd.concat([spy_close, rsp_close], axis=1, join="inner")
        
        # Fallback safeguard check if matching data is insufficient
        if df.empty or len(df) < 5:
            return pd.DataFrame()
            
        df["Ratio"] = df["SPY"] / df["RSP"]
        return df
    except Exception:
        return pd.DataFrame()


# Load Data
with st.spinner("Synchronizing market feeds and macro metrics..."):
    df_icsa = fetch_fred_api("ICSA", fred_key) if fred_key else pd.DataFrame()
    df_ccsa = fetch_fred_api("CCSA", fred_key) if fred_key else pd.DataFrame()
    df_spread = fetch_fred_api("BAMLH0A0HYM2", fred_key) if fred_key else pd.DataFrame()
    df_mkt = fetch_mkt_data()

# -----------------------------------------------------------------------------
# PHASE 1: METRICS DISPLAY
# -----------------------------------------------------------------------------
st.header("🚨 Systemic Framework Watches")
col1, col2, col3, col4 = st.columns(4)

# 1. INITIAL CLAIMS CARD
with col1:
    st.subheader("Initial Claims")
    if not df_icsa.empty and len(df_icsa) >= 2:
        latest_icsa = df_icsa["ICSA"].iloc[-1]
        prev_icsa = df_icsa["ICSA"].iloc[-2]
        icsa_delta = latest_icsa - prev_icsa
        as_of = df_icsa.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="Weekly Jobless Claims",
            value=f"{latest_icsa:,.0f}",
            delta=f"{icsa_delta:,.0f} vs last wk",
            delta_color="inverse",
            help=f"Observed on {as_of}. Within the hypothesis, employment data is watched because drops in aggregate employment could logically affect non-discretionary 401(k) allocations."
        )
        st.caption(f"Latest Obs: {as_of}")
        if latest_icsa > 250000:
            st.warning("⚠️ High Stress Watch (>250k)")
        else:
            st.success("🟢 Historical Baseline Range")
    else:
        st.error("❌ Stale or missing macro data feed")

# 2. CONTINUING CLAIMS CARD
with col2:
    st.subheader("Continuing Claims")
    if not df_ccsa.empty and len(df_ccsa) >= 2:
        latest_ccsa = df_ccsa["CCSA"].iloc[-1]
        prev_ccsa = df_ccsa["CCSA"].iloc[-2]
        ccsa_delta = latest_ccsa - prev_ccsa
        as_of = df_ccsa.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="Insured Unemployed",
            value=f"{latest_ccsa:,.0f}",
            delta=f"{ccsa_delta:,.0f} vs last wk",
            delta_color="inverse",
            help=f"Observed on {as_of}. Tracks extended unemployment trends under study for structural impact on regular investment flows."
        )
        st.caption(f"Latest Obs: {as_of}")
        if latest_ccsa > 1900000:
            st.warning("⚠️ Elevated Risk Watch (>1.9M)")
        else:
            st.success("🟢 Baseline Range")
    else:
        st.error("❌ Stale or missing macro data feed")

# 3. HIGH YIELD SPREAD CARD
with col3:
    st.subheader("Credit Risk Premium")
    if not df_spread.empty and len(df_spread) >= 2:
        latest_spread = df_spread["BAMLH0A0HYM2"].iloc[-1]
        prev_spread = df_spread["BAMLH0A0HYM2"].iloc[-2]
        spread_delta = round(latest_spread - prev_spread, 2)
        as_of = df_spread.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="HY Bond Spread",
            value=f"{latest_spread}%",
            delta=f"{spread_delta}% vs prev day",
            delta_color="inverse",
            help=f"Observed on {as_of}. Monitors broad active-market valuation premiums as a gauge for systemic liquidity pressure."
        )
        st.caption(f"Latest Obs: {as_of}")
        if latest_spread > 4.5:
            st.warning("⚠️ Credit Expansion Watch (>4.5%)")
        else:
            st.success("🟢 Baseline Dispersion Level")
    else:
        st.error("❌ Credit risk feed unavailable")

# 4. CONCENTRATION CARD (SPY/RSP PROXY)
with col4:
    st.subheader("Market Concentration Proxy")
    if not df_mkt.empty and len(df_mkt) >= 5:
        latest_ratio = df_mkt["Ratio"].iloc[-1]
        prev_ratio = df_mkt["Ratio"].iloc[-5]
        ratio_delta = round(latest_ratio - prev_ratio, 3)
        as_of = df_mkt.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="SPY / RSP Ratio",
            value=f"{latest_ratio:.3f}",
            delta=f"{ratio_delta:.3f} (5d change)",
            help=f"Observed on {as_of}. This is a concentration proxy tracking the performance of capitalization weights against equal weights, not a direct measurement of total systemic passive share."
        )
        st.caption(f"Latest Obs: {as_of}")
        if latest_ratio > 3.0:
            st.info("ℹ️ Elevated Concentration Regime")
        else:
            st.success("🟢 Broad Capital Representation")
    else:
        st.error("⚠️ Yahoo Finance returns stale/missing data")

st.divider()

# -----------------------------------------------------------------------------
# PHASE 2: CHARTS
# -----------------------------------------------------------------------------
st.header("📈 Data Visualizations & Structural Frameworks")

tab1, tab2, tab3 = st.tabs(
    ["🔎 Concentration Proxy Trends", "🧑‍🔧 Labor Data Series", "📉 Fixed Income Spreads"]
)

with tab1:
    st.subheader("SPY (Cap-Weighted) vs RSP (Equal-Weighted) Ratio Trend")
    with st.expander("💡 Analytical Note: What does this chart proxy?", expanded=True):
        st.markdown("""
        * **Proxy Nature:** This line tracks capitalization versus equal weight allocation trends. It does **not** trace absolute index market share directly.
        * **Upward Slopes:** Reflect heavy mega-cap concentration dominance. 
        * **Downward Slopes:** Reflect a more balanced return profile among smaller constituent companies.
        """)
        
    if not df_mkt.empty:
        fig1 = go.Figure()
        fig1.add_hrect(y0=0, y1=2.5, line_width=0, fillcolor="rgba(0, 255, 0, 0.05)", annotation_text="Historical Baseline Sector Participation", annotation_position="bottom left")
        fig1.add_hrect(y0=3.0, y1=4.5, line_width=0, fillcolor="rgba(255, 165, 0, 0.05)", annotation_text="Elevated Inelastic Concentration Range", annotation_position="top left")
        fig1.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Ratio"], mode="lines", name="SPY/RSP Ratio", line=dict(color="#1f77b4", width=2.5)))
        fig1.update_layout(xaxis_title="Date", yaxis_title="Ratio Value", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.warning("⚠️ Visualization unavailable due to date alignment limits or server timeout.")

with tab2:
    st.subheader("Weekly Initial Jobless Claims")
    with st.expander("💡 Analytical Note: Framework significance", expanded=True):
        st.markdown("""
        * **Tracking Purpose:** Evaluates consistency in payroll environments.
        * **Reference Mark:** The line at **250,000** highlights a historical shift level watched within the framework to monitor potential flow friction points.
        """)
        
    if not df_icsa.empty:
        plot_df = df_icsa.tail(104)
        fig2 = go.Figure()
        fig2.add_hline(y=250000, line_dash="dash", line_color="orange", line_width=1.5, annotation_text="Framework Reference Level")
        fig2.add_trace(go.Scatter(x=plot_df.index, y=plot_df["ICSA"], mode="lines", name="Initial Claims", line=dict(color="#FF4B4B", width=2)))
        fig2.update_layout(xaxis_title="Date", yaxis_title="Claims Volume", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Please verify your FRED API Key configuration to display historical lines.")

with tab3:
    st.subheader("ICE BofA High Yield Option-Adjusted Spread")
    with st.expander("💡 Analytical Note: Volatility context", expanded=True):
        st.markdown("""
        * **Tracking Purpose:** Evaluates relative pricing risks in corporate debt.
        * **Reference Mark:** Spreads above **4.5%** historically signal broad macroeconomic or financing adjustments under review by active asset pricing markets.
        """)
        
    if not df_spread.empty:
        plot_df = df_spread.tail(260)
        fig3 = go.Figure()
        fig3.add_hline(y=4.5, line_dash="dash", line_color="orange", line_width=1.5, annotation_text="Macro Reference Level")
        fig3.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BAMLH0A0HYM2"], mode="lines", name="Credit Spread", line=dict(color="#00C0F2", width=2)))
        fig3.update_layout(xaxis_title="Date", yaxis_title="Spread Percentage (%)", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("Please verify your FRED API Key configuration to display historical lines.")


# Sidebar parameter and background context information
with st.sidebar:
    st.title("🧩 Framework Definitions")
    
    st.info("""
    **The 75% - 83% Structural Limit:**
    In academic modeling (such as Green, Krishnan, and Sturm), theoretical outer bounds are analyzed where complete domination of passive architecture complicates pricing functionality. 
    
    Because true aggregated passive share involves multi-asset tracking matrix allocations that cannot be fetched daily via text tickers, this dashboard utilizes **the SPY/RSP Ratio as a visual proxy for trend concentration** rather than an explicit data measurement of that limit.
    """)
