import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import feedparser
import requests
import numpy as np  # เพิ่ม numpy สำหรับคำนวณเชิงสถิติ

# [UPDATE] ใช้ Ticker หลักเป็น USD เพื่อความแม่นยำของกราฟ
COIN_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "BNB": "BNB-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "PEPE": "PEPE-USD",
    "SHIB": "SHIB-USD"
}

@st.cache_data(ttl=60)
def get_crypto_data(symbol_key, period="2y", interval="1d"):
    # 1. ดึงข้อมูล Crypto เป็น USD
    symbol = COIN_MAP.get(symbol_key, "BTC-USD")
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    
    if df.empty:
        return None

    # [Fix MultiIndex] แก้ปัญหาหัวตารางซ้อนกัน
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except: 
        pass

    if 'Close' not in df.columns:
        return None

    # 2. ใช้ราคา USD โดยตรง (ไม่แปลงสกุลเงิน)

    # 3. คำนวณอินดิเคเตอร์ (คำนวณจากราคา USD)
    # RSI
    try:
        df['RSI'] = ta.rsi(df['Close'], length=14)
    except: 
        df['RSI'] = 50
    
    # MACD
    try:
        macd = ta.macd(df['Close'])
        if macd is not None and not macd.empty:
            df['MACD'] = macd.iloc[:, 0] 
            df['MACD_SIGNAL'] = macd.iloc[:, 2]
        else:
            df['MACD'] = 0
            df['MACD_SIGNAL'] = 0
    except:
        df['MACD'] = 0
        df['MACD_SIGNAL'] = 0
    
    # Bollinger Bands
    try:
        bb = ta.bbands(df['Close'], length=20)
        if bb is not None and not bb.empty:
            df['BB_UPPER'] = bb.iloc[:, 0]
            df['BB_LOWER'] = bb.iloc[:, 2]
    except: 
        pass

    # EMA
    try:
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)
    except: 
        pass

    # [NEW] ADX (Trend Strength) - บอกว่าเทรนด์แรงแค่ไหน
    try:
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx is not None and not adx.empty:
            df['ADX'] = adx.iloc[:, 0]  # ADX_14
    except: 
        df['ADX'] = 20

    # [NEW] ATR (Volatility) - บอกความผันผวน (ไว้คำนวณ Stop Loss)
    try:
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    except: 
        df['ATR'] = 0

    # [NEW] Support/Resistance (คำนวณแนวรับต้านย้อนหลัง 30 วัน)
    try:
        last_30 = df.tail(30)
        df['Support_Level'] = last_30['Low'].min()
        df['Resistance_Level'] = last_30['High'].max()
    except:
        df['Support_Level'] = df['Close'].min()
        df['Resistance_Level'] = df['Close'].max()

    # --- [NEW V2] StochRSI (ไวรับสัญญาณสั้น 72 ชม.) ---
    try:
        stoch = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
        df['Stoch_K'] = stoch.iloc[:, 0]
        df['Stoch_D'] = stoch.iloc[:, 1]
    except:
        df['Stoch_K'] = 50
        df['Stoch_D'] = 50

    # --- [NEW V2] OBV (On-Balance Volume) - ดูไส้ในว่าเงินเข้าหรือออกจริง ---
    if 'Volume' in df.columns:
        df['OBV'] = ta.obv(df['Close'], df['Volume'])
        # คำนวณ OBV Slope 5 วัน (เพื่อดูทิศทางเงิน)
        df['OBV_Slope'] = df['OBV'].diff(5)
    else:
        df['OBV'] = 0
        df['OBV_Slope'] = 0

    # --- [NEW V2] Pivot Points (แนวรับต้านคณิตศาสตร์) ---
    # ใช้ค่าของแท่งเมื่อวานมาคำนวณแนวรับวันนี้
    try:
        if len(df) > 0:
            last = df.iloc[-1]
            P = (last['High'] + last['Low'] + last['Close']) / 3
            df['Pivot_P'] = P
            df['Pivot_R1'] = (2 * P) - last['Low']
            df['Pivot_S1'] = (2 * P) - last['High']
        else:
            df['Pivot_P'] = df['Close'].iloc[-1]
            df['Pivot_R1'] = df['Close'].iloc[-1] * 1.05
            df['Pivot_S1'] = df['Close'].iloc[-1] * 0.95
    except:
        df['Pivot_P'] = df['Close'].iloc[-1]
        df['Pivot_R1'] = df['Close'].iloc[-1] * 1.05
        df['Pivot_S1'] = df['Close'].iloc[-1] * 0.95

    return df

@st.cache_data(ttl=600)
def get_crypto_news(symbol_key):
    try:
        rss_url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(rss_url)
        news_list = []
        keyword = symbol_key.lower()
        
        count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            summary = entry.summary.lower()
            if keyword in title or keyword in summary or "market" in title or "bitcoin" in title:
                news_list.append(f"- {entry.title} ({entry.published})")
                count += 1
                if count >= 5: 
                    break 
                
        if not news_list: 
            return "ไม่มีข่าวสำคัญในช่วง 24 ชม. ให้วิเคราะห์จากกราฟเป็นหลัก"
        return "\n".join(news_list)
    except:
        return "ไม่สามารถดึงข่าวได้ (RSS Error)"

def get_fear_and_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = r.json()
        return data['data'][0]
    except:
        return {"value_classification": "Unknown", "value": "50"}