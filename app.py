import os
import sqlite3
import re
import yfinance as yf
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v12.db')

# --- 1. 國字轉數字引擎 ---
def cn_to_num(cn):
    digits = {'零':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    units = {'十':10,'百':100,'千':1000,'萬':10000}
    res, quota, tmp = 0, 1, 0
    for char in reversed(cn):
        if char in digits:
            tmp += digits[char] * quota
        elif char in units:
            quota = units[char]
            if quota >= 10000:
                res += tmp
                tmp = 0
                res *= quota
                quota = 1
        else: continue
    return res + tmp

def smart_extract_amt(text):
    # 優先找阿拉伯數字
    nums = re.findall(r'\d+', text)
    if nums: return float(nums[0])
    # 找國字數字 (例如: 六萬五)
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums: return cn_to_num(cn_nums.group())
    return 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, category TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    cursor.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 3. HTML 模板 (多圖表版) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Gemini AI 財富大腦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0b0e14; color: #adbac7; font-family: sans-serif; }
        .ai-card { background: #22272e; border: 1px solid #444c56; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .btn-gemini { background: #347d39; color: white; border: none; border-radius: 6px; padding: 10px 20px; }
        .progress { height: 12px; background-color: #444c56; border-radius: 6px; }
    </style>
</head>
<body>
    <div class="container py-4">
        <h3 class="mb-4 text-white">🤖 Gemini AI 財富大腦 <span class="badge bg-primary fs-6">v12</span></h3>
        
        <div class="ai-card">
            <form action="/process" method="POST">
                <textarea name="user_input" class="form-control bg-dark text-white border-secondary mb-3" rows="2" 
                          placeholder="試試看：領薪水六萬五、繳卡費十一萬、買2330兩張"></textarea>
                <button class="btn btn-gemini w-100">執行 AI 指令</button>
            </form>
        </div>

        <div class="row">
            <div class="col-md-4">
                <div class="ai-card">
                    <h6>🎯 目標進度</h6>
                    <h3 class="text-white">${{ "{:,.0f}".format(total_val) }}</h3>
                    <div class="progress my-2"><div class="progress-bar bg-info" style="width: {{ progress }}%"></div></div>
                    <small>距離 100 萬目標還差 {{ 100 - progress }}%</small>
                </div>
                <div class="ai-card">
                    <h6>📊 動態資產分佈</h6>
                    <canvas id="pieChart"></canvas>
                </div>
            </div>
            <div class="col-md-8">
                <div class="ai-card">
                    <h6>📈 資產累積趨勢 (最近10筆)</h6>
                    <canvas id="lineChart" height="120"></canvas>
                </div>
                <div class="ai-card">
                    <h6>📝 最近交易紀錄</h6>
                    <table class="table table-dark table-hover sm">
                        <thead><tr><th>時間</th><th>內容</th><th>金額</th><th>操作</th></tr></thead>
                        <tbody>
                            {% for item in history %}
                            <tr>
                                <td><small>{{ item[4][5:16] }}</small></td>
                                <td>{{ item[1] }}</td>
                                <td class="{{ 'text-danger' if item[2] < 0 else 'text-success' }}">{{ "{:,.0f}".format(item[2]) }}</td>
                                <td><a href="/delete/{{ item[0] }}" class="text-muted small">刪除</a></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 圓餅圖數據
        new Chart(document.getElementById('pieChart'), {
            type: 'pie',
            data: {
                labels: {{ cat_labels | safe }},
                datasets: [{
                    data: {{ cat_values | safe }},
                    backgroundColor: ['#347d39', '#388bfd', '#f1e05a', '#f85149', '#8957e5', '#da336a'],
                    borderWidth: 0
                }]
            },
            options: { plugins: { legend: { position: 'bottom', labels: { color: '#adbac7' } } } }
        });

        // 趨勢圖數據
        new Chart(document.getElementById('lineChart'), {
            type: 'line',
            data: {
                labels: {{ trend_labels | safe }},
                datasets: [{
                    label: '資產總值',
                    data: {{ trend_values | safe }},
                    borderColor: '#388bfd',
                    tension: 0.3,
                    fill: true,
                    backgroundColor: 'rgba(56, 139, 253, 0.1)'
                }]
            },
            options: { scales: { y: { grid: { color: '#444c56' } }, x: { grid: { display: false } } } }
        });
    </script>
</body>
</html>
"""

# --- 4. 路由與邏輯 ---
@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 抓取所有紀錄
    c.execute('SELECT * FROM assets ORDER BY date ASC')
    all_data = c.fetchall()
    
    # 計算趨勢 (Line Chart)
    current_total = 0
    trend_values, trend_labels = [], []
    cat_map = {}
    
    for item in all_data:
        current_total += item[2]
        trend_values.append(current_total)
        trend_labels.append(item[4][5:10]) # 取月-日
        # 分類統計 (Pie Chart)
        cat = item[3]
        cat_map[cat] = cat_map.get(cat, 0) + item[2]

    # 過濾負值分類 (圓餅圖不顯示負數)
    cat_labels = [k for k, v in cat_map.items() if v > 0]
    cat_values = [v for k, v in cat_map.items() if v > 0]

    # 目標
    c.execute('SELECT target_amount FROM goals WHERE id=1')
    g_amt = c.fetchone()[0]
    progress = min(100, round((current_total / g_amt) * 100, 1)) if g_amt > 0 else 0

    conn.close()
    return render_template_string(HTML_TEMPLATE, total_val=current_total, progress=progress, 
                                  history=all_data[::-1][:8], cat_labels=cat_labels, cat_values=cat_values,
                                  trend_labels=trend_labels[-10:], trend_values=trend_values[-10:])

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '')
    # 拆分指令
    cmds = re.split(r'[，。, \n]+', text)
    conn = sqlite3.connect(db_path)
    
    for cmd in cmds:
        if not cmd: continue
        amt = smart_extract_amt(cmd)
        if amt == 0: continue
        
        # 判斷分類與金額正負
        category = "一般"
        if "薪" in cmd or "入" in cmd: category = "收入"
        elif "卡" in cmd or "支" in cmd or "付" in cmd: 
            category = "支出"; amt = -amt
        elif "股票" in cmd or "買" in cmd or re.search(r'\d{4}', cmd):
            category = "股票"
            if "買" in cmd and "張" in cmd: amt *= 1000 # 簡單模擬張數
            # 這裡可擴充 yfinance 抓現價，為簡化先以金額/股數紀錄
        elif "黃金" in cmd: category = "黃金"
        elif "郵局" in cmd: category = "儲蓄"

        conn.execute('INSERT INTO assets (name, amount, category) VALUES (?, ?, ?)', (cmd, amt, category))
    
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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
