from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    # 建立現金表
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL)')
    # 建立股票交易表 (包含日期)
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, price REAL, date TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    
    # 算現金總額 (改用 SQL 直接加總，不透過 pandas)
    cursor.execute('SELECT SUM(amount) FROM cash')
    total_cash = cursor.fetchone()[0] or 0
    
    # 抓取所有股票持倉
    cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
    stocks = cursor.fetchall()
    
    # 抓取流水帳紀錄 (顯示最近 10 筆)
    cursor.execute('SELECT id, symbol, shares, price, date FROM trades ORDER BY date DESC LIMIT 10')
    history = cursor.fetchall()
    
    stock_list = []
    total_stock_value = 0
    
    for symbol, shares in stocks:
        if shares > 0:
            try:
                # 抓取即時股價
                ticker = yf.Ticker(symbol)
                price = ticker.fast_info['last_price']
                value = shares * price
                total_stock_value += value
                stock_list.append({'symbol': symbol, 'shares': shares, 'price': round(price, 2), 'value': round(value, 2)})
            except:
                stock_list.append({'symbol': symbol, 'shares': shares, 'price': "N/A", 'value': 0})

    conn.close()
    return render_template('index.html', total_cash=total_cash, total_stock_value=round(total_stock_value, 2), stocks=stock_list, history=history)

@app.route('/add_cash', methods=['POST'])
def add_cash():
    bank_name = request.form.get('bank_name')
    amount = request.form.get('amount')
    conn = sqlite3.connect('assets.db')
    conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (bank_name, amount))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_trade', methods=['POST'])
def add_trade():
    symbol = request.form.get('symbol')
    shares = request.form.get('shares')
    price = request.form.get('price')
    date = request.form.get('date')
    conn = sqlite3.connect('assets.db')
    conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, ?, ?)', (symbol, shares, price, date))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_trade/<int:id>')
def delete_trade(id):
    conn = sqlite3.connect('assets.db')
    conn.execute('DELETE FROM trades WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
