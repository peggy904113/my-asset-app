import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <body style="background:#0d1117; color:#58a6ff; display:flex; flex-direction:column; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
        <h1 style="border:2px solid #58a6ff; padding:20px; border-radius:15px;">🚀 基礎連線已恢復正常</h1>
        <p style="color:white;">如果你看到這個畫面，代表你的 Render 設定對了！</p>
        <p style="color:gray;">請告訴我，我馬上把「10萬解析」和「舊版功能」裝回來。</p>
    </body>
    """

if __name__ == '__main__':
    # 這是修復 502 的唯一關鍵：必須讀取 PORT 環境變數
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
