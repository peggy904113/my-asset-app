from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import sqlite3
import pandas as pd

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY, amount REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, symbol TEXT, shares INTEGER, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

init_db()

def get_ai_advice(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo")
        if df.empty: return "資料分析中..."
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1+rs)).iloc[-1]
        if rsi < 30: return f"🔥 RSI={int(rsi)} 低於30(超跌)，適合分批買進。"
        if rsi > 70: return f"⚠️ RSI={int(rsi)} 高於70(過熱)，建議先觀望。"
        return "✅ 趨勢穩定，適合長期持有。"
    except: return "暫無建議"

@app.route('/')
def index():
    conn = sqlite3.connect('assets.db')
    # 讀取資料
    cash_df = pd.read_sql_query("SELECT * FROM cash", conn)
    trades_df = pd.read_sql_query("SELECT * FROM trades ORDER BY date DESC", conn)
    
    total_cash = cash_df['amount'].sum()
    summary = []
    total_stock_value = 0
    
    if not trades_df.empty:
        symbols = trades_df['symbol'].unique()
        for s in symbols:
            s_trades = trades_df[trades_df['symbol'] == s]
            total_shares = s_trades['shares'].sum()
            if total_shares <= 0: continue
            
            # 平均成本計算 (只計買入部分的加權，這是較準確的做法)
            buy_trades = s_trades[s_trades['shares'] > 0]
            avg_cost = (buy_trades['shares'] * buy_trades['price']).sum() / buy_trades['shares'].sum()
            
            price = yf.Ticker(s).fast_info['last_price']
            val = price * total_shares
            profit_pct = ((price - avg_cost) / avg_cost) * 100
            
            total_stock_value += val
            summary.append({
                'symbol': s, 'shares': total_shares, 'cost': round(avg_cost, 2),
                'price': round(price, 2), 'profit': round(profit_pct, 2),
                'advice': get_ai_advice(s)
            })
    
    # 轉換歷史明細為字典格式供前端顯示
    history = trades_df.to_dict(orient='records')
    conn.close()
    return render_template('index.html', cash=int(total_cash), stocks=summary, total=int(total_cash + total_stock_value), history=history)

@app.route('/add_cash', methods=['POST'])
def add_cash():
    bank_name = request.form.get('bank_name') # 接收銀行名稱
    amount = request.form.get('amount')
    conn = sqlite3.connect('assets.db')
    # 我們把銀行名稱存在 name 欄位
    conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (bank_name, amount))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_stock', methods=['POST'])
def add_stock():
    symbol = request.form.get('symbol').upper()
    shares = int(request.form.get('shares'))
    price = float(request.form.get('price'))
    conn = sqlite3.connect('assets.db')
    conn.execute('INSERT INTO trades (symbol, shares, price) VALUES (?, ?, ?)', (symbol, shares, price))
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