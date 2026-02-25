import os
import re
import psycopg2
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# 從 Render 環境變數讀取連線資訊
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# 初始化資料庫（確保有 note 欄位來存細節）
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id SERIAL PRIMARY KEY, 
                    display_name TEXT, amount REAL, category TEXT, cost REAL, date TEXT, note TEXT)''')
    conn.commit()
    cur.close()
    conn.close()

# --- AI 智慧解析：強化卡費模式 ---
def super_parser(text):
    text = text.replace(',', '').strip()
    now = datetime.now()
    current_month = f"{now.month}月"
    
    # 提取金額
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '萬' in text: amt *= 10000

    # 1. 偵測「卡費」指令：[銀行名] [金額] 卡費 / 扣卡費 / 繳卡費
    if any(w in text for w in ['卡費', '信用卡', '刷卡']):
        # 提取銀行名稱
        bank_name = re.sub(r'\d+\.?\d*|萬|卡費|信用卡|刷卡|扣|繳|支付|支出', '', text).strip()
        if not bank_name: bank_name = "通用卡"
        
        # 格式化名稱：銀行名 + 月份 + 卡費
        formatted_name = f"{bank_name} {current_month} 卡費"
        return "DECREASE", amt, formatted_name, "支出"

    # 2. 轉帳模式
    transfer_match = re.search(r'(.+?)(?:\d+\.?\d*[萬]?)\s*(?:轉到|轉入|繳|扣)\s*(.+)', text)
    if transfer_match:
        from_acc = re.sub(r'\d+\.?\d*|萬', '', transfer_match.group(1)).strip()
        to_acc = transfer_match.group(2).strip()
        return "TRANSFER", amt, from_acc, to_acc

    # 3. 一般模式 (買進/存入)
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    clean_name = re.sub(r'\d+\.?\d*|萬|張|成本|買進|買|存款', '', text).strip()
    cat = "證券" if any(w in text for w in ['股', '張', '成本', '買進']) else "存款"
    
    return "NORMAL", amt, clean_name, {"cat": cat, "cost": cost}

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    mode, val, name, extra = super_parser(text)
    
    conn = get_db_connection()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%m-%d %H:%M")

    if mode == "DECREASE":
        # 銀行卡費模式：直接從該名稱扣除金額
        cur.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (%s, %s, %s, %s)', 
                    (name, -val, "支出", now_str))
    elif mode == "TRANSFER":
        cur.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (%s, %s, %s, %s)', (name, -val, "存款", now_str))
        cur.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (%s, %s, %s, %s)', (extra, val, "存款", now_str))
    else: # NORMAL
        if val != 0:
            cur.execute('INSERT INTO assets (display_name, amount, category, cost, date) VALUES (%s, %s, %s, %s, %s)', 
                        (name, val, extra['cat'], extra['cost'], now_str))
    
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

# --- (其餘 index 渲染與 HTML 保持不變) ---

if __name__ == '__main__':
    init_db() # 啟動時初始化雲端表格
    app.run(host='0.0.0.0', port=5000)
