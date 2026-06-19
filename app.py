import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import requests

# Set up Page Config
st.set_page_config(
    page_title="Passive Endgame Monitor", page_icon="📊", layout="wide"
)

st.title("📊 Mike Green's Passive Endgame Monitor")
st.markdown(
    """
**Hey! Read this if you forget what this screen is:** This dashboard tracks whether the stock market is becoming 
dangerously unstable because everyone is automatically buying index funds. If employment drops, these automatic 
buys stop, and the market plumbing could break.
"""
)
st.divider()

# Timezone-naive date fix: Use UTC for server consistency
UTC_TODAY = datetime.datetime.now(datetime.timezone.utc).date()

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS 
# -----------------------------------------------------------------------------
def format_obs_date(df):
    if df.empty:
        return "N/A"
    return df.index[-1].strftime("%b %d, %Y")

@st.cache_data(ttl=3600)
def fetch_fred_api(series_id, api_key):
    if not api_key:
        return pd.DataFrame(), "N/A"
    obs_url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    meta_url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={api_key}&file_type=json"
    try:
        obs_res = requests.get(obs_url, timeout=10).json()
        meta_res = requests.get(meta_url, timeout=10).json()
        if "observations" not in obs_res:
            return pd.DataFrame(), "N/A"
        df = pd.DataFrame(obs_res["observations"])
        df["DATE"] = pd.to_datetime(df["date"])
        df[series_id] = pd.to_numeric(df["value"], errors="coerce")
        df = df.set_index("DATE")[[series_id]].dropna()
        last_updated = "N/A"
        if "seriess" in meta_res and len(meta_res["seriess"]) > 0:
            raw_date = meta_res["seriess"][0].get("last_updated", "")
            if raw_date:
                last_updated = pd.to_datetime(raw_date).strftime("%b %d, %Y")
        return df, last_updated
    except Exception:
        return pd.DataFrame(), "N/A"

@st.cache_data(ttl=3600)
def fetch_mkt_data():
    start_date = UTC_TODAY - datetime.timedelta(days=365)
    try:
        spy_ticker = yf.Ticker("SPY").history(start=start_date, end=UTC_TODAY)
        rsp_ticker = yf.Ticker("RSP").history(start=start_date, end=UTC_TODAY)
        cor_ticker = yf.Ticker("^COR3M").history(start=start_date, end=UTC_TODAY) # Vol Dispersion Proxy
        
        if spy_ticker.empty or rsp_ticker.empty:
            return pd.DataFrame()
            
        spy_ticker.index = spy_ticker.index.tz_localize(None)
        rsp_ticker.index = rsp_ticker.index.tz_localize(None)
        
        spy_close = spy_ticker["Close"].rename("SPY")
        rsp_close = rsp_ticker["Close"].rename("RSP")
        df = pd.concat([spy_close, rsp_close], axis=1, join="inner")
        df["Ratio"] = df["SPY"] / df["RSP"]
        
        if not cor_ticker.empty:
            cor_ticker.index = cor_ticker.index.tz_localize(None)
            df = df.join(cor_ticker["Close"].rename("Correlation"), how="left")
            
        return df.dropna()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_divergence_data():
    """Fetches Category 3: Copper vs Gold real-economy indicator"""
    start_date = UTC_TODAY - datetime.timedelta(days=365)
    try:
        copper = yf.Ticker("HG=F").history(start=start_date, end=UTC_TODAY)
        gold = yf.Ticker("GC=F").history(start=start_date, end=UTC_TODAY)
        
        if copper.empty or gold.empty:
            return pd.DataFrame()
            
        copper.index = copper.index.tz_localize(None)
        gold.index = gold.index.tz_localize(None)
        
        df = pd.concat([copper["Close"].rename("Copper"), gold["Close"].rename("Gold")], axis=1, join="inner")
        df["Divergence_Ratio"] = df["Copper"] / df["Gold"]
        return df.dropna()
    except Exception:
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# INITIAL LOAD
# -----------------------------------------------------------------------------
fred_key = None
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
else:
    fred_key = st.sidebar.text_input("🔑 Enter Free FRED API Key:", type="password")

with st.spinner("Loading framework indicators..."):
    df_icsa, icsa_updated = fetch_fred_api("ICSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_ccsa, ccsa_updated = fetch_fred_api("CCSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_spread, spread_updated = fetch_fred_api("BAMLH0A0HYM2", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_mkt = fetch_mkt_data()
    df_div = fetch_divergence_data()

# -----------------------------------------------------------------------------
# METRICS DISPLAY
# -----------------------------------------------------------------------------
st.header("🚨 Systemic Threshold Alerts")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.subheader("Initial Claims")
    if not df_icsa.empty and len(df_icsa) >= 2:
        latest_icsa = df_icsa["ICSA"].iloc[-1]
        st.metric(label="Weekly Jobless Claims", value=f"{latest_icsa:,.0f}")
        st.caption(f"📅 **Obs:** {format_obs_date(df_icsa)}")
        st.error("🚨 Over 250k!") if latest_icsa > 250000 else st.success("🟢 OK: Under 250k")

with col2:
    st.subheader("Credit Risk")
    if not df_spread.empty and len(df_spread) >= 2:
        latest_spread = df_spread["BAMLH0A0HYM2"].iloc[-1]
        st.metric(label="HY Bond Spread", value=f"{latest_spread:.2f}%")
        st.caption(f"📅 **Obs:** {format_obs_date(df_spread)}")
        st.error("🚨 Stress: Over 4.5%!") if latest_spread > 4.5 else st.success("🟢 OK: Normal Spreads")

with col3:
    st.subheader("Market Concentration")
    if not df_mkt.empty:
        latest_ratio = df_mkt["Ratio"].iloc[-1]
        st.metric(label="SPY / RSP Ratio", value=f"{latest_ratio:.3f}")
        st.caption(f"📅 **Obs:** {format_obs_date(df_mkt)}")
        st.warning("⚠️ Ratio over 3.0") if latest_ratio > 3.0 else st.success("🟢 Broad Market")

with col4:
    st.subheader("Volatility Dispersion")
    if not df_mkt.empty and "Correlation" in df_mkt.columns:
        latest_cor = df_mkt["Correlation"].iloc[-1]
        st.metric(label="3M Implied Correlation Index", value=f"{latest_cor:.2f}%", help="Category 2 Proxy: High index correlations indicate individual stock fundamentals are being overriden by structural passive flows.")
        st.caption(f"📅 **Obs:** {format_obs_date(df_mkt)}")
        st.warning("⚠️ Mechanical Inelasticity High") if latest_cor > 60.0 else st.success("🟢 Normal Autonomy")

st.divider()

# -----------------------------------------------------------------------------
# VISUALIZATION TABS (Includes Category 3 Addition)
# -----------------------------------------------------------------------------
st.header("📈 Framework Visualizations")
tab1, tab2, tab3 = st.tabs(["🔎 Market Mechanics & Dispersion", "🧑‍🔧 Labor Flows", "📉 Real Economy Divergence (Check Engine)"])

with tab1:
    if not df_mkt.empty:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Ratio"], mode="lines", name="SPY/RSP Ratio", line=dict(color="#1f77b4", width=3)))
        fig1.update_layout(xaxis_title="Date", yaxis_title="Ratio", margin=dict(l=20, r=20, t=20, b=20))
        fig1.update_xaxes(showspikes=True, spikecolor="gray", spikemode="across")
        st.plotly_chart(fig1, use_container_width=True)

with tab2:
    if not df_icsa.empty:
        fig2 = go.Figure()
        fig2.add_hline(y=250000, line_dash="dash", line_color="red")
        fig2.add_trace(go.Scatter(x=df_icsa.tail(104).index, y=df_icsa.tail(104)["ICSA"], mode="lines", name="Claims", line=dict(color="#FF4B4B")))
        fig2.update_layout(xaxis_title="Date", yaxis_title="Claims Volume", margin=dict(l=20, r=20, t=20, b=20))
        fig2.update_xaxes(showspikes=True, spikecolor="gray", spikemode="across")
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Copper / Gold Ratio (Industrial Economy Health)")
    with st.expander("💡 How to read the Check Engine Light", expanded=True):
        st.markdown("""
        * **What is it?** Measures heavy industrial demand (Copper) against pure monetary safety (Gold). 
        * **The Divergence Danger:** If the S&P 500 is going up but this line is **crashing**, it proves that the real physical economy is entering a quiet recession while the passive indexing engine is simply running on automatic pilot.
        """)
    if not df_div.empty:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df_div.index, y=df_div["Divergence_Ratio"], mode="lines", name="Copper/Gold Ratio", line=dict(color="#E67E22", width=2.5)))
        fig3.update_layout(xaxis_title="Date", yaxis_title="Copper vs Gold Value", margin=dict(l=20, r=20, t=20, b=20))
        fig3.update_xaxes(showspikes=True, spikecolor="gray", spikemode="across")
        st.plotly_chart(fig3, use_container_width=True)

# -----------------------------------------------------------------------------
# SIDEBAR: STRUCTURAL ANCHORS (Category 2 Lagged/Glacial Data)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Controls")
    if st.button("🔄 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    
    # CATEGORY 2 MACRO ANCHOR (Hardcoded/Glacial Tracking)
    st.title("🧮 Glacier Metrics (Lagged)")
    st.markdown("**Total Passive Asset Market Share:**")
    st.progress(0.54) # Represents 54%
    st.caption("Current Estimate: **~54.0%** (Source: Mike Green / ICI Consensus). *The absolute mechanical breaking point is modeled at **83.0%**.*")
    
    st.divider()
    st.info("💡 **Theory Check:** Passive flows buy without calculating valuation or fundamentals. This app watches when the mechanical engine runs out of physical economic fuel.")
