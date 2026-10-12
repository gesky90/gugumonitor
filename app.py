import streamlit as st
import pandas as pd
import time
import threading
import os
import requests
from datetime import datetime

# ==========================================
# 游戏基础配置与 UI 映射 (从你的模板中提取)
# ==========================================
CONFIG = {
    1: {'id': 'A', 'name': '观光小火车', 'm': 4, 'color': '#3b82f6'}, # 蓝
    2: {'id': 'B', 'name': '旋转木马', 'm': 4, 'color': '#3b82f6'},
    3: {'id': 'C', 'name': '童话剧场', 'm': 4, 'color': '#3b82f6'},
    4: {'id': 'D', 'name': '彩虹滑道', 'm': 9, 'color': '#8b5cf6'}, # 紫
    5: {'id': 'E', 'name': '海盗船', 'm': 15, 'color': '#ec4899'}, # 粉
    6: {'id': 'F', 'name': '星空大摆锤', 'm': 20, 'color': '#ef4444'}, # 红
    7: {'id': 'G', 'name': '云霄飞车', 'm': 30, 'color': '#eab308'}, # 黄
}

# 页面基础配置 (宽屏模式)
st.set_page_config(page_title="愤怒的小咕 - 监控台", layout="wide")

# ==========================================
# 注入自定义 CSS (还原你的 UI 审美)
# ==========================================
st.markdown("""
<style>
    /* 全局背景和字体微调 */
    .stApp { background-color: #f8fafc; }
    
    /* AI 黑框终端样式 */
    .ai-console {
        background-color: #111827;
        border-radius: 8px;
        padding: 20px;
        color: #4ade80;
        font-family: monospace;
        font-size: 14px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
        line-height: 1.6;
    }
    
    /* 遗漏警报红框样式 */
    .omit-box {
        background-color: white;
        border-top: 4px solid #ef4444;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* 星级徽章样式 */
    .badge {
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 后台数据抓取逻辑 (保持之前的纯净简单)
# ==========================================
DATA_FILE = "game_history.csv"
SESSION_ID = "52ce2bd8196b4428bf9e7fe94c406c1c" # 你的真实会话ID

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=["timestamp", "time_str", "result"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def get_latest_result():
    today_str = datetime.now().strftime("%Y-%m-%d")
    api_url = f"https://lending-mon-manual-charge.trycloudflare.com/api/data?date={today_str}&session={SESSION_ID}"
    try:
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=5)
        data = response.json()
        def extract_latest(obj):
            if isinstance(obj, list) and len(obj) > 0: return extract_latest(obj[-1])
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (int, float)) and 1 <= v <= 7: return int(v)
                    elif isinstance(v, (dict, list)):
                        res = extract_latest(v)
                        if res: return res
            return None
        return extract_latest(data)
    except:
        return None

def background_scraper():
    while True:
        res = get_latest_result()
        if res is not None and 1 <= res <= 7:
            df = load_data()
            now = datetime.now()
            current_minute_str = now.strftime("%Y-%m-%d %H:%M")
            if len(df) == 0 or df.iloc[-1]['time_str'] != current_minute_str:
                new_row = {"timestamp": now.timestamp(), "time_str": current_minute_str, "result": res}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
        time.sleep(10)

if 'scraper_started' not in st.session_state:
    threading.Thread(target=background_scraper, daemon=True).start()
    st.session_state.scraper_started = True

# ==========================================
# 前端网页排版 (左侧控制 + 右侧大屏)
# ==========================================
st.markdown("### 📊 愤怒的小咕 - 模拟游戏监控台 (解锁尊享版 无限制)")
df = load_data()

# 左右分栏布局 (比例 1 : 3)
left_col, right_col = st.columns([1, 3])

with left_col:
    # 按钮控制区
    if st.button("🔄 刷新最新数据", use_container_width=True):
        st.rerun()
    if st.button("🗑️ 清空所有记录", use_container_width=True):
        if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
        st.rerun()
        
    st.markdown(f"**总期数:** {len(df)} 局")
    
    # 遗漏统计区 (红框 UI)
    st.markdown("<div class='omit-box'>", unsafe_allow_html=True)
    st.markdown("#### ⏳ 间隔统计 (遗漏值)")
    
    if len(df) > 0:
        for i in range(1, 8):
            conf = CONFIG[i]
            count_total = len(df[df["result"] == i])
            if count_total > 0:
                miss_count = len(df) - 1 - df[df["result"] == i].index[-1]
            else:
                miss_count = len(df)
            
            color = "red" if miss_count >= 10 else "black"
            weight = "bold" if miss_count >= 10 else "normal"
            
            st.markdown(
                f"<div style='display: flex; justify-content: space-between; border-bottom: 1px dashed #eee; padding: 5px 0;'>"
                f"<span style='color: #4b5563; font-size: 14px;'>{conf['id']}. {conf['name']}</span>"
                f"<span style='color: {color}; font-weight: {weight};'>{miss_count} 把</span>"
                f"</div>", 
                unsafe_allow_html=True
            )
    else:
        st.caption("等待数据中...")
    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    # AI 动态运算引擎黑框 (还原你的黑色代码框 UI)
    last_record = "监听中..." if len(df) == 0 else f"开出 【 {CONFIG[df.iloc[-1]['result']]['id']} - {CONFIG[df.iloc[-1]['result']]['name']} 】"
    ai_text = f"""
    🤖 AI 动态运算引擎 (纯净版)
    --------------------------------------------------
    [*] 系统状态: 数据抓取引擎运行正常
    [*] 历史记录: 已累计抓取 {len(df)} 局数据
    [>] 最新一期: {last_record}
    [!] 策略提示: 当前为纯净挂机模式，无限累加记录中。
    """
    st.markdown(f"<div class='ai-console'>{ai_text.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

    # 优化的数据报表表头
    st.markdown("#### 📈 当日数据报表 (结合项目名称)")
    if len(df) > 0:
        table_data = []
        for i in range(1, 8):
            conf = CONFIG[i]
            count_total = len(df[df["result"] == i])
            rate = f"{(count_total / len(df) * 100):.1f}%" if len(df) > 0 else "0%"
            
            table_data.append({
                "塔名 (游乐项目)": f"{conf['id']}. {conf['name']}",
                "星级/倍率": f"{conf['m']} 星",
                "总出现次数": count_total,
                "当前命中频率": rate
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    
    # 历史走势图 (自动折行)
    st.markdown("#### 📌 历史走势图")
    if len(df) > 0:
        results_all = df["result"].tolist()
        trend_data = []
        for i in range(0, len(results_all), 30):
            chunk_results = results_all[i:i+30]
            row_dict = {"起始局": f"第 {i+1} 局"}
            for j in range(30):
                if j < len(chunk_results):
                    num = chunk_results[j]
                    # 将数字转换为带名字的简称，例如：A(4星)
                    row_dict[f"走势 {j+1}"] = f"{CONFIG[num]['id']}塔" 
                else:
                    row_dict[f"走势 {j+1}"] = ""
            trend_data.append(row_dict)
            
        st.dataframe(pd.DataFrame(trend_data), use_container_width=True, hide_index=True)
    else:
        st.info("数据积累中，1分钟后展示走势...")

# 页面自动刷新
time.sleep(10)
st.rerun()
