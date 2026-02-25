import os
from flask import Flask, render_template_string, request, redirect, url_for
import yfinance as yf
import sqlite3
import re

app = Flask(__name__)
# 使用 v9 資料庫，確保結構乾淨
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v9.db')

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL)')
    conn.commit()
    conn.close()

init_db()

# --- AI 解析引擎 ---
def smart_parser(text):
    # A. 轉帳
    transfer_match = re.search(r"(.+?)\s*(?:轉|移|轉帳)\s*(?:到|至)?\s*(.+?)\s*(\d+)", text)
    if transfer_match:
        from_b, to_b, amt = transfer_match.groups()
        return "transfer", {"from": from_b, "to": to_b, "amount": float(amt)}
    # B. 股票
    stock_match = re.search(r"(?:買|賣)?\s*([A-Z0-9\.]+)\s*(\d+)\s*(?:股|張)?", text.upper())
    if stock_match:
        symbol, shares = stock_match.groups()
        if "張" in text: shares = float(shares) * 1000
        if symbol.isdigit() and len(symbol) >= 4 and "." not in symbol: symbol += ".TW"
        return "stock", {"symbol": symbol, "shares": float(shares)}
    # C. 現金
    cash_match = re.search(r"(.+?)\s*(-?\d+)", text)
    if cash_match:
        name, amt = cash_match.groups()
        return "cash", {"name": name, "amount": float(amt)}
    return None, None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Gemini AI 智能財富</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .ai-section { background: linear-gradient(135deg, #1e3a8a 0%, #0d1117 100%); padding: 50px 0; border-bottom: 1px solid #30363d; }
        .ai-input-wrapper { background: #0d1117; border: 2px solid #388bfd; border-radius: 50px; padding: 10px 25px; display: flex; box-shadow: 0 0 20px rgba(56, 139, 253, 0.3); }
        .ai-input-wrapper input { background: transparent; border: none; color: white; flex-grow: 1; outline: none; font-size: 1.2rem; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 15px; margin-bottom: 20px; }
        .btn-ai { background: #238636; color: white; border-radius: 30px; border: none; padding: 8px 25px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="ai-section text-center">
        <div class="container">
            <h2 class="fw-bold text-white mb-4">🤖 Gemini AI 智慧助理</h2>
            <div class="row justify-content-center">
                <div class="col-lg-8">
                    <form action="/smart_input" method="POST" class="ai-input-wrapper">
                        <input type="text" name="raw_text" placeholder="輸入範例：買 2330 1張 / 中信轉台新 3000 / 薪水 50000" required>
                        <button type="submit" class="btn btn-ai">執行</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    <div class="container mt-5">
        <div class="row">
            <div class="col-md-4">
                <div class="card p-4 text-center">
                    <h6 class="text-muted">總資產估值 (TWD)</h6>
                    <h2 class="text-primary fw-bold">${{ "{:,.0f}".format(total_cash + total_stock) }}</h2>
                    <hr style="border-color:#333">
                    <div class="d-flex justify-content-between small"><span>現金</span><span>${{ "{:,.0f}".format(total_cash) }}</span></div>
                    <div class="d-flex justify-content-between small"><span>股票</span><span class="text-success">${{ "{:,.0f}".format(total_stock) }}</span></div>
                </div>
            </div>
            <div class="col-md-8">
                <div class="card p-4">
                    <h6 class="fw-bold mb-3">我的資產清單</h6>
                    <table class="table table-dark table-hover">
                        <thead><tr><th>名稱</th><th>分類</th><th>金額/現值</th><th>操作</th></tr></thead>
                        <tbody>
                            {% for c in cash_items %}
                            <tr><td>{{ c[1] }}</td><td><span class="badge bg-secondary">現金</span></td><td>${{ "{:,.0f}".format(c[2]) }}</td><td><a href="/delete/{{ c[0] }}" class="text-danger">刪除</a></td></tr>
                            {% endfor %}
                            {% for s in stocks %}
                            <tr><td>{{ s.symbol }}</td><td><span class="badge bg-success">股票</span></td><td class="text-success">${{ "{:,.0f}".format(s.value) }}</td><td>-</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, amount FROM cash ORDER BY id DESC')
        cash_items = cursor.fetchall()
        cursor.execute('SELECT SUM(amount) FROM cash')
        res_cash = cursor.fetchone()
        total_cash = float(res_cash[0]) if res_cash and res_cash[0] is not None else 0.0
        
        cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
        stocks_raw = cursor.fetchall()
        stock_list, total_stock = [], 0.0
        
        for symbol, shares in stocks_raw:
            if shares > 0:
                try:
                    # 加入 timeout 與防錯
                    ticker = yf.Ticker(symbol)
                    price = ticker.fast_info.get('last_price')
                    if price is None or price == 0:
                        price = 0
                    val = shares * price
                    total_stock += val
                    stock_list.append({'symbol': symbol, 'value': val})
                except:
                    stock_list.append({'symbol': symbol, 'value': 0})
        conn.close()
        return render_template_string(HTML_TEMPLATE, total_cash=total_cash, total_stock=total_stock, cash_items=cash_items, stocks=stock_list)
    except Exception as e:
        return f"系統初始化中...請重新整理。({str(e)})"

@app.route('/smart_input', methods=['POST'])
def smart_input():
    raw_text = request.form.get('raw_text', '')
    cat, data = smart_parser(raw_text)
    if cat:
        conn = sqlite3.connect(db_path)
        if cat == "transfer":
            conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (f"轉出: {data['from']}", -data['amount']))
            conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (f"轉入: {data['to']}", data['amount']))
        elif cat == "stock":
            conn.execute('INSERT INTO trades (symbol, shares) VALUES (?, ?)', (data['symbol'], data['shares']))
        elif cat == "cash":
            conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (data['name'], data['amount']))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect(db_path)
    conn.execute('DELETE FROM cash WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
