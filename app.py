import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for
import yfinance as yf

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v20.db')

# --- 1. 強化版 AI 數字解析 (解決 10萬變 10元問題) ---
def cn_to_num(cn):
    if not cn: return 0
    digits = {'零':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    units = {'十':10,'百':100,'千':1000,'萬':10000}
    
    # 如果純粹是數字加「萬」，例如 "10萬"
    pure_num_match = re.search(r'(\d+)\s*萬', cn)
    if pure_num_match:
        return float(pure_num_match.group(1)) * 10000

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
    # 先處理「數字+萬」的特殊情況
    text = text.replace(',', '')
    special_wan = re.search(r'(\d+\.?\d*)\s*萬', text)
    if special_wan:
        return float(special_wan.group(1)) * 10000
    
    # 處理純國字數字
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums:
        return cn_to_num(cn_nums.group())
        
    # 處理一般阿拉伯數字
    nums = re.findall(r'-?\d+\.?\d*', text)
    if nums: return float(nums[0])
    return 0

# --- 2. 匯率轉換工具 ---
def get_ex_rate(currency_name):
    rates = {"美金": "USDTWD=X", "USD": "USDTWD=X", "日幣": "JPYTWD=X", "JPY": "JPYTWD=X", "歐元": "EURTWD=X", "人民幣": "CNYTWD=X"}
    if currency_name in rates:
        try:
            ticker = yf.Ticker(rates[currency_name])
            return ticker.fast_info.get('last_price', 1)
        except: return 1
    return 1

# --- 3. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, symbol TEXT, currency TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 4. 豪華圖表版 HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Gemini AI 全球財富腦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --bg: #0d1117; --card: #161b22; --border: #30363d; }
        body { background-color: var(--bg); color: #c9d1d9; font-family: sans-serif; padding-bottom: 50px; }
        .ai-header { background: linear-gradient(135deg, #1e3a8a 0%, #0d1117 100%); padding: 30px 15px; border-bottom: 1px solid var(--border); }
        .ai-input-wrapper { background: #0d1117; border: 2px solid #388bfd; border-radius: 30px; padding: 8px 15px; display: flex; align-items: center; }
        .ai-input-wrapper input { background: transparent; border: none; color: white; flex-grow: 1; outline: none; font-size: 16px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 15px; margin-top: 15px; }
        .progress { height: 12px; background-color: #30363d; border-radius: 6px; }
        .btn-ai { background: #238636; color: white; border-radius: 20px; border: none; padding: 5px 15px; font-weight: bold; }
        .history-item { border-bottom: 1px solid var(--border); padding: 12px 0; display: flex; justify-content: space-between; align-items: center; }
        .currency-tag { font-size: 10px; background: #30363d; padding: 2px 6px; border-radius: 4px; color: #58a6ff; }
    </style>
</head>
<body>
    <div class="ai-header text-center">
        <h5 class="fw-bold text-white mb-2">🤖 GEMINI 全球財富助理</h5>
        <div class="container">
            <form action="/process" method="POST" class="ai-input-wrapper">
                <input type="text" name="user_input" placeholder="例如：美金 1000、日幣十萬、10萬..." required>
                <button type="submit" class="btn-ai">解析</button>
            </form>
        </div>
    </div>

    <div class="container mt-3">
        <div class="card p-3 text-center">
            <p class="text-muted mb-1 small">總資產價值 (折合台幣)</p>
            <h2 class="text-white fw-bold">${{ "{:,.0f}".format(total_val) }}</h2>
            <div class="progress mt-2">
                <div class="progress-bar bg-info" style="width: {{ progress }}%"></div>
            </div>
            <div class="d-flex justify-content-between mt-1 small text-muted">
                <span>達成率 {{ progress }}%</span>
                <span>目標：${{ "{:,.0f}".format(goal_amt) }}</span>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6"><div class="card p-3"><h6 class="fw-bold mb-3 small">📊 分佈</h6><div style="height: 180px;"><canvas id="pieChart"></canvas></div></div></div>
            <div class="col-md-6"><div class="card p-3"><h6 class="fw-bold mb-3 small">📈 走勢</h6><div style="height: 180px;"><canvas id="lineChart"></canvas></div></div></div>
        </div>

        <div class="card p-3 mt-3">
            <h6 class="fw-bold mb-3 small">📝 最近紀錄</h6>
            {% for item in assets %}
            <div class="history-item">
                <div>
                    <div class="text-white">{{ item.name }}</div>
                    <span class="currency-tag">{{ item.currency }}</span>
                </div>
                <div class="text-end">
                    <div class="fw-bold {{ 'text-success' if item.display_amount >= 0 else 'text-danger' }}">
                        ${{ "{:,.0f}".format(item.display_amount) }}
                    </div>
                    <a href="/delete/{{ item.id }}" class="text-danger small">移除</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const commonOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#c9d1d9', font: { size: 10 } } } } };
        new Chart(document.getElementById('pieChart'), { type: 'doughnut', data: { labels: {{ cat_labels | safe }}, datasets: [{ data: {{ cat_values | safe }}, backgroundColor: ['#58a6ff', '#238636', '#f1e05a', '#f85149'], borderWidth: 0 }] }, options: commonOptions });
        new Chart(document.getElementById('lineChart'), { type: 'line', data: { labels: {{ trend_labels | safe }}, datasets: [{ label: '資產', data: {{ trend_values | safe }}, borderColor: '#58a6ff', tension: 0.3, fill: true, backgroundColor: 'rgba(88, 166, 255, 0.1)' }] }, options: { ...commonOptions, scales: { y: { ticks: { color: '#8b949e' } }, x: { ticks: { color: '#8b949e' } } } } });
    </script>
</body>
</html>
"""

# --- 5. 路由與數據處理 ---
@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT target_amount FROM goals WHERE id=1')
    goal_amt = c.fetchone()[0]
    c.execute('SELECT id, name, amount, category, symbol, currency, date FROM assets ORDER BY date ASC')
    raw_data = c.fetchall()
    
    processed_assets, total_val, cat_map = [], 0, {}
    trend_values, trend_labels = [0], ["Start"]

    for item in raw_data:
        aid, name, amt, cat, sym, curr, date = item
        rate = get_ex_rate(curr) if curr != "TWD" else 1
        
        if cat == '股票' and sym:
            try:
                price = yf.Ticker(sym).fast_info.get('last_price', 0)
                display_amt = amt * price
            except: display_amt = 0
        else:
            display_amt = amt * rate
        
        total_val += display_amt
        cat_map[cat] = cat_map.get(cat, 0) + display_amt
        trend_values.append(total_val)
        trend_labels.append(date[5:10])
        processed_assets.append({'id': aid, 'name': name, 'display_amount': display_amt, 'category': cat, 'currency': curr})

    progress = min(100, round((total_val / goal_amt) * 100, 1)) if goal_amt > 0 else 0
    conn.close()
    return render_template_string(HTML_TEMPLATE, assets=processed_assets[::-1], total_val=total_val, goal_amt=goal_amt, progress=progress, cat_labels=list(cat_map.keys()), cat_values=list(cat_map.values()), trend_labels=trend_labels, trend_values=trend_values)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    amt = smart_extract_amt(text)
    conn = sqlite3.connect(db_path)
    
    curr = "TWD"
    for c in ["美金", "USD", "日幣", "JPY", "歐元", "人民幣"]:
        if c in text.upper(): curr = c; break

    if "目標" in text:
        conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
    elif any(w in text for w in ["股", "張"]) or re.search(r'\d{4}', text):
        sym_match = re.search(r'([A-Z0-9\.]+)', text.upper())
        sym = sym_match.group() if sym_match else ""
        if sym.isdigit() and len(sym) >= 4: sym += ".TW"
        shares = amt * 1000 if "張" in text else amt
        conn.execute('INSERT INTO assets (name, amount, category, symbol, currency) VALUES (?, ?, ?, ?, ?)', (text, shares, "股票", sym, "TWD"))
    else:
        cat = "支出" if any(w in text for w in ["付", "花", "買", "支出"]) else "儲蓄"
        if cat == "支出": amt = -abs(amt)
        conn.execute('INSERT INTO assets (name, amount, category, symbol, currency) VALUES (?, ?, ?, ?, ?)', (text, amt, cat, "", curr))
        
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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
