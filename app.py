import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for
import yfinance as yf

app = Flask(__name__)
# 使用 v16 版本資料庫
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v16.db')

# --- 1. AI 數字解析邏輯 (支援國字與阿拉伯數字) ---
def cn_to_num(cn):
    if not cn: return 0
    digits = {'零':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    units = {'十':10,'百':100,'千':1000,'萬':10000}
    res, quota, tmp = 0, 1, 0
    try:
        for char in reversed(cn):
            if char in digits: tmp += digits[char] * quota
            elif char in units:
                quota = units[char]
                if quota >= 10000: res += tmp; tmp = 0; res *= quota; quota = 1
        return res + tmp
    except: return 0

def smart_extract_amt(text):
    text = text.replace(',', '')
    nums = re.findall(r'-?\d+\.?\d*', text)
    if nums: return float(nums[0])
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums: return cn_to_num(cn_nums.group())
    return 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    # 統一儲存表
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, symbol TEXT)''')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)') # 預設百萬目標
    conn.commit()
    conn.close()

init_db()

# --- 3. 整合型 HTML 介面 (AI 感 + 進度條 + 手機優化) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Gemini AI 財富大腦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --accent: #58a6ff; }
        body { background-color: var(--bg); color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding-bottom: 30px; }
        .ai-header { background: linear-gradient(135deg, #1e3a8a 0%, #0d1117 100%); padding: 30px 15px; border-bottom: 1px solid var(--border); }
        .ai-input-wrapper { background: #0d1117; border: 2px solid #388bfd; border-radius: 30px; padding: 8px 15px; display: flex; align-items: center; box-shadow: 0 0 15px rgba(56, 139, 253, 0.2); }
        .ai-input-wrapper input { background: transparent; border: none; color: white; flex-grow: 1; outline: none; font-size: 16px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 15px; margin-top: 15px; }
        .progress { height: 12px; background-color: #30363d; border-radius: 6px; }
        .btn-ai { background: #238636; color: white; border: none; border-radius: 20px; padding: 5px 15px; font-weight: bold; }
        .history-item { border-bottom: 1px solid var(--border); padding: 12px 0; display: flex; justify-content: space-between; align-items: center; }
        .badge-stock { background: #238636; color: white; font-size: 10px; }
        .badge-cash { background: #388bfd; color: white; font-size: 10px; }
    </style>
</head>
<body>
    <div class="ai-header text-center">
        <h5 class="fw-bold text-white mb-3">🤖 GEMINI AI 智慧助理</h5>
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-lg-8">
                    <form action="/process" method="POST" class="ai-input-wrapper">
                        <input type="text" name="user_input" placeholder="試試：中信五萬、買 2330 1張、目標兩百萬" required>
                        <button type="submit" class="btn-ai">執行</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div class="container mt-3">
        <div class="card p-3 text-center">
            <p class="text-muted mb-1 small">總資產估值 (TWD)</p>
            <h2 class="text-white fw-bold">${{ "{:,.0f}".format(total_val) }}</h2>
            <div class="px-4 mt-2">
                <div class="progress">
                    <div class="progress-bar bg-info" style="width: {{ progress }}%"></div>
                </div>
                <div class="d-flex justify-content-between mt-1 small text-muted">
                    <span>達成率 {{ progress }}%</span>
                    <span>目標：${{ "{:,.0f}".format(goal_amt) }}</span>
                </div>
            </div>
        </div>

        <div class="card p-3 mt-3">
            <h6 class="fw-bold mb-3">🗂️ 資產明細與實時市值</h6>
            {% for item in assets %}
            <div class="history-item">
                <div>
                    <div class="text-white">{{ item.name }}</div>
                    {% if item.category == '股票' %}
                        <span class="badge badge-stock">股票 {{ item.symbol }}</span>
                    {% else %}
                        <span class="badge badge-cash">現金/存款</span>
                    {% endif %}
                </div>
                <div class="text-end">
                    <div class="fw-bold {{ 'text-success' if item.amount >= 0 else 'text-danger' }}">
                        ${{ "{:,.0f}".format(item.display_amount) }}
                    </div>
                    <a href="/delete/{{ item.id }}" class="text-danger small text-decoration-none">移除</a>
                </div>
            </div>
            {% endfor %}
            {% if not assets %}
                <p class="text-center text-muted my-3">目前尚無資料，請開始對 AI 說話吧！</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

# --- 4. 核心路由邏輯 ---
@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 抓取目標
    c.execute('SELECT target_amount FROM goals WHERE id=1')
    goal_amt = c.fetchone()[0]
    
    # 抓取所有資產
    c.execute('SELECT id, name, amount, category, symbol FROM assets ORDER BY id DESC')
    raw_assets = c.fetchall()
    
    processed_assets = []
    total_val = 0
    
    for item in raw_assets:
        aid, name, amt, cat, sym = item
        display_amt = amt
        
        # 如果是股票，抓取現價
        if cat == '股票' and sym:
            try:
                price = yf.Ticker(sym).fast_info.get('last_price', 0)
                display_amt = amt * price # 此處的 amt 儲存的是股數
            except:
                display_amt = 0
        
        total_val += display_amt
        processed_assets.append({
            'id': aid, 'name': name, 'amount': amt, 'category': cat, 
            'symbol': sym, 'display_amount': display_amt
        })
    
    progress = min(100, round((total_val / goal_amt) * 100, 1)) if goal_amt > 0 else 0
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, assets=processed_assets, total_val=total_val, 
                                  goal_amt=goal_amt, progress=progress)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    if not text: return redirect(url_for('index'))
    
    conn = sqlite3.connect(db_path)
    
    # AI 智慧解析分流
    amt = smart_extract_amt(text)
    
    # 1. 處理目標設定
    if "目標" in text:
        conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
    
    # 2. 處理轉帳邏輯
    elif any(w in text for w in ["轉", "移"]):
        match = re.search(r"(.+?)\s*(?:轉|移)\s*(?:到|至)?\s*(.+?)\s*", text)
        if match:
            from_b, to_b = match.groups()
            conn.execute('INSERT INTO assets (name, amount, category) VALUES (?, ?, ?)', (f"轉出: {from_b}", -amt, "儲蓄"))
            conn.execute('INSERT INTO assets (name, amount, category) VALUES (?, ?, ?)', (f"轉入: {to_b}", amt, "儲蓄"))
    
    # 3. 處理股票邏輯
    elif any(w in text for w in ["股", "張"]) or re.search(r'\d{4}', text):
        sym_match = re.search(r'([A-Z0-9\.]+)', text.upper())
        sym = sym_match.group() if sym_match else ""
        if sym.isdigit() and len(sym) >= 4: sym += ".TW"
        
        # 解析股數 (如果是張則 *1000)
        shares = amt
        if "張" in text: shares *= 1000
        conn.execute('INSERT INTO assets (name, amount, category, symbol) VALUES (?, ?, ?, ?)', (text, shares, "股票", sym))
    
    # 4. 一般收支
    else:
        cat = "支出" if any(w in text for w in ["付", "花", "買", "支出"]) else "儲蓄"
        if cat == "支出": amt = -abs(amt)
        conn.execute('INSERT INTO assets (name, amount, category) VALUES (?, ?, ?)', (text, amt, cat))
        
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect(db_path)
    conn.execute('DELETE FROM assets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
