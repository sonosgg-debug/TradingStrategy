"""
strategy_pullback.py
전략 A: 눌림목(Pullback / Mean Reversion in Trend) 전략 모듈
- 6대 기술적 지표 및 눌림목 특화 지표(IBS, 20일 이격도, 거래량 수축비, 볼린저 %B 등) 계산
- Type A (보수적·안정적 지지 반등) & Type B (공격적·과매도 터치 반등) 기본 프리셋 제공
- 사용자 맞춤형 파라미터 필터링 및 종합 매수 적합도 스코어링(0~100점)
"""

import pandas as pd
import numpy as np
import ta


# 1. 전략 A 기본 프리셋 딕셔너리
PULLBACK_PRESETS = {
    "Type A (보수적·안정적 지지 반등)": {
        "description": "중장기 정배열 우량주가 20일선까지 건전한 조정을 거친 후, 거래량이 마르고 아래꼬리를 달며 반등하는 정석 눌림목",
        "long_ma": 120,               # 장기 추세선 (Close > MA)
        "require_ma_align": True,      # 20MA > 60MA 정배열 필수
        "disparity_min": 97.0,         # 20일선 이격도 하한 (%)
        "disparity_max": 103.0,        # 20일선 이격도 상한 (%)
        "touch_ma20": True,            # 당일 20일선 부근 터치 여부 (Low <= MA20 * 1.01)
        "vol_ratio_max": 80.0,         # 20일 평균 거래량 대비 당일 거래량 상한 (%) (거래량 수축)
        "ibs_min": 0.50,               # IBS 하한 ((C-L)/(H-L) >= 0.50)
        "rsi_min": 40.0,               # RSI(14) 하한
        "rsi_max": 58.0,               # RSI(14) 상한
        "bb_pct_min": 0.30,            # 볼린저밴드 %B 하한 (중심선 부근 지지)
        "bb_pct_max": 0.70,            # 볼린저밴드 %B 상한
        "macd_turnaround": True,       # MACD 히스토그램 상승 반전 (Hist[0] > Hist[1])
        "min_score": 60                # 매수 발굴 최소 적합도 점수
    },
    "Type B (공격적·과매도 터치 반등)": {
        "description": "장기 상승 추세 내에서 단기 급락으로 볼린저 밴드 하단 및 RSI 과매도 구간을 터치한 후 강한 반등을 노리는 공격적 타점",
        "long_ma": 200,               # 장기 추세선 (Close > MA 200)
        "require_ma_align": False,     # 일시적 데드크로스 허용
        "disparity_min": 88.0,         # 20일선 이격도 하한 (%)
        "disparity_max": 99.0,         # 20일선 이격도 상한 (%) (20일선 아래 이탈 구간)
        "touch_ma20": False,
        "vol_ratio_max": 150.0,        # 과매도 투매 물량 소화 허용
        "ibs_min": 0.35,               # 아래꼬리 형성 여부
        "rsi_min": 25.0,               # RSI(14) 하한 (극단 과매도 포함)
        "rsi_max": 45.0,               # RSI(14) 상한
        "bb_pct_min": 0.00,            # 볼린저밴드 %B 하한 (하단 밴드 터치)
        "bb_pct_max": 0.30,            # 볼린저밴드 %B 상한
        "macd_turnaround": True,       # MACD 히스토그램 하락세 둔화
        "min_score": 55                # 매수 발굴 최소 적합도 점수
    }
}


def calculate_pullback_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV 주가 데이터프레임에 눌림목 전략에 필요한 핵심 기술적 지표들을 추가합니다.
    """
    if df is None or len(df) < 20:
        return df

    df = df.copy()

    # 컬럼명 영문 표준화 (Open, High, Low, Close, Volume)
    col_map = {}
    for col in df.columns:
        c_low = str(col).lower()
        if "open" in c_low or "시가" in str(col):
            col_map[col] = "Open"
        elif "high" in c_low or "고가" in str(col):
            col_map[col] = "High"
        elif "low" in c_low or "저가" in str(col):
            col_map[col] = "Low"
        elif "close" in c_low or "종가" in str(col):
            col_map[col] = "Close"
        elif "volume" in c_low or "거래량" in str(col):
            col_map[col] = "Volume"

    if col_map:
        df = df.rename(columns=col_map)

    # 1. 이동평균선 (SMA: 5, 20, 60, 120, 200)
    df["SMA_5"] = df["Close"].rolling(window=5).mean()
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["SMA_60"] = df["Close"].rolling(window=60).mean()
    df["SMA_120"] = df["Close"].rolling(window=120).mean()
    df["SMA_200"] = df["Close"].rolling(window=200).mean()

    # 2. 20일선 이격도(Disparity, %)
    safe_sma20 = df["SMA_20"].replace(0, np.nan)
    df["Disparity_20"] = (df["Close"] / safe_sma20) * 100.0

    # 60일선 이격도(Disparity, %)
    safe_sma60 = df["SMA_60"].replace(0, np.nan)
    df["Disparity_60"] = (df["Close"] / safe_sma60) * 100.0

    # 3. IBS (Internal Bar Strength): (Close - Low) / (High - Low)
    # 분모가 0인 경우(점상한가/점하한가 등) 0.5로 대체
    hl_range = df["High"] - df["Low"]
    df["IBS"] = np.where(hl_range > 0, (df["Close"] - df["Low"]) / hl_range, 0.5)

    # Reverse IBS / Upper Shadow Ratio: (High - Close) / (High - Low)
    df["IBS_Reverse"] = np.where(hl_range > 0, (df["High"] - df["Close"]) / hl_range, 0.5)

    # 4. RSI (14) 및 단기 RSI (2)
    rsi14 = ta.momentum.RSIIndicator(close=df["Close"], window=14)
    df["RSI_14"] = rsi14.rsi()

    rsi2 = ta.momentum.RSIIndicator(close=df["Close"], window=2)
    df["RSI_2"] = rsi2.rsi()

    # 5. 볼린저 밴드 (20, 2)
    bb = ta.volatility.BollingerBands(close=df["Close"], window=20, window_dev=2)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Middle"] = bb.bollinger_mavg()
    df["BB_Lower"] = bb.bollinger_lband()
    df["BB_Percent"] = bb.bollinger_pband()  # %B (0 ~ 1)
    df["BB_Width"] = bb.bollinger_wband()

    # 6. MACD (12, 26, 9)
    macd = ta.trend.MACD(close=df["Close"], window_slow=26, window_fast=12, window_sign=9)
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()

    # 7. 거래량 지표: 5일, 20일 거래량 이동평균 및 비율
    df["VMA_5"] = df["Volume"].rolling(window=5).mean()
    df["VMA_20"] = df["Volume"].rolling(window=20).mean()
    safe_vma20 = df["VMA_20"].replace(0, np.nan)
    df["Vol_Ratio_20"] = (df["Volume"] / safe_vma20) * 100.0  # 당일 거래량 / 20일 평균 (%)

    # 거래대금 (종가 * 거래량) 및 5일 평균 거래대금 (단위: 억원)
    df["Trading_Value_Won"] = df["Close"] * df["Volume"]
    df["Trading_Value_5D_Eok"] = df["Trading_Value_Won"].rolling(window=5).mean() / 100_000_000.0

    return df


def evaluate_pullback_at_bar(df: pd.DataFrame, idx: int = -1, params: dict = None) -> dict:
    """
    특정 캔들(기본값: 최신봉 -1) 시점에서 눌림목 전략 조건 충족 여부와 적합도 점수(0~100점)를 계산합니다.
    """
    if df is None or len(df) < 25:
        return None

    if params is None:
        params = PULLBACK_PRESETS["Type A (보수적·안정적 지지 반등)"]

    n = len(df)
    target_idx = idx if idx >= 0 else n + idx
    if target_idx < 1 or target_idx >= n:
        return None

    cur = df.iloc[target_idx]
    prev = df.iloc[target_idx - 1]

    close = float(cur["Close"])
    open_p = float(cur.get("Open", close))
    high = float(cur["High"])
    low = float(cur["Low"])
    volume = float(cur["Volume"])

    sma20 = float(cur["SMA_20"]) if pd.notna(cur.get("SMA_20")) else close
    sma60 = float(cur["SMA_60"]) if pd.notna(cur.get("SMA_60")) else close
    sma120 = float(cur["SMA_120"]) if pd.notna(cur.get("SMA_120")) else None
    sma200 = float(cur["SMA_200"]) if pd.notna(cur.get("SMA_200")) else None

    disparity_20 = float(cur["Disparity_20"]) if pd.notna(cur.get("Disparity_20")) else 100.0
    ibs = float(cur["IBS"]) if pd.notna(cur.get("IBS")) else 0.5
    rsi14 = float(cur["RSI_14"]) if pd.notna(cur.get("RSI_14")) else 50.0
    rsi2 = float(cur["RSI_2"]) if pd.notna(cur.get("RSI_2")) else 50.0
    bb_pct = float(cur["BB_Percent"]) if pd.notna(cur.get("BB_Percent")) else 0.5
    bb_lower = float(cur["BB_Lower"]) if pd.notna(cur.get("BB_Lower")) else close
    macd_val = float(cur["MACD"]) if pd.notna(cur.get("MACD")) else 0.0
    macd_hist = float(cur["MACD_Hist"]) if pd.notna(cur.get("MACD_Hist")) else 0.0
    prev_macd_hist = float(prev["MACD_Hist"]) if pd.notna(prev.get("MACD_Hist")) else 0.0
    vol_ratio = float(cur["Vol_Ratio_20"]) if pd.notna(cur.get("Vol_Ratio_20")) else 100.0
    trading_val_5d_eok = float(cur["Trading_Value_5D_Eok"]) if pd.notna(cur.get("Trading_Value_5D_Eok")) else 0.0

    # ------------------ 조건별 평가 및 점수 산정 ------------------
    score = 0
    checks = {}

    # 1. 장기 추세 필터 (배점: 15점)
    long_ma_period = params.get("long_ma", 120)
    target_long_ma = sma120 if long_ma_period == 120 else sma200
    if target_long_ma is not None:
        cond_long = close >= target_long_ma
        checks["장기추세 (Close > MA)"] = cond_long
        if cond_long:
            score += 15
    else:
        checks["장기추세 (Close > MA)"] = True
        score += 10

    # 2. 중기 이평 정배열 (배점: 15점)
    require_align = params.get("require_ma_align", True)
    if require_align:
        cond_align = sma20 > sma60
        checks["중기 정배열 (20MA > 60MA)"] = cond_align
        if cond_align:
            score += 15
    else:
        checks["중기 정배열 (20MA > 60MA)"] = True
        score += 10

    # 3. 20일선 이격도 및 눌림목 도달 (배점: 25점)
    disp_min = params.get("disparity_min", 97.0)
    disp_max = params.get("disparity_max", 103.0)
    cond_disp = (disp_min <= disparity_20 <= disp_max)
    checks["20일선 이격도 수렴"] = cond_disp
    if cond_disp:
        score += 15

    touch_ma20 = params.get("touch_ma20", False)
    if touch_ma20:
        cond_touch = (low <= sma20 * 1.015) and (close >= sma20 * 0.985)
        checks["20일선 지지/터치"] = cond_touch
        if cond_touch:
            score += 10
    else:
        score += 5
        checks["20일선 지지/터치"] = True

    # 4. 거래량 수축 (배점: 15점)
    vol_max = params.get("vol_ratio_max", 80.0)
    cond_vol = (vol_ratio <= vol_max)
    checks["거래량 수축 (조정 시 급감)"] = cond_vol
    if cond_vol:
        score += 15
    elif vol_ratio <= 100.0:
        score += 8

    # 5. IBS 필터 (아래꼬리 및 반등 강도, 배점: 15점)
    ibs_threshold = params.get("ibs_min", 0.50)
    cond_ibs = (ibs >= ibs_threshold)
    checks["IBS 반등 지지력"] = cond_ibs
    if cond_ibs:
        score += 15
    elif ibs >= 0.40:
        score += 7

    # 6. 보조지표 (RSI, 볼린저밴드, MACD, 배점: 15점)
    rsi_min = params.get("rsi_min", 40.0)
    rsi_max = params.get("rsi_max", 58.0)
    cond_rsi = (rsi_min <= rsi14 <= rsi_max)
    checks["RSI(14) 눌림목 구간"] = cond_rsi
    if cond_rsi:
        score += 5

    bb_min = params.get("bb_pct_min", 0.30)
    bb_max = params.get("bb_pct_max", 0.70)
    cond_bb = (bb_min <= bb_pct <= bb_max)
    checks["볼린저밴드 %B 위치"] = cond_bb
    if cond_bb:
        score += 5

    macd_turn = params.get("macd_turnaround", True)
    cond_macd = True
    if macd_turn:
        cond_macd = (macd_hist > prev_macd_hist) or (macd_val > 0)
        checks["MACD 턴어라운드"] = cond_macd
        if cond_macd:
            score += 5
    else:
        checks["MACD 턴어라운드"] = True
        score += 5

    score = int(np.clip(score, 0, 100))

    # 종합 의견 결정
    min_score_required = params.get("min_score", 55)
    is_buy = (score >= min_score_required) and all(checks.values())

    if score >= 75 and is_buy:
        opinion = "STRONG BUY"
        opinion_kr = "강력 매수"
    elif is_buy:
        opinion = "BUY"
        opinion_kr = "매수"
    elif score >= 50:
        opinion = "WATCH"
        opinion_kr = "관망/대기"
    else:
        opinion = "PASS"
        opinion_kr = "제외"

    # 전일 대비 등락률
    prev_close = float(prev["Close"])
    change_rate = ((close - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0

    return {
        "is_buy": is_buy,
        "score": score,
        "opinion": opinion,
        "opinion_kr": opinion_kr,
        "close": close,
        "change_rate": change_rate,
        "volume": volume,
        "vol_ratio": vol_ratio,
        "disparity_20": disparity_20,
        "ibs": ibs,
        "rsi_14": rsi14,
        "rsi_2": rsi2,
        "bb_percent": bb_pct,
        "macd_hist": macd_hist,
        "trading_value_5d_eok": trading_val_5d_eok,
        "checks": checks
    }
