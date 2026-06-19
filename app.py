import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import requests

# Page Configuration
st.set_page_config(
    page_title="Passive Endgame Monitor", page_icon="📊", layout="wide"
)

st.title("📊 Mike Green's Passive Endgame Monitor")
st.markdown(
    """
**System Overview:** This dashboard monitors the structural risks of passive indexing. 
When automated inflows (payrolls) drop or market concentration peaks, the deterministic mechanical buying engine faces a liquidity cliff.
"""
)
st.divider()

UTC_TODAY = datetime.datetime.now(datetime.timezone.utc).date()

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def format_obs_date(df):
    if df.empty: return "N/A"
    return df.index[-1].strftime("%b %d, %Y")

@st.cache_data(ttl=3600)
def fetch_fred_api(series_id, api_key):
    if not api_key: return pd.DataFrame(), "N/A"
    obs_url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    meta_url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={api_key}&file_type=json"
    try:
        obs_res = requests.get(obs_url, timeout=10).json()
        meta_res = requests.get(meta_url, timeout=10).json()
        if "observations" not in obs_res: return pd.DataFrame(), "N/A"
        df = pd.DataFrame(obs_res["observations"])
        df["DATE"] = pd.to_datetime(df["date"])
        df[series_id] = pd.to_numeric(df["value"], errors="coerce")
        df = df.set_index("DATE")[[series_id]].dropna()
        last_updated = "N/A"
        if "seriess" in meta_res and len(meta_res["seriess"]) > 0:
            raw_date = meta_res["seriess"][0].get("last_updated", "")
            if raw_date: last_updated = pd.to_datetime(raw_date).strftime("%b %d, %Y")
        return df, last_updated
    except Exception:
        return pd.DataFrame(), "N/A"

@st.cache_data(ttl=3600)
def fetch_mkt_data():
    start_date = UTC_TODAY - datetime.timedelta(days=365)
    try:
        # Core Ratios
        spy = yf.Ticker("SPY").history(start=start_date, end=UTC_TODAY)["Close"].rename("SPY")
        rsp = yf.Ticker("RSP").history(start=start_date, end=UTC_TODAY)["Close"].rename("RSP")
        
        # Volatility Dispersion Proxies
        vix = yf.Ticker("^VIX").history(start=start_date, end=UTC_TODAY)["Close"].rename("VIX")
        vvix = yf.Ticker("^VVIX").history(start=start_date, end=UTC_TODAY)["Close"].rename("VVIX")
        
        # Real Economy Divergence Commodities
        copper = yf.Ticker("HG=F").history(start=start_date, end=UTC_TODAY)["Close"].rename("Copper")
        gold = yf.Ticker("GC=F").history(start=start_date, end=UTC_TODAY)["Close"].rename("Gold")
        lumber = yf.Ticker("LBS=F").history(start=start_date, end=UTC_TODAY)["Close"].rename("Lumber")

        # Concat aligning all timelines safely
        df = pd.concat([spy, rsp, vix, vvix, copper, gold, lumber], axis=1, join="inner")
        df.index = df.index.tz_localize(None)
        
        # Derived Indicators
        df["Concentration_Ratio"] = df["SPY"] / df["RSP"]
        df["Vol_Dispersion"] = df["VVIX"] / df["VIX"]
        df["Copper_Gold"] = df["Copper"] / df["Gold"]
        df["Lumber_Gold"] = df["Lumber"] / df["Gold"]
        
        return df.dropna()
    except Exception:
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# DATA LOADING
# -----------------------------------------------------------------------------
fred_key = None
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
else:
    fred_key = st.sidebar.text_input("🔑 Enter Free FRED API Key:", type="password")

with st.spinner("Compiling structural risk framework..."):
    df_icsa, icsa_updated = fetch_fred_api("ICSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    # OECD Consumer/Labor Proxy Indicator
    df_jobs, jobs_updated = fetch_fred_api("CSCICP03USM665S", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_spread, spread_updated = fetch_fred_api("BAMLH0A0HYM2", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_mkt = fetch_mkt_data()

# -----------------------------------------------------------------------------
# FRONT METRIC TILES
# -----------------------------------------------------------------------------
st.header("🚨 Systemic Threshold Alerts")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.subheader("Labor Flow Engine")
    if not df_icsa.empty:
        latest_icsa = df_icsa["ICSA"].iloc[-1]
        st.metric(label="Weekly Jobless Claims", value=f"{latest_icsa:,.0f}")
        st.caption(f"📅 **Obs:** {format_obs_date(df_icsa)}")
        st.error("🚨 Over 250k Threshold!") if latest_icsa > 250000 else st.success("🟢 Flow Engine Healthy")
    else:
        st.error("❌ Link FRED API Key")

with col2:
    st.subheader("Jobs Confidence")
    if not df_jobs.empty:
        latest_jobs = df_jobs["CSCICP03USM665S"].iloc[-1]
        st.metric(label="OECD Us Confidence Proxy", value=f"{latest_jobs:.2f}")
        st.caption(f"📅 **Obs:** {format_obs_date(df_jobs)}")
        st.error("🚨 Consumer Confidence Contracting") if latest_jobs < 98.5 else st.success("🟢 Confidence Stable")
    else:
        st.error("❌ Link FRED API Key")

with col3:
    st.subheader("Market Concentration")
    if not df_mkt.empty:
        latest_ratio = df_mkt["Concentration_Ratio"].iloc[-1]
        st.metric(label="SPY / RSP Ratio", value=f"{latest_ratio:.3f}")
        st.caption(f"📅 **Obs:** {format_obs_date(df_mkt)}")
        st.warning("⚠️ Extreme Top-Heavy Concentration") if latest_ratio > 3.0 else st.success("🟢 Normal Capital Dispersion")
    else:
        st.error("❌ Market Data Delay")

with col4:
    st.subheader("Volatility Dispersion")
    if not df_mkt.empty:
        latest_disp = df_mkt["Vol_Dispersion"].iloc[-1]
        st.metric(label="VVIX / VIX Ratio", value=f"{latest_disp:.2f}x")
        st.caption(f"📅 **Obs:** {format_obs_date(df_mkt)}")
        st.warning("⚠️ Hidden Single-Stock Chaos") if latest_disp > 5.5 else st.success("🟢 Compressed/Quiet Index")
    else:
        st.error("❌ Vol Data Delay")

st.divider()

# -----------------------------------------------------------------------------
# GRAPH VISUALIZATIONS
# -----------------------------------------------------------------------------
st.header("📈 Deep Framework Diagnostics")
tab1, tab2, tab3 = st.tabs(["⚙️ Volatility & Mechanics", "🧑‍🔧 Labor Dynamics", "📉 Real Economy Check-Engine Light"])

with tab1:
    st.subheader("Under-The-Hood Option Dispersion Proxy (VVIX / VIX)")
    if not df_mkt.empty:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Vol_Dispersion"], mode="lines", name="VVIX/VIX Ratio", line=dict(color="#9b59b6", width=2.5)))
        fig1.update_layout(xaxis_title="Date", yaxis_title="Ratio Multiple", margin=dict(l=20, r=20, t=20, b=20))
        fig1.update_xaxes(showspikes=True, spikecolor="gray", spikemode="across")
        st.plotly_chart(fig1, use_container_width=True)

with tab2:
    st.subheader("Structural Automated Inflow Health")
    if not df_jobs.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_jobs.index, y=df_jobs["CSCICP03USM665S"], mode="lines", name="OECD Proxy", line=dict(color="#2ecc71", width=2.5)))
        fig2.update_layout(xaxis_title="Date", yaxis_title="Index Level", margin=dict(l=20, r=20, t=20, b=20))
        fig2.update_xaxes(showspikes=True, spikecolor="gray", spikemode="across")
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Industrial Commodities Priced in Gold (Real-World vs Financial Matrix)")
    if not df_mkt.empty:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Copper_Gold"], mode="lines", name="Copper/Gold Ratio", line=dict(color="#d35400", width=2)))
        fig3.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Lumber_Gold"], mode="lines", name="Lumber/Gold Ratio", line=dict(color="#f39c12", width=2)))
        fig3.update_layout(xaxis_title="Date", yaxis_title="Ratio Pricing", margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", y=1.1))
        fig3.update_xaxes(showspikes=True, spikecolor="gray", spikemode="across")
        st.plotly_chart(fig3, use_container_width=True)

# -----------------------------------------------------------------------------
# SIDEBAR CONTROL & QUALITATIVE LEGISLATION REGISTRY
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Controls")
    if st.button("🔄 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    
    # 4. PASSIVE AUM INTERACTIVE INPUT (Option A)
    st.title("🧮 Glacier Metrics")
    passive_share = st.number_input(
        "Update Passive Market Share % (ICI Data):",
        min_value=0.0, max_value=100.0, value=54.2, step=0.1,
        help="Update manually when monthly/quarterly Investment Company Institute reports drop."
    )
    st.progress(passive_share / 100.0)
    st.caption(f"Current State: **{passive_share}%**. Theoretical breaking threshold: **83.0%**.")
    
    st.divider()
    
    # 5. 401(k) STRUCTURAL REGULATORY WATCH
    st.title("📜 Policy Tracker (401k Inflows)")
    st.markdown("**SECURE Act 2.0 Structural Roadmap:**")
    
    st.checkbox("Mandatory Auto-Enrollment (New 2025+ Corporate Plans)", value=True, disabled=True)
    st.checkbox("Catch-up limit increases for older workers", value=True, disabled=True)
    st.checkbox("Expanded Part-Time Employee Eligible Pools", value=False, help="Keep an eye on further corporate adoption or legal pushbacks that impact general workforce participation volume.")
    
    st.info("💡 **Passive Theory Rule:** Legislative moves forcing structural auto-enrollment create a constant blind bid baseline, completely detached from underlying company valuations.")
