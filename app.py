import os
import sqlite3
import re
import json
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
# 升級到 v50 支援更細緻的分類與趨勢紀錄
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v50.db')

# --- 1. AI 邏輯與名稱解析 ---
def smart_parser(text):
    text = text.replace(',', '').strip()
    
    # 解析金額與單位 (張=1000, 萬=10000)
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '張' in text: amt *= 1000
        elif '萬' in text: amt *= 10000
    
    # 提取成本 (例如: 成本 600)
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    
    # 清洗名稱：移除金額、單位、關鍵字，只留下銀行或股票名
    clean_name = re.sub(r'\d+\.?\d*|萬|張|成本|買入|買|存款|活存|預備金', '', text).strip()
    if not clean_name: clean_name = "未命名項目"
    
    # 自動判定類別
    if any(w in text for w in ['股', '張', '成本', '買入', '證券']):
        category = "證券"
    else:
        category = "存款"
        
    return clean_name, amt, category, cost

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    # type 欄位用來細分 (活存/預備金/投資)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    display_name TEXT, amount REAL, category TEXT, sub_type TEXT, 
                    cost REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. 專業分頁 HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 財富管家</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .nav-tabs { border-bottom: 1px solid #30363d; margin-bottom: 25px; justify-content: center; }
        .nav-link { color: #8b949e; border: none !important; font-weight: 500; padding: 12px 25px; }
        .nav-link.active { color: #58a6ff !important; background: transparent !important; border-bottom: 3px solid #58a6ff !important; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 20px; margin-bottom: 20px; }
        .ai-input { background: #0d1117; border: 1px solid #388bfd; border-radius: 30px; color: white; padding: 15px 25px; width: 100%; outline: none; margin-bottom: 20px; }
        .trend-card { height: 200px; }
        .price-tag { color: #ffffff; font-weight: bold; font-size: 1.1rem; }
        .ai-status { font-size: 0.75rem; background: rgba(56, 139, 253, 0.15); color: #58a6ff; padding: 4px 10px; border-radius: 6px; }
    </style>
</head>
<body>
    <div class="container py-4">
        <form action="/process" method="POST">
            <input type="text" name="user_input" class="ai-input" placeholder="例如: 中信 10萬 (存款) 或 台積電 1張 成本 600 (證券)">
        </form>

        <ul class="nav nav-tabs" id="myTab">
            <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#tab1">總覽趨勢</a></li>
            <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#tab2">證券持倉</a></li>
            <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#tab3">存款明細</a></li>
        </ul>

        <div class="tab-content">
            <div class="tab-pane fade show active" id="tab1">
                <div class="card text-center">
                    <div class="text-muted small">預估總資產市值 (TWD)</div>
                    <h1 class="fw-bold text-white mt-1">${{ "{:,.0f}".format(total_val) }}</h1>
                </div>
                <div class="card trend-card">
                    <canvas id="trendChart"></canvas>
                </div>
                <div class="row">
                    <div class="col-6"><div class="card text-center"><h6>存款</h6><h4 class="text-info">${{ "{:,.0f}".format(dep_val) }}</h4></div></div>
                    <div class="col-6"><div class="card text-center"><h6>證券</h6><h4 class="text-success">${{ "{:,.0f}".format(stk_val) }}</h4></div></div>
                </div>
            </div>

            <div class="tab-pane fade" id="tab2">
                <div class="card">
                    <h6 class="fw-bold mb-3">📈 證券資產 AI 診斷</h6>
                    {% for item in history if item[3] == '證券' %}
                    <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-3">
                        <div>
                            <div class="fw-bold text-white">{{ item[1] }}</div>
                            <div class="ai-status">AI 駐守：成本 {{ "{:,.0f}".format(item[5]) if item[5] > 0 else '未紀錄' }}</div>
                        </div>
                        <div class="text-end">
                            <div class="price-tag">{{ "{:,.0f}".format(item[2]) }} 股</div>
                            <a href="/delete/{{ item[0] }}" class="text-danger small text-decoration-none">移除</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div class="tab-pane fade" id="tab3">
                <div class="card">
                    <h6 class="fw-bold mb-3">🏦 銀行資產分類</h6>
                    {% for item in history if item[3] == '存款' %}
                    <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-3">
                        <div>
                            <div class="fw-bold text-white">{{ item[1] }}</div>
                            <span class="badge bg-dark text-muted">{{ '活存/緊急預備金' }}</span>
                        </div>
                        <div class="text-end">
                            <div class="price-tag text-info">${{ "{:,.0f}".format(item[2]) }}</div>
                            <a href="/delete/{{ item[0] }}" class="text-danger small text-decoration-none">移除</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('trendChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ trend_labels | safe }},
                datasets: [{
                    label: '資產趨勢',
                    data: {{ trend_values | safe }},
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { display: false }, y: { grid: { color: '#30363d' } } }
            }
        });
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM assets ORDER BY date ASC')
    raw_data = c.fetchall()
    
    total_val, dep_val, stk_val = 0, 0, 0
    trend_labels, trend_values = [], []
    
    for item in raw_data:
        val = item[2]
        total_val += val
        if item[3] == "存款": dep_val += val
        else: stk_val += val
        
        # 建立趨勢圖數據
        trend_labels.append(item[6][5:16]) 
        trend_values.append(total_val)
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, 
                                 history=raw_data[::-1], 
                                 total_val=total_val, dep_val=dep_val, stk_val=stk_val,
                                 trend_labels=json.dumps(trend_labels), 
                                 trend_values=json.dumps(trend_values))

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    name, amt, cat, cost = smart_parser(text)
    
    if amt != 0:
        conn = sqlite3.connect(db_path)
        conn.execute('''INSERT INTO assets (display_name, amount, category, cost, date) 
                        VALUES (?, ?, ?, ?, ?)''', 
                     (name, amt, cat, cost, datetime.now().strftime("%Y-%m-%d %H:%M")))
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
