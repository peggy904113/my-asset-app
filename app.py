import os
import sqlite3
import re
import json
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
# 升級到 v55 支援轉帳邏輯
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v55.db')

def smart_parser(text):
    text = text.replace(',', '').strip()
    
    # 提取金額
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '張' in text: amt *= 1000
        elif '萬' in text: amt *= 10000

    # 轉帳邏輯偵測
    transfer_match = re.search(r'(.+?)(\d+\.?\d*)\s*[萬|張]?\s*轉入(.+)', text)
    if transfer_match:
        from_bank = transfer_match.group(1).strip()
        to_bank = transfer_match.group(3).strip()
        return "TRANSFER", amt, from_bank, to_bank

    # 一般解析
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    clean_name = re.sub(r'\d+\.?\d*|萬|張|成本|買入|買|存款|活存|預備金|轉入|轉到', '', text).strip()
    
    category = "證券" if any(w in text for w in ['股', '張', '成本', '買入']) else "存款"
    return category, amt, clean_name, cost

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    display_name TEXT, amount REAL, category TEXT, cost REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    result = smart_parser(text)
    
    conn = sqlite3.connect(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if result[0] == "TRANSFER":
        # 處理轉帳：A 減、B 加
        amt, from_b, to_b = result[1], result[2], result[3]
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (from_b, -amt, "存款", now))
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (to_b, amt, "存款", now))
    else:
        cat, amt, name, cost = result
        if amt != 0:
            conn.execute('INSERT INTO assets (display_name, amount, category, cost, date) VALUES (?, ?, ?, ?, ?)', (name, amt, cat, cost, now))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# ... (其餘 index 與 HTML 模板保持與上一版一致，但增加分類加總邏輯)
