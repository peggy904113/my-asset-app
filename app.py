import os
import sqlite3
import re
import json
import io
import csv
from flask import Flask, render_template_string, request, redirect, url_for, Response
from datetime import datetime

app = Flask(__name__)

# 因為免費版沒 Disk，我們先存在當前路徑，並提醒你定期備份
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets_backup_safe.db')

# ... (其餘解析邏輯 super_parser 維持不變) ...

# --- 新增匯出功能，讓你在更新前可以先存檔 ---
@app.route('/export')
def export_data():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM assets')
    rows = c.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', '名稱', '金額', '類別', '成本', '日期', '備註'])
    writer.writerows(rows)
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=assets_backup.csv"}
    )
