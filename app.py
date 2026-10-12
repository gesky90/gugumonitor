import streamlit as st
import pandas as pd
import time
import threading
import os
import requests
import json
from datetime import datetime

# 配置页面
st.set_page_config(page_title="游戏数据监控台", layout="wide")

DATA_FILE = "history_data.csv"

# 【配置区】如果后续 session 过期，只需在这里更换新的 session 字符串即可
SESSION_ID = "52ce2bd8196b4428bf9e7fe94c406c1c"

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["timestamp", "time_str", "result"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def get_latest_result():
    # 自动获取当前日期，保证跨天不中断
    today_str = datetime.now().strftime("%Y-%m-%d")
    api_url = f"https://lending-mon-manual-charge.trycloudflare.com/api/data?date={today_str}&session={SESSION_ID}"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        response = requests.get(api_url, headers=headers, timeout=5)
        data = response.json()
        
        # 自动遍历解析 JSON，寻找最新的一局结果（1-7的数字）
        def extract_latest(obj):
            if isinstance(obj, list) and len(obj) > 0:
                return extract_latest(obj[-1])  # 假设最新的一局在列表最后
            elif isinstance(obj, dict):
                # 优先寻找可能的键名
                for key in ['result', 'tower', 'win', 'number', 'val']:
                    for k in obj.keys():
                        if key in k.lower() and isinstance(obj[k], (int, float)) and 1 <= obj[k] <= 7:
                            return int(obj[k])
                # 如果没有常见键名，暴力寻找 1-7 的值
                for k, v in obj.items():
                    if isinstance(v, (int, float)) and 1 <= v <= 7:
                        return int(v)
                    elif isinstance(v, (dict, list)):
                        res = extract_latest(v)
                        if res: return res
            return None

        # 尝试通过字典值中的列表来提取（例如 data['list']）
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0:
                    result = extract_latest(v[-1])
                    if result: return result
        
        return extract_latest(data)

    except Exception as e:
        return None

def background_scraper():
    """后台线程：每10秒抓取一次，自动比对去重"""
    while True:
        result = get_latest_result()
        if result is not None and 1 <= result <= 7:
            df = load_data()
            now = datetime.now()
            current_minute_str = now.strftime("%Y-%m-%d %H:%M")
            
            # 因为每分钟出一局，这里做去重：同一分钟内只记录一次
            if len(df) == 0 or df.iloc[-1]['time_str'] != current_minute_str:
                new_row = {
                    "timestamp": now.timestamp(),
                    "time_str": current_minute_str,
                    "result": result
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
        
        time.sleep(10)  # 严格执行每10秒请求一次接口

# 启动单例后台线程
if 'scraper_started' not in st.session_state:
    threading.Thread(target=background_scraper, daemon=True).start()
    st.session_state.scraper_started = True

# ================== 页面前端排版 ==================
st.title("📊 7塔自动监控台 (云端24小时持续挂机)")

col1, col2 = st.columns([1, 10])
with col1:
    if st.button("🔄 手动刷新"):
        st.rerun()
with col2:
    if st.button("🗑️ 清空记录"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.rerun()

df = load_data()

if len(df) == 0:
    st.warning("⏳ 已连接接口，正在监听。由于游戏每分钟一局，请等待倒计时结束后刷新查看...")
else:
    st.success(f"✅ 数据抓取正常，累计已获取 {len(df)} 局记录。最新记录时间：{df.iloc[-1]['time_str']}")
    
    one_hour_ago = datetime.now().timestamp() - 3600
    df_1h = df[df["timestamp"] >= one_hour_ago]

    st.subheader("1. 近1小时各项核心指标")
    stats = []
    for i in range(1, 8):
        count_1h = len(df_1h[df_1h["result"] == i])
        
        # 遗漏次数计算
        if count_1h > 0:
            last_idx = df[df["result"] == i].index[-1]
            miss_count = len(df) - 1 - last_idx
        else:
            miss_count = len(df)
            
        # 连出次数与概率计算
        results_list = df_1h["result"].tolist()
        consecutive_count = 0
        for j in range(1, len(results_list)):
            if results_list[j] == i and results_list[j-1] == i:
                consecutive_count += 1
                
        prob = f"{(consecutive_count / len(results_list) * 100):.1f}%" if len(results_list) > 0 else "0%"

        stats.append({
            "塔号": f"{i}塔",
            "1小时出现次数": count_1h,
            "当前遗漏次数": miss_count,
            "1小时内连出次数": consecutive_count,
            "1小时内连出概率": prob
        })
    st.table(pd.DataFrame(stats))

    st.subheader("2. 无限累加走势图 (横向1分钟，纵向30分钟)")
    st.caption("走势满30局自动换行往下累计，不设上限")
    
    results_all = df["result"].tolist()
    time_all = df["time_str"].tolist()
    
    trend_data = []
    for i in range(0, len(results_all), 30):
        chunk_results = results_all[i:i+30]
        chunk_times = time_all[i:i+30]
        
        row_dict = {"起始时间": chunk_times[0].split(" ")[-1]}
        for j in range(30):
            col_name = f"{j+1}分"
            if j < len(chunk_results):
                row_dict[col_name] = chunk_results[j]
            else:
                row_dict[col_name] = ""
        trend_data.append(row_dict)
        
    st.dataframe(pd.DataFrame(trend_data), use_container_width=True)

# 设置网页每10秒自动刷新一次界面 (展示最新数据)
time.sleep(10)
st.rerun()
