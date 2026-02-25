import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v14.db')

# --- 數字解析邏輯 (保留國字與數字) ---
def cn_to_num(cn):
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
    nums = re.findall(r'\d+', text)
    if nums: return float(nums[0])
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums: return cn_to_num(cn_nums.group())
    return 0

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, category TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 針對手機與視覺協調性優化的 HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Gemini AI 財富助理</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --bg-color: #0d1117; --card-bg: #161b22; --border-color: #30363d; --text-main: #c9d1d9; --accent: #58a6ff; }
        body { background-color: var(--bg-color); color: var(--text-main); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; margin: 0; padding-bottom: 30px; }
        
        /* 頂部導航 */
        .header { background: #010409; padding: 15px; border-bottom: 1px solid var(--border-color); text-align: center; }
        .header h5 { margin: 0; font-weight: 600; color: white; letter-spacing: 1px; }

        /* 卡片統一樣式 */
        .ai-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; margin-top: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        
        /* 輸入框優化 */
        textarea.form-control { background-color: #010409 !important; border: 1px solid var(--border-color); color: white !important; border-radius: 10px; font-size: 16px; } /* 16px 防止手機自動放大 */
        .btn-submit { background: linear-gradient(135deg, #238636 0%, #2ea043 100%); border: none; color: white; font-weight: bold; border-radius: 10px; padding: 12px; transition: 0.3s; }
        .btn-submit:active { transform: scale(0.98); }

        /* 進度條 */
        .progress { height: 24px; background-color: #30363d; border-radius: 12px; overflow: hidden; }
        .progress-bar { font-weight: bold; line-height: 24px; transition: width 1s ease-in-out; }

        /* 圖表容器 */
        .chart-container { position: relative; width: 100%; margin: auto; }

        /* 紀錄列表 */
        .history-table { width: 100%; margin-top: 10px; border-collapse: collapse; }
        .history-table td { padding: 12px 8px; border-bottom: 1px solid var(--border-color); vertical-align: middle; }
        .delete-link { color: #f85149; text-decoration: none; font-size: 14px; padding: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h5>🤖 GEMINI AI 財富教練 <small style="font-size: 10px; color: #8b949e;">V14</small></h5>
    </div>

    <div class="container">
        <div class="ai-card">
            <form action="/process" method="POST">
                <textarea name="user_input" class="form-control mb-3" rows="2" placeholder="在此輸入：領薪水 65000，設定目標 120萬..."></textarea>
                <button class="btn-submit w-100">發送 AI 指令</button>
            </form>
        </div>

        <div class="row">
            <div class="col-12 col-lg-4">
                <div class="ai-card text-center">
                    <p class="text-muted mb-1" style="font-size: 14px;">預估總資產 (TWD)</p>
                    <h2 class="fw-bold text-white mb-3">${{ "{:,.0f}".format(total_val) }}</h2>
                    <div class="progress mb-2">
                        <div class="progress-bar bg-info" role="progressbar" style="width: {{ progress }}%;">{{ progress }}%</div>
                    </div>
                    <small class="text-muted">目標：${{ "{:,.0f}".format(goal_amt) }}</small>
                </div>

                <div class="ai-card">
                    <h6 class="mb-3">📊 資產佔比</h6>
                    <div class="chart-container">
                        <canvas id="pieChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-8">
                <div class="ai-card">
                    <h6 class="mb-3">📈 資產走勢</h6>
                    <div class="chart-container">
                        <canvas id="lineChart" height="200"></canvas>
                    </div>
                </div>

                <div class="ai-card">
                    <h6 class="mb-3">📝 最近異動</h6>
                    <div class="table-responsive">
                        <table class="history-table">
                            {% for item in history %}
                            <tr>
                                <td>
                                    <div style="font-size: 15px; color: #fff;">{{ item[1] }}</div>
                                    <div style="font-size: 11px; color: #8b949e;">{{ item[4][5:16] }}</div>
                                </td>
                                <td class="text-end fw-bold {{ 'text-danger' if item[2] < 0 else 'text-success' }}">
                                    ${{ "{:,.0f}".format(item[2]) }}
                                </td>
                                <td class="text-end">
                                    <a href="/delete/{{ item[0] }}" class="delete-link">刪除</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#c9d1d9', font: { size: 12 } } } }
        };

        // 圓餅圖
        new Chart(document.getElementById('pieChart'), {
            type: 'doughnut',
            data: {
                labels: {{ cat_labels | safe }},
                datasets: [{
                    data: {{ cat_values | safe }},
                    backgroundColor: ['#58a6ff', '#238636', '#f1e05a', '#f85149', '#8957e5'],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: chartOptions
        });

        // 線圖
        new Chart(document.getElementById('lineChart'), {
            type: 'line',
            data: {
                labels: {{ trend_labels | safe }},
                datasets: [{
                    label: '資產淨值',
                    data: {{ trend_values | safe }},
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { grid: { color: '#30363d' }, ticks: { color: '#8b949e' } },
                    x: { grid: { display: false }, ticks: { color: '#8b949e' } }
                }
            }
        });
    </script>
</body>
</html>
"""

# --- 路由邏輯 (維持穩定) ---
@app.route('/')
def index():
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM assets ORDER BY date ASC')
        all_data = c.fetchall()
        
        current_total = 0
        trend_values, trend_labels = [0], ["開始"]
        cat_map = {}
        
        for item in all_data:
            current_total += item[2]
            trend_values.append(current_total)
            trend_labels.append(item[4][5:10])
            if item[2] > 0:
                cat_map[item[3]] = cat_map.get(item[3], 0) + item[2]

        c.execute('SELECT target_amount FROM goals WHERE id=1')
        g_amt = c.fetchone()[0]
        progress = min(100, round((current_total / g_amt) * 100, 1)) if g_amt > 0 else 0
        conn.close()

        return render_template_string(HTML_TEMPLATE, total_val=current_total, progress=progress, goal_amt=g_amt,
                                      history=all_data[::-1][:8], 
                                      cat_labels=list(cat_map.keys()), cat_values=list(cat_map.values()),
                                      trend_labels=trend_labels[-10:], trend_values=trend_values[-10:])
    except Exception as e:
        return f"<h1>系統渲染中...</h1><p>{str(e)}</p>"

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '')
    cmds = re.split(r'[，。, \n]+', text)
    conn = sqlite3.connect(db_path)
    for cmd in cmds:
        if not cmd: continue
        amt = smart_extract_amt(cmd)
        if amt == 0 and "目標" not in cmd: continue
        
        cat = "一般"
        if "薪" in cmd: cat = "薪水"
        elif any(w in cmd for w in ["卡", "支出", "付", "花"]): cat = "支出"; amt = -amt
        elif "股" in cmd or re.search(r'\d{4}', cmd): cat = "股票"
        elif "目標" in cmd:
            conn.execute('UPDATE goals SET target_amount = ? WHERE id = 1', (amt,))
            continue
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
