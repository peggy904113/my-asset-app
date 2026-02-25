import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 跳轉到 v25，保證資料庫全新乾淨
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v25.db')

# --- 1. 強化版數字解析 ---
def smart_extract_amt(text):
    text = text.replace(',', '').strip()
    # 處理「10萬」、「5.5萬」
    wan_match = re.search(r'(\d+\.?\d*)\s*萬', text)
    if wan_match: return float(wan_match.group(1)) * 10000
    
    # 處理「十萬」等大額國字
    if '十萬' in text: return 100000
    if '百萬' in text: return 1000000
    
    nums = re.findall(r'-?\d+\.?\d*', text)
    return float(nums[0]) if nums else 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, currency TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 3. 簡約穩定版介面 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini AI 財富大腦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 15px; margin-top: 15px; }
        .ai-input { background: #0d1117; border: 2px solid #388bfd; border-radius: 25px; color: white; padding: 10px 20px; width: 100%; }
    </style>
</head>
<body>
    <div class="container py-4">
        <h5 class="text-center text-white mb-4">🤖 Gemini 智慧財富助理</h5>
        <form action="/process" method="POST" class="mb-4">
            <input type="text" name="user_input" class="ai-input" placeholder="試試：10萬、美金 1000..." required autofocus>
        </form>

        <div class="card p-3 text-center">
            <small class="text-muted">預估總資產 (TWD)</small>
            <h2 class="text-white fw-bold">${{ "{:,.0f}".format(total_val) }}</h2>
            <div class="progress mt-2" style="height: 8px;">
                <div class="progress-bar bg-info" style="width: {{ progress }}%"></div>
            </div>
            <small class="text-muted mt-2">目標：${{ "{:,.0f}".format(goal_amt) }} ({{ progress }}%)</small>
        </div>

        <div class="card p-3">
            <h6 class="small fw-bold mb-3">最近紀錄</h6>
            {% for item in assets %}
            <div class="d-flex justify-content-between border-bottom border-secondary py-2 small">
                <div><div>{{ item.name }}</div><span class="badge bg-dark text-info">{{ item.currency }}</span></div>
                <div class="text-end">
                    <div class="fw-bold {{ 'text-success' if item.amount >= 0 else 'text-danger' }}">${{ "{:,.0f}".format(item.amount) }}</div>
                    <a href="/delete/{{ item.id }}" class="text-danger" style="text-decoration:none">刪除</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT target_amount FROM goals WHERE id=1')
    goal_amt = c.fetchone()[0]
    
    c.execute('SELECT id, name, amount, currency FROM assets ORDER BY id DESC')
    raw_data = c.fetchall()
    
    # 預設固定匯率，保證網頁秒開不當機
    rates = {"美金": 32.5, "USD": 32.5, "日幣": 0.21, "JPY": 0.21}
    
    assets_list = []
    total_val = 0
    for item in raw_data:
        aid, name, amt, curr = item
        rate = rates.get(curr, 1.0)
        display_amt = amt * rate
        total_val += display_amt
        assets_list.append({'id': aid, 'name': name, 'amount': display_amt, 'currency': curr})
    
    progress = min(100, round((total_val / goal_amt) * 100, 1)) if goal_amt > 0 else 0
    conn.close()
    return render_template_string(HTML_TEMPLATE, assets=assets_list, total_val=total_val, goal_amt=goal_amt, progress=progress)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    amt = smart_extract_amt(text)
    conn = sqlite3.connect(db_path)
    
    curr = "TWD"
    for c in ["美金", "USD", "日幣", "JPY"]:
        if c in text.upper(): curr = c; break

    if "目標" in text:
        conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
    else:
        cat = "支出" if any(w in text for w in ["付", "花", "買", "支出"]) else "儲蓄"
        if cat == "支出": amt = -abs(amt)
        conn.execute('INSERT INTO assets (name, amount, category, currency) VALUES (?, ?, ?, ?)', (text, amt, cat, curr))
    
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
