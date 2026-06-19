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
# API KEY RESOLUTION (Streamlit Secrets or Sidebar Input fallback)
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
    start_date = UTC_TODAY - datetime.timedelta(days=365)
    try:
        spy_ticker = yf.Ticker("SPY").history(start=start_date, end=UTC_TODAY)
        rsp_ticker = yf.Ticker("RSP").history(start=start_date, end=UTC_TODAY)
        
        if spy_ticker.empty or rsp_ticker.empty:
            return pd.DataFrame()
            
        # FIX: Strip out timezones completely so the dates join perfectly
        spy_ticker.index = spy_ticker.index.tz_localize(None)
        rsp_ticker.index = rsp_ticker.index.tz_localize(None)
        
        spy_close = spy_ticker["Close"].rename("SPY")
        rsp_close = rsp_ticker["Close"].rename("RSP")
        
        # Align SPY and RSP on matching trading dates using an inner join
        df = pd.concat([spy_close, rsp_close], axis=1, join="inner")
        
        # Calculate ratio and wipe out any rows with an empty value
        df["Ratio"] = df["SPY"] / df["RSP"]
        df = df.dropna()
        
        if df.empty or len(df) < 5:
            return pd.DataFrame()
            
        return df
    except Exception:
        return pd.DataFrame()


# Load Data
with st.spinner("Fetching latest market and macro plumbing metrics..."):
    df_icsa = fetch_fred_api("ICSA", fred_key) if fred_key else pd.DataFrame()
    df_ccsa = fetch_fred_api("CCSA", fred_key) if fred_key else pd.DataFrame()
    df_spread = fetch_fred_api("BAMLH0A0HYM2", fred_key) if fred_key else pd.DataFrame()
    df_mkt = fetch_mkt_data()

# -----------------------------------------------------------------------------
# PHASE 1: METRICS DISPLAY (With floating information icons + Freshness Dates)
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
        as_of_date = df_icsa.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="Weekly Jobless Claims",
            value=f"{latest_icsa:,.0f}",
            delta=f"{icsa_delta:,.0f} vs last wk",
            delta_color="inverse",
            help="WHAT TO LOOK FOR: If this number shoots ABOVE 250k, it means people are losing jobs. When people lose jobs, their automatic 401k stock buying stops, and the stock market loses its steady fuel."
        )
        st.caption(f"📅 Latest Obs: {as_of_date}")
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
        as_of_date = df_ccsa.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="Insured Unemployed",
            value=f"{latest_ccsa:,.0f}",
            delta=f"{ccsa_delta:,.0f} vs last wk",
            delta_color="inverse",
            help="WHAT TO LOOK FOR: Tracks people stuck out of work. If this crosses 1.9 Million, systemic 401(k) inflows fade away completely."
        )
        st.caption(f"📅 Latest Obs: {as_of_date}")
        if latest_ccsa > 1900000:
            st.error("🚨 DANGER: Over 1.9M Threshold!")
        else:
            st.success("🟢 OK: Under 1.9M")
    else:
        st.error("❌ CCSA data unavailable")

# 3. HIGH YIELD SPREAD CARD
with col3:
    st.subheader("Credit Risk")
    if not df_spread.empty and len(df_spread) >= 2:
        latest_spread = df_spread["BAMLH0A0HYM2"].iloc[-1]
        prev_spread = df_spread["BAMLH0A0HYM2"].iloc[-2]
        spread_delta = round(latest_spread - prev_spread, 2)
        as_of_date = df_spread.index[-1].strftime("%b %d, %Y")
        
        st.metric(
            label="HY Bond Spread",
            value=f"{latest_spread}%",
            delta=f"{spread_delta}% vs prev day",
            delta_color="inverse",
            help="WHAT TO LOOK FOR: This tracks smart bond investors. If this crosses 4.5%, it means real economic panic is happening under the surface, even if the passive stock market looks happy."
        )
        st.caption(f"📅 Latest Obs: {as_of_date}")
        if latest_spread > 4.5:
            st.error("🚨 STRESS ALERT: Over 4.5%!")
        else:
            st.success("🟢 OK: Normal Spreads")
    else:
        st.error("❌ Yield Spread data unavailable")

# 4. INELASTICITY CARD (With NaN Guards)
with col4:
    st.subheader("Market Distortion")
    if not df_mkt.empty and len(df_mkt) >= 5:
        latest_ratio = df_mkt["Ratio"].iloc[-1]
        prev_ratio = df_mkt["Ratio"].iloc[-5]
        ratio_delta = round(latest_ratio - prev_ratio, 3)
        as_of_date = df_mkt.index[-1].strftime("%b %d, %Y")
        
        if pd.isna(latest_ratio):
            st.error("❌ Market data calculation error")
        else:
            st.metric(
                label="SPY / RSP Ratio",
                value=f"{latest_ratio:.3f}",
                delta=f"{ratio_delta:.3f} (5d change)",
                help="WHAT TO LOOK FOR: Tracks how 'top-heavy' the stock market is. Above 3.00 means passive flows are blindly forcing all the market's money into just the top 10 mega-caps (like Nvidia and Apple), leaving the other 490 stocks starved."
            )
            st.caption(f"📅 Latest Obs: {as_of_date}")
            if latest_ratio > 3.0:
                st.warning("⚠️ TOP-HEAVY: Ratio over 3.0")
            else:
                st.success("🟢 BROAD MARKET: Ratio under 3.0")
    else:
        st.error("❌ Market data unavailable")

st.divider()

# -----------------------------------------------------------------------------
# PHASE 2: CHARTS WITH INTEGRATED "CHEAT SHEETS"
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
        * **Going UP?** Passive indexing is winning. Money is flowing blindly into the top mega-caps regardless of reality.
        * **Going DOWN or Flat?** Healthy market environment. Capital is spreading naturally into a wide array of businesses.
        * **Levels to watch:** Below **2.50** is structurally very safe. Over **3.00** means extreme fragility.
        """)
        
    if not df_mkt.empty:
        fig1 = go.Figure()
        fig1.add_hrect(y0=0, y1=2.5, line_width=0, fillcolor="rgba(0, 255, 0, 0.1)", annotation_text="Healthy Range", annotation_position="bottom left")
        fig1.add_hrect(y0=3.0, y1=4.5, line_width=0, fillcolor="rgba(255, 0, 0, 0.1)", annotation_text="Dangerous Structural Fragility Zone", annotation_position="top left")
        
        fig1.add_trace(go.Scatter(x=df_mkt.index, y=df_mkt["Ratio"], mode="lines", name="Current Ratio", line=dict(color="#1f77b4", width=3)))
        fig1.update_layout(xaxis_title="Date", yaxis_title="Ratio Value", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.warning("Cannot display visualization: Market alignment dataset empty.")

with tab2:
    st.subheader("Weekly Initial Jobless Claims")
    with st.expander("💡 Cheat Sheet: How do I read this chart?", expanded=True):
        st.markdown("""
        * **What is it?** Shows how many new people lost their job this week.
        * **Why it matters:** No job = no 401(k) automated paycheck deduction.
        * **The Trigger Line:** The **red dashed line at 250,000** is the danger threshold. If the line breaks above that, the automated buying engine starts to stutter.
        """)
        
    if not df_icsa.empty:
        plot_df = df_icsa.tail(104)
        fig2 = go.Figure()
        fig2.add_hline(y=250000, line_dash="dash", line_color="red", line_width=2)
        fig2.add_trace(go.Scatter(x=plot_df.index, y=plot_df["ICSA"], mode="lines", name="Initial Claims", line=dict(color="#FF4B4B", width=2.5)))
        fig2.update_layout(xaxis_title="Date", yaxis_title="Claims Volume", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("ICE BofA High Yield Option-Adjusted Spread")
    with st.expander("💡 Cheat Sheet: How do I read this chart?", expanded=True):
        st.markdown("""
        * **What is it?** Tracks risk premiums in the corporate bond market.
        * **Why it matters:** Bond markets are run by active, alert professionals. They notice stress long before the stock market does.
        * **The Trigger Line:** The **red dashed line at 4.5%** represents structural credit stress. If it points sharply up, an economic downturn is unfolding underneath the passive market structure.
        """)
        
    if not df_spread.empty:
        plot_df = df_spread.tail(260)
        fig3 = go.Figure()
        fig3.add_hline(y=4.5, line_dash="dash", line_color="red", line_width=2)
        fig3.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BAMLH0A0HYM2"], mode="lines", name="Credit Spread", line=dict(color="#00C0F2", width=2.5)))
        fig3.update_layout(xaxis_title="Date", yaxis_title="Spread Percentage (%)", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig3, use_container_width=True)


# Sidebar parameters and background context information
with st.sidebar:
    st.title("🧩 Passive Index Theory Reminders")
    
    st.info("""
    **Where is the 83% Breaking Point?**
    Mike Green proves that when the total passive index share hits **83%**, the market's basic pricing engine mechanically breaks down. 
    
    Because this total metric can't be fetched live via tickers daily, we use the **SPY/RSP Concentration Ratio** as our main proxy tool!
    """)
