import os
import sqlite3
import yfinance as yf
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v10.db')

# --- 資料庫初始化 (新增目標表) ---
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, category TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, cost REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_name TEXT, target_amount REAL)')
    # 初始化一個百萬目標
    cursor.execute('INSERT OR IGNORE INTO goals (id, target_name, target_amount) VALUES (1, "百萬大關", 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 核心 UI 模板 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini 財富助理</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .ai-card { background: linear-gradient(145deg, #1c2128, #0d1117); border: 1px solid #30363d; border-radius: 15px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
        .progress { height: 25px; border-radius: 12px; background-color: #30363d; }
        .btn-gemini { background: linear-gradient(90deg, #4f46e5, #06b6d4); color: white; border: none; border-radius: 20px; font-weight: bold; }
        .chat-box { height: 150px; overflow-y: auto; background: #161b22; border-radius: 10px; padding: 15px; border-left: 4px solid #58a6ff; }
        .stock-up { color: #39d353; } .stock-down { color: #f85149; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark mb-4">
        <div class="container">
            <span class="navbar-brand mb-0 h1">🤖 Gemini AI 財富教練</span>
        </div>
    </nav>

    <div class="container">
        <div class="row mb-4">
            <div class="col-12">
                <div class="ai-card p-4">
                    <h5 class="mb-3">💬 助理對話記錄</h5>
                    <div class="chat-box mb-3" id="chatHistory">
                        {{ ai_feedback | safe }}
                    </div>
                    <form action="/smart_process" method="POST" class="input-group">
                        <input type="text" name="user_input" class="form-control bg-dark text-white border-secondary" 
                               placeholder="輸入：買入 2330 1張 / 信用卡支出 118646 / 設定目標 100萬">
                        <button class="btn btn-gemini px-4" type="submit">發送指令</button>
                    </form>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-md-6">
                <div class="ai-card p-4 h-100">
                    <h5>🎯 {{ goal_name }} 進度</h5>
                    <h2 class="fw-bold text-primary mt-3">${{ "{:,.0f}".format(total_val) }} / ${{ "{:,.0f}".format(goal_amt) }}</h2>
                    <div class="progress mt-4">
                        <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" 
                             style="width: {{ progress }}%">{{ progress }}%</div>
                    </div>
                    <p class="mt-3 text-muted">💡 離職倒數中，加油！再漲 {{ 100 - progress }}% 就達標了。</p>
                </div>
            </div>
            <div class="col-md-6">
                <div class="ai-card p-4 h-100 text-center">
                    <h5>📊 資產佔比</h5>
                    <canvas id="assetChart"></canvas>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <div class="ai-card p-4 border-warning">
                    <h5 class="text-warning">🔔 助理買賣分析</h5>
                    <div class="mt-2">
                        {% for advice in trade_advice %}
                            <div class="p-2 border-bottom border-secondary">{{ advice | safe }}</div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('assetChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['現金', '股票', '黃金/其他'],
                datasets: [{
                    data: [{{ total_cash }}, {{ total_stock }}, 100000],
                    backgroundColor: ['#58a6ff', '#39d353', '#f1e05a'],
                    borderWidth: 0
                }]
            },
            options: { plugins: { legend: { labels: { color: '#c9d1d9' } } } }
        });
    </script>
</body>
</html>
"""

# --- 路由邏輯 ---
@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    # 抓取現金
    c = conn.cursor()
    c.execute('SELECT SUM(amount) FROM cash')
    total_cash = c.fetchone()[0] or 0.0
    
    # 抓取股票並分析建議
    c.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
    stocks_raw = c.fetchall()
    total_stock = 0.0
    trade_advice = []
    
    for sym, sh in stocks_raw:
        if sh > 0:
            ticker = yf.Ticker(sym)
            price = ticker.fast_info.get('last_price') or 0
            val = sh * price
            total_stock += val
            # 簡單分析建議 (你可以根據需求修改)
            if sym == "2449.TW": # 京元電
                 trade_advice.append(f"📈 <b>京元電子</b> 獲利豐厚！目前總值 ${val:,.0f}，若要湊百萬可考慮分批了結。")
            if sym == "2330.TW":
                 trade_advice.append(f"💪 <b>台積電</b> 是你的核心，目前穩定貢獻 ${val:,.0f}，建議續抱。")

    # 抓取目標
    c.execute('SELECT target_name, target_amount FROM goals WHERE id=1')
    g_name, g_amt = c.fetchone()
    
    total_val = total_cash + total_stock + 100000 # 加上你的郵局十萬
    progress = round((total_val / g_amt) * 100, 1)
    
    ai_feedback = request.args.get('feedback', '歡迎回來！今天想怎麼調整資產？')
    
    conn.close()
    return render_template_string(HTML_TEMPLATE, total_cash=total_cash, total_stock=total_stock, 
                                  total_val=total_val, goal_name=g_name, goal_amt=g_amt, 
                                  progress=progress, trade_advice=trade_advice, ai_feedback=ai_feedback)

@app.route('/smart_process', methods=['POST'])
def smart_process():
    text = request.form.get('user_input', '').strip()
    conn = sqlite3.connect(db_path)
    feedback = "我收到了！"
    
    # 這裡未來可以串接真實 Gemini API 做語意分析
    # 目前先用進階規則模擬 AI 歸類
    if "目標" in text:
        new_amt = "".join(filter(str.isdigit, text))
        if new_amt:
            conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (float(new_amt),))
            feedback = f"目標已更新為 {new_amt} 元！加油，我們一起達成。"
    elif "買" in text or "賣" in text:
        # 簡單解析：買 2330 1000
        parts = text.split()
        if len(parts) >= 3:
            sym = parts[1] + ".TW" if "." not in parts[1] else parts[1]
            sh = float(parts[2]) * (-1 if "賣" in text else 1)
            conn.execute('INSERT INTO trades (symbol, shares) VALUES (?, ?)', (sym.upper(), sh))
            feedback = f"已記錄股票交易：{sym} {abs(sh)} 股。"
    elif "支出" in text or "卡費" in text or "薪水" in text:
        amt = "".join(filter(str.isdigit, text))
        if amt:
            val = float(amt) * (-1 if "支出" in text or "卡費" in text else 1)
            conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (text, val))
            feedback = f"已記錄金額：{val} 元。"
            
    conn.commit()
    conn.close()
    return redirect(url_for('index', feedback=feedback))

if __name__ == '__main__':
    app.run(debug=True)
