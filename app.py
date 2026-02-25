import os
import sqlite3
import re
import yfinance as yf
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v10.db')

# --- 1. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_name TEXT, target_amount REAL)')
    cursor.execute('INSERT OR IGNORE INTO goals (id, target_name, target_amount) VALUES (1, "百萬大關", 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 2. HTML 模板 (新增最近紀錄與刪除按鈕) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini AI 財富助理 v11</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .ai-card { background: #161b22; border: 1px solid #30363d; border-radius: 15px; padding: 20px; margin-bottom: 20px; }
        .progress { height: 30px; border-radius: 15px; background-color: #30363d; }
        .btn-gemini { background: linear-gradient(90deg, #4f46e5, #06b6d4); color: white; border: none; border-radius: 20px; }
        .table-dark { --bs-table-bg: #161b22; }
        .delete-btn { color: #f85149; text-decoration: none; font-size: 0.8rem; }
        .delete-btn:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container py-5">
        <h2 class="text-center mb-4 text-white">🤖 Gemini AI 財富教練</h2>

        <div class="ai-card border-primary">
            <h6 class="text-primary">助理回應：</h6>
            <p class="mb-0">{{ ai_feedback | safe }}</p>
        </div>

        <div class="ai-card shadow">
            <form action="/smart_process" method="POST">
                <label class="mb-2">請輸入指令（支援多行或一段話包含多個動作）：</label>
                <textarea name="user_input" class="form-control bg-dark text-white border-secondary mb-3" rows="3" 
                          placeholder="範例：薪水 60000 繳卡費 118000 買 2330 1張"></textarea>
                <button class="btn btn-gemini w-100" type="submit">執行批次指令</button>
            </form>
        </div>

        <div class="row">
            <div class="col-md-7">
                <div class="ai-card">
                    <h5>🎯 {{ goal_name }} 進度</h5>
                    <h2 class="fw-bold text-white mt-3">${{ "{:,.0f}".format(total_val) }} / ${{ "{:,.0f}".format(goal_amt) }}</h2>
                    <div class="progress mt-3">
                        <div class="progress-bar progress-bar-striped progress-bar-animated bg-success" 
                             style="width: {{ progress }}%">{{ progress }}%</div>
                    </div>
                </div>

                <div class="ai-card">
                    <h5>📝 最近變動紀錄</h5>
                    <table class="table table-dark table-sm mt-3">
                        <thead><tr><th>內容</th><th>金額/股數</th><th>操作</th></tr></thead>
                        <tbody>
                            {% for item in history %}
                            <tr>
                                <td>{{ item.name }}</td>
                                <td class="{{ 'text-danger' if item.amt < 0 else 'text-success' }}">${{ "{:,.0f}".format(item.amt) }}</td>
                                <td><a href="/delete/{{ item.type }}/{{ item.id }}" class="delete-btn" onclick="return confirm('確定刪除？')">刪除</a></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="col-md-5">
                <div class="ai-card text-center">
                    <h5>📊 資產佔比</h5>
                    <canvas id="assetChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('assetChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['現金', '股票', '其他'],
                datasets: [{
                    data: [{{ total_cash }}, {{ total_stock }}, 100000],
                    backgroundColor: ['#388bfd', '#238636', '#f1e05a'],
                    borderWidth: 0
                }]
            },
            options: { plugins: { legend: { labels: { color: '#c9d1d9' } } } }
        });
    </script>
</body>
</html>
"""

# --- 3. 核心處理邏輯 ---

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 計算現金與股票 (同前)
    c.execute('SELECT SUM(amount) FROM cash')
    total_cash = c.fetchone()[0] or 0.0
    c.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
    stocks_raw = c.fetchall()
    total_stock = 0.0
    for sym, sh in stocks_raw:
        if sh > 0:
            try:
                price = yf.Ticker(sym).fast_info.get('last_price') or 0
                total_stock += (sh * price)
            except: pass

    # 獲取紀錄用於刪除列表 (顯示最近 5 筆)
    history = []
    c.execute('SELECT id, name, amount FROM cash ORDER BY id DESC LIMIT 5')
    for r in c.fetchall(): history.append({'type': 'cash', 'id': r[0], 'name': r[1], 'amt': r[2]})
    c.execute('SELECT id, symbol, shares FROM trades ORDER BY id DESC LIMIT 5')
    for r in c.fetchall(): history.append({'type': 'trade', 'id': r[0], 'name': r[1], 'amt': r[2]})

    # 目標
    c.execute('SELECT target_name, target_amount FROM goals WHERE id=1')
    g_name, g_amt = c.fetchone()
    total_val = total_cash + total_stock + 100000
    progress = round((total_val / g_amt) * 100, 1)
    
    ai_feedback = request.args.get('feedback', '準備好挑戰百萬了嗎？一次輸入多個指令也沒問題！')
    conn.close()
    return render_template_string(HTML_TEMPLATE, total_cash=total_cash, total_stock=total_stock, total_val=total_val, goal_name=g_name, goal_amt=g_amt, progress=progress, history=history, ai_feedback=ai_feedback)

@app.route('/smart_process', methods=['POST'])
def smart_process():
    raw_text = request.form.get('user_input', '').strip()
    # 支援用逗號、句號或換行拆分指令
    commands = re.split(r'[，。,\n\s]+', raw_text)
    conn = sqlite3.connect(db_path)
    success_count = 0
    
    for cmd in commands:
        if not cmd: continue
        numbers = re.findall(r'\d+', cmd)
        if not numbers: continue
        amt = float(numbers[0])
        
        if "目標" in cmd:
            conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
            success_count += 1
        elif "買" in cmd or "賣" in cmd:
            code = re.search(r'\d{4}', cmd)
            if code:
                sym = code.group() + ".TW"
                shares = amt * 1000 if "張" in cmd else amt
                if "賣" in cmd: shares *= -1
                conn.execute('INSERT INTO trades (symbol, shares) VALUES (?, ?)', (sym, shares))
                success_count += 1
        else: # 現金
            is_neg = any(w in cmd for w in ["支出", "卡費", "付", "花", "扣"])
            val = amt * (-1 if is_neg else 1)
            conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (cmd, val))
            success_count += 1
            
    conn.commit()
    conn.close()
    return redirect(url_for('index', feedback=f"✅ 成功處理 {success_count} 項指令！"))

@app.route('/delete/<type>/<int:id>')
def delete_item(type, id):
    conn = sqlite3.connect(db_path)
    table = "cash" if type == "cash" else "trades"
    conn.execute(f'DELETE FROM {table} WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', feedback="🗑️ 紀錄已刪除。"))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
