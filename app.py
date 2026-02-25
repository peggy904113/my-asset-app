import os
from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3

# --- 路徑設定：確保在雲端能找到檔案 ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')
db_path = os.path.join(base_dir, 'assets.db')

app = Flask(__name__, template_folder=template_dir)

# --- 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 建立現金表
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL)')
    # 建立股票交易表
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, price REAL, date TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 計算現金總額
        cursor.execute('SELECT SUM(amount) FROM cash')
        row_cash = cursor.fetchone()
        total_cash = float(row_cash[0]) if row_cash and row_cash[0] is not None else 0.0
        
        # 2. 抓取持倉股票彙整
        cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
        stocks_data = cursor.fetchall()
        
        # 3. 抓取最近 10 筆交易紀錄
        cursor.execute('SELECT id, symbol, shares, price, date FROM trades ORDER BY date DESC LIMIT 10')
        history = cursor.fetchall()
        
        stock_list = []
        total_stock_value = 0.0
        
        # 處理每一支股票的即時現值
        for symbol, shares in stocks_data:
            if shares and shares > 0:
                try:
                    ticker = yf.Ticker(symbol)
                    # 抓取最新股價 (fast_info 較快)
                    current_price = float(ticker.fast_info.get('last_price', 0))
                    value = shares * current_price
                    total_stock_value += value
                    stock_list.append({
                        'symbol': symbol,
                        'shares': shares,
                        'price': f"{current_price:.2f}",
                        'value': f"{value:.2f}"
                    })
                except:
                    # 如果抓不到股價，給予預設值
                    stock_list.append({
                        'symbol': symbol,
                        'shares': shares,
                        'price': "N/A",
                        'value': "0.00"
                    })
        
        conn.close()
        
        # 將結果傳給 HTML
        return render_template('index.html', 
                               total_cash=f"{total_cash:,.2f}", 
                               total_stock_value=f"{total_stock_value:,.2f}", 
                               stocks=stock_list, 
                               history=history)
    except Exception as e:
        return f"程式執行時發生錯誤，請聯絡 AI 助手。錯誤訊息: {str(e)}"

@app.route('/add_cash', methods=['POST'])
def add_cash():
    bank_name = request.form.get('bank_name')
    amount = request.form.get('amount')
    if bank_name and amount:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (bank_name, float(amount)))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/add_trade', methods=['POST'])
def add_trade():
    symbol = request.form.get('symbol').upper() # 強制大寫，如 2330.TW
    shares = request.form.get('shares')
    price = request.form.get('price')
    date = request.form.get('date')
    if symbol and shares:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO trades (symbol, shares, price, date) VALUES (?, ?, ?, ?)', 
                     (symbol, float(shares), float(price) if price else 0, date))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/delete_trade/<int:id>')
def delete_trade(id):
    conn = sqlite3.connect(db_path)
    conn.execute('DELETE FROM trades WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
