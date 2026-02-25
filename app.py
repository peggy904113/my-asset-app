import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 資料庫檔案路徑
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v13.db')

# --- 1. 強化版國字數字解析 ---
def cn_to_num(cn):
    if not cn: return 0
    digits = {'零':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    units = {'十':10,'百':100,'千':1000,'萬':10000}
    res, quota, tmp = 0, 1, 0
    try:
        for char in reversed(cn):
            if char in digits:
                tmp += digits[char] * quota
            elif char in units:
                quota = units[char]
                if quota >= 10000:
                    res += tmp; tmp = 0; res *= quota; quota = 1
        return res + tmp
    except: return 0

def smart_extract_amt(text):
    # 優先找阿拉伯數字
    nums = re.findall(r'\d+', text)
    if nums: return float(nums[0])
    # 找國字數字
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums: return cn_to_num(cn_nums.group())
    return 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, category TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 3. HTML 模板 (加入防呆與移動端優化) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini AI 財富大腦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .ai-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 15px; margin-bottom: 15px; }
        .btn-gemini { background: #238636; color: white; border: none; border-radius: 6px; padding: 10px; width: 100%; }
        .progress { height: 20px; background-color: #30363d; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container py-3">
        <h4 class="mb-3 text-white">🤖 Gemini 財富大腦 v13</h4>
        
        <div class="ai-card">
            <form action="/process" method="POST">
                <textarea name="user_input" class="form-control bg-dark text-white border-secondary mb-2" rows="2" 
                          placeholder="例如：薪水六萬五、繳卡費十一萬"></textarea>
                <button class="btn-gemini">執行指令</button>
            </form>
        </div>

        <div class="row">
            <div class="col-12 col-md-4">
                <div class="ai-card text-center">
                    <h6>🎯 達成進度</h6>
                    <h2 class="text-white">${{ "{:,.0f}".format(total_val) }}</h2>
                    <div class="progress my-2"><div class="progress-bar bg-info" style="width: {{ progress }}%"></div></div>
                    <small>達成率 {{ progress }}%</small>
                </div>
                <div class="ai-card">
                    <canvas id="pieChart"></canvas>
                </div>
            </div>
            <div class="col-12 col-md-8">
                <div class="ai-card">
                    <canvas id="lineChart" height="150"></canvas>
                </div>
                <div class="ai-card">
                    <h6>📝 歷史紀錄 (最近五筆)</h6>
                    <table class="table table-dark table-sm">
                        {% for item in history %}
                        <tr>
                            <td>{{ item[1] }}</td>
                            <td class="{{ 'text-danger' if item[2] < 0 else 'text-success' }}">${{ "{:,.0f}".format(item[2]) }}</td>
                            <td><a href="/delete/{{ item[0] }}" class="text-muted small">刪除</a></td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        try {
            // 圓餅圖
            new Chart(document.getElementById('pieChart'), {
                type: 'pie',
                data: {
                    labels: {{ cat_labels | safe }},
                    datasets: [{
                        data: {{ cat_values | safe }},
                        backgroundColor: ['#388bfd', '#238636', '#f1e05a', '#f85149'],
                        borderWidth: 0
                    }]
                }
            });

            // 線圖
            new Chart(document.getElementById('lineChart'), {
                type: 'line',
                data: {
                    labels: {{ trend_labels | safe }},
                    datasets: [{
                        label: '資產走勢',
                        data: {{ trend_values | safe }},
                        borderColor: '#388bfd',
                        fill: false
                    }]
                }
            });
        } catch (e) { console.log("圖表渲染錯誤:", e); }
    </script>
</body>
</html>
"""

# --- 4. 路由邏輯 ---
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
            if item[2] > 0: # 圓餅圖只算正向資產
                cat_map[item[3]] = cat_map.get(item[3], 0) + item[2]

        c.execute('SELECT target_amount FROM goals WHERE id=1')
        g_amt = c.fetchone()[0]
        progress = min(100, round((current_total / g_amt) * 100, 1)) if g_amt > 0 else 0
        conn.close()

        return render_template_string(HTML_TEMPLATE, total_val=current_total, progress=progress, 
                                      history=all_data[::-1][:5], 
                                      cat_labels=list(cat_map.keys()), cat_values=list(cat_map.values()),
                                      trend_labels=trend_labels[-10:], trend_values=trend_values[-10:])
    except Exception as e:
        return f"<h1>系統運行中...但出現一點問題：</h1><p>{str(e)}</p>"

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '')
    cmds = re.split(r'[，。, \n]+', text)
    conn = sqlite3.connect(db_path)
    for cmd in cmds:
        if not cmd: continue
        amt = smart_extract_amt(cmd)
        if amt == 0: continue
        
        cat = "一般"
        if "薪" in cmd: cat = "薪水"
        elif any(w in cmd for w in ["卡", "支出", "付"]): cat = "支出"; amt = -amt
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
