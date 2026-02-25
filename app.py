@app.route('/')
def index():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 抓取現金
        cursor.execute('SELECT SUM(amount) FROM cash')
        row = cursor.fetchone()
        total_cash = float(row[0]) if row and row[0] is not None else 0.0
        
        # 抓取股票
        cursor.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
        stocks = cursor.fetchall()
        
        # 抓取紀錄
        cursor.execute('SELECT id, symbol, shares, price, date FROM trades ORDER BY date DESC LIMIT 10')
        history = cursor.fetchall()
        
        stock_list = []
        total_stock_value = 0.0
        
        for symbol, shares in stocks:
            if shares and shares > 0:
                try:
                    ticker = yf.Ticker(symbol)
                    # 使用更穩定的方式抓價格
                    info = ticker.fast_info
                    price = float(info.get('last_price', 0))
                    value = shares * price
                    total_stock_value += value
                    stock_list.append({
                        'symbol': symbol, 
                        'shares': shares, 
                        'price': f"{price:.2f}", 
                        'value': f"{value:.2f}"
                    })
                except:
                    stock_list.append({
                        'symbol': symbol, 
                        'shares': shares, 
                        'price': "0.00", 
                        'value': "0.00"
                    })
        
        conn.close()
        
        # 確保傳給網頁的數字都有預設值
        return render_template('index.html', 
                               total_cash=f"{total_cash:.2f}", 
                               total_stock_value=f"{total_stock_value:.2f}", 
                               stocks=stock_list, 
                               history=history)
    except Exception as e:
        return f"這是一點小微調，請重新整理網頁試試: {str(e)}"
