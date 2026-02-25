import os
from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3

base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
# 這裡一定要改名為 assets_v4.db
db_path = os.path.join(base_dir, 'assets_v4.db')

app = Flask(__name__, template_folder=template_dir)

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 現金表：包含名稱、金額、幣別
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, currency TEXT DEFAULT "TWD")')
    # 股票表
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, price REAL, date TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 抓取現金明細清單 (解決你想看哪家銀行多少錢的需求)
    cursor.execute('SELECT id, name, amount, currency FROM cash ORDER BY id DESC')
    cash_items = cursor.fetchall()
    
    # 2. 計算現金總額
    cursor.execute('SELECT SUM(amount) FROM cash')
    res_cash = cursor.fetchone()
    total_cash = float(res_cash[0]) if res_cash and res_cash[0] is not None else 0.0
    
    # 3. 股票持倉彙整
    cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
    stocks_raw = cursor.fetchall()
    stock_list = []
    total_stock_value = 0.0
    
    for symbol, shares in stocks_raw:
        if shares > 0:
            try:
                ticker = yf.Ticker(symbol)
                price = float(ticker.fast_info.get('last_price', 0))
                value = shares * price
                total_stock_value += value
                stock_list.append({'symbol': symbol, 'shares': shares, 'price': round(price, 2), 'value': round(value, 2)})
            except:
                stock_list.append({'symbol': symbol, 'shares': shares, 'price': 0.0, 'value': 0.0})

    conn.close()
    return render_template('index.html', 
                           total_cash=f"{total_cash:,.2f}", 
                           total_stock_value=f"{total_stock_value:,.2f}", 
                           cash_items=cash_items, 
                           stocks=stock_list)

@app.route('/add_cash', methods=['POST'])
def add_cash():
    name = request.form.get('bank_name')
    amt = request.form.get('amount')
    curr = request.form.get('currency', 'TWD')
    if name and amt:
        conn = sqlite3.connect(db_path)
        # 這裡支援輸入負數 (支出/卡費)
        conn.execute('INSERT INTO cash (name, amount, currency) VALUES (?, ?, ?)', (name, float(amt), curr))
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

@app.route('/add_trade', methods=['POST'])
def add_trade():
    sym = request.form.get('symbol', '').upper()
    shs = request.form.get('shares')
    if sym and shs:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, ?, ?)', 
                     (sym, float(shs), 0, ""))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
