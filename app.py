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
# HELPER FUNCTIONS (Cleaned & Consolidated)
# -----------------------------------------------------------------------------
def format_obs_date(df):
    """Helper function to format the latest observation date cleanly."""
    if df.empty:
        return "N/A"
    return df.index[-1].strftime("%b %d, %Y")

@st.cache_data(ttl=3600)
def fetch_fred_api(series_id, api_key):
    """Fetches series observations alongside metadata properties from FRED."""
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
        
        # Pull last update time from metadata
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
    """Grab Yahoo Finance data & strictly align dates."""
    start_date = UTC_TODAY - datetime.timedelta(days=365)
    try:
        spy_ticker = yf.Ticker("SPY").history(start=start_date, end=UTC_TODAY)
        rsp_ticker = yf.Ticker("RSP").history(start=start_date, end=UTC_TODAY)
        
        if spy_ticker.empty or rsp_ticker.empty:
            return pd.DataFrame()
            
        spy_ticker.index = spy_ticker.index.tz_localize(None)
        rsp_ticker.index = rsp_ticker.index.tz_localize(None)
        
        spy_close = spy_ticker["Close"].rename("SPY")
        rsp_close = rsp_ticker["Close"].rename("RSP")
        
        df = pd.concat([spy_close, rsp_close], axis=1, join="inner")
        df["Ratio"] = df["SPY"] / df["RSP"]
        df = df.dropna()
        
        if df.empty or len(df) < 5:
            return pd.DataFrame()
            
        return df
    except Exception:
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# API KEY RESOLUTION & INITIAL LOAD
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
    st.warning("⚠️ Please enter your free FRED API Key in the left sidebar to show the Macro Flow numbers.")

with st.spinner("Fetching latest market and macro plumbing metrics..."):
    df_icsa, icsa_updated = fetch_fred_api("ICSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_ccsa, ccsa_updated = fetch_fred_api("CCSA", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_spread, spread_updated = fetch_fred_api("BAMLH0A0HYM2", fred_key) if fred_key else (pd.DataFrame(), "N/A")
    df_mkt = fetch_mkt_data()

# -----------------------------------------------------------------------------
# EXECUTIVE AT-A-GLANCE STATUS SUMMARY
# -----------------------------------------------------------------------------
if not df_mkt.empty and not df_icsa.empty and not df_spread.empty:
    current_ratio = df_mkt["Ratio"].iloc[-1]
    current_icsa = df_icsa["ICSA"].iloc[-1]
    current_spread = df_spread["BAMLH0A0HYM2"].iloc[-1]
    
    triggers_tripped = 0
    if current_ratio > 3.0: triggers_tripped += 1
    if current_icsa > 250000: triggers_tripped += 1
    if current_spread > 4.5: triggers_tripped += 1
    
    if triggers_tripped >= 2:
        st.error("🚨 **SYSTEMIC ASSESSMENT:** Multiple system threshold conditions are triggered. High concentration/stress environment.")
    elif triggers_tripped == 1:
        st.warning("⚠️ **SYSTEMIC ASSESSMENT:** One system criteria watch active. Review individual cards below.")
    else:
        st.success("🟢 **SYSTEMIC ASSESSMENT:** Everything is clear. All parameters are tracking inside normal baseline boundaries.")
else:
    st.info("💡 **SYSTEMIC ASSESSMENT:** Connect your API key to generate system health status indicators.")

st.divider()

# -----------------------------------------------------------------------------
# PHASE 1: METRICS DISPLAY
# -----------------------------------------------------------------------------
st.header("🚨 Systemic Threshold Alerts")
col1, col2, col3, col4 = st.columns(4)

# 1. INITIAL CLAIMS CARD
with col1:
    st.subheader("Initial Claims")
    if not df_icsa.empty and len(df_icsa) >= 2:
        latest_icsa = df_icsa["ICSA"].iloc[-1]
        prev_icsa = df_icsa["ICSA"].iloc[-2]
        icsa_delta = latest_icsa - prev_icsa
        
        st.metric(
            label="Weekly Jobless Claims",
            value=f"{latest_icsa:,.0f}",
            delta=f"{icsa_delta:,.0f} vs last wk",
            delta_color="inverse",
            help="WHAT TO LOOK FOR: If this number shoots ABOVE 250k, it means people are losing jobs. When people lose jobs, their automatic 401k stock buying stops."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_icsa)} | **Release:** {icsa_updated}")
        if latest_icsa > 250000:
            st.error("🚨 DANGER: Over 250k Threshold!")
        else:
            st.success("🟢 OK: Under 250k")
    else:
        st.error("❌ ICSA data unavailable")

# 2. CONTINUING CLAIMS CARD
with col2:
    st.subheader("Continuing Claims")
    if not df_ccsa.empty and len(df_ccsa) >= 2:
        latest_ccsa = df_ccsa["CCSA"].iloc[-1]
        prev_ccsa = df_ccsa["CCSA"].iloc[-2]
        ccsa_delta = latest_ccsa - prev_ccsa
        
        st.metric(
            label="Insured Unemployed",
            value=f"{latest_ccsa:,.0f}",
            delta=f"{ccsa_delta:,.0f} vs last wk",
            delta_color="inverse",
            help="WHAT TO LOOK FOR: Tracks people stuck out of work. If this crosses 1.9 Million, systemic 401(k) inflows fade away completely."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_ccsa)} | **Release:** {ccsa_updated}")
        if latest_ccsa > 1900000:
            st.error("🚨 DANGER: Over 1.9M Threshold!")
        else:
            st.success("🟢 OK: Under 1.9M")
    else:
        st.error("❌ CCSA data unavailable")

# 3. HIGH YIELD SPREAD CARD (Updated Formatting)
with col3:
    st.subheader("Credit Risk")
    if not df_spread.empty and len(df_spread) >= 2:
        latest_spread = df_spread["BAMLH0A0HYM2"].iloc[-1]
        prev_spread = df_spread["BAMLH0A0HYM2"].iloc[-2]
        spread_delta = latest_spread - prev_spread
        
        st.metric(
            label="HY Bond Spread",
            value=f"{latest_spread:.2f}%",
            delta=f"{spread_delta:.2f}% vs prev day",
            delta_color="inverse",
            help="WHAT TO LOOK FOR: This tracks smart bond investors. If this crosses 4.5%, it means real economic panic is happening under the surface."
        )
        st.caption(f"📅 **Obs:** {format_obs_date(df_spread)} | **Release:** {spread_updated}")
        if latest_spread > 4.5:
            st.error("🚨 STRESS ALERT: Over 4.5%!")
        else:
            st.success("🟢 OK: Normal Spreads")
    else:
        st.error("❌ Yield Spread data unavailable")

# 4. MARKET CONCENTRATION PROXY CARD (Renamed & Cleaned)
with col4:
    st.subheader("Market Concentration")
    if not df_mkt.empty and len(df_mkt) >= 5:
        latest_ratio = df_mkt["Ratio"].iloc[-1]
        prev_ratio = df_mkt["Ratio"].iloc[-5]
        ratio_delta = latest_ratio - prev_ratio
        
        if pd.isna(latest_ratio):
            st.error("❌ Market data calculation error")
        else:
            st.metric(
                label="SPY / RSP Ratio",
                value=f"{latest_ratio:.3f}",
                delta=f"{ratio_delta:.3f} (5d change)",
                help="WHAT TO LOOK FOR: Tracks how 'top-heavy' the stock market is. Above 3.00 means passive flows are blindly forcing all the market's money into just the top 10 mega-caps."
            )
            st.caption(f"📅 **Obs:** {format_obs_date(df_mkt)} (Real-time)")
            if latest_ratio > 3.0:
                st.warning("⚠️ TOP-HEAVY: Ratio over 3.0")
            else:
                st.success("🟢 BROAD MARKET: Ratio under 3.0")
    else:
        st.error("❌ Market data unavailable")

st.divider()

# -----------------------------------------------------------------------------
# PHASE 2: CHARTS WITH CROSSHAIRS
# -----------------------------------------------------------------------------
st.header("📈 Data Visualizations & Cheat Sheets")

tab1, tab2, tab3 = st.tabs(
    ["🔎 SPY/RSP Concentration Chart", "🧑‍🔧 Labor Inflow Chart", "📉 Credit Health Chart"]
)

with tab1:
    st.subheader("SPY (Market-Cap Weighted) vs RSP (Equal Weighted) Ratio")
    with st.expander("💡 Cheat Sheet: How do I read this chart?", expanded=True):
        st.markdown("""
        * **What is it?** It compares the largest stocks to the average stock.
        * **Going UP?** Passive indexing is winning. Money is flowing blindly into the top mega-caps.
        * **Going DOWN or Flat?** Healthy market environment. Capital is spreading naturally into a wide array of businesses.
        * **Levels to watch:** Below **2.50** is structurally safe. Over **3.00** means extreme fragility.
        """)
        
    if not df_mkt.empty:
        fig1 = go.Figure()
        fig1.add_hrect(y0=0, y1=2.5, line_width=0, fillcolor="rgba(0, 255, 0, 0.1)", annotation_text="Healthy Range", annotation_position="bottom left")
        fig1.add_hrect(y0=3.0, y1=4.5, line_width=0, fillcolor="rgba(255, 0, 0, 0.1)", annotation_text="Dangerous Structural Fragility Zone", annotation_position="top left")
        fig1.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Ratio"], mode="lines", name="Current Ratio", line=dict(color="#1f77b4", width=3)))
        fig1.update_layout(xaxis_title="Date", yaxis_title="Ratio Value", margin=dict(l=20, r=20, t=20, b=20))
        
        # Interactive Mouse Tracker Crosshairs
        fig1.update_xaxes(showspikes=True, spikecolor="gray", spikethickness=1, spikemode="across")
        fig1.update_yaxes(showspikes=True, spikecolor="gray", spikethickness=1, spikemode="across")
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.warning("Cannot display visualization: Market alignment dataset empty.")

with tab2:
    st.subheader("Weekly Initial Jobless Claims")
    with st.expander("💡 Cheat Sheet: How do I read this chart?", expanded=True):
        st.markdown("""
        * **What is it?** Shows how many new people lost their job this week.
        * **Why it matters:** No job = no 401(k) automated paycheck deduction.
        * **The Trigger Line:** The **red dashed line at 250,000** is the danger threshold.
        """)
        
    if not df_icsa.empty:
        plot_df = df_icsa.tail(104)
        fig2 = go.Figure()
        fig2.add_hline(y=250000, line_dash="dash", line_color="red", line_width=2)
        fig2.add_trace(go.Scatter(x=plot_df.index, y=plot_df["ICSA"], mode="lines", name="Initial Claims", line=dict(color="#FF4B4B", width=2.5)))
        fig2.update_layout(xaxis_title="Date", yaxis_title="Claims Volume", margin=dict(l=20, r=20, t=20, b=20))
        
        fig2.update_xaxes(showspikes=True, spikecolor="gray", spikethickness=1, spikemode="across")
        fig2.update_yaxes(showspikes=True, spikecolor="gray", spikethickness=1, spikemode="across")
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("ICE BofA High Yield Option-Adjusted Spread")
    with st.expander("💡 Cheat Sheet: How do I read this chart?", expanded=True):
        st.markdown("""
        * **What is it?** Tracks risk premiums in the corporate bond market.
        * **Why it matters:** Bond markets notice stress long before the stock market does.
        * **The Trigger Line:** The **red dashed line at 4.5%** represents structural credit stress.
        """)
        
    if not df_spread.empty:
        plot_df = df_spread.tail(260)
        fig3 = go.Figure()
        fig3.add_hline(y=4.5, line_dash="dash", line_color="red", line_width=2)
        fig3.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BAMLH0A0HYM2"], mode="lines", name="Credit Spread", line=dict(color="#00C0F2", width=2.5)))
        fig3.update_layout(xaxis_title="Date", yaxis_title="Spread Percentage (%)", margin=dict(l=20, r=20, t=20, b=20))
        
        fig3.update_xaxes(showspikes=True, spikecolor="gray", spikethickness=1, spikemode="across")
        fig3.update_yaxes(showspikes=True, spikecolor="gray", spikethickness=1, spikemode="across")
        st.plotly_chart(fig3, use_container_width=True)

# Sidebar App Controls & Reminders
with st.sidebar:
    st.title("⚙️ App Controls")
    if st.button("🔄 Clear Cache & Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    
    st.title("🧩 Passive Index Theory Reminders")
    st.info("""
    **Where is the 83% Breaking Point?**
    Mike Green proves that when the total passive index share hits **83%**, the market's basic pricing engine mechanically breaks down. 
    
    Because this total metric can't be fetched live via tickers daily, we use the **SPY/RSP Concentration Ratio** as our main proxy tool!
    """)
