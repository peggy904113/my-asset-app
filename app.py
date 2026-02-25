import os
from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3

base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
db_path = os.path.join(base_dir, 'assets.db')

app = Flask(__name__, template_folder=template_dir)

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, price REAL, date TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 現金加總
    cursor.execute('SELECT SUM(amount) FROM cash')
    res_cash = cursor.fetchone()
    total_cash = float(res_cash[0]) if res_cash and res_cash[0] is not None else 0.0
    
    # 股票持倉
    cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
    stocks_raw = cursor.fetchall()
    
    # 歷史紀錄
    cursor.execute('SELECT id, symbol, shares, price, date FROM trades ORDER BY date DESC LIMIT 10')
    history = cursor.fetchall()
    
    stock_list = []
    total_stock_value = 0.0
    
    for symbol, shares in stocks_raw:
        if shares > 0:
            try:
                ticker = yf.Ticker(symbol)
                price = float(ticker.fast_info.get('last_price', 0))
                value = shares * price
                total_stock_value += value
                stock_list.append({
                    'symbol': symbol,
                    'shares': shares,
                    'price': round(price, 2),
                    'value': round(value, 2)
                })
            except:
                stock_list.append({'symbol': symbol, 'shares': shares, 'price': 0.0, 'value': 0.0})

    conn.close()
    
    # 重要：這裡傳出的變數名稱要跟 HTML 裡面的一模一樣
    return render_template('index.html', 
                           total_cash=total_cash, 
                           total_stock_value=total_stock_value, 
                           stocks=stock_list, 
                           history=history)

@app.route('/add_cash', methods=['POST'])
def add_cash():
    name = request.form.get('bank_name')
    amt = request.form.get('amount')
    if name and amt:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (name, float(amt)))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/add_trade', methods=['POST'])
def add_trade():
    sym = request.form.get('symbol').upper()
    shs = request.form.get('shares')
    pri = request.form.get('price')
    dat = request.form.get('date')
    if sym and shs:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, ?, ?)', 
                     (sym, float(shs), float(pri) if pri else 0, dat))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
