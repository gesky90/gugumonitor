# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
import threading
import time
from datetime import datetime, date
import pandas as pd
import requests

# ==========================================
# 页面基础配置与高颜值 UI 样式注入
# ==========================================
st.set_page_config(page_title="愤怒的小咕 - 纯净监控台", layout="wide")
st.markdown("""
<style>
    /* 遗漏统计框 */
    .omit-box {
        background-color: white;
        border-top: 4px solid #ef4444;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    /* 走势图容器 */
    .trend-container {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-top: 10px;
    }
    .trend-row {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px dashed #f3f4f6;
    }
    .trend-label {
        width: 85px;
        font-size: 13px;
        color: #6b7280;
        font-weight: bold;
    }
    .trend-grid {
        display: flex;
        gap: 6px;
    }
    
    /* 走势图方块基础样式 */
    .trend-box {
        width: 32px;
        height: 32px;
        border-radius: 6px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-weight: bold;
        font-size: 15px;
    }
    
    /* === 颜色分级与发光特效 === */
    /* 小奖 1-3：低调灰色 */
    .bg-gray { background-color: #e5e7eb; color: #6b7280; } 
    
    /* 大奖 4-7：高亮渐变 + 发光特效 */
    .bg-D { background-color: #a855f7; color: white; box-shadow: 0 0 8px rgba(168, 85, 247, 0.6); } /* 彩虹-紫 */
    .bg-E { background-color: #ec4899; color: white; box-shadow: 0 0 8px rgba(236, 72, 153, 0.6); } /* 海盗-粉 */
    .bg-F { background-color: #ef4444; color: white; box-shadow: 0 0 8px rgba(239, 68, 68, 0.6); } /* 摆锤-红 */
    .bg-G { background-color: #eab308; color: white; box-shadow: 0 0 8px rgba(234, 179, 8, 0.6); }  /* 云霄-金 */
    
    .empty-box {
        width: 32px; height: 32px; border-radius: 6px;
        background-color: #f9fafb; border: 1px solid #f3f4f6;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 基础配置与视觉映射
# ==========================================
BASE_DIR = os.getcwd()
DATA_FILE = os.path.join(BASE_DIR, 'game_history.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'sync_config.json')

# 核心映射配置
CONFIG = {
    'A': {'name': '观光小火车', 'm': 4},
    'B': {'name': '旋转木马', 'm': 4},
    'C': {'name': '童话剧场', 'm': 4},
    'D': {'name': '彩虹滑道', 'm': 9},
    'E': {'name': '海盗船', 'm': 15},
    'F': {'name': '星空大摆锤', 'm': 20},
    'G': {'name': '云霄飞车', 'm': 30},
}
OPTIONS = list(CONFIG.keys())
TOWER_MAP_REMOTE = {1: 'G', 2: 'F', 3: 'E', 4: 'D', 5: 'C', 6: 'B', 7: 'A'}

# UI 视觉映射字典 (首字 + 颜色类)
UI_MAP = {
    'A': {'char': '观', 'class': 'bg-gray'},
    'B': {'char': '旋', 'class': 'bg-gray'},
    'C': {'char': '童', 'class': 'bg-gray'},
    'D': {'char': '彩', 'class': 'bg-D'},
    'E': {'char': '海', 'class': 'bg-E'},
    'F': {'char': '星', 'class': 'bg-F'},
    'G': {'char': '云', 'class': 'bg-G'}
}

# 状态管理
if 'global_history' not in st.session_state:
    st.session_state.global_history = []
if 'syncing' not in st.session_state:
    st.session_state.syncing = False

def get_sync_config():
    cfg = {"url": "https://lending-mon-manual-charge.trycloudflare.com", "interval": 5, "enabled": True}
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, encoding='utf-8') as f:
                cfg.update(json.load(f))
    except: pass
    return cfg

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.global_history = data if isinstance(data, list) else []
        except: st.session_state.global_history = []

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state.global_history, f, ensure_ascii=False)

def get_pure_history():
    return [x.get("result", x) if isinstance(x, dict) else x for x in st.session_state.global_history]

# ==========================================
# 远程同步后台线程 (高频防缓存)
# ==========================================
def fetch_remote_rows(day):
    cfg = get_sync_config()
    # 加上时间戳绕过 Cloudflare 缓存，确保秒级更新
    url = f"{cfg['url'].rstrip('/')}/api/data?date={day}&_t={int(time.time())}"
    try:
        # 使用 Session 提速
        session = requests.Session()
        resp = session.get(url, timeout=10)
        arr = resp.json()
        if not isinstance(arr, list): return []
        rows = []
        for it in arr:
            t = it.get('hitTower')
            sid = it.get('sessionId')
            if t in TOWER_MAP_REMOTE and sid:
                rows.append({'sid': str(sid), 'letter': TOWER_MAP_REMOTE[t], 'ts': it.get('timestamp', 0)})
        rows.sort(key=lambda x: x['ts'])
        return rows
    except:
        return []

def sync_remote_once(day=None):
    if st.session_state.syncing: return
    st.session_state.syncing = True
    try:
        day = day or date.today().strftime('%Y-%m-%d')
        rows = fetch_remote_rows(day)
        known = {h.get('sid') for h in st.session_state.global_history if isinstance(h, dict) and h.get('sid')}
        added = False
        for row in rows:
            if row['sid'] not in known:
                st.session_state.global_history.append({"result": row['letter'], "sid": row['sid']})
                known.add(row['sid'])
                added = True
        if added: save_data()
    finally:
        st.session_state.syncing = False

def background_worker():
    while True:
        cfg = get_sync_config()
        if cfg.get('enabled', True):
            sync_remote_once()
        # 强制高频 5 秒刷新
        time.sleep(5)

if 'worker_started' not in st.session_state:
    load_data()
    threading.Thread(target=background_worker, daemon=True).start()
    st.session_state.worker_started = True

# ==========================================
# Streamlit 前端渲染
# ==========================================
st.markdown("### 📊 愤怒的小咕 - 纯净数据监控台")

# --- 左侧栏控制 ---
with st.sidebar:
    st.header("⚙️ 控制面板")
    st.write(f"当前累计记录: **{len(st.session_state.global_history)}** 局")
    
    if st.button("🔄 手动刷新页面数据", use_container_width=True):
        sync_remote_once()
        st.rerun()

# --- 数据计算 ---
pure_history = get_pure_history()
omit_counts = {o: 0 for o in OPTIONS}
total_counts = {o: 0 for o in OPTIONS}

for o in OPTIONS:
    count = 0
    for x in reversed(pure_history):
        if x == o: break
        count += 1
    omit_counts[o] = count
    total_counts[o] = pure_history.count(o)

# --- 主界面布局 ---
col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("<div class='omit-box'>", unsafe_allow_html=True)
    st.markdown("#### ⏳ 间隔统计 (遗漏值)")
    for o in OPTIONS:
        color = "red" if omit_counts[o] >= 10 else "black"
        weight = "bold" if omit_counts[o] >= 10 else "normal"
        st.markdown(
            f"<div style='display: flex; justify-content: space-between; border-bottom: 1px dashed #eee; padding: 5px 0;'>"
            f"<span style='color: #4b5563; font-size: 14px;'>{o}. {CONFIG[o]['name']}</span>"
            f"<span style='color: {color}; font-weight: {weight};'>{omit_counts[o]} 把</span>"
            f"</div>", 
            unsafe_allow_html=True
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("#### 📊 数据统计大表")
    table_data = []
    for o in OPTIONS:
        table_data.append({
            "游乐项目": f"{o}. {CONFIG[o]['name']}",
            "星级/倍率": f"{CONFIG[o]['m']}星",
            "当前遗漏 (局)": omit_counts[o],
            "累计出现次数": total_counts[o]
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    
    # ----------------------------------------
    # 高颜值走势图生成 (15局/行)
    # ----------------------------------------
    st.markdown("#### 📌 历史走势图 (15分钟/行)")
    
    if len(pure_history) > 0:
        html_str = "<div class='trend-container'>"
        
        # 将历史记录按 15 个一组进行切割
        for i in range(0, len(pure_history), 15):
            chunk = pure_history[i:i+15]
            start_num = i + 1
            end_num = i + 15
            
            html_str += f"<div class='trend-row'>"
            html_str += f"<div class='trend-label'>第 {start_num}-{end_num} 局</div>"
            html_str += "<div class='trend-grid'>"
            
            # 渲染这 15 个方块，不够的用空方格补齐，保持排版整齐
            for j in range(15):
                if j < len(chunk):
                    opt = chunk[j]
                    ui_info = UI_MAP[opt]
                    html_str += f"<div class='trend-box {ui_info['class']}'>{ui_info['char']}</div>"
                else:
                    html_str += "<div class='empty-box'></div>"
                    
            html_str += "</div></div>"
            
        html_str += "</div>"
        st.markdown(html_str, unsafe_allow_html=True)
    else:
        st.info("🚀 数据正在初始化抓取中，稍等几秒...")

# 前端自动刷新机制：缩短到每5秒刷新一次前端画面，配合后台的5秒抓取，实现光速同步
time.sleep(5)
st.rerun()
