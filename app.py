import os
from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3

base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
db_path = os.path.join(base_dir, 'assets_v4.db')

app = Flask(__name__, template_folder=template_dir)

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, currency TEXT DEFAULT "TWD")')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, price REAL, date TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, amount, currency FROM cash ORDER BY id DESC')
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
    return render_template('index.html', total_cash=total_cash, total_stock_value=total_stock_value, cash_items=cash_items, stocks=stock_list)

# 新增/編輯現金
@app.route('/save_cash', methods=['POST'])
def save_cash():
    item_id = request.form.get('id')
    name = request.form.get('bank_name')
    amt = request.form.get('amount')
    conn = sqlite3.connect(db_path)
    if item_id: # 如果有 ID 代表是編輯
        conn.execute('UPDATE cash SET name=?, amount=? WHERE id=?', (name, float(amt), item_id))
    else: # 否則就是新增
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (name, float(amt)))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# 轉帳功能
@app.route('/transfer', methods=['POST'])
def transfer():
    from_bank = request.form.get('from_bank')
    to_bank = request.form.get('to_bank')
    amt = float(request.form.get('amount', 0))
    if from_bank and to_bank and amt > 0:
        conn = sqlite3.connect(db_path)
        # 轉出紀錄 (負數)
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (f"轉帳至 {to_bank}", -amt))
        # 轉入紀錄 (正數)
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (f"來自 {from_bank} 轉帳", amt))
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
        conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, 0, "")', (sym, float(shs)))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
