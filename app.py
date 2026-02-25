import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 使用最基礎的資料庫名稱
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v1.db')

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>恢復穩定版</title></head>
<body style="background:#0d1117; color:white; padding:20px;">
    <h2>💰 基礎記帳模式 (連線正常)</h2>
    <form action="/process" method="POST">
        <input type="text" name="user_input" placeholder="例如：早餐 100" style="padding:10px; width:200px;">
        <button type="submit">送出</button>
    </form>
    <ul>
        {% for item in assets %}
        <li>{{ item[1] }}: ${{ item[2] }} <a href="/delete/{{ item[0] }}" style="color:red;">刪除</a></li>
        {% endfor %}
    </ul>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(db_path)
    assets = conn.execute('SELECT * FROM assets ORDER BY id DESC').fetchall()
    conn.close()
    return render_template_string(HTML_TEMPLATE, assets=assets)

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '')
    nums = re.findall(r'\d+', text)
    if nums:
        amt = float(nums[0])
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO assets (name, amount, category) VALUES (?, ?, ?)', (text, amt, "一般"))
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
