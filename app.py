import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 升級到 v36 支援成本欄位
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v36.db')

def smart_extract_amt(text):
    text = text.replace(',', '').strip()
    # 處理「張」：1張 = 1000股
    zhang_match = re.search(r'(\d+\.?\d*)\s*張', text)
    if zhang_match:
        return float(zhang_match.group(1)) * 1000
    # 處理「萬」
    wan_match = re.search(r'(\d+\.?\d*)\s*萬', text)
    if wan_match:
        return float(wan_match.group(1)) * 10000
    # 處理純數字
    nums = re.findall(r'\d+\.?\d*', text)
    return float(nums[0]) if nums else 0

def extract_cost(text):
    # 尋找「成本」後面的數字
    match = re.search(r'成本\s*(\d+\.?\d*)', text)
    return float(match.group(1)) if match else 0

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, currency TEXT, type TEXT, cost REAL)''')
    conn.commit()
    conn.close()

init_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 財富儀表板</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; }
        .main-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
        .ai-input { background: #0d1117; border: 2px solid #388bfd; border-radius: 30px; color: white; padding: 12px 20px; width: 100%; outline: none; }
        .ai-tip { font-size: 0.75rem; color: #f1e05a; background: rgba(241, 224, 90, 0.1); padding: 4px 8px; border-radius: 4px; display: inline-block; margin-top: 5px; }
        .stock-tag { font-size: 0.7rem; background: #238636; color: white; padding: 2px 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container py-4">
        <h5 class="text-center fw-bold mb-4">🤖 AI 證券駐守助理</h5>
        
        <form action="/process" method="POST" class="mb-4">
            <input type="text" name="user_input" class="ai-input" placeholder="例如: 買 2330 1張 成本 600">
            <small class="text-muted ps-2">支援格式：10萬、1張、成本 100</small>
        </form>

        <div class="row">
            <div class="col-6"><div class="main-card text-center">
                <small class="text-muted">資產總計</small>
                <h3 class="fw-bold text-white">${{ "{:,.0f}".format(total_val) }}</h3>
            </div></div>
            <div class="col-6"><div class="main-card" style="height: 105px; padding: 5px;"><canvas id="assetChart"></canvas></div></div>
        </div>

        <div class="main-card">
            <h6 class="fw-bold mb-3">我的持倉與 AI 診斷</h6>
            {% for item in history %}
            <div class="border-bottom border-secondary py-3">
                <div class="d-flex justify-content-between">
                    <div>
                        <span class="fw-bold text-white">{{ item[1] }}</span>
                        {% if item[4] == '證券' %}<span class="stock-tag">證券</span>{% endif %}
                    </div>
                    <div class="text-end">
                        <div class="fw-bold">${{ "{:,.0f}".format(item[2]) if item[4] != '證券' else "{:,.0f} 股".format(item[2]) }}</div>
                        <a href="/delete/{{ item[0] }}" class="text-danger small" style="text-decoration:none;">移除</a>
                    </div>
                </div>
                {% if item[4] == '證券' %}
                    <div class="ai-tip">
                        {% if item[5] > 0 %}
                            🤖 AI 駐守：成本 {{ item[5] }}。建議設 10% 停損點於 {{ item[5] * 0.9 }}，若大盤轉弱請注意風險。
                        {% else %}
                            🤖 AI 建議：未記錄成本。建議輸入「成本 XXX」以利 AI 追蹤風險。
                        {% endif %}
                    </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('assetChart').getContext('2d');
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['一般', '證券'],
                datasets: [{
                    data: [{{ type_sums['一般'] }}, {{ type_sums['證券'] }}],
                    backgroundColor: ['#58a6ff', '#238636'],
                    borderWidth: 0
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, name, amount, currency, type, cost FROM assets ORDER BY id DESC')
    history = c.fetchall()
    
    total_val = 0
    type_sums = {'一般': 0, '證券': 0}
    for item in history:
        # 簡單邏輯：如果是證券，總額先以股數計算（未來可再加入即時股價）
        val = item[2]
        total_val += val
        type_sums[item[4]] += val
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, history=history, total_val=total_val, type_sums=type_sums)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    amt = smart_extract_amt(text)
    cost = extract_cost(text)
    
    asset_type = "證券" if any(w in text for w in ["股", "張", "買", "成本"]) else "一般"
    
    if amt != 0:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO assets (name, amount, currency, type, cost) VALUES (?, ?, ?, ?, ?)', 
                     (text, amt, "TWD", asset_type, cost))
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
