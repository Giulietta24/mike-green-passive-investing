import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import requests

# 1. PAGE SETUP
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

# Get server timezone-naive current date safely
UTC_TODAY = datetime.datetime.now(datetime.timezone.utc).date()

# -----------------------------------------------------------------------------
# 2. DATA ACQUISITION ENGINES
# -----------------------------------------------------------------------------
def format_obs_date(df, column_name):
    if df.empty or column_name not in df.columns: return "N/A"
    valid_series = df[column_name].dropna()
    if valid_series.empty: return "N/A"
    return valid_series.index[-1].strftime("%b %d, %Y")

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
    tickers = {
        "SPY": "SPY", "RSP": "RSP", 
        "VIX": "^VIX", "VVIX": "^VVIX", 
        "Copper": "HG=F", "Gold": "GC=F", "Lumber": "LBS=F"
    }
    series_list = []
    
    for name, sym in tickers.items():
        try:
            t = yf.Ticker(sym).history(start=start_date, end=UTC_TODAY)
            if not t.empty:
                s = t["Close"].rename(name)
                s.index = s.index.tz_localize(None)
                series_list.append(s)
        except Exception:
            continue
            
    if not series_list:
        return pd.DataFrame()
        
    df = pd.concat(series_list, axis=1, join="outer")
    df = df.ffill().dropna(subset=["SPY", "RSP"])
    
    df["Concentration_Ratio"] = df["SPY"] / df["RSP"]
    if "VVIX" in df.columns and "VIX" in df.columns:
        df["Vol_Dispersion"] = df["VVIX"] / df["VIX"]
    if "Copper" in df.columns and "Gold" in df.columns:
        df["Copper_Gold"] = df["Copper"] / df["Gold"]
    if "Lumber" in df.columns and "Gold" in df.columns:
        df["Lumber_Gold"] = df["Lumber"] / df["Gold"]
        
    return df

# -----------------------------------------------------------------------------
# 3. GLOBAL DATA LOADING
# -----------------------------------------------------------------------------
fred_key = None
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
else:
    fred_key = st.sidebar.text_input("🔑 Enter Free FRED API Key:", type="password")

with st.spinner("Compiling structural risk framework..."):
    # FETCHING BOTH INITIAL (ICSA) AND CONTINUING (CCSA) CLAIMS NOW
    df_icsa, _ = fetch_fred_api("ICSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_ccsa, _ = fetch_fred_api("CCSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_jobs, _ = fetch_fred_api("CSCICP03USM665S", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_mkt = fetch_mkt_data()

# Merge FRED claims files together cleanly for mapping
df_claims = pd.DataFrame()
if not df_icsa.empty and not df_ccsa.empty:
    df_claims = pd.concat([df_icsa, df_ccsa], axis=1, join="inner")

# -----------------------------------------------------------------------------
# 4. SYSTEMIC SUMMARY BANNER
# -----------------------------------------------------------------------------
if not df_mkt.empty and not df_claims.empty and not df_jobs.empty:
    current_ratio = df_mkt["Concentration_Ratio"].iloc[-1]
    current_icsa = df_claims["ICSA"].iloc[-1]
    current_disp = df_mkt.get("Vol_Dispersion", pd.Series([0])).iloc[-1]
    
    triggers_tripped = 0
    if current_ratio > 3.0: triggers_tripped += 1
    if current_icsa > 250000: triggers_tripped += 1
    if current_disp > 5.5: triggers_tripped += 1
    
    if triggers_tripped >= 2:
        st.error("🚨 **SYSTEMIC ASSESSMENT:** Multiple framework conditions are triggered. High concentration/stress environment.")
    elif triggers_tripped == 1:
        st.warning("⚠️ **SYSTEMIC ASSESSMENT:** Isolated structural watch active. Review specific charts below.")
    else:
        st.success("🟢 **SYSTEMIC ASSESSMENT:** All metrics currently within normal historical baseline ranges.")
else:
    st.info("💡 **SYSTEMIC ASSESSMENT:** Connect your FRED API key to generate system health status indicators.")

st.divider()

# -----------------------------------------------------------------------------
# 5. FRONT METRIC TILES
# -----------------------------------------------------------------------------
st.header("🚨 Systemic Threshold Alerts")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.subheader("Labor Flow Engine")
    if not df_claims.empty:
        latest_icsa = df_claims["ICSA"].iloc[-1]
        st.metric(
            label="Weekly Jobless Claims", 
            value=f"{latest_icsa:,.0f}",
            help="WHAT TO LOOK FOR: If this shoots ABOVE 250k, people are losing jobs. Automatic 401(k) stock buying drops to zero, and the blind market floor vanishes."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_claims, 'ICSA')}")
        if latest_icsa > 250000:
            st.error("🚨 DANGER: Over 250k!")
        else:
            st.success("🟢 Flow Engine Healthy")
    else:
        st.error("❌ Link FRED API Key")

with col2:
    st.subheader("Jobs Confidence")
    if not df_jobs.empty:
        latest_jobs = df_jobs["CSCICP03USM665S"].iloc[-1]
        st.metric(
            label="OECD US Confidence Proxy", 
            value=f"{latest_jobs:.2f}",
            help="WHAT TO LOOK FOR: Tracks broad economic safety. Below 100 indicates contraction; crossing under 98.5 confirms major structural workforce disruptions."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_jobs, 'CSCICP03USM665S')}")
        if latest_jobs < 98.5:
            st.error("🚨 Confidence Contracting")
        else:
            st.success("🟢 Confidence Stable")
    else:
        st.error("❌ Link FRED API Key")

with col3:
    st.subheader("Market Concentration")
    if not df_mkt.empty:
        latest_ratio = df_mkt["Concentration_Ratio"].iloc[-1]
        st.metric(
            label="SPY / RSP Ratio", 
            value=f"{latest_ratio:.3f}",
            help="WHAT TO LOOK FOR: Above 3.00 means passive flows are blindly forcing all capital into just the top mega-caps, leaving the rest of the index starved."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_mkt, 'Concentration_Ratio')}")
        if latest_ratio > 3.0:
            st.warning("⚠️ Extreme Concentration")
        else:
            st.success("🟢 Normal Dispersion")
    else:
        st.error("❌ Market Data Delay")

with col4:
    st.subheader("Volatility Dispersion")
    if not df_mkt.empty and "Vol_Dispersion" in df_mkt.columns:
        latest_disp = df_mkt["Vol_Dispersion"].iloc[-1]
        st.metric(
            label="VVIX / VIX Ratio", 
            value=f"{latest_disp:.2f}x",
            help="WHAT TO LOOK FOR: Multiples climbing past 5.5x indicate that while the index looks dead calm, underlying single stocks are experiencing structural stress."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_mkt, 'Vol_Dispersion')}")
        if latest_disp > 5.5:
            st.warning("⚠️ Hidden Systemic Chaos")
        else:
            st.success("🟢 Compressed Index")
    else:
        st.error("❌ Vol Data Delay")

st.divider()

# -----------------------------------------------------------------------------
# 6. GRAPH VISUALIZATIONS & ADHD CHEAT SHEETS
# -----------------------------------------------------------------------------
st.header("📈 Deep Framework Diagnostics")
tab1, tab2, tab3 = st.tabs(["⚙️ Volatility Dispersion Mechanics", "🧑‍🔧 Labor Dynamics (The Fuel)", "📉 Real Economy Check-Engine Light"])

with tab1:
    st.subheader("Under-The-Hood Option Dispersion Proxy (VVIX / VIX)")
    with st.expander("💡 Cheat Sheet: How do I read this chart?", expanded=True):
        st.markdown("""
        * **What is it?** Compares index volatility (VIX) against option asset volatility vectors (VVIX).
        * **Going UP?** Passive indexing concentration handles and masks structural, localized market pricing risks.
        """)
    if not df_mkt.empty and "Vol_Dispersion" in df_mkt.columns:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Vol_Dispersion"], mode="lines", name="VVIX/VIX Ratio", line=dict(color="#9b59b6", width=2.5)))
        fig1.update_layout(xaxis_title="Date", yaxis_title="Ratio Multiple", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig1, use_container_width=True)

with tab2:
    st.subheader("Initial vs. Continuing Unemployment Claims")
    with st.expander("💡 Cheat Sheet: Dual-Engine Fuel Loss Tracking", expanded=True):
        st.markdown("""
        * **Initial Claims (Red Line):** Shows how many people lost their job *this week*.
        * **Continuing Claims (Blue Line):** Shows how many people *remain* unemployed. 
        * **Why this combo is lethal:** If Continuing Claims scale upward, it means individuals are stuck out of work. Their recurring payroll retirement bid allocations are wiped out over a sustained period, removing the baseline mechanical bid keeping index valuations inflated.
        """)
    if not df_claims.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_claims.index, y=df_claims["ICSA"], mode="lines", name="Initial Claims (Weekly)", line=dict(color="#FF4B4B", width=2)))
        fig2.add_trace(go.Scatter(x=df_claims.index, y=df_claims["CCSA"], mode="lines", name="Continuing Claims (Sustained)", line=dict(color="#1f77b4", width=2), yaxis="y2"))
        
        # Setup dual axis layout so different scale sizes display perfectly together
        fig2.update_layout(
            xaxis_title="Date",
            yaxis=dict(title="Initial Claims Volume", titlefont=dict(color="#FF4B4B"), tickfont=dict(color="#FF4B4B")),
            yaxis2=dict(title="Continuing Claims Volume", titlefont=dict(color="#1f77b4"), tickfont=dict(color="#1f77b4"), overlaying="y", side="right"),
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Industrial Commodities Priced in Gold")
    if not df_mkt.empty and "Copper_Gold" in df_mkt.columns:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Copper_Gold"], mode="lines", name="Copper/Gold Ratio", line=dict(color="#d35400", width=2)))
        if "Lumber_Gold" in df_mkt.columns:
            fig3.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Lumber_Gold"], mode="lines", name="Lumber/Gold Ratio", line=dict(color="#f39c12", width=2)))
        fig3.update_layout(xaxis_title="Date", yaxis_title="Ratio Pricing", margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig3, use_container_width=True)

# -----------------------------------------------------------------------------
# 7. SIDEBAR REFRESH & REGISTRIES
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Controls")
    if st.button("🔄 Clear Cache & Refresh Data"):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    
    st.title("🧮 Glacier Metrics")
    passive_share = st.number_input(
        "Update Passive Market Share % (ICI Data):",
        min_value=0.0, max_value=100.0, value=54.2, step=0.1
    )
    st.progress(passive_share / 100.0)
    st.caption(f"Current State: **{passive_share}%**. Breaking threshold: **83.0%**.")
    
    st.divider()
    
    st.title("📜 Policy Tracker (401k Inflows)")
    st.markdown("**SECURE Act 2.0 Structural Roadmap:**")
    st.checkbox("Mandatory Auto-Enrollment (New Corporate Plans)", value=True, disabled=True)
    st.checkbox("Catch-up limit increases for older workers", value=True, disabled=True)
    st.checkbox("Expanded Part-Time Employee Pools", value=False)
