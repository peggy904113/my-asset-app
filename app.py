import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
# 回歸 v15，這通常是你最穩定的版本號
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v15.db')

# --- 1. 基礎數字解析 ---
def cn_to_num(cn):
    if not cn: return 0
    digits = {'零':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    units = {'十':10,'百':100,'千':1000,'萬':10000}
    res, quota, tmp = 0, 1, 0
    try:
        for char in reversed(cn):
            if char in digits: tmp += digits[char] * quota
            elif char in units:
                quota = units[char]
                if quota >= 10000: res += tmp; tmp = 0; res *= quota; quota = 1
        return res + tmp
    except: return 0

def smart_extract_amt(text):
    text = text.replace(',', '')
    nums = re.findall(r'\d+\.?\d*', text)
    if nums: return float(nums[0])
    cn_nums = re.search(r'[零一二兩三四五六七八九十百千萬]+', text)
    if cn_nums: return cn_to_num(cn_nums.group())
    return 0

# --- 2. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, amount REAL, category TEXT, 
                    date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, target_amount REAL)')
    conn.execute('INSERT OR IGNORE INTO goals (id, target_amount) VALUES (1, 1000000)')
    conn.commit()
    conn.close()

init_db()

# --- 3. 基礎 HTML 模板 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回歸穩定版</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; padding: 20px; }
        .ai-card { background: #161b22; border: 1px solid #30363d; border-radius: 15px; padding: 18px; margin-top: 15px; }
        .btn-submit { background: #238636; border: none; color: white; width: 100%; padding: 10px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h5 class="text-center text-white">💰 穩定版記帳系統</h5>
        <div class="ai-card">
            <form action="/process" method="POST">
                <input type="text" name="user_input" class="form-control bg-dark text-white border-secondary mb-2" placeholder="輸入文字 (如: 郵局十萬)">
                <button class="btn-submit">送出</button>
            </form>
        </div>
        <div class="ai-card text-center">
            <p class="text-muted mb-1 small">總資產 (TWD)</p>
            <h2 class="text-white">${{ "{:,.0f}".format(total_val) }}</h2>
        </div>
        <div class="ai-card">
            <h6 class="mb-3">最近紀錄</h6>
            {% for item in
