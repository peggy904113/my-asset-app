import os
import sqlite3
import re
import json
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v65.db')

# --- 1. AI 智慧解析：新增卡費偵測 ---
def super_parser(text):
    text = text.replace(',', '').strip()
    
    # 提取金額
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '萬' in text: amt *= 10000
        elif '張' in text: amt *= 1000

    # A. 轉帳模式 (包含繳卡費)
    # 例如：中信轉2萬繳卡費、郵局轉到中信
    transfer_match = re.search(r'(.+?)(?:\d+\.?\d*[萬張]?)\s*(?:轉到|轉入|匯給|移至|繳|扣)\s*(.+)', text)
    if transfer_match:
        from_acc = re.sub(r'\d+\.?\d*|萬|張', '', transfer_match.group(1)).strip()
        to_acc = transfer_match.group(2).strip()
        return "TRANSFER", amt, from_acc, to_acc

    # B. 支出/扣掉模式
    # 例如：中信扣卡費 5000、生活費支出 3000
    if any(w in text for w in ['扣掉', '支出', '減少', '刷卡', '卡費']):
        clean_name = re.sub(r'\d+\.?\d*|萬|張|扣掉|支出|減少|刷卡|卡費', '', text).strip()
        if not clean_name: clean_name = "信用卡/支出"
        return "DECREASE", amt, clean_name, None

    # C. 一般存入模式
    cost_match = re.search(r'成本\s*(\d+\.?\d*)', text)
    cost = float(cost_match.group(1)) if cost_match else 0
    clean_name = re.sub(r'\d+\.?\d*|萬|張|成本|買入|買|存款|活存', '', text).strip()
    category = "證券" if any(w in text for w in ['股', '張', '成本', '買入']) else "存款"
    
    return "NORMAL", amt, clean_name, {"cat": category, "cost": cost}

# --- (資料庫與路由邏輯) ---
@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    mode, amt, name1, extra = super_parser(text)
    conn = sqlite3.connect(db_path)
    now = datetime.now().strftime("%m-%d %H:%M")

    if mode == "TRANSFER":
        # 轉帳或繳費：來源帳戶減，目的(或卡費)紀錄
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (name1, -amt, "存款", now))
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (extra, amt, "支出", now))
    elif mode == "DECREASE":
        # 直接扣除
        conn.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (?, ?, ?, ?)', (name1, -amt, "存款", now))
    else:
        if amt != 0:
            conn.execute('INSERT INTO assets (display_name, amount, category, cost, date) VALUES (?, ?, ?, ?)', (name1, amt, extra['cat'], extra['cost'], now))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))
