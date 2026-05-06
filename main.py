import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
from datetime import datetime
import pytz
import time

# --- 1. SETUP UI & STYLE ---
st.set_page_config(page_title="JABAT CUAN PRO", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .welcome-container {
        text-align: center; padding: 80px 20px;
        background: radial-gradient(circle, #1e293b 0%, #0f172a 100%);
        border-radius: 30px; border: 1px solid #334155; margin: 40px 0;
    }
    .dashboard-header {
        background: linear-gradient(90deg, #1e293b 0%, #334155 100%);
        padding: 25px; border-radius: 15px; border-left: 10px solid #10b981; margin-bottom: 25px;
    }
    .main-card {
        background: #1e293b; border-radius: 15px; padding: 20px;
        border: 1px solid #334155; margin-bottom: 15px;
    }
    .metric-pill {
        background: #0f172a; padding: 12px; border-radius: 10px;
        border: 1px solid #334155; text-align: center; margin-bottom:10px;
    }
    .alert-box {
        padding: 20px; background-color: #fef2f2; border: 2px solid #ef4444;
        border-radius: 15px; color: #b91c1c; margin-bottom: 20px; text-align: center;
        animation: blinker 1.5s linear infinite; font-weight: bold;
    }
    @keyframes blinker { 50% { opacity: 0.5; } }
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: #020617; color: #ffffff;
        text-align: center; padding: 12px; font-size: 13px;
        border-top: 2px solid #10b981; z-index: 100;
        font-weight: 500;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- 2. CORE FUNCTIONS ---
def play_alert_sound():
    audio_html = """<audio autoplay><source src="https://www.soundjay.com/buttons/beep-01a.mp3" type="audio/mpeg"></audio>"""
    st.components.v1.html(audio_html, height=0)


def get_advanced_analysis(df, ihsg_df):
    try:
        if len(df) < 40 or ihsg_df.empty:
            return None
        tr = pd.concat(
            [
                df["High"] - df["Low"],
                abs(df["High"] - df["Close"].shift()),
                abs(df["Low"] - df["Close"].shift()),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        ma20 = df["Close"].rolling(20).mean().iloc[-1]
        curr_p = df["Close"].iloc[-1]
        # Proteksi pembagian nol pada Volume
        avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
        rvol = df["Volume"].iloc[-1] / avg_vol if avg_vol > 0 else 1.0

        # RS Calculation
        rs = (df["Close"].iloc[-1] / df["Close"].iloc[-20]) / (
            ihsg_df["Close"].iloc[-1] / ihsg_df["Close"].iloc[-20]
        )
        return {
            "atr": atr,
            "rvol": rvol,
            "rs": rs,
            "ma20": ma20,
            "above_ma20": curr_p > ma20,
            "weekly_up": curr_p > df["Close"].iloc[-20],
        }
    except:
        return None


# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def fetch_market_data():
    return yf.Ticker("^JKSE").history(period="6mo")


ihsg_data = fetch_market_data()
csv_path = "saham.csv"
if os.path.exists(csv_path):
    df_csv = pd.read_csv(csv_path, header=None)
    tickers = [
        (
            f"{s.strip().upper()}.JK"
            if not s.strip().endswith(".JK")
            else s.strip().upper()
        )
        for s in df_csv[0].dropna()
    ]
else:
    tickers = ["BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK", "BBNI.JK", "BRMS.JK"]

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🔱 JABAT CUAN PRO")
    search_ticker = st.text_input("🔍 Cari Kode Saham", "").upper()
    modal = st.number_input("💰 Modal Trading (Rp)", value=10000000, step=1000000)
    risk_per_trade = st.slider("🛡️ Risiko (Loss) per Trade (%)", 0.1, 5.0, 1.0)
    st.divider()
    min_p = st.number_input("📉 Min Price", value=50)
    max_p = st.number_input("📈 Max Price", value=80)
    st.divider()
    enable_auto = st.toggle("🛰️ Auto-Pilot Mode")
    refresh_int = st.select_slider("Refresh (Menit)", options=[1, 5, 10, 30], value=5)
    run = st.button("🚀 MULAI SCAN", use_container_width=True)

# --- 5. MAIN LOGIC ---
if run or search_ticker or enable_auto:
    target_tickers = [f"{search_ticker}.JK"] if search_ticker else tickers
    results, summary_list, potential_alerts = [], [], []
    count_above_ma = 0

    pbar = st.progress(0)
    for i, t in enumerate(target_tickers):
        pbar.progress((i + 1) / len(target_tickers))
        try:
            df = yf.Ticker(t).history(period="6mo")
            if df.empty or len(df) < 2:
                continue
            curr_p = df["Close"].iloc[-1]
            if not (min_p <= curr_p <= max_p):
                continue

            an = get_advanced_analysis(df, ihsg_data)
            if not an:
                continue
            if an["above_ma20"]:
                count_above_ma += 1

            score = 0
            if an["above_ma20"]:
                score += 40
            if an["rvol"] > 1.5:
                score += 30
            if an["rs"] > 1.05:
                score += 20
            if an["weekly_up"]:
                score += 10

            stock_data = {
                "sym": t.replace(".JK", ""),
                "p": curr_p,
                "sc": score,
                "an": an,
                "df": df,
            }
            results.append(stock_data)
            if score >= 80:
                potential_alerts.append(stock_data["sym"])
        except:
            continue
    pbar.empty()

    if potential_alerts:
        play_alert_sound()
        st.markdown(
            f'<div class="alert-box">🚨 SIGNAL BELI: {", ".join(potential_alerts)}</div>',
            unsafe_allow_html=True,
        )

    if results:
        breadth = (count_above_ma / len(results)) * 100
        sentiment = (
            "🚀 BULLISH"
            if breadth > 60
            else ("⚠️ CAUTION" if breadth > 40 else "💀 BEARISH")
        )
        s_color = (
            "#10b981" if breadth > 60 else ("#f59e0b" if breadth > 40 else "#ef4444")
        )

        st.markdown(
            f"""
            <div class="dashboard-header">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <small style="color:#94a3b8;">SENTIMEN PASAR</small>
                        <div style="font-size:32px; font-weight:900; color:{s_color};">{sentiment} ({breadth:.1f}%)</div>
                    </div>
                    <div style="text-align:right;">
                        <small style="color:#94a3b8;">ALOKASI RISIKO</small><br>
                        <b style="font-size:20px;">Rp {(modal * risk_per_trade/100):,.0f} / trade</b>
                    </div>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # --- REVISI RADAR MAP (CEGAH ERROR SIZE NAN) ---
        st.subheader("🎯 The Beast Radar (Selection Matrix)")
        radar_df = pd.DataFrame(
            [
                {
                    "Ticker": i["sym"],
                    "Score": i["sc"],
                    "RS": i["an"]["rs"],
                    "Volume": (
                        i["an"]["rvol"]
                        if (i["an"]["rvol"] > 0 and not pd.isna(i["an"]["rvol"]))
                        else 0.1
                    ),
                }
                for i in results
            ]
        )

        # Validasi tambahan untuk data radar
        if not radar_df.empty:
            radar_df["Score"] = radar_df["Score"].fillna(0)
            radar_df["RS"] = radar_df["RS"].fillna(1.0)

            fig_radar = px.scatter(
                radar_df,
                x="RS",
                y="Score",
                size="Volume",
                text="Ticker",
                color="Score",
                color_continuous_scale="Viridis",
                height=400,
                size_max=40,
            )
            fig_radar.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_radar, use_container_width=True)
        st.divider()

        for item in sorted(results, key=lambda x: x["sc"], reverse=True):
            status_color = (
                "#10b981"
                if item["sc"] >= 80
                else ("#3b82f6" if item["sc"] >= 60 else "#64748b")
            )

            st.markdown(
                f"""
                <div class="main-card" style="border-left: 5px solid {status_color}">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size:24px; font-weight:bold;">{item['sym']} <small style="font-size:14px; color:#94a3b8;">| Rp {item['p']:,}</small></span>
                        <span style="color:{status_color}; font-weight:900; font-size:24px;">{item['sc']}%</span>
                    </div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns([2, 1, 1.2])
            with c1:
                fig = go.Figure(
                    data=[
                        go.Candlestick(
                            x=item["df"].index[-60:],
                            open=item["df"]["Open"][-60:],
                            high=item["df"]["High"][-60:],
                            low=item["df"]["Low"][-60:],
                            close=item["df"]["Close"][-60:],
                        )
                    ]
                )
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=250,
                    margin=dict(l=0, r=0, t=0, b=0),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True, key=f"ch_{item['sym']}")
            with c2:
                st.markdown(
                    f"""
                    <div class="metric-pill"><small>Rel. Strength</small><br><b>{item['an']['rs']:.2f}</b></div>
                    <div class="metric-pill"><small>Whale Vol</small><br><b>{item['an']['rvol']:.2f}x</b></div>
                    <div class="metric-pill"><small>Trend</small><br><b style="color:{status_color}">{"UPTREND" if item['an']['above_ma20'] else "SIDEWAYS"}</b></div>
                """,
                    unsafe_allow_html=True,
                )
            with c3:
                entry_p = item["p"]
                sl_p = entry_p - (1.5 * item["an"]["atr"])
                tp_p = entry_p + (3 * item["an"]["atr"])
                risk_money = modal * (risk_per_trade / 100)
                lot_size = (
                    int(risk_money / (entry_p - sl_p) / 100)
                    if (entry_p - sl_p) > 0
                    else 0
                )

                st.markdown(
                    f"""
                    <div style="background:#0f172a; padding:15px; border-radius:10px; border:1px solid #334155;">
                        <div style="color:#ffffff; font-size:16px; border-bottom:1px solid #334155; padding-bottom:5px; margin-bottom:10px;">
                            <b>🎯 ENTRY: Rp {int(entry_p):,}</b>
                        </div>
                        <div style="color:#10b981; margin-bottom:5px;"><small>TARGET PROFIT (TP):</small><br><b>Rp {int(tp_p):,}</b></div>
                        <div style="color:#ef4444; margin-bottom:10px;"><small>STOP LOSS (SL):</small><br><b>Rp {int(sl_p):,}</b></div>
                        <div style="color:#f59e0b; border-top:1px solid #334155; pt-5;"><small>REKOMENDASI UKURAN:</small><br><b>{lot_size:,} LOT</b></div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
                if item["sc"] >= 60:
                    summary_list.append(
                        [item["sym"], int(entry_p), int(tp_p), int(sl_p), lot_size]
                    )
            st.divider()

        if summary_list:
            st.subheader("📋 Rekapitulasi Rencana Trading")
            st.table(
                pd.DataFrame(
                    summary_list,
                    columns=[
                        "Ticker",
                        "Harga Entry",
                        "Target (TP)",
                        "Proteksi (SL)",
                        "Jumlah Lot",
                    ],
                )
            )

    if enable_auto:
        time.sleep(refresh_int * 60)
        st.rerun()
else:
    st.markdown(
        """
        <div class="welcome-container">
            <h1 style="font-size: 80px; margin-bottom:0;">🔱</h1>
            <h1 style="font-size: 50px; font-weight: 900; color: #10b981; margin-top:0;">JABAT CUAN PRO</h1>
            <p style="font-size: 20px; color: #94a3b8;">The Professional Grade Intelligence Scanner</p>
            <div style="max-width: 600px; margin: 0 auto; text-align: left; background: #1e293b; padding: 25px; border-radius: 15px;">
                <p>✅ <b>Real-time Entry:</b> Harga beli sesuai data market terakhir.</p>
                <p>✅ <b>Smart Protection:</b> Stop Loss dinamis berbasis volatilitas (ATR).</p>
                <p>✅ <b>Money Management:</b> Menghitung Lot agar risiko modal tetap terjaga.</p>
            </div>
            <p style="margin-top: 30px; color: #475569;">Created by Sondang Gloria Sijabat</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

# --- 6. FOOTER ---
tz = pytz.timezone("Asia/Jakarta")
now = datetime.now(tz)
hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
st.markdown(
    f"""
    <div style="height: 100px;"></div>
    <div class="footer">
        {hari_list[now.weekday()]}, {now.strftime("%d-%m-%Y | %H:%M:%S")} WIB | 
        Sistem: {"AUTOPILOT" if enable_auto else "MANUAL"} | 
        Author: <b>Sondang Gloria Sijabat</b>
    </div>
""",
    unsafe_allow_html=True,
)
