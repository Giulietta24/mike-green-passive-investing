import datetime
import urllib.request
import pandas as pd
import plotly.graph_objects as go
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
st.divider()

# Timezone-naive date fix: Use UTC for server consistency
UTC_TODAY = datetime.datetime.now(datetime.timezone.utc).date()


# Helper function to grab FRED data safely bypassing bot blocks with explicit timeouts
@st.cache_data(ttl=3600)
def fetch_fred_csv(series_id):
    # Using the direct data download URL endpoint with an explicit timeout
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        # Added a strict 10-second timeout so the app never hangs indefinitely
        with urllib.request.urlopen(req, timeout=10) as response:
            df = pd.read_csv(response, parse_dates=["DATE"], index_col="DATE")

        df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
        df = df.dropna()
        return df
    except Exception as e:
        # Log error to Streamlit components so you can see if a specific download fails
        st.sidebar.error(f"FRED {series_id} load failed.")
        return pd.DataFrame()


# Helper function to grab Yahoo Finance data safely guarding against multi-index columns
@st.cache_data(ttl=3600)
def fetch_mkt_data():
    start_date = UTC_TODAY - datetime.timedelta(days=365)
    try:
        # Download tickers individually to bypass any multi-index pandas data structure variations
        spy = yf.Ticker("SPY").history(start=start_date, end=UTC_TODAY)
        rsp = yf.Ticker("RSP").history(start=start_date, end=UTC_TODAY)
        
        if spy.empty or rsp.empty:
            return pd.DataFrame()
            
        # Reconstruct a clean, flat dataframe manually
        df = pd.DataFrame(index=spy.index)
        df["SPY"] = spy["Close"]
        df["RSP"] = rsp["Close"]
        df["Ratio"] = df["SPY"] / df["RSP"]
        df = df.dropna()
        return df
    except Exception as e:
        st.sidebar.error(f"Market data load failed.")
        return pd.DataFrame()


# -----------------------------------------------------------------------------
# DATA RECOVERY PIPELINE (Granular failure handling)
# -----------------------------------------------------------------------------
with st.spinner("Fetching latest market and macro plumbing metrics..."):
    df_icsa = fetch_fred_csv("ICSA")
    df_ccsa = fetch_fred_csv("CCSA")
    df_spread = fetch_fred_csv("BAMLH0A0HYM2")
    df_mkt = fetch_mkt_data()

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
        as_of_date = df_icsa.index[-1].strftime("%b %d, %Y")

        st.metric(
            label="Weekly Jobless Claims",
            value=f"{latest_icsa:,.0f}",
            delta=f"{icsa_delta:,.0f} vs last wk",
            delta_color="inverse",
        )
        st.caption(f"As of {as_of_date}")
        if latest_icsa > 250000:
            st.error("⚠️ Over Trigger Threshold (> 250k)")
        else:
            st.success("🟢 Safe Range (< 250k)")
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
        )
        st.caption(f"As of {as_of_date}")
        if latest_ccsa > 1900000:
            st.error("⚠️ Over Trigger Threshold (> 1.9M)")
        else:
            st.success("🟢 Safe Range (< 1.9M)")
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
        )
        st.caption(f"As of {as_of_date}")
        if latest_spread > 4.5:
            st.error("⚠️ Credit Stress Alert (> 4.5%)")
        else:
            st.success("🟢 Normal Credit Spread")
    else:
        st.error("❌ Yield Spread data unavailable")

# 4. INELASTICITY CARD
with col4:
    st.subheader("Market Concentration")
    if not df_mkt.empty and len(df_mkt) >= 5:
        latest_ratio = df_mkt["Ratio"].iloc[-1]
        prev_ratio = df_mkt["Ratio"].iloc[-5]
        ratio_delta = round(latest_ratio - prev_ratio, 3)
        as_of_date = df_mkt.index[-1].strftime("%b %d, %Y")

        st.metric(
            label="SPY / RSP Ratio",
            value=f"{latest_ratio:.3f}",
            delta=f"{ratio_delta:.3f} (5d change)",
        )
        st.caption(f"As of {as_of_date}")
        st.info("Higher ratio = Higher Concentration")
    else:
        st.error("❌ Market data unavailable")

st.divider()

# -----------------------------------------------------------------------------
# PHASE 2: CHARTS
# -----------------------------------------------------------------------------
st.header("📈 Data Visualizations")

tab1, tab2, tab3 = st.tabs(
    ["SPY/RSP Concentration", "Labor Market Flows", "Credit Health"]
)

with tab1:
    st.subheader("SPY (Market-Cap Weighted) vs RSP (Equal Weighted) Ratio")
    if not df_mkt.empty:
        fig1 = go.Figure()
        fig1.add_trace(
            go.Scatter(
                x=df_mkt.index,
                y=df_mkt["Ratio"],
                mode="lines",
                name="SPY/RSP Ratio",
            )
        )
        fig1.update_layout(
            xaxis_title="Date", yaxis_title="Ratio Value", margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.warning("Cannot display visualization: Market dataset empty")

with tab2:
    st.subheader("Weekly Initial Jobless Claims")
    if not df_icsa.empty:
        plot_df = df_icsa.tail(104)
        fig2 = go.Figure()
        fig2.add_hline(
            y=250000,
            line_dash="dash",
            line_color="red",
            annotation_text="Danger Trigger (250k)",
            annotation_position="top left",
        )
        fig2.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df["ICSA"],
                mode="lines",
                name="Initial Claims",
                line=dict(color="#FF4B4B"),
            )
        )
        fig2.update_layout(
            xaxis_title="Date", yaxis_title="Claims Volume", margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Cannot display visualization: ICSA dataset empty")

with tab3:
    st.subheader("ICE BofA High Yield Option-Adjusted Spread")
    if not df_spread.empty:
        plot_df = df_spread.tail(260)
        fig3 = go.Figure()
        fig3.add_hline(
            y=4.5,
            line_dash="dash",
            line_color="red",
            annotation_text="Stress Alert (4.5%)",
            annotation_position="top left",
        )
        fig3.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df["BAMLH0A0HYM2"],
                mode="lines",
                name="Credit Spread",
                line=dict(color="#00C0F2"),
            )
        )
        fig3.update_layout(
            xaxis_title="Date", yaxis_title="Spread Percentage (%)", margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("Cannot display visualization: Spread dataset empty")

# Sidebar Theory Tooltips
with st.sidebar:
    st.title("Dashboard Parameters")
    with st.expander("ℹ️ About the Threshold Targets"):
        st.markdown(
            """
        These triggers are derived from **Mike Green's Passive Market Structure Research**:
        * **250k Initial Claims / 1.9M Continuing Claims:** Structural breakdown parameters for automated 401(k) inflows.
        * **4.5% High Yield Spread:** Real-time marker of pricing elasticity shifting in active markets.
        * **83% Passive Threshold:** Mathematical breaking point of the market index clearing engine.
        """
        )
