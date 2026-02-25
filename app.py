import os
import sqlite3
import re
import yfinance as yf
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 資料庫路徑
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v10.db')

# --- 1. 資料庫與初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 現金表 (增加分類 category)
    cursor.execute('CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, category TEXT)')
    # 交易表 (增加成本 cost)
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, shares REAL, cost REAL)')
    # 目標表
    cursor.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_name TEXT, target_amount REAL)')
    # 預設一個百萬目標 (如果不存在)
    cursor.execute('INSERT OR IGNORE INTO goals (id, target_name, target_amount) VALUES (1, "百萬大關", 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 2. HTML 模板 (包含圖表與進度條) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini AI 財富助理</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .ai-card { background: #161b22; border: 1px solid #30363d; border-radius: 15px; padding: 20px; margin-bottom: 20px; }
        .progress { height: 30px; border-radius: 15px; background-color: #30363d; }
        .btn-gemini { background: linear-gradient(90deg, #4f46e5, #06b6d4); color: white; border: none; border-radius: 20px; }
        .feedback-box { background: #1c2128; border-left: 4px solid #388bfd; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .advice-item { border-bottom: 1px solid #30363d; padding: 10px 0; }
        .advice-item:last-child { border-bottom: none; }
    </style>
</head>
<body>
    <div class="container py-5">
        <h2 class="text-center mb-4 text-white">🤖 Gemini AI 財富教練</h2>

        <div class="feedback-box">
            <h6 class="text-primary">助理說：</h6>
            <p class="mb-0">{{ ai_feedback }}</p>
        </div>

        <div class="ai-card shadow">
            <form action="/smart_process" method="POST" class="input-group">
                <input type="text" name="user_input" class="form-control bg-dark text-white border-secondary" 
                       placeholder="輸入範例：買 2330 1000 / 薪水 65000 / 信用卡支出 118646 / 設定目標 1200000">
                <button class="btn btn-gemini px-4" type="submit">執行指令</button>
            </form>
        </div>

        <div class="row">
            <div class="col-md-7">
                <div class="ai-card">
                    <h5>🎯 {{ goal_name }} 進度</h5>
                    <h2 class="fw-bold text-white mt-3">${{ "{:,.0f}".format(total_val) }} / ${{ "{:,.0f}".format(goal_amt) }}</h2>
                    <div class="progress mt-3">
                        <div class="progress-bar progress-bar-striped progress-bar-animated bg-success" 
                             style="width: {{ progress }}%">{{ progress }}%</div>
                    </div>
                    <p class="mt-3 text-muted">💡 離達成目標還差 ${{ "{:,.0f}".format(goal_amt - total_val) }}，繼續加油！</p>
                </div>

                <div class="ai-card">
                    <h5 class="text-warning mb-3">🔔 智能交易分析與建議</h5>
                    {% for advice in trade_advice %}
                        <div class="advice-item">{{ advice | safe }}</div>
                    {% endfor %}
                    {% if not trade_advice %}
                        <p class="text-muted small">目前標的波動穩定，暫無特別建議。</p>
                    {% endif %}
                </div>
            </div>

            <div class="col-md-5">
                <div class="ai-card text-center">
                    <h5>📊 資產比例分配</h5>
                    <canvas id="assetChart" class="mt-3"></canvas>
                </div>
                <div class="ai-card">
                    <h6>明細速覽</h6>
                    <div class="d-flex justify-content-between"><span>現金總額</span><span>${{ "{:,.0f}".format(total_cash) }}</span></div>
                    <div class="d-flex justify-content-between"><span>股票現值</span><span>${{ "{:,.0f}".format(total_stock) }}</span></div>
                    <div class="d-flex justify-content-between"><span>其他(郵局)</span><span>$100,000</span></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('assetChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['現金', '股票', '其他'],
                datasets: [{
                    data: [{{ total_cash }}, {{ total_stock }}, 100000],
                    backgroundColor: ['#388bfd', '#238636', '#f1e05a'],
                    borderColor: '#161b22',
                    borderWidth: 2
                }]
            },
            options: { plugins: { legend: { labels: { color: '#c9d1d9' } } } }
        });
    </script>
</body>
</html>
"""

# --- 3. 核心處理邏輯 ---
@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. 計算現金
    c.execute('SELECT SUM(amount) FROM cash')
    res_cash = c.fetchone()
    total_cash = float(res_cash[0]) if res_cash and res_cash[0] else 0.0
    
    # 2. 計算股票現值與建議
    c.execute('SELECT symbol, SUM(shares) FROM trades GROUP BY symbol')
    stocks_raw = c.fetchall()
    total_stock = 0.0
    trade_advice = []
    
    for sym, sh in stocks_raw:
        if sh > 0:
            try:
                ticker = yf.Ticker(sym)
                price = ticker.fast_info.get('last_price') or 0
                val = sh * price
                total_stock += val
                # 簡單建議邏輯
                if sym == "2449.TW": # 京元電
                    trade_advice.append(f"🟢 <b>京元電</b> 表現強勁，現值 ${val:,.0f}，若要繳卡費可考慮部分了結。")
                elif sym == "2330.TW":
                    trade_advice.append(f"💎 <b>台積電</b> 是穩定的核心資產，目前價值 ${val:,.0f}，建議長抱。")
            except:
                pass

    # 3. 獲取目標
    c.execute('SELECT target_name, target_amount FROM goals WHERE id=1')
    goal_res = c.fetchone()
    g_name, g_amt = goal_res if goal_res else ("百萬大關", 1000000)
    
    # 總結
    total_val = total_cash + total_stock + 100000 # 加上郵局存款
    progress = round((total_val / g_amt) * 100, 1) if g_amt > 0 else 0
    
    ai_feedback = request.args.get('feedback', '準備好迎接 100 萬了嗎？輸入指令來更新資產！')
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, total_cash=total_cash, total_stock=total_stock,
                                  total_val=total_val, goal_name=g_name, goal_amt=g_amt,
                                  progress=progress, trade_advice=trade_advice, ai_feedback=ai_feedback)

@app.route('/smart_process', methods=['POST'])
def smart_process():
    text = request.form.get('user_input', '').strip()
    if not text:
        return redirect(url_for('index'))
        
    conn = sqlite3.connect(db_path)
    feedback = f"助理聽不太懂『{text}』，請試試看更直白的輸入法！"
    
    # 提取文字中的所有數字
    numbers = re.findall(r'\d+', text)
    amt = float(numbers[0]) if numbers else 0
    
    # A. 更新目標
    if "目標" in text and amt > 0:
        conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
        feedback = f"🎯 目標已更新為 {amt:,.0f} 元！離 100 萬更近了。"
        
    # B. 股票交易 (買/賣)
    elif ("買" in text or "賣" in text) and amt > 0:
        stock_code = re.search(r'\d{4}', text)
        if stock_code:
            sym = stock_code.group() + ".TW"
            # 如果輸入「買 2330 1」，我們當作 1 張 (1000股)
            shares = amt * 1000 if "張" in text else amt
            if "賣" in text: shares *= -1
            conn.execute('INSERT INTO trades (symbol, shares) VALUES (?, ?)', (sym, shares))
            feedback = f"📈 記錄成功：{'賣出' if shares < 0 else '買進'} {sym} {abs(shares)} 股。"

    # C. 現金變動 (薪水/支出/卡費)
    elif amt > 0:
        is_neg = any(w in text for w in ["支出", "卡費", "付", "花", "減", "扣"])
        val = amt * (-1 if is_neg else 1)
        conn.execute('INSERT INTO cash (name, amount) VALUES (?, ?)', (text, val))
        feedback = f"💰 已記錄{'支出' if is_neg else '收入'}：{text} (${abs(val):,.0f})"

    conn.commit()
    conn.close()
    return redirect(url_for('index', feedback=feedback))

if __name__ == '__main__':
    # Render 環境需要監聽 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
