import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 使用 v30 資料庫，徹底避開舊結構衝突
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v30.db')

# --- 1. AI 數字解析邏輯 (修正 10萬變 10元) ---
def smart_extract_amt(text):
    text = text.replace(',', '').strip()
    # 處理「10萬」、「5.5萬」
    wan_match = re.search(r'(\d+\.?\d*)\s*萬', text)
    if wan_match: return float(wan_match.group(1)) * 10000
    # 處理常見國字
    if '十萬' in text: return 100000
    if '百萬' in text: return 1000000
    # 處理純數字
    nums = re.findall(r'-?\d+\.?\d*', text)
    return float(nums[0]) if nums else 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, currency TEXT, symbol TEXT)''')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 3. 仿截圖專業版 HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>資產管理系統</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-size: 0.9rem; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; height: 100%; }
        .nav-tabs .nav-link { color: #8b949e; border: none; }
        .nav-tabs .nav-link.active { color: #58a6ff; background: transparent; border-bottom: 2px solid #58a6ff; }
        .form-control { background: #0d1117; border: 1px solid #30363d; color: white; }
        .btn-primary { background: #238636; border: none; font-weight: bold; width: 100%; }
        .btn-stock { background: #2ea043; border: none; font-weight: bold; width: 100%; }
        .table { color: #c9d1d9; border-color: #30363d; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="row mb-4">
        <div class="col-12">
            <div class="card p-3 text-center">
                <div class="text-muted small">總資產價值 (預估 TWD)</div>
                <h2 class="fw-bold text-white mt-1">${{ "{:,.0f}".format(total_val) }}</h2>
                <div class="progress mt-2" style="height: 6px;"><div class="progress-bar bg-primary" style="width: {{ progress }}%"></div></div>
                <div class="d-flex justify-content-between mt-1 small"><span class="text-muted">達成率 {{ progress }}%</span><span class="text-muted">目標 ${{ "{:,.0f}".format(goal_amt) }}</span></div>
            </div>
        </div>
    </div>

    <div class="row g-3">
        <div class="col-md-5">
            <div class="card p-3">
                <ul class="nav nav-tabs mb-3" id="myTab">
                    <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#general">一般紀錄</a></li>
                    <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#transfer">銀行轉帳</a></li>
                </ul>
                <div class="tab-content">
                    <div class="tab-pane fade show active" id="general">
                        <form action="/process" method="POST">
                            <input type="text" name="user_input" class="form-control mb-2" placeholder="銀行名稱/項目 (例如: 10萬)">
                            <button type="submit" class="btn btn-primary">儲存變動</button>
                        </form>
                    </div>
                </div>
                <hr class="my-4" style="border-color: #30363d">
                <h6 class="text-success mb-3">+ 記錄股票持倉</h6>
                <form action="/process" method="POST">
                    <input type="text" name="stock_input" class="form-control mb-2" placeholder="代號 (如 2330.TW)">
                    <input type="text" name="shares_input" class="form-control mb-2" placeholder="股數 (例如: 1000)">
                    <button type="submit" class="btn btn-stock">更新股票</button>
                </form>
            </div>
        </div>

        <div class="col-md-7">
            <div class="card p-3">
                <h6 class="fw-bold mb-3">資產明細一覽表</h6>
                <table class="table">
                    <thead class="text-muted"><tr><th>名稱/代號</th><th>類型</th><th>現值</th><th>操作</th></tr></thead>
                    <tbody>
                        {% for item in assets %}
                        <tr>
                            <td>{{ item.name }}</td>
                            <td><span class="badge {{ 'bg-success' if item.category == '股票' else 'bg-secondary' }}">{{ item.category }}</span></td>
                            <td class="{{ 'text-success' if item.amount >= 0 else 'text-danger' }}">${{ "{:,.0f}".format(item.amount) }}</td>
                            <td><a href="/delete/{{ item.id }}" class="text-danger text-decoration-none small">移除</a></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT target_amount FROM goals WHERE id=1')
    goal_amt = c.fetchone()[0]
    c.execute('SELECT id, name, amount, category, currency FROM assets ORDER BY id DESC')
    raw_data = c.fetchall()
    
    # 使用固定匯率，防止 502 當機
    rates = {"美金": 32.5, "USD": 32.5, "日幣": 0.21, "JPY": 0.21}
    total_val = 0
    assets_list = []
    
    for item in raw_data:
        aid, name, amt, cat, curr = item
        rate = rates.get(curr, 1.0)
        display_amt = amt * rate
        total_val += display_amt
        assets_list.append({'id': aid, 'name': name, 'amount': display_amt, 'category': cat})
    
    progress = min(100, round((total_val / goal_amt) * 100, 1)) if goal_amt > 0 else 0
    conn.close()
    return render_template_string(HTML_TEMPLATE, assets=assets_list, total_val=total_val, goal_amt=goal_amt, progress=progress)

@app.route('/process', methods=['POST'])
def process():
    conn = sqlite3.connect(db_path)
    # 處理股票輸入
    if 'stock_input' in request.form:
        sym = request.form.get('stock_input', '').upper()
        shares = smart_extract_amt(request.form.get('shares_input', '0'))
        if sym:
            conn.execute('INSERT INTO assets (name, amount, category, symbol, currency) VALUES (?, ?, ?, ?, ?)', (sym, shares, "股票", sym, "TWD"))
    # 處理一般輸入
    else:
        text = request.form.get('user_input', '').strip()
        amt = smart_extract_amt(text)
        curr = "TWD"
        for c in ["美金", "USD", "日幣", "JPY"]:
            if c in text.upper(): curr = c; break
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
