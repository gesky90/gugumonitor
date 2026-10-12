# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
import threading
import time
from datetime import datetime, date
import requests

# 尝试导入无感自动刷新组件
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ==========================================
# 页面基础配置与高颜值 UI 样式注入
# ==========================================
st.set_page_config(page_title="愤怒的小咕 - 纯净监控台", layout="wide")
st.markdown("""
<style>
    /* 容器基础样式 */
    .white-box {
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .omit-box { border-top: 4px solid #ef4444; }
    .table-box { border-top: 4px solid #3b82f6; }
    .trend-box-container { border-top: 4px solid #10b981; }

    /* 走势图排版 */
    .trend-row {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
        padding-bottom: 10px;
        border-bottom: 1px dashed #f3f4f6;
    }
    .trend-label {
        width: 100px;
        font-size: 13px;
        color: #6b7280;
        font-weight: bold;
    }
    .trend-grid { display: flex; gap: 6px; flex-wrap: wrap; }
    
    /* === 颜色分级与发光特效 === */
    .icon-box {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        font-weight: bold;
        border-radius: 6px;
    }
    
    /* 走势图大方块 (32x32) */
    .sz-lg { width: 32px; height: 32px; font-size: 15px; }
    /* 表格/列表小方块 (24x24) */
    .sz-sm { width: 24px; height: 24px; font-size: 12px; margin-right: 8px; }

    /* 小奖 1-3：低调灰色 */
    .bg-gray { background-color: #e5e7eb; color: #6b7280; } 
    /* 大奖 4-7：高亮渐变 + 发光特效 */
    .bg-D { background-color: #a855f7; color: white; box-shadow: 0 0 8px rgba(168, 85, 247, 0.6); } /* 紫 */
    .bg-E { background-color: #ec4899; color: white; box-shadow: 0 0 8px rgba(236, 72, 153, 0.6); } /* 粉 */
    .bg-F { background-color: #ef4444; color: white; box-shadow: 0 0 8px rgba(239, 68, 68, 0.6); } /* 红 */
    .bg-G { background-color: #eab308; color: white; box-shadow: 0 0 8px rgba(234, 179, 8, 0.6); } /* 金 */
    
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

# UI 视觉映射字典
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
    url = f"{cfg['url'].rstrip('/')}/api/data?date={day}&_t={int(time.time())}"
    try:
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
        time.sleep(5) # 后台严格5秒抓取一次

if 'worker_started' not in st.session_state:
    load_data()
    threading.Thread(target=background_worker, daemon=True).start()
    st.session_state.worker_started = True

# ==========================================
# Streamlit 前端渲染与静默刷新
# ==========================================
# 启动前端页面无感倒计时自动刷新 (每隔5秒重新加载一次页面组件，不卡死后端)
if HAS_AUTOREFRESH:
    st_autorefresh(interval=5000, key="data_refresher")

st.markdown("### 📊 愤怒的小咕 - 纯净数据监控台")

if not HAS_AUTOREFRESH:
    st.error("⚠️ 未检测到自动刷新插件，请在 requirements.txt 中添加 `streamlit-autorefresh` 以开启丝滑自动刷新。")

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

# 渲染左侧：遗漏统计 (带彩色徽章)
with col1:
    html_omit = "<div class='white-box omit-box'><h4>⏳ 间隔统计 (遗漏值)</h4>"
    for o in OPTIONS:
        ui = UI_MAP[o]
        omit = omit_counts[o]
        color = "#ef4444" if omit >= 10 else "#111827"
        weight = "bold" if omit >= 10 else "500"
        
        html_omit += f"""
        <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #e5e7eb; padding: 8px 0;'>
            <div style='display: flex; align-items: center; color: #374151; font-size: 14px; font-weight: 500;'>
                <span class='icon-box sz-sm {ui['class']}'>{ui['char']}</span>
                {o}. {CONFIG[o]['name']}
            </div>
            <span style='color: {color}; font-weight: {weight};'>{omit} 把</span>
        </div>
        """
    html_omit += "</div>"
    st.markdown(html_omit, unsafe_allow_html=True)

# 渲染右侧：数据大表与走势图
with col2:
    # 渲染数据统计大表 (手写 HTML 替换默认表格，支持彩色 UI)
    html_table = f"""
    <div class='white-box table-box'>
        <h4 style='margin-bottom: 15px;'>📊 数据统计大表</h4>
        <table style='width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;'>
            <tr style='border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;'>
                <th style='padding: 10px 8px;'>游乐项目</th>
                <th style='padding: 10px 8px;'>星级/倍率</th>
                <th style='padding: 10px 8px;'>当前遗漏 (局)</th>
                <th style='padding: 10px 8px;'>累计出现次数</th>
            </tr>
    """
    for o in OPTIONS:
        ui = UI_MAP[o]
        omit = omit_counts[o]
        omit_color = "#ef4444" if omit >= 10 else "#111827"
        omit_weight = "bold" if omit >= 10 else "500"
        
        html_table += f"""
            <tr style='border-bottom: 1px solid #f3f4f6;'>
                <td style='padding: 10px 8px; display: flex; align-items: center; color: #1f2937; font-weight: 500;'>
                    <span class='icon-box sz-sm {ui['class']}'>{ui['char']}</span>
                    {o}. {CONFIG[o]['name']}
                </td>
                <td style='padding: 10px 8px; color: #4b5563;'>{CONFIG[o]['m']}星</td>
                <td style='padding: 10px 8px; color: {omit_color}; font-weight: {omit_weight};'>{omit}</td>
                <td style='padding: 10px 8px; color: #111827; font-weight: 500;'>{total_counts[o]}</td>
            </tr>
        """
    html_table += "</table></div>"
    st.markdown(html_table, unsafe_allow_html=True)
    
    # 渲染历史走势图 (15分钟/行)
    if len(pure_history) > 0:
        html_trend = "<div class='white-box trend-box-container'><h4 style='margin-bottom: 15px;'>📌 历史走势图 (15分钟/行)</h4>"
        
        for i in range(0, len(pure_history), 15):
            chunk = pure_history[i:i+15]
            start_num = i + 1
            end_num = i + 15
            
            html_trend += f"<div class='trend-row'>"
            html_trend += f"<div class='trend-label'>第 {start_num:02d}-{end_num:02d} 分</div>"
            html_trend += "<div class='trend-grid'>"
            
            for j in range(15):
                if j < len(chunk):
                    opt = chunk[j]
                    ui_info = UI_MAP[opt]
                    html_trend += f"<div class='icon-box sz-lg {ui_info['class']}'>{ui_info['char']}</div>"
                else:
                    html_trend += "<div class='empty-box'></div>"
                    
            html_trend += "</div></div>"
            
        html_trend += "</div>"
        st.markdown(html_trend, unsafe_allow_html=True)
    else:
        st.info("🚀 数据正在初始化抓取中，稍等几秒...")
