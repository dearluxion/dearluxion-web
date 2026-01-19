import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import feedparser
import requests

COIN_MAP = {
    "BTC": "BTC-USD",
    "SHIB": "SHIB-USD"
}

@st.cache_data(ttl=300)
def get_crypto_data(symbol_key, period="6mo", interval="1d"):
    symbol = COIN_MAP.get(symbol_key, "BTC-USD")
    df = yf.download(symbol, period=period, interval=interval)
    
    if df.empty:
        return None

    # --- [จุดแก้ปัญหาโลกแตก] ---
    # yfinance ชอบส่งหัวตารางซ้อนกันมา (MultiIndex) เราต้องตบให้เรียบก่อน
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # -------------------------

    # คำนวณ RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # คำนวณ MACD
    macd = ta.macd(df['Close'])
    # กันเหนียว: ถ้าคำนวณไม่ได้ ให้ใส่ 0 ไปก่อน
    if macd is not None:
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
    else:
        df['MACD'] = 0
        df['MACD_SIGNAL'] = 0
    
    # Bollinger Bands
    bb = ta.bbands(df['Close'], length=20)
    if bb is not None:
        df['BB_UPPER'] = bb['BBU_20_2.0']
        df['BB_LOWER'] = bb['BBL_20_2.0']

    # EMA
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

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
                if count >= 5: break 
                
        if not news_list: return "ไม่มีข่าวสำคัญในช่วง 24 ชม. ให้วิเคราะห์จากกราฟเป็นหลัก"
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