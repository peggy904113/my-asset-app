<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 資產管家 Pro +</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #f4f7f6; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar { background: #1a2a6c; background: linear-gradient(to right, #b21f1f, #fdbb2d, #1a2a6c); color: white; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .ai-card { background: #fff; border-left: 5px solid #fdbb2d; border-radius: 12px; padding: 20px; margin-bottom: 25px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
        .card { border: none; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); margin-bottom: 20px; }
        .chart-container { position: relative; height: 300px; width: 100%; }
        .btn-custom { border-radius: 10px; padding: 10px; font-weight: bold; }
    </style>
</head>
<body>

<nav class="navbar mb-4">
    <div class="container text-center">
        <h2 class="m-0">AI 智能資產總覽</h2>
    </div>
</nav>

<div class="container">
    <div class="ai-card">
        <h5 class="fw-bold"><i class="bi bi-robot"></i> AI 理財助手建議</h5>
        <p id="ai-insight" class="text-muted">正在分析您的資產組合...</p>
        <hr>
        <small class="text-secondary">💡 提示：您的股票配置佔總資產約 <span id="stock-percent">--</span>%，建議維持在 40-60% 以分散風險。</small>
    </div>

    <div class="row mb-4">
        <div class="col-lg-8">
            <div class="card p-4">
                <h6 class="fw-bold">資產趨勢成長曲線</h6>
                <div class="chart-container">
                    <canvas id="growthChart"></canvas>
                </div>
            </div>
        </div>
        <div class="col-lg-4">
            <div class="card p-4">
                <h6 class="fw-bold">資產比例圖</h6>
                <div class="chart-container">
                    <canvas id="pieChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <div class="row">
        <div class="col-lg-4">
            <div class="card p-3 mb-3">
                <h6 class="fw-bold text-primary">現金/銀行/支出</h6>
                <form action="/add_cash" method="POST">
                    <input type="text" name="bank_name" class="form-control mb-2" placeholder="名稱">
                    <input type="number" step="any" name="amount" class="form-control mb-2" placeholder="金額 (支出輸入負數)">
                    <button class="btn btn-primary w-100 btn-custom">紀錄</button>
                </form>
            </div>
            <div class="card p-3">
                <h6 class="fw-bold text-success">證券/股票持倉</h6>
                <form action="/add_trade" method="POST">
                    <input type="text" name="symbol" class="form-control mb-2" placeholder="代號 (如 2330.TW)">
                    <input type="number" step="any" name="shares" class="form-control mb-2" placeholder="股數">
                    <button class="btn btn-success w-100 btn-custom">記錄持股</button>
                </form>
            </div>
        </div>

        <div class="col-lg-8">
            <div class="card p-3">
                <h6 class="fw-bold mb-3">資產細項</h6>
                <table class="table align-middle">
                    <thead><tr><th>項目</th><th>類型</th><th>金額/市值</th></tr></thead>
                    <tbody>
                        {% for item in cash_items %}
                        <tr><td>{{ item[1] }}</td><td><span class="badge bg-light text-dark">現金</span></td><td>${{ item[2] }}</td></tr>
                        {% endfor %}
                        {% for s in stocks %}
                        <tr><td>{{ s.symbol }}</td><td><span class="badge bg-success">股票</span></td><td>${{ s.value }}</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
    // --- 圖表數據初始化 ---
    const totalCash = {{ total_cash | replace(',', '') }};
    const totalStock = {{ total_stock_value | replace(',', '') }};
    
    // 1. 資產比例圖 (Pie Chart)
    const ctxPie = document.getElementById('pieChart').getContext('2d');
    new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: ['現金', '股票'],
            datasets: [{
                data: [totalCash, totalStock],
                backgroundColor: ['#3498db', '#2ecc71'],
                borderWidth: 0
            }]
        }
    });

    // 2. 成長曲線模擬 (Line Chart)
    // 這裡我們先用模擬數據，之後可以改為從資料庫抓取歷史紀錄
    const ctxLine = document.getElementById('growthChart').getContext('2d');
    new Chart(ctxLine, {
        type: 'line',
        data: {
            labels: ['1月', '2月', '3月', '4月', '5月', '6月'],
            datasets: [{
                label: '總資產變化',
                data: [totalCash*0.8, totalCash*0.85, totalCash*0.9, totalCash*0.95, totalCash*0.98, totalCash+totalStock],
                borderColor: '#1a2a6c',
                tension: 0.4,
                fill: true,
                backgroundColor: 'rgba(26, 42, 108, 0.1)'
            }]
        },
        options: { maintainAspectRatio: false }
    });

    // 3. AI 助理邏輯 (簡單模擬)
    const stockPercent = (totalStock / (totalCash + totalStock) * 100).toFixed(1);
    document.getElementById('stock-percent').innerText = stockPercent;
    
    let insight = "";
    if (totalStock == 0) insight = "您的資產目前全為現金。考慮到通貨膨脹，建議可以開始研究一些穩健的 ETF。";
    else if (stockPercent > 70) insight = "哇！您的投資非常積極。目前股市佔比偏高，請注意市場波動風險。";
    else insight = "您的資產配置非常平衡，這是一個很健康的財務表現！";
    document.getElementById('ai-insight').innerText = insight;

</script>
</body>
</html>
