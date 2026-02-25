import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "<h1>系統恢復成功！</h1><p>如果你看到這行，代表 Render 的 Start Command 終於改對了。</p>"

if __name__ == '__main__':
    # 這是 Render 要求的絕對格式
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
