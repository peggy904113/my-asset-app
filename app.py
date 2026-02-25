import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
# 升級到 v40 支援完整分頁與折線圖趨勢
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v40.db')

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    bank_name TEXT, amount REAL, category TEXT, type TEXT, cost REAL, date TEXT)''')
    conn.commit()
    conn.close()

def smart_extract(text):
    # 提取數字
    nums = re.findall(r'\d+\.?\d*', text.replace(',', ''))
    amt = float(nums[0]) if nums else 0
    # 單位轉換：張 -> 1000, 萬 -> 10000
    if '張' in text: amt *= 1000
    elif '萬' in text: amt *= 10000
    
    # 提取成本
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    
    # 提取銀行名稱 (簡單取第一個中文字群)
    bank_match = re.search(r'([\u4e00-\u9fa5]+)', text)
    bank = bank_match.group(1) if bank_match else "未命名"
    
    return bank, amt, cost

init_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 財富儀表板</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .nav-tabs { border-bottom: 1px solid #30363d; margin-bottom: 20px; }
        .nav-link { color: #8b949e; border: none !important; }
        .nav-link.active { color: #58a6ff !important; background: transparent !important; border-bottom: 2px solid #58a6ff !important; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
        .ai-input { background: #0d1117; border: 2px solid #388bfd; border-radius: 30px; color: white; padding: 12px 20px; width: 100%; outline: none; }
        .ai-tip { font-size: 0.75rem; color: #f1e05a; background: rgba(241, 224, 90, 0.1); padding: 6px 10px; border-radius: 6px; display: block; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container py-4">
        <h4 class="text-center fw-bold mb-4">🤖 AI 智慧理財大腦</h4>
        
        <form action="/process" method="POST" class="mb-4">
            <input type="text" name="user_input" class="ai-input" placeholder="例如: 中信 10萬 (存款)、台積電 1張 成本 600 (證券)">
        </form>

        <ul class="nav nav-tabs justify-content-center" id="myTab">
            <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#summary">資產總覽</a></li>
            <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#deposit">銀行存款</a></li>
            <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#stock">證券投資</a></li>
        </ul>

        <div class="tab-content">
            <div class="tab-pane fade show active" id="summary">
                <div class="row">
                    <div class="col-md-6">
                        <div class="card text-center">
                            <small class="text-muted">預估總資產 (折合 TWD)</small>
                            <h2 class="fw-bold text-white">${{ "{:,.0f}".format(total_val) }}</h2>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card" style="height: 120px; padding: 10px;"><canvas id="trendChart"></canvas></div>
                    </div>
                </div>
                <div class="card"><canvas id="pieChart" style="max-height: 200px;"></canvas></div>
            </div>

            <div class="tab-pane fade" id="deposit">
                <div class="card">
                    <h6 class="fw-bold mb-3">各銀行存款明細</h6>
                    {% for item in history if item[4] == '存款' %}
                    <div class="d-flex justify-content-between border-bottom border-secondary py-3">
                        <div><span class="text-white">{{ item[1] }}</span> <span class="badge bg-dark text-info">存款</span></div>
                        <div class="text-end text-white fw-bold">${{ "{:,.0f}".format(item[2]) }}<br><a href="/delete/{{ item[0] }}" class="text-danger small" style="text-decoration:none;">移除</a></div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div class="tab-pane fade" id="stock">
                <div class="card">
                    <h6 class="fw-bold mb-3">證券持倉診斷</h6>
                    {% for item in history if item[4] == '證券' %}
                    <div class="border-bottom border-secondary py-3">
                        <div class="d-flex justify-content-between">
                            <span class="text-white fw-bold">{{ item[1] }}</span>
                            <span class="text-info">{{ "{:,.0f}".format(item[2]) }} 股</span>
                        </div>
                        <div class="ai-tip">
                            {% if item[5] > 0 %}
                            🤖 AI 駐守：成本 {{ item[5] }}。建議停損位：{{ item[5] * 0.9 }}。目前觀察大盤支撐力道。
                            {% else %}
                            🤖 AI 建議：請輸入成本以利計算風險。
                            {% endif %}
                        </div>
                        <div class="text-end"><a href="/delete/{{ item[0] }}" class="text-danger small" style="text-decoration:none;">移除</a></div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <script>
        // 折線圖
        new Chart(document.getElementById('trendChart'), {
            type: 'line',
            data: { labels: {{ dates | safe }}, datasets: [{ data: {{ values | safe }}, borderColor: '#58a6ff', tension: 0.3, fill: true, backgroundColor: 'rgba(88, 166, 255, 0.1)' }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } }
        });
        // 圓餅圖
        new Chart(document.getElementById('pieChart'), {
            type: 'doughnut',
            data: { labels: ['存款', '證券'], datasets: [{ data: [{{ deposit_val }}, {{ stock_val }}], backgroundColor: ['#388bfd', '#238636'], borderWidth: 0 }] },
            options: { plugins: { legend: { position: 'bottom', labels: { color: '#c9d1d9' } } } }
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
    history = c.fetchall()
    
    total_val, deposit_val, stock_val = 0, 0, 0
    dates, values = [], []
    
    for item in history:
        val = item[2]
        total_val += val
        if item[4] == '存款': deposit_val += val
        else: stock_val += val
        
        dates.append(item[6][5:10]) # 取 MM-DD
        values.append(total_val)
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, history=history[::-1], total_val=total_val, deposit_val=deposit_val, stock_val=stock_val, dates=dates, values=values)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    bank, amt, cost = smart_extract(text)
    
    # AI 劃分類別：有「股、張、成本、或純數字代號」歸類證券，其餘歸存款
    asset_type = "證券" if any(w in text for w in ["股", "張", "成本"]) or (bank.isdigit() and len(bank)>=4) else "存款"
    
    if amt != 0:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO assets (bank_name, amount, category, type, cost, date) VALUES (?, ?, ?, ?, ?, ?)', 
                     (bank, amt, "自動歸類", asset_type, cost, datetime.now().strftime("%Y-%m-%d %H:%M")))
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
