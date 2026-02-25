import os
import sqlite3
import re
import json
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
# 使用新資料庫版本確保欄位對齊
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v60.db')

# --- 1. AI 智慧解析大腦 ---
def super_parser(text):
    text = text.replace(',', '').strip()
    
    # 提取金額與單位
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '張' in text: amt *= 1000
        elif '萬' in text: amt *= 10000

    # 判斷指令類型
    # A. 轉帳模式：[銀行A] [金額] 轉到/轉入 [銀行B]
    transfer_match = re.search(r'(.+?)(\d+\.?\d*[萬張]?)\s*(?:轉到|轉入|匯給|移至)\s*(.+)', text)
    if transfer_match:
        from_bank = re.sub(r'\d+\.?\d*|萬|張', '', transfer_match.group(1)).strip()
        to_bank = transfer_match.group(3).strip()
        return "TRANSFER", amt, from_bank, to_bank

    # B. 扣除模式：[銀行] 扣掉 [金額] 或 [銀行] [金額] 扣掉
    if '扣掉' in text or '支出' in text or '減少' in text:
        clean_name = re.sub(r'\d+\.?\d*|萬|張|扣掉|支出|減少', '', text).strip()
        return "DECREASE", amt, clean_name, None

    # C. 一般模式 (新增資產)
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    # 清洗名稱，移除數字、單位與動作詞
    clean_name = re.sub(r'\d+\.?\d*|萬|張|成本|買入|買|存款|活存|預備金', '', text).strip()
    category = "證券" if any(w in text for w in ['股', '張', '成本', '買入']) else "存款"
    
    return "NORMAL", amt, clean_name, {"cat": category, "cost": cost}

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    display_name TEXT, amount REAL, category TEXT, cost REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 2. 路由處理 ---
@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    mode, amt, name1, extra = super_parser(text)
    
    conn = sqlite3.connect(db_path)
    now = datetime.now().strftime("%m-%d %H:%M")

    if mode == "TRANSFER":
        # 轉帳：A減 B加
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (name1, -amt, "存款", now))
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (extra, amt, "存款", now))
    elif mode == "DECREASE":
        # 扣掉：直接存入負數
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (name1, -amt, "存款", now))
    else:
        # 一般：存入正數
        if amt != 0:
            conn.execute('INSERT INTO assets (display_name, amount, category, cost, date) VALUES (?, ?, ?, ?, ?)', 
                         (name1, amt, extra['cat'], extra['cost'], now))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# --- (index 頁面與之前分頁 HTML 相同，僅需確保呈現時有做 SUM 加總) ---
