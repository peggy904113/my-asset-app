import os
from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3

# --- 核心路徑修正 ---
# 這裡確保程式能精準定位到 templates 資料夾
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
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT SUM(amount) FROM cash')
        total_cash = cursor.fetchone()[0] or 0
        cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
        stocks = cursor.fetchall()
        cursor.execute('SELECT id, symbol, shares, price, date FROM trades ORDER BY date DESC LIMIT 10')
        history = cursor.fetchall()
        
        stock_list = []
        total_stock_value = 0
        for symbol, shares in stocks:
            if shares > 0:
                try:
                    ticker = yf.Ticker(symbol)
                    price = ticker.fast_info['last_price']
                    value = shares * price
                    total_stock_value += value
                    stock_list.append({'symbol': symbol, 'shares': shares, 'price': round(price, 2), 'value': round(value, 2)})
                except:
                    stock_list.append({'symbol': symbol, 'shares': shares, 'price': "N/A", 'value': 0})
        conn.close()
        return render_template('index.html', total_cash=total_cash, total_stock_value=round(total_stock_value, 2), stocks=stock_list, history=history)
    except Exception as e:
        return f"資料庫或檔案讀取錯誤: {str(e)}" # 如果還是錯，這行會告訴我們原因

@app.route('/add_cash', methods=['POST'])
def add_cash():
    bank_name = request.form.get('bank_name')
    amount = request.form.get('amount')
    conn = sqlite3.connect(db_path)
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
    conn = sqlite3.connect(db_path)
    conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, ?, ?)', (symbol, shares, price, date))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Render 會自動給予 PORT，這行能增加相容性
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
