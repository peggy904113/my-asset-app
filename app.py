import os
import sqlite3
import re
import json
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
# 升級到 v70 支援買賣結算與損益紀錄
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v70.db')

def super_parser(text):
    text = text.replace(',', '').strip()
    
    # 提取金額/股數
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '張' in text: amt *= 1000
        elif '萬' in text: amt *= 10000

    # 1. 股票賣出模式 (計算損益)
    # 例如：賣出 2330 1張 售價 700
    if '賣出' in text or '賣' in text:
        price_match = re.search(r'(?:售價|價格|賣)\s*(\d+\.?\d*)', text)
        sell_price = float(price_match.group(1)) if price_match else 0
        name = re.sub(r'\d+\.?\d*|萬|張|賣出|賣|售價|價格', '', text).strip()
        return "SELL", amt, name, sell_price

    # 2. 轉帳/扣卡費模式
    transfer_match = re.search(r'(.+?)(?:\d+\.?\d*[萬張]?)\s*(?:轉到|轉入|匯給|移至|繳|扣)\s*(.+)', text)
    if transfer_match:
        from_acc = re.sub(r'\d+\.?\d*|萬|張', '', transfer_match.group(1)).strip()
        to_acc = transfer_match.group(2).strip()
        return "TRANSFER", amt, from_acc, to_acc

    # 3. 扣除模式 (支出)
    if any(w in text for w in ['扣掉', '支出', '減少', '刷卡', '卡費']):
        name = re.sub(r'\d+\.?\d*|萬|張|扣掉|支出|減少|刷卡|卡費', '', text).strip()
        return "DECREASE", amt, name if name else "支出", None

    # 4. 一般模式 (買進/存入)
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    name = re.sub(r'\d+\.?\d*|萬|張|成本|買進|買|存款|活存', '', text).strip()
    cat = "證券" if any(w in text for w in ['股', '張', '成本', '買進', '買']) else "存款"
    
    return "NORMAL", amt, name, {"cat": cat, "cost": cost}

def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    display_name TEXT, amount REAL, category TEXT, cost REAL, date TEXT, note TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    mode, val1, name1, extra = super_parser(text)
    conn = sqlite3.connect(db_path)
    now = datetime.now().strftime("%m-%d %H:%M")

    if mode == "SELL":
        # 賣出邏輯：尋找該股成本
        c = conn.cursor()
        c.execute('SELECT cost FROM assets WHERE display_name = ? AND category = "證券" ORDER BY id DESC LIMIT 1', (name1,))
        row = c.fetchone()
        buy_cost = row[0] if row else 0
        profit = (extra - buy_cost) * val1 if buy_cost > 0 else 0
        
        # 紀錄：減少股數，增加獲利現金
        conn.execute('INSERT INTO assets (display_name, amount, category, date, note) VALUES (?, ?, ?, ?, ?)', 
                     (name1, -val1, "證券", now, f"賣出結算：獲利 ${profit:,.0f}"))
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', ("證券結算現金", extra * val1, "存款", now))

    elif mode == "TRANSFER":
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (name1, -val1, "存款", now))
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (extra, val1, "存款", now))
    
    elif mode == "DECREASE":
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (name1, -val1, "存款", now))
    
    else: # NORMAL
        if val1 != 0:
            conn.execute('INSERT INTO assets (display_name, amount, category, cost, date) VALUES (?, ?, ?, ?, ?)', 
                         (name1, val1, extra['cat'], extra['cost'], now))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))
