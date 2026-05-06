import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- 1. SETUP KONFIGURASI HALAMAN ---
st.set_page_config(page_title="JABAT CUAN - SCREENER", layout="wide")

# --- 2. SETUP SESSION ANTI-BLOKIR & CACHE ---
@st.cache_resource
def get_safe_session():
    # Cache data selama 1 jam untuk mengurangi request ke Yahoo
    session = requests_cache.CachedSession('yfinance_cache', expire_after=3600)
    
    # Strategi Retry jika terkena limit: Coba lagi 5 kali dengan jeda meningkat
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    # Identitas Browser agar tidak terbaca sebagai bot mentah
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

session = get_safe_session()

# --- 3. FUNGSI ANALISIS TEKNIS ---
def get_advanced_analysis(df, ihsg_df):
    try:
        # Kalkulasi MA20 & MA50
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        
        curr_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        
        # Relative Strength (RS) terhadap IHSG
        ihsg_return = (ihsg_df['Close'].iloc[-1] / ihsg_df['Close'].iloc[-60])
        stock_return = (df['Close'].iloc[-1] / df['Close'].iloc[-60])
        rs_score = stock_return / ihsg_return
        
        # Relative Volume (RVOL)
        avg_vol = df['Volume'].rolling(window=20).mean().iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        rvol = curr_vol / avg_vol if avg_vol > 0 else 0
        
        return {
            'above_ma20': curr_price > df['MA20'].iloc[-1],
            'above_ma50': curr_price > df['MA50'].iloc[-1],
            'rs': rs_score,
            'rvol': rvol,
            'weekly_up': curr_price > df['Close'].iloc[-5],
            'change_pct': ((curr_price - prev_price) / prev_price) * 100
        }
    except:
        return None

# --- 4. SIDEBAR & INPUT ---
st.sidebar.header("🔱 JABAT CUAN CONTROL")
modal = st.sidebar.number_input("Modal Trading (Rp)", min_value=1000000, value=10000000, step=1000000)
risk_pct = st.sidebar.slider("Resiko per Trade (%)", 1, 5, 2)
min_p = st.sidebar.number_input("Harga Min", value=100)
max_p = st.sidebar.number_input("Harga Max", value=10000)

# Load daftar saham
try:
    ticker_df = pd.read_csv("saham.csv")
    list_saham = ticker_df['Ticker'].tolist()
except:
    list_saham = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "ASII.JK", "TLKM.JK", "GOTO.JK", "AMRT.JK"]
    st.sidebar.warning("File saham.csv tidak ditemukan, menggunakan Bluechip default.")

# --- 5. MAIN LOGIC ---
st.title("🚀 IDX BEAST v17.5 - ROBUST CLOUD")
st.write(f"Update: {datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')} WIB")

if st.button("🔥 MULAI PEMINDAIAN PERANG"):
    results = []
    
    with st.status("Menarik Data IHSG...", expanded=True) as status:
        try:
            ihsg_data = yf.Ticker("^JKSE", session=session).history(period="6mo")
            st.write("IHSG Berhasil ditarik.")
            
            pbar = st.progress(0)
            for i, t in enumerate(list_saham):
                pbar.progress((i + 1) / len(list_saham))
                # Jeda tipis untuk stabilitas cloud
                time.sleep(0.3)
                
                try:
                    # Ambil data saham
                    s_obj = yf.Ticker(t, session=session)
                    df = s_obj.history(period="6mo")
                    
                    if df.empty or len(df) < 20: continue
                    
                    curr_p = df["Close"].iloc[-1]
                    if not (min_p <= curr_p <= max_p): continue
                    
                    an = get_advanced_analysis(df, ihsg_data)
                    if not an: continue
                    
                    # Logika Skor (Skala 100)
                    score = 0
                    if an['above_ma20']: score += 40
                    if an['rvol'] > 1.2: score += 30
                    if an['rs'] > 1.0: score += 20
                    if an['change_pct'] > 0: score += 10
                    
                    results.append({
                        "Ticker": t.replace(".JK", ""),
                        "Harga": curr_p,
                        "Change (%)": round(an['change_pct'], 2),
                        "RVOL": round(an['rvol'], 2),
                        "RS": round(an['rs'], 2),
                        "Skor": score
                    })
                except:
                    continue
            
            status.update(label="Pemindaian Selesai!", state="complete")
        except Exception as e:
            st.error(f"Gagal koneksi ke Yahoo: {e}")

    # --- 6. DISPLAY HASIL ---
    if results:
        final_df = pd.DataFrame(results).sort_values(by="Skor", ascending=False)
        
        # Filter skor tinggi
        top_picks = final_df[final_df['Skor'] >= 70]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🎯 Top Analysis (Skor > 70)")
            st.dataframe(top_picks, use_container_width=True)
            
        with col2:
            st.subheader("💰 Money Management")
            if not top_picks.empty:
                pick = top_picks.iloc[0]
                risk_amt = modal * (risk_pct / 100)
                # Contoh SL di 5%
                sl_price = pick['Harga'] * 0.95
                qty = int(risk_amt / (pick['Harga'] - sl_price)) if pick['Harga'] > sl_price else 0
                
                st.info(f"**Saham Terbaik: {pick['Ticker']}**")
                st.write(f"Rekomendasi Beli: {pick['Harga']}")
                st.write(f"Stop Loss (5%): {int(sl_price)}")
                st.success(f"**Beli: {qty // 100} Lot**")
                st.write(f"Total Modal Terpakai: Rp {int(qty * pick['Harga']):,}")
    else:
        st.warning("Tidak ada saham yang memenuhi kriteria saat ini.")
