# -*- coding: utf-8 -*-
"""
愤怒的小咕 · 模拟游戏监控台（Streamlit 增强版）
=====================================================
功能：
  1) 核心算法无损保留：市场心理学、庄家模拟、安全策略、按局回测补记。
  2) Streamlit 实时渲染：抛弃了 Flask 和 HTML，纯 Python 绘制高颜值界面。
  3) 后台自动同步：后台独立线程按配置频率自动拉取 Cloudflare 数据并持久化。
"""
import streamlit as st
import json
import os
import random
import threading
import time
from datetime import datetime, date
import pandas as pd
import requests

# ==========================================
# 页面基础配置与 UI 样式注入
# ==========================================
st.set_page_config(page_title="愤怒的小咕 - 量化引擎", layout="wide")
st.markdown("""
<style>
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
        white-space: pre-wrap;
    }
    .omit-box {
        background-color: white;
        border-top: 4px solid #ef4444;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .stats-box {
        background-color: white;
        border-top: 4px solid #3b82f6;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 游戏基础配置与参数 (保持原样)
# ==========================================
BASE_DIR = os.getcwd()
DATA_FILE = os.path.join(BASE_DIR, 'game_history.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'sync_config.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

CONFIG = {
    'A': {'name': '观光小火车', 'p': 0.2472, 'm': 4},
    'B': {'name': '旋转木马', 'p': 0.2472, 'm': 4},
    'C': {'name': '童话剧场', 'p': 0.2472, 'm': 4},
    'D': {'name': '彩虹滑道', 'p': 0.1100, 'm': 9},
    'E': {'name': '海盗船', 'p': 0.0660, 'm': 15},
    'F': {'name': '星空大摆锤', 'p': 0.0495, 'm': 20},
    'G': {'name': '云霄飞车', 'p': 0.0329, 'm': 30},
}
OPTIONS = list(CONFIG.keys())
REWARDS_TABLE = [
    {'name': '缤纷幻境', 'value': 50000}, {'name': '精灵奇缘', 'value': 50000},
    {'name': '天马星梦', 'value': 20000}, {'name': '翎光城堡', 'value': 20000},
    {'name': '兔然心动', 'value': 13140}, {'name': '奇喵之旅', 'value': 5000},
    {'name': '闪亮登场', 'value': 1000}, {'name': '糖果船', 'value': 200},
    {'name': '欢乐菇', 'value': 10}
]
PARAMS = {
    "history_weight": 0.25, "max_bonus_low_m": 1.2, "max_bonus_high_m": 0.6,
    "omit_start": 6, "omit_cap": 30, "anti_decay_d5": 0.2, "high_prob_overflow_cap": 0.5,
    "total_players_min": 300, "total_players_max": 600,
    "p1_unit": 2, "p2_unit": 2, "p3_unit_omit": 1, "p3_unit_rand": 1,
    "p4_unit_each": 1, "p5_unit_low": 1, "p5_unit_high": 1,
    "p6_unit_fixed": 1, "p6_unit_rand": 1, "my_unit": 10
}

REMOTE_DEFAULT = {
    "url": "https://lending-mon-manual-charge.trycloudflare.com",
    "interval": 15, "enabled": True
}
TOWER_MAP_REMOTE = {1: 'G', 2: 'F', 3: 'E', 4: 'D', 5: 'C', 6: 'B', 7: 'A'}
TOWER_NAME_REMOTE = {1: '云霄飞车', 2: '星空大摆锤', 3: '海盗船', 4: '彩虹滑道', 5: '童话剧场', 6: '旋转木马', 7: '观光小火车'}

sync_state = {
    "last_sync": None, "last_success": None, "last_error": None, "last_fetched": 0,
    "total_imported": 0, "remote_latest": None, "remote_latest_time": None, "syncing": False,
}

# ==========================================
# 核心算法引擎 (完全保留)
# ==========================================
def calculate_gift(bet_tons, star_level):
    contribution = bet_tons * star_level * 10
    gifts = []
    rem = contribution
    for r in REWARDS_TABLE:
        count = rem // r['value']
        if count > 0:
            gifts.append(f"{r['name']}x{count}")
            rem %= r['value']
    return contribution, (" + ".join(gifts) if gifts else "无")

class MarketPsychologyEngine:
    def __init__(self): self.history = []
    def omission(self):
        result = {}
        for o in OPTIONS:
            count = 0
            for x in reversed(self.history):
                if x == o: break
                count += 1
            result[o] = count
        return result
    def calculate_distribution(self, bonus_scale=1.0):
        omit = self.omission()
        scores = {}
        recent_5_rev = list(reversed(self.history[-5:]))
        for o in OPTIONS:
            original_p, m, base = CONFIG[o]['p'], CONFIG[o]['m'], CONFIG[o]['p']
            consecutive_count = 0
            for x in reversed(self.history):
                if x == o: consecutive_count += 1
                else: break
            if self.history:
                real = self.history.count(o) / len(self.history)
                if real > original_p: base += (real - original_p) * PARAMS["history_weight"] * bonus_scale
            if consecutive_count >= 3: scores[o] = original_p
            else:
                m_ratio = (m - 4) / 26.0
                dyn_max_low = PARAMS["max_bonus_low_m"] * bonus_scale
                dyn_max_high = PARAMS["max_bonus_high_m"] * bonus_scale
                max_bonus = dyn_max_low - m_ratio * (dyn_max_low - dyn_max_high)
                omit_val = omit[o]
                omit_factor = 0.0 if omit_val < PARAMS["omit_start"] else min(omit_val - PARAMS["omit_start"], float(PARAMS["omit_cap"] - PARAMS["omit_start"])) / float(PARAMS["omit_cap"] - PARAMS["omit_start"])
                omission_multiplier = omit_factor * max_bonus
                anti_multiplier = 0.0
                if o in recent_5_rev:
                    distance = recent_5_rev.index(o) + 1
                    factor = PARAMS["anti_decay_d5"] + (5 - distance) / 4.0 * (1.0 - PARAMS["anti_decay_d5"])
                    anti_multiplier = factor * max_bonus
                scores[o] = max(original_p, base * (1.0 + omission_multiplier + anti_multiplier))
        high_opts, low_opts = ['D', 'E', 'F', 'G'], ['A', 'B', 'C']
        final_probs = {}
        high_prob_sum = sum(scores[o] for o in high_opts)
        if high_prob_sum >= 1.0:
            scale = PARAMS["high_prob_overflow_cap"] / high_prob_sum
            high_prob_sum = PARAMS["high_prob_overflow_cap"]
            for o in high_opts: scores[o] *= scale
        for o in high_opts: final_probs[o] = scores[o]
        remain_prob = 1.0 - high_prob_sum
        low_score_sum = sum(scores[o] for o in low_opts)
        for o in low_opts:
            final_probs[o] = remain_prob * (scores[o] / low_score_sum) if low_score_sum > 0 else remain_prob / len(low_opts)
        return final_probs

class PlayerSimulator:
    def __init__(self, prob):
        self.prob = prob
        self.bettors = {o: 0 for o in OPTIONS}
    def simulate(self, omit, herd_scale=1.0):
        pool = {o: 0 for o in OPTIONS}
        self.bettors = {o: 0 for o in OPTIONS}
        highest_prob_opt = max(OPTIONS, key=lambda x: self.prob[x])
        highest_ev_opt = max(OPTIONS, key=lambda x: self.prob[x] * CONFIG[x]['m'])
        highest_omit_opt = max(OPTIONS, key=lambda x: omit[x])
        total_players = random.randint(PARAMS["total_players_min"], PARAMS["total_players_max"])
        weights = [random.random() for _ in range(6)]
        counts = [int(total_players * (w / sum(weights))) for w in weights]
        counts[0] += total_players - sum(counts)
        p1, p2, p3, p4, p5, p6 = counts
        if herd_scale != 1.0:
            s1, s2, s3 = int(p1 * (1.0 - herd_scale)), int(p2 * (1.0 - herd_scale)), int(p3 * (1.0 - herd_scale))
            p1, p2, p3 = p1 - s1, p2 - s2, p3 - s3
            p4 += (s1 + s2 + s3)
        for _ in range(p1): pool[highest_prob_opt] += PARAMS["p1_unit"]; self.bettors[highest_prob_opt] += 1
        for _ in range(p2): pool[highest_ev_opt] += PARAMS["p2_unit"]; self.bettors[highest_ev_opt] += 1
        for _ in range(p3):
            pool[highest_omit_opt] += PARAMS["p3_unit_omit"]; self.bettors[highest_omit_opt] += 1
            r = random.choice(OPTIONS)
            pool[r] += PARAMS["p3_unit_rand"]; self.bettors[r] += (1 if r != highest_omit_opt else 0)
        for _ in range(p4):
            r1, r2 = random.choice(OPTIONS), random.choice(OPTIONS)
            pool[r1] += PARAMS["p4_unit_each"]; pool[r2] += PARAMS["p4_unit_each"]
            self.bettors[r1] += 1; self.bettors[r2] += (1 if r1 != r2 else 0)
        for _ in range(p5):
            rl, rh = random.choice(['A', 'B', 'C']), random.choice(['D', 'E', 'F', 'G'])
            pool[rl] += PARAMS["p5_unit_low"]; pool[rh] += PARAMS["p5_unit_high"]
            self.bettors[rl] += 1; self.bettors[rh] += 1
        for fixed_opt in random.choices(OPTIONS, weights=[CONFIG[o]['p'] for o in OPTIONS], k=p6):
            pool[fixed_opt] += PARAMS["p6_unit_fixed"]; self.bettors[fixed_opt] += 1
            r = random.choice(OPTIONS)
            pool[r] += PARAMS["p6_unit_rand"]; self.bettors[r] += (1 if r != fixed_opt else 0)
        return pool

class HouseAnalyzer:
    def calculate(self, pool):
        total = sum(pool.values())
        return {o: {'profit': total - pool[o] * CONFIG[o]['m'], 'payout': pool[o] * CONFIG[o]['m']} for o in OPTIONS}
    def best_open(self, pool):
        res = self.calculate(pool)
        return max(res, key=lambda x: res[x]['profit'])

class SafeStrategy:
    def check(self, pool, bet):
        house = HouseAnalyzer()
        before = house.best_open(pool)
        new_pool = pool.copy()
        for k, v in bet.items(): new_pool[k] += v
        return before == house.best_open(new_pool), before, house.best_open(new_pool)
    def get_fixed_combos(self, pool, prob, best_open):
        my_unit = PARAMS["my_unit"]
        sorted_by_prob = sorted(OPTIONS, key=lambda x: prob[x], reverse=True)
        opt_prob = sorted_by_prob[0] if sorted_by_prob[0] != best_open else sorted_by_prob[1]
        combo2 = (best_open, opt_prob)
        rate2 = prob[best_open] + prob[opt_prob]
        ok2, _, after2 = self.check(pool, {best_open: my_unit, opt_prob: my_unit})
        sorted_by_ev = sorted(OPTIONS, key=lambda x: prob[x] * CONFIG[x]['m'], reverse=True)
        opt_ev = next((x for x in sorted_by_ev if x not in combo2), None)
        combo3 = (best_open, opt_prob, opt_ev)
        rate3 = prob[best_open] + prob[opt_prob] + prob[opt_ev]
        ok3, _, after3 = self.check(pool, {best_open: my_unit, opt_prob: my_unit, opt_ev: my_unit})
        return (rate2, combo2, after2, ok2), (rate3, combo3, after3, ok3)
    def best_chase(self, omit):
        high_opts = ['D', 'E', 'F', 'G']
        best_opt = max(high_opts, key=lambda o: omit[o])
        return best_opt, omit[best_opt], int((1.0 / CONFIG[best_opt]['p']) * 1.5)

# ==========================================
# 状态与持久化逻辑
# ==========================================
if 'global_history' not in st.session_state:
    st.session_state.global_history = []
if 'current_preds' not in st.session_state:
    st.session_state.current_preds = {"c2": [], "c3": [], "house": ""}

def get_sync_config():
    cfg = dict(REMOTE_DEFAULT)
    try:
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
            if data and isinstance(data[0], str):
                st.session_state.global_history = [{"result": x, "pred_c2": [], "pred_c3": [], "pred_house": ""} for x in data]
            else:
                st.session_state.global_history = data
        except: st.session_state.global_history = []

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state.global_history, f, ensure_ascii=False)

def get_pure_history():
    return [x.get("result", x) if isinstance(x, dict) else x for x in st.session_state.global_history]

def calculate_dynamic_factors():
    valid_evals = [h for h in st.session_state.global_history if h.get("pred_c2")]
    recent = valid_evals[-15:]
    if len(recent) < 5: return 1.0, 1.0, "[自适应] 数据积累中 (1.0x)", "text-yellow-600"
    hits = sum(1 for h in recent if h["result"] in h["pred_c2"])
    rate = hits / len(recent)
    if rate >= 0.45: return 1.2, 1.2, f"[自适应] 庄家杀热期 | 近期胜率{rate * 100:.0f}% -> 放大杀熟参数", "text-red-600"
    elif rate < 0.33: return 0.4, 0.2, f"[自适应] 自然概率回归期 | 近期胜率{rate * 100:.0f}% -> 瓦解散户，回归随机", "text-blue-600"
    return 1.0, 1.0, f"[自适应] 正常博弈震荡期 | 近期胜率{rate * 100:.0f}% -> 维持标准参数", "text-green-600"

def run_analysis(history):
    engine = MarketPsychologyEngine()
    engine.history = history
    omit = engine.omission()
    bonus_scale, herd_scale, dyn_text, dyn_color = calculate_dynamic_factors()
    prob = engine.calculate_distribution(bonus_scale)
    simulator = PlayerSimulator(prob)
    pool = simulator.simulate(omit, herd_scale)
    bettors = simulator.bettors
    house = HouseAnalyzer()
    house_result = house.calculate(pool)
    best_open = house.best_open(pool)
    strategy = SafeStrategy()
    combo2, combo3 = strategy.get_fixed_combos(pool, prob, best_open)
    chase_opt, chase_omit, suggest_entry = strategy.best_chase(omit)
    return {
        "omit": omit, "prob": prob, "pool": pool, "bettors": bettors,
        "house_result": house_result, "best_open": best_open,
        "combo2": combo2, "combo3": combo3,
        "chase_opt": chase_opt, "chase_omit": chase_omit, "suggest_entry": suggest_entry,
        "dyn_text": dyn_text, "dyn_color": dyn_color,
    }

def compute_prediction_snapshot(history):
    a = run_analysis(history)
    return list(a['combo2'][1]), list(a['combo3'][1]), a['best_open']

def get_full_analysis():
    pure_history = get_pure_history()
    a = run_analysis(pure_history)
    st.session_state.current_preds = {"c2": list(a['combo2'][1]), "c3": list(a['combo3'][1]), "house": a['best_open']}
    return a

# ==========================================
# 远程同步后台线程
# ==========================================
def fetch_remote_rows(day):
    cfg = get_sync_config()
    url = cfg['url'].rstrip('/') + '/api/data?date=' + day
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

def sync_remote_once(day=None):
    if sync_state['syncing']: return
    sync_state['syncing'] = True
    try:
        day = day or date.today().strftime('%Y-%m-%d')
        rows = fetch_remote_rows(day)
        known = {h.get('sid') for h in st.session_state.global_history if isinstance(h, dict) and h.get('sid')}
        added = 0
        for row in rows:
            if row['sid'] in known: continue
            c2, c3, house = compute_prediction_snapshot(get_pure_history())
            st.session_state.global_history.append({
                "result": row['letter'], "sid": row['sid'],
                "pred_c2": c2, "pred_c3": c3, "pred_house": house
            })
            known.add(row['sid'])
            added += 1
        if added: save_data()
        now = datetime.now().strftime('%H:%M:%S')
        sync_state.update({'last_sync': now, 'last_fetched': len(rows), 'total_imported': sync_state['total_imported'] + added})
    except Exception as e:
        sync_state['last_error'] = str(e)
    finally:
        sync_state['syncing'] = False

def background_worker():
    while True:
        try:
            cfg = get_sync_config()
            if cfg.get('enabled', True): sync_remote_once()
        except: pass
        time.sleep(max(5, int(get_sync_config().get('interval', 15))))

if 'worker_started' not in st.session_state:
    load_data()
    threading.Thread(target=background_worker, daemon=True).start()
    st.session_state.worker_started = True

# ==========================================
# Streamlit 前端渲染与拼接
# ==========================================
st.markdown("### 📊 愤怒的小咕 - 模拟游戏监控台 (量化增强版)")

# 左侧栏控制与配置
with st.sidebar:
    st.header("⚙️ 引擎控制台")
    st.write(f"当前总期数: **{len(st.session_state.global_history)}**")
    
    if st.button("撤销上一局 (手动)", use_container_width=True):
        if st.session_state.global_history:
            st.session_state.global_history.pop()
            save_data()
            st.rerun()
    if st.button("清空所有数据", use_container_width=True):
        st.session_state.global_history = []
        save_data()
        st.rerun()
        
    st.divider()
    st.subheader("🌐 同步设置")
    cfg = get_sync_config()
    new_url = st.text_input("数据接口 URL", value=cfg.get('url', ''))
    new_interval = st.number_input("同步间隔 (秒)", min_value=5, value=cfg.get('interval', 15))
    is_enabled = st.checkbox("启用自动同步", value=cfg.get('enabled', True))
    
    if st.button("保存并手动同步一次", use_container_width=True):
        save_sync_config({"url": new_url, "interval": new_interval, "enabled": is_enabled})
        sync_remote_once()
        st.rerun()

# 核心计算与数据准备
analysis = get_full_analysis()
omit, prob, pool, bettors = analysis['omit'], analysis['prob'], analysis['pool'], analysis['bettors']
house_result, best_open = analysis['house_result'], analysis['best_open']
combo2, combo3 = analysis['combo2'], analysis['combo3']
chase_opt, chase_omit, suggest_entry = analysis['chase_opt'], analysis['chase_omit'], analysis['suggest_entry']

total_evals, c2_hits, c3_hits, house_hits = 0, 0, 0, 0
for item in st.session_state.global_history:
    if item.get("pred_c2"):
        total_evals += 1
        if item.get("result") in item.get("pred_c2"): c2_hits += 1
        if item.get("result") in item.get("pred_c3"): c3_hits += 1
        if item.get("result") == item.get("pred_house"): house_hits += 1

# 主界面布局
col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("<div class='stats-box'>", unsafe_allow_html=True)
    st.markdown("#### 📈 预测准确率看板")
    st.markdown(f"**已验证局数:** {total_evals} 局")
    st.markdown(f"**双项命中:** {c2_hits}局 ({c2_hits/total_evals*100:.1f}% if total_evals else '0.0%')")
    st.markdown(f"**三项命中:** {c3_hits}局 ({c3_hits/total_evals*100:.1f}% if total_evals else '0.0%')")
    st.markdown(f"**单杀庄家:** {house_hits}局 ({house_hits/total_evals*100:.1f}% if total_evals else '0.0%')")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='omit-box'>", unsafe_allow_html=True)
    st.markdown("#### ⏳ 间隔统计 (遗漏值)")
    for o in OPTIONS:
        color = "red" if omit[o] >= 10 else "black"
        weight = "bold" if omit[o] >= 10 else "normal"
        st.markdown(
            f"<div style='display: flex; justify-content: space-between; border-bottom: 1px dashed #eee; padding: 5px 0;'>"
            f"<span style='color: #4b5563; font-size: 14px;'>{o}. {CONFIG[o]['name']}</span>"
            f"<span style='color: {color}; font-weight: {weight};'>{omit[o]} 把</span>"
            f"</div>", 
            unsafe_allow_html=True
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    # 构造 AI 文本并显示黑框终端
    r2, c2_o, after2, ok2 = combo2
    r3, c3_o, after3, ok3 = combo3
    ai_text = f"""🤖 AI 动态运算引擎
--------------------------------------------------
[*] 当前自适应状态: {analysis['dyn_text']}

[*] 庄家避险最优开盘: 【 {best_open} - {CONFIG[best_open]['name']} 】
    预期收割利润 : {house_result[best_open]['profit']:.1f} 吨蘑菇

[>] 智能定点狙击方案 (各投入 {PARAMS['my_unit']} 吨):
    [双项] {c2_o[0]}(避险) + {c2_o[1]}(高概) | 胜率: {r2*100:.2f}% | 动作: 庄开 {after2}
           > 估算: {calculate_gift(PARAMS['my_unit'], CONFIG[c2_o[0]]['m'])[1]}
    [三项] {c3_o[0]}(避险) + {c3_o[1]}(高概) + {c3_o[2]}(高EV) | 胜率: {r3*100:.2f}% | 动作: 庄开 {after3}

[>] 高星遗漏追号方案:
    重点关注 : 【 {chase_opt} - {CONFIG[chase_opt]['name']} 】 ({CONFIG[chase_opt]['m']}星) | 建议切入 : 遗漏 {suggest_entry} 期
"""
    st.markdown(f"<div class='ai-console'>{ai_text}</div>", unsafe_allow_html=True)

    # 渲染数据分析大表
    st.markdown("#### 📊 实时市场盘口推演表")
    table_data = []
    positive_profits = {o: house_result[o]['profit'] for o in OPTIONS if house_result[o]['profit'] > 0}
    top3_profits = sorted(positive_profits, key=positive_profits.get, reverse=True)[:3]
    
    for o in OPTIONS:
        table_data.append({
            "项目": f"{o}. {CONFIG[o]['name']} ({CONFIG[o]['m']}星)",
            "AI预测概率": f"{(prob[o] * 100):.2f}%",
            "当前遗漏": omit[o],
            "市场盘口": f"{bettors[o]}人 / {pool[o]:.0f}吨",
            "庄家利润 (若开此项)": f"★ {house_result[o]['profit']:.1f}" if o in top3_profits else f"{house_result[o]['profit']:.1f}"
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    
    # 渲染走势图
    st.markdown("#### 📌 历史走势图")
    pure_history = get_pure_history()
    if len(pure_history) > 0:
        trend_data = []
        for i in range(0, len(pure_history), 30):
            chunk = pure_history[i:i+30]
            row_dict = {"起始局": f"第 {i+1} 局"}
            for j in range(30):
                row_dict[f"走势 {j+1}"] = f"{chunk[j]}" if j < len(chunk) else ""
            trend_data.append(row_dict)
        st.dataframe(pd.DataFrame(trend_data), use_container_width=True, hide_index=True)
    else:
        st.info("数据积累中，等待接口拉取...")

# 页面自动刷新逻辑 (保持画面与后台线程同步)
time.sleep(10)
st.rerun()
