import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 換到 v35 確保支援證券與 AI 欄位
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v35.db')

def smart_extract_amt(text):
    text = text.replace(',', '').strip()
    wan_match = re.search(r'(\d+\.?\d*)\s*萬', text)
    if wan_match: return float(wan_match.group(1)) * 10000
    nums = re.findall(r'-?\d+\.?\d*', text)
    return float(nums[0]) if nums else 0

def init_db():
    conn = sqlite3.connect(db_path)
    # 增加 type (類別) 與 cost (成本) 欄位
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
        .ai-input { background: #0d1117; border: 1px solid #388bfd; border-radius: 30px; color: white; padding: 12px 20px; width: 100%; outline: none; }
        .ai-tip { font-size: 0.75rem; color: #f1e05a; background: rgba(241, 224, 90, 0.1); padding: 4px 8px; border-radius: 4px; display: inline-block; }
    </style>
</head>
<body>
    <div class="container py-4">
        <h5 class="text-center fw-bold mb-4">🤖 AI 財富診斷儀表板</h5>
        
        <form action="/process" method="POST" class="mb-4">
            <input type="text" name="user_input" class="ai-input" placeholder="例如: 買入 2330 1000股、美金 1000..." required>
        </form>

        <div class="row">
            <div class="col-md-7">
                <div class="main-card text-center">
                    <small class="text-muted">預估總資產 (TWD)</small>
                    <h2 class="fw-bold text-white">${{ "{:,.0f}".format(total_val) }}</h2>
                </div>
            </div>
            <div class="col-md-5">
                <div class="main-card" style="height: 140px; padding: 10px;">
                    <canvas id="assetChart"></canvas>
                </div>
            </div>
        </div>

        <div class="main-card">
            <h6 class="fw-bold mb-3">資產明細與 AI 建議</h6>
            {% for item in history %}
            <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-3">
                <div>
                    <div class="fw-bold text-white">{{ item[1] }}</div>
                    {% if item[4] == '證券' %}
                        <div class="ai-tip">🤖 AI 建議：定期觀察大盤，若獲利超 20% 可考慮分批停利</div>
                    {% else %}
                        <span class="badge bg-dark text-info" style="font-size: 0.6rem;">{{ item[3] }}</span>
                    {% endif %}
                </div>
                <div class="text-end">
                    <div class="fw-bold">${{ "{:,.0f}".format(item[2] * rates.get(item[3], 1.0)) }}</div>
                    <a href="/delete/{{ item[0] }}" class="text-danger small" style="text-decoration:none;">移除</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('assetChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
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
    c.execute('SELECT id, name, amount, currency, type FROM assets ORDER BY id DESC')
    history = c.fetchall()
    rates = {"美金": 32.5, "USD": 32.5, "日幣": 0.21, "JPY": 0.21, "TWD": 1.0}
    
    total_val = 0
    type_sums = {'一般': 0, '證券': 0}
    
    for item in history:
        val = item[2] * rates.get(item[3], 1.0)
        total_val += val
        type_sums[item[4]] = type_sums.get(item[4], 0) + val
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, history=history, total_val=total_val, rates=rates, type_sums=type_sums)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    amt = smart_extract_amt(text)
    
    # AI 判斷類別
    asset_type = "一般"
    if any(w in text for w in ["股", "張", "買入", "證券", "2330"]):
        asset_type = "證券"
    
    curr = "TWD"
    for c in ["美金", "USD", "日幣", "JPY"]:
        if c in text.upper(): curr = c; break

    if amt != 0:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO assets (name, amount, currency, type) VALUES (?, ?, ?, ?)', 
                     (text, amt, curr, asset_type))
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
