import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_vStable.db')

# 修正 10萬 解析邏輯
def smart_extract_amt(text):
    text = text.replace(',', '').strip()
    wan_match = re.search(r'(\d+\.?\d*)\s*萬', text)
    if wan_match: return float(wan_match.group(1)) * 10000
    if '十萬' in text: return 100000
    if '百萬' in text: return 1000000
    nums = re.findall(r'-?\d+\.?\d*', text)
    return float(nums[0]) if nums else 0

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY, name TEXT, amount REAL)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    data = conn.execute('SELECT * FROM assets ORDER BY id DESC').fetchall()
    total = sum(item[2] for item in data)
    conn.close()
    return f"<h1>系統已恢復</h1><p>總資產：{total}</p><ul>" + "".join([f"<li>{i[1]}: {i[2]}</li>" for i in data]) + "</ul>"

@app.route('/process', methods=['POST'])
def process():
    # 這裡放你的解析邏輯...
    return redirect('/')

# 這是 Render 最喜歡的啟動方式
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
