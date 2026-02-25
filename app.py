import os
from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3
import re

base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
# 使用 v7 版本資料庫以確保全新結構
db_path = os.path.join(base_dir, 'assets_v7.db')

app = Flask(__name__, template_folder=template_dir)

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, currency TEXT DEFAULT "TWD")')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, price REAL, date TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- AI 智慧解析引擎 ---
def smart_parser(text):
    # A. 偵測轉帳 (範例：中信轉台新 5000)
    transfer_match = re.search(r"(.+?)\s*(?:轉|移|轉帳)\s*(?:到|至)?\s*(.+?)\s*(\d+)", text)
    if transfer_match:
        from_b, to_b, amt = transfer_match.groups()
        return "transfer", {"from": from_b, "to": to_b, "amount": float(amt)}

    # B. 偵測股票 (範例：買 2330 1張 / AAPL 10股)
    stock_match = re.search(r"(?:買|賣)?\s*([A-Z0-9\.]+)\s*(\d+)\s*(?:股|張)?", text.upper())
    if stock_match:
        symbol, shares = stock_match.groups()
        if "張" in text: 
            shares = float(shares) * 1000
        # 台灣股票自動補 .TW
        if symbol.isdigit() and len(symbol) >= 4:
            symbol += ".TW"
        return "stock", {"symbol": symbol, "shares": float(shares)}

    # C. 一般現金收支 (範例：午餐 -200 / 薪水 50000)
    cash_match = re.search(r"(.+?)\s*(-?\d+)", text)
    if cash_match:
        name, amt = cash_match.groups()
        return "cash", {"name": name, "amount": float(amt)}
    
    return None, None

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
        stock_list = []
        total_stock_value = 0.0
        
        for symbol, shares in stocks_raw:
            if shares > 0:
                try:
                    ticker = yf.Ticker(symbol)
                    price = float(ticker.fast_info.get('last_price', 0))
                    val = shares * price
                    total_stock_value += val
                    stock_list.append({'symbol': symbol, 'shares': shares, 'price': round(price, 2), 'value': round(val, 2)})
                except:
                    stock_list.append({'symbol': symbol, 'shares': shares, 'price': 0, 'value': 0})
        conn.close()
        
        return render_template('index.html', 
                               total_cash=total_cash, 
                               total_stock_value=total_stock_value, 
                               cash_items=cash_items, 
                               stocks=stock_list)
    except Exception as e:
        return f"AI 助理啟動中，請重新整理... (Error: {str(e)})"

@app.route('/smart_input', methods=['POST'])
def smart_input():
    raw_text = request.form.get('raw_text', '')
    category, data = smart_parser(raw_text)
    
    conn = sqlite3.connect(db_path)
    if category == "transfer":
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (f"轉出: {data['from']}", -data['amount']))
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (f"轉入: {data['to']}", data['amount']))
    elif category == "stock":
        conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, 0, "")', (data['symbol'], data['shares']))
    elif category == "cash":
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (data['name'], data['amount']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_cash/<int:id>')
def delete_cash(id):
    conn = sqlite3.connect(db_path)
    conn.execute('DELETE FROM cash WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
