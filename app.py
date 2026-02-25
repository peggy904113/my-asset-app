import yfinance as yf # 引入即時報價套件

def get_stock_info(code):
    """透過 yfinance 抓取台股名稱與即時價格"""
    try:
        # 台股代號後方需加上 .TW (上市) 或 .TWO (上櫃)
        # 這裡先預設嘗試上市，若失敗再嘗試上櫃
        ticker_code = f"{code}.TW"
        ticker = yf.Ticker(ticker_code)
        info = ticker.info
        
        # 抓取名稱與現價
        name = info.get('longName') or info.get('shortName') or code
        price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
        return name, price
    except:
        return code, 0

def super_parser(text):
    text = text.replace(',', '').strip()
    now = datetime.now()
    
    # 提取金額/股數
    amt = 0
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        amt = float(nums[0])
        if '萬' in text: amt *= 10000
        elif '張' in text: amt *= 1000

    # 1. 股票自動辨識
    stock_code_match = re.search(r'(\d{4,5})', text)
    if stock_code_match and any(w in text for w in ['買', '賣', '股', '張']):
        code = stock_code_match.group(1)
        # AI 自動去查即時名稱與股價
        real_name, real_price = get_stock_info(code)
        
        # 如果使用者有自訂成本，就用自訂的，否則用現價
        cost_match = re.search(r'(?:成本|售價|價格|買在|賣在)\s*(\d+\.?\d*)', text)
        final_price = float(cost_match.group(1)) if cost_match else real_price
        
        mode = "SELL" if '賣' in text else "NORMAL"
        return mode, amt, real_name, {"cat": "證券", "cost": final_price}

    # 2. 卡費邏輯 (維持原樣)
    if any(w in text for w in ['卡費', '信用卡']):
        bank = re.sub(r'\d+\.?\d*|萬|卡費|信用卡|刷卡|扣|繳', '', text).strip()
        return "DECREASE", amt, f"{bank} {now.month}月 卡費", "支出"

    # 3. 一般存款模式
    clean_name = re.sub(r'\d+\.?\d*|萬|存款|活存', '', text).strip()
    return "NORMAL", amt, clean_name, {"cat": "存款", "cost": 0}
