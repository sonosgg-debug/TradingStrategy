"""
engine.py
멀티스레딩(ThreadPoolExecutor) 기반 초고속 주가 수집 및
전략 A (눌림목) 조건 스크리닝 실행 엔진 모듈
"""

import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import FinanceDataReader as fdr

from data_loader import (
    KST, get_now_kst, get_market_universe, format_marcap,
    get_latest_expected_trading_day
)
from strategy_pullback import (
    calculate_pullback_indicators, evaluate_pullback_at_bar, PULLBACK_PRESETS
)


def fetch_stock_history_cached(code: str, start_date: str) -> pd.DataFrame:
    """
    단일 종목의 일봉 데이터를 다운로드하고 6대 기술적 지표 및 눌림목 지표를 계산합니다.
    """
    try:
        df = fdr.DataReader(code, start_date)
        if df is None or len(df) < 30:
            return None

        # 최근 5영업일 거래정지 또는 무거래 종목 제외
        recent_vol = df["Volume"].iloc[-5:].sum()
        if pd.isna(recent_vol) or recent_vol <= 0:
            return None

        # 장 개장 전 또는 당일 더미 봉(Volume=0) 방어 처리
        if df["Volume"].iloc[-1] == 0 and len(df) > 1:
            df = df.iloc[:-1]

        # 지표 계산
        df_ind = calculate_pullback_indicators(df)
        return df_ind
    except Exception:
        return None


def _process_stock_worker(
    code: str,
    name: str,
    market: str,
    marcap: float,
    start_date: str,
    target_date_str: str,
    min_trading_val_eok: float,
    params: dict
) -> dict:
    """
    단일 종목 스크리닝 워커 함수
    """
    try:
        df_ind = fetch_stock_history_cached(code, start_date)
        if df_ind is None or len(df_ind) < 25:
            return None

        # target_date에 해당하는 행 찾기
        idx = -1
        if target_date_str:
            clean_target = target_date_str.replace('-', '')
            matching_indices = [
                i for i, d in enumerate(df_ind.index)
                if (d.strftime('%Y%m%d') if hasattr(d, 'strftime') else str(d)[:10].replace('-', '')) == clean_target
            ]
            if matching_indices:
                idx = matching_indices[-1]
            else:
                # 지정 날짜 이전 중 가장 가까운 날짜
                prior_indices = [
                    i for i, d in enumerate(df_ind.index)
                    if (d.strftime('%Y%m%d') if hasattr(d, 'strftime') else str(d)[:10].replace('-', '')) <= clean_target
                ]
                if prior_indices:
                    idx = prior_indices[-1]
                else:
                    return None

        # 눌림목 조건 평가
        res = evaluate_pullback_at_bar(df_ind, idx=idx, params=params)
        if res is None:
            return None

        # 5일 평균 거래대금 최소 필터 검증 (사이드바 설정값)
        if min_trading_val_eok > 0:
            if res["trading_value_5d_eok"] < min_trading_val_eok:
                return None

        # 매수 조건 부합 여부 확인 (최소 점수 이상)
        min_score = params.get("min_score", 50)
        if res["score"] < min_score:
            return None

        # 시가총액 단위 환산
        marcap_won = marcap if marcap >= 1_000_000_000 else (marcap * 100_000_000)
        marcap_eok = int(round(marcap_won / 100_000_000))
        marcap_str = format_marcap(marcap)

        return {
            "종목코드": code,
            "종목명": name,
            "시장": market,
            "현재가": int(round(res["close"])),
            "등락률": round(res["change_rate"], 2),
            "시가총액": marcap_eok,
            "시가총액_표시": marcap_str,
            "5일평균거래대금": round(res["trading_value_5d_eok"], 1),
            "20일선 이격도": round(res["disparity_20"], 1),
            "IBS": round(res["ibs"], 2),
            "RSI(14)": round(res["rsi_14"], 1),
            "볼린저 %B": round(res["bb_percent"], 2),
            "거래량 비율": round(res["vol_ratio"], 1),
            "적합도 점수": res["score"],
            "투자의견": res["opinion_kr"],
            "투자의견_영문": res["opinion"],
            "is_buy": res["is_buy"],
            "checks": res["checks"]
        }
    except Exception:
        return None


def run_strategy_screening(
    market: str = "코스피 (KOSPI)",
    scope: str = "시총 상위 200 (쾌속 모드)",
    min_marcap_eok: int = 0,
    min_trading_val_eok: float = 0.0,
    target_date_str: str = None,
    params: dict = None,
    max_workers: int = 20,
    progress_callback = None
) -> pd.DataFrame:
    """
    멀티스레딩을 활용하여 전체 시장 유니버스를 대상으로 전략 조건 검색을 수행합니다.
    """
    if params is None:
        params = PULLBACK_PRESETS["Type A (보수적·안정적 지지 반등)"]

    if target_date_str is None:
        target_date_str = get_latest_expected_trading_day()

    # 1. 대상 유니버스 추출
    df_universe = get_market_universe(
        market=market,
        scope=scope,
        min_marcap_eok=min_marcap_eok
    )
    total_stocks = len(df_universe)
    if total_stocks == 0:
        return pd.DataFrame()

    # 200일선 계산을 위해 약 450일 전 데이터부터 조회
    start_date = (get_now_kst() - timedelta(days=450)).strftime("%Y-%m-%d")

    results = []
    completed_count = 0

    m_upper = market.upper() if market else ""
    is_all = "ALL" in m_upper or "전체" in market
    default_market = "KOSPI" if not ("KOSDAQ" in m_upper or "코스닥" in market) else "KOSDAQ"

    # 2. 멀티스레드 병렬 실행
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_stock = {}
        for _, row in df_universe.iterrows():
            row_mkt = str(row.get("Market", "")).upper()
            row_mkt_id = str(row.get("MarketId", "")).upper()
            if "KOSPI" in row_mkt or row_mkt_id == "STK":
                stock_market = "KOSPI"
            elif "KOSDAQ" in row_mkt or row_mkt_id == "KSQ":
                stock_market = "KOSDAQ"
            else:
                stock_market = default_market

            future = executor.submit(
                _process_stock_worker,
                row["Code"],
                row["Name"],
                stock_market,
                row["Marcap_Num"],
                start_date,
                target_date_str,
                min_trading_val_eok,
                params
            )
            future_to_stock[future] = row["Code"]

        for future in as_completed(future_to_stock):
            completed_count += 1
            if progress_callback:
                progress_callback(completed_count, total_stocks)
            try:
                res = future.result()
                if res is not None:
                    results.append(res)
            except Exception:
                pass

    if not results:
        return pd.DataFrame()

    df_res = pd.DataFrame(results)

    # 적합도 점수 내림차순, 시가총액 내림차순 정렬
    df_res = df_res.sort_values(by=["적합도 점수", "시가총액"], ascending=[False, False]).reset_index(drop=True)
    return df_res
