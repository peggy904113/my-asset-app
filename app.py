import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 使用 v15 資料庫檔案
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v15.db')

# --- 1. AI 語意解析引擎 ---
def cn_to_num(cn):
    """將國字數字轉換為阿拉伯數字"""
    if not cn: return 0
    digits = {'零':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    units = {'十':10,'百':100,'千':1000,'萬':10000}
    res, quota, tmp = 0, 1, 0
    try:
        for char in reversed(cn):
            if char in digits: tmp += digits[char] * quota
            elif char in units:
                quota = units[char]
                if quota >= 10000: res += tmp; tmp = 0; res *= quota; quota = 1
        return res + tmp
    except: return 0

def smart_extract_amt(text):
    """從文字中精準提取金額"""
    text = text.replace(',', '') # 移除千分位逗號
    nums = re.findall(r'\d+\.?\d*', text)
    if nums: return float(nums[0])
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums: return cn_to_num(cn_nums.group())
    return 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, 
                    date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 3. 響應式 HTML 模板 (針對手機優化) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Gemini AI 財富大腦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #c9d1d9; }
        body { background-color: var(--bg); color: var(--text); font-family: sans-serif; padding-bottom: 50px; }
        .ai-card { background: var(--card); border: 1px solid var(--border); border-radius: 15px; padding: 18px; margin-top: 15px; }
        .btn-submit { background: linear-gradient(135deg, #238636, #2ea043); border: none; color: white; border-radius: 10px; padding: 12px; font-weight: bold; width: 100%; }
        .progress { height: 24px; background-color: #30363d; border-radius: 12px; }
        textarea { font-size: 16px !important; } /* 防止 iOS 自動放大 */
        .history-item { border-bottom: 1px solid var(--border); padding: 10px 0; display: flex; justify-content: space-between; align-items: center; }
        .history-item:last-child { border-bottom: none; }
    </small></style>
</head>
<body>
    <div class="container py-3">
        <h5 class="text-center text-white mb-3">🤖 GEMINI AI 財富教練</h5>
        
        <div class="ai-card">
            <form action="/process" method="POST">
                <textarea name="user_input" class="form-control bg-dark text-white border-secondary mb-2" rows="2" 
                          placeholder="例如：郵局十萬、台新五萬、薪水六萬..."></textarea>
                <button class="btn-submit">發送 AI 指令</button>
            </form>
        </div>

        <div class="ai-card text-center">
            <p class="text-muted mb-1 small">目前估值 (TWD)</p>
            <h2 class="text-white">${{ "{:,.0f}".format(total_val) }}</h2>
            <div class="progress my-2">
                <div class="progress-bar bg-info" style="width: {{ progress }}%">{{ progress }}%</div>
            </div>
            <small class="text-muted">目標：${{ "{:,.0f}".format(goal_amt) }}</small>
        </div>

        <div class="row">
            <div class="col-12 col-md-6">
                <div class="ai-card">
                    <h6 class="mb-3">📊 資產分佈</h6>
                    <canvas id="pieChart"></canvas>
                </div>
            </div>
            <div class="col-12 col-md-6">
                <div class="ai-card">
                    <h6 class="mb-3">📈 增長趨勢</h6>
                    <canvas id="lineChart" height="200"></canvas>
                </div>
            </div>
        </div>

        <div class="ai-card">
            <h6 class="mb-3">📝 最近異動紀錄</h6>
            {% for item in history %}
            <div class="history-item">
                <div>
                    <div style="color: #fff;">{{ item[1] }}</div>
                    <small style="color: #8b949e; font-size: 11px;">{{ item[4][5:16] }}</small>
                </div>
                <div class="text-end">
                    <div class="fw-bold {{ 'text-danger' if item[2] < 0 else 'text-success' }}">
                        ${{ "{:,.0f}".format(item[2]) }}
                    </div>
                    <a href="/delete/{{ item[0] }}" class="text-danger small" style="text-decoration: none;">刪除</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const commonOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#c9d1d9' } } } };
        
        // 圓餅圖
        new Chart(document.getElementById('pieChart'), {
            type: 'doughnut',
            data: {
                labels: {{ cat_labels | safe }},
                datasets: [{
                    data: {{ cat_values | safe }},
                    backgroundColor: ['#58a6ff', '#238636', '#f1e05a', '#f85149', '#8957e5'],
                    borderWidth: 0
                }]
            },
            options: commonOptions
        });

        // 走勢圖
        new Chart(document.getElementById('lineChart'), {
            type: 'line',
            data: {
                labels: {{ trend_labels | safe }},
                datasets: [{
                    label: '淨資產',
                    data: {{ trend_values | safe }},
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: { ...commonOptions, scales: { y: { ticks: { color: '#8b949e' } }, x: { ticks: { color: '#8b949e' } } } }
        });
    </script>
</body>
</html>
"""

# --- 4. 路由處理邏輯 ---
@app.route('/')
def index():
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM assets ORDER BY date ASC')
        all_data = c.fetchall()
        
        current_total = 0
        trend_values, trend_labels = [0], ["Start"]
        cat_map = {}
        
        for item in all_data:
            current_total += item[2]
            trend_values.append(current_total)
            trend_labels.append(item[4][5:10])
            # 圓餅圖統計分類 (金額大於 0 才顯示)
            if item[2] > 0:
                cat_map[item[3]] = cat_map.get(item[3], 0) + item[2]

        c.execute('SELECT target_amount FROM goals WHERE id=1')
        g_amt = c.fetchone()[0]
        progress = min(100, round((current_total / g_amt) * 100, 1)) if g_amt > 0 else 0
        conn.close()

        return render_template_string(HTML_TEMPLATE, total_val=current_total, progress=progress, goal_amt=g_amt,
                                      history=all_data[::-1][:8], 
                                      cat_labels=list(cat_map.keys()), cat_values=list(cat_map.values()),
                                      trend_labels=trend_labels[-15:], trend_values=trend_values[-15:])
    except Exception as e:
        return f"<h1>系統渲染中...</h1><p>{str(e)}</p>"

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    cmds = re.split(r'[，。, \n]+', text)
    conn = sqlite3.connect(db_path)
    for cmd in cmds:
        if not cmd: continue
        amt = smart_extract_amt(cmd)
        
        # 判斷分類
        cat = "一般"
        if any(w in cmd for w in ["郵局", "台新", "中信", "國泰", "銀行", "存", "現金"]): cat = "儲蓄"
        elif any(w in cmd for w in ["薪", "收入", "入帳"]): cat = "收入"
        elif any(w in cmd for w in ["支出", "卡", "付", "花", "買"]):
            cat = "支出"; amt = -abs(amt) # 強制變負數
        elif any(w in cmd for w in ["股", "張"]) or re.search(r'\d{4}', cmd): cat = "股票"
        elif "目標" in cmd:
            conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
            continue

        if amt != 0:
            conn.execute('INSERT INTO assets (name, amount, category) VALUES (?, ?, ?)', (cmd, amt, cat))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect(db_path)
    conn.execute('DELETE FROM assets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
