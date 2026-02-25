import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 使用當前恢復成功的資料庫路徑
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_final.db')

# --- 1. AI 數字解析 (解決 10萬變 10元) ---
def smart_extract_amt(text):
    text = text.replace(',', '').strip()
    # 優先處理「數字+萬」格式
    wan_match = re.search(r'(\d+\.?\d*)\s*萬', text)
    if wan_match:
        return float(wan_match.group(1)) * 10000
    # 處理純數字
    nums = re.findall(r'-?\d+\.?\d*', text)
    if nums:
        return float(nums[0])
    return 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    # 增加 currency 欄位支援外幣
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, currency TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. 專業深色介面 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>資產管理助理</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .main-card { background: #161b22; border: 1px solid #30363d; border-radius: 15px; padding: 25px; margin-top: 20px; }
        .ai-input { background: #0d1117; border: 2px solid #388bfd; border-radius: 30px; color: white; padding: 12px 25px; width: 100%; outline: none; }
        .asset-val { font-size: 2.5rem; font-weight: bold; color: #ffffff; }
        .currency-badge { font-size: 0.7rem; background: #30363d; color: #58a6ff; padding: 2px 8px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="text-center mb-4">
            <h4 class="fw-bold">🤖 智慧資產助手</h4>
        </div>

        <form action="/process" method="POST" class="mb-4">
            <input type="text" name="user_input" class="ai-input" placeholder="試試輸入：10萬、美金 1000、日幣五萬..." required autofocus>
        </form>

        <div class="main-card text-center mb-4">
            <div class="text-muted small">預估總資產 (折合台幣)</div>
            <div class="asset-val">${{ "{:,.0f}".format(total_val) }}</div>
        </div>

        <div class="main-card">
            <h6 class="fw-bold mb-3">最近資產變動</h6>
            {% for item in history %}
            <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-3">
                <div>
                    <div class="fw-bold text-white">{{ item[1] }}</div>
                    <span class="currency-badge">{{ item[3] }}</span>
                </div>
                <div class="text-end">
                    <div class="fw-bold {{ 'text-success' if item[2] >= 0 else 'text-danger' }}">
                        ${{ "{:,.0f}".format(item[2] * rates.get(item[3], 1.0)) }}
                    </div>
                    <a href="/delete/{{ item[0] }}" class="text-danger small" style="text-decoration:none;">移除</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 確保抓取所有欄位包含幣別
    c.execute('SELECT id, name, amount, currency FROM assets ORDER BY id DESC')
    history = c.fetchall()
    
    # 預設匯率 (避免連網抓取導致 502)
    rates = {"美金": 32.5, "USD": 32.5, "日幣": 0.21, "JPY": 0.21, "TWD": 1.0}
    
    total_val = 0
    for item in history:
        # 計算折合台幣總值
        total_val += item[2] * rates.get(item[3], 1.0)
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, history=history, total_val=total_val, rates=rates)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    amt = smart_extract_amt(text)
    
    # 自動偵測幣別
    curr = "TWD"
    for c in ["美金", "USD", "日幣", "JPY"]:
        if c in text.upper():
            curr = c
            break

    if amt != 0:
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO assets (name, amount, currency) VALUES (?, ?, ?)', (text, amt, curr))
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
