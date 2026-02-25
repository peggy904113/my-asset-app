import csv
from flask import Response

# ... (保留之前的 super_parser 和路由)

@app.route('/export')
def export_data():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM assets')
    rows = c.fetchall()
    
    # 建立 CSV 格式
    def generate():
        data = io.StringIO()
        w = csv.writer(data)
        w.writerow(('ID', '名稱', '金額', '類別', '成本', '日期', '備註'))
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        for row in rows:
            w.writerow(row)
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="my_assets_backup.csv")
    return response

# ... (HTML 模板中可以在總覽分頁加一個 <a href="/export">備份資料</a>)
