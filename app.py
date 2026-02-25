import os
import re
import psycopg2  # 引入 PostgreSQL 驅動
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# --- 這裡填入你在 Supabase 取得的網址 ---
# 建議把網址存在 Render 的 Environment Variables 裡比較安全
DATABASE_URL = os.environ.get('DATABASE_URL', '你的Supabase_URI網址')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# 初始化雲端資料庫表格
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS assets 
                   (id SERIAL PRIMARY KEY, 
                    display_name TEXT, amount REAL, category TEXT, cost REAL, date TEXT, note TEXT)''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ... (其餘 super_parser 解析邏輯維持不變) ...

@app.route('/process', methods=['POST'])
def process():
    text = request.form.get('user_input', '').strip()
    mode, val1, name1, extra = super_parser(text)
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%m-%d %H:%M")

    # 這裡的 SQL 語法稍微改為 PostgreSQL 格式 (%s)
    if mode == "SELL":
        cur.execute('SELECT cost FROM assets WHERE display_name = %s AND category = %s ORDER BY id DESC LIMIT 1', (name1, "證券"))
        row = cur.fetchone()
        buy_cost = row[0] if row else 0
        profit = (extra - buy_cost) * val1 if buy_cost > 0 else 0
        cur.execute('INSERT INTO assets (display_name, amount, category, date, note) VALUES (%s, %s, %s, %s, %s)', 
                     (name1, -val1, "證券", now, f"賣出結算：獲利 ${profit:,.0f}"))
        cur.execute('INSERT INTO assets (display_name, amount, category, date) VALUES (%s, %s, %s, %s)', ("證券結算現金", extra * val1, "存款", now))
    # ... 其餘邏輯以此類推 ...
    
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))
