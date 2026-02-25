import os
import sqlite3
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_v99.db')

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
    conn.close()
    return f"<h1>系統復活測試</h1><p>如果你看到這行，代表連線通了！</p><p>目前數量: {len(data)}</p>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
