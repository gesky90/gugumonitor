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
# 页面基础配置与 UI 样式注入
# ==========================================
st.set_page_config(page_title="愤怒的小咕 - 纯净监控台", layout="wide")
st.markdown("""
<style>
    .omit-box {
        background-color: white;
        border-top: 4px solid #ef4444;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 基础配置
# ==========================================
BASE_DIR = os.getcwd()
DATA_FILE = os.path.join(BASE_DIR, 'game_history.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'sync_config.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

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

# 状态管理
if 'global_history' not in st.session_state:
    st.session_state.global_history = []
if 'syncing' not in st.session_state:
    st.session_state.syncing = False

def get_sync_config():
    cfg = {"url": "https://lending-mon-manual-charge.trycloudflare.com", "interval": 15, "enabled": True}
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, encoding='utf-8') as f:
                cfg.update(json.load(f))
    except: pass
    return cfg

def save_sync_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

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
# 远程同步后台线程
# ==========================================
def fetch_remote_rows(day):
    cfg = get_sync_config()
    url = cfg['url'].rstrip('/') + '/api/data?date=' + day
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': UA})
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
        time.sleep(max(5, int(cfg.get('interval', 15))))

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
    
    if st.button("清空所有数据", use_container_width=True):
        st.session_state.global_history = []
        save_data()
        st.rerun()
        
    st.divider()
    st.subheader("🌐 接口设置")
    cfg = get_sync_config()
    new_url = st.text_input("数据接口 URL", value=cfg.get('url', ''))
    is_enabled = st.checkbox("启用后台自动同步", value=cfg.get('enabled', True))
    
    if st.button("保存并手动同步", use_container_width=True):
        save_sync_config({"url": new_url, "interval": cfg.get('interval', 15), "enabled": is_enabled})
        sync_remote_once()
        st.rerun()

# --- 数据计算 ---
pure_history = get_pure_history()
omit_counts = {o: 0 for o in OPTIONS}
total_counts = {o: 0 for o in OPTIONS}

for o in OPTIONS:
    # 计算遗漏
    count = 0
    for x in reversed(pure_history):
        if x == o: break
        count += 1
    omit_counts[o] = count
    # 计算累计出现次数
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
    st.markdown("#### 📊 各项数据统计表")
    table_data = []
    for o in OPTIONS:
        table_data.append({
            "游乐项目": f"{o}. {CONFIG[o]['name']}",
            "星级/倍率": f"{CONFIG[o]['m']}星",
            "当前遗漏 (局)": omit_counts[o],
            "累计出现次数": total_counts[o]
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    
    st.markdown("#### 📌 历史走势图 (横向60分钟/1小时)")
    if len(pure_history) > 0:
        trend_data = []
        # 改为每 60 局（1小时）一行
        for i in range(0, len(pure_history), 60):
            chunk = pure_history[i:i+60]
            row_dict = {"起始时间段": f"第 {i+1} 局起"}
            for j in range(60):
                row_dict[f"{j+1}分"] = f"{chunk[j]}" if j < len(chunk) else ""
            trend_data.append(row_dict)
        st.dataframe(pd.DataFrame(trend_data), use_container_width=True, hide_index=True)
    else:
        st.info("数据积累中，请等待接口拉取...")

# 页面自动刷新逻辑 (保持每10秒刷新画面)
time.sleep(10)
st.rerun()
