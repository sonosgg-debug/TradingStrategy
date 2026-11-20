"""
data_loader.py
한국거래소(KRX) 주식 시장 거래일 계산, 공휴일 방어,
상장 종목 유니버스 및 시가총액/유동성 필터링 데이터 로더 모듈
"""

import os
import io
import time
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import FinanceDataReader as fdr

# 한국 표준시(KST, UTC+9)
KST = timezone(timedelta(hours=9))

# 한국거래소(KRX) 정규 휴장일 및 법정 공휴일 (2024~2027)
KRX_HOLIDAYS = {
    # 2024
    '20240101', '20240209', '20240212', '20240301', '20240410', '20240501', '20240506',
    '20240515', '20240606', '20240815', '20240916', '20240917', '20240918', '20241001',
    '20241003', '20241009', '20241225', '20241231',
    # 2025
    '20250101', '20250128', '20250129', '20250130', '20250303', '20250501', '20250505',
    '20250506', '20250606', '20250815', '20251003', '20251006', '20251007', '20251008',
    '20251009', '20251225', '20251231',
    # 2026
    '20260101', '20260216', '20260217', '20260218', '20260302', '20260501', '20260505',
    '20260525', '20260603', '20260606', '20260817', '20260924', '20260925', '20261005',
    '20261009', '20261225', '20261231',
    # 2027
    '20270101', '20270208', '20270209', '20270210', '20270301', '20270503', '20270505',
    '20270513', '20270607', '20270816', '20270914', '20270915', '20270916', '20271004',
    '20271011', '20271225', '20271231'
}

_CACHED_TRADING_DAYS = None
_CACHED_KRX_LISTING_DF = None
_CACHED_FALLBACK_MARCAP = None


def get_now_kst() -> datetime:
    """한국 표준시(KST, UTC+9) 현재 datetime 객체 반환"""
    return datetime.now(KST)


def is_krx_trading_day(date_val) -> bool:
    """주어진 날짜가 실제 KRX 거래일(주말 및 휴장일 제외)인지 판별"""
    if date_val is None:
        return False
    if isinstance(date_val, datetime):
        d_obj = date_val.date()
    elif isinstance(date_val, str):
        clean_date = date_val.replace('-', '').strip()
        try:
            d_obj = datetime.strptime(clean_date, "%Y%m%d").date()
        except Exception:
            return False
    else:
        d_obj = date_val

    d_str = d_obj.strftime("%Y%m%d")
    return (d_obj.weekday() < 5) and (d_str not in KRX_HOLIDAYS)


def get_krx_trading_days(count: int = 120) -> list:
    """
    한국거래소(KRX) 실제 거래일(개장일) 목록 (0.00초 즉시 반환 + 네이버 금융 2초 타임아웃 보강)
    """
    global _CACHED_TRADING_DAYS
    if _CACHED_TRADING_DAYS is not None and len(_CACHED_TRADING_DAYS) >= count:
        return _CACHED_TRADING_DAYS

    # 1단계: 휴장일 리스트 기반 기본 거래일 계산 (즉시 0.00초)
    fallback_days = []
    d = get_now_kst().date()
    for _ in range(count * 3):
        d_str = d.strftime('%Y%m%d')
        if d.weekday() < 5 and d_str not in KRX_HOLIDAYS:
            fallback_days.append(d_str)
            if len(fallback_days) >= count:
                break
        d -= timedelta(days=1)
    default_days = sorted(fallback_days)

    # 2단계: 네이버 증시 API 동적 검증 (2초 타임아웃)
    days = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        pages_needed = max(1, (count + 59) // 60)
        for page in range(1, min(pages_needed + 1, 4)):
            url = f'https://m.stock.naver.com/api/stock/005930/price?pageSize=60&page={page}'
            r = requests.get(url, headers=headers, timeout=2.0)
            if r.status_code == 200:
                items = r.json()
                if items and isinstance(items, list):
                    days.extend([
                        item['localTradedAt'].replace('-', '')
                        for item in items
                        if isinstance(item, dict) and 'localTradedAt' in item
                    ])
                else:
                    break
    except Exception:
        pass

    if days and len(days) >= count:
        _CACHED_TRADING_DAYS = sorted(list(set(days)))
    else:
        _CACHED_TRADING_DAYS = default_days

    return _CACHED_TRADING_DAYS


def get_latest_expected_trading_day(target_date=None, **kwargs) -> str:
    """
    [가이드 04 준수] 언제 접속하더라도 확정 마감된 최신 실제 거래일을 YYYY-MM-DD 형태로 반환.
    - target_date가 지정된 경우: 해당 날짜가 거래일이면 유지, 휴장일이면 직전 거래일로 역추적
    - target_date가 없는 경우: 15:45 이전, 새벽(00:00~08:59), 주말, 공휴일엔 전일/직전 금요일로 역추적
    """
    now_kst = get_now_kst()
    today = now_kst.date()

    if target_date is not None:
        if isinstance(target_date, str):
            clean_str = target_date.replace('-', '').strip()
            try:
                cur_d = datetime.strptime(clean_str, "%Y%m%d").date()
            except Exception:
                cur_d = today
        elif isinstance(target_date, datetime):
            cur_d = target_date.date()
        else:
            cur_d = target_date

        # 미래 날짜는 오늘로 캡
        if cur_d > today:
            cur_d = today

        # 해당 날짜가 오늘인 경우 15:45 마감 전이면 전일로 이동
        if cur_d == today:
            if not (now_kst.hour > 15 or (now_kst.hour == 15 and now_kst.minute >= 45)):
                cur_d -= timedelta(days=1)

        # 직전 유효 거래일 역추적
        for _ in range(60):
            if is_krx_trading_day(cur_d):
                return cur_d.strftime("%Y-%m-%d")
            cur_d -= timedelta(days=1)
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # 오늘이 평일이고 15:45 이후이며 거래일이면 오늘 반환
    if (now_kst.hour > 15 or (now_kst.hour == 15 and now_kst.minute >= 45)):
        if is_krx_trading_day(today):
            return today.strftime("%Y-%m-%d")

    # 장전, 새벽, 주말, 공휴일: 직전 실제 개장 거래일 역추적
    d = today - timedelta(days=1)
    for _ in range(60):
        if is_krx_trading_day(d):
            return d.strftime("%Y-%m-%d")
        d -= timedelta(days=1)

    return (today - timedelta(days=1)).strftime("%Y-%m-%d")


def is_valid_screening_stock(code: str, name: str) -> bool:
    """
    스크리닝 잡음 제거: 우선주, 스팩(SPAC), ETF/ETN, 리츠/투융자회사 제외
    """
    code_str = str(code).strip()
    name_str = str(name).strip()

    # 1. 우선주 배제 (보통 끝자리 '0'이 아니거나 명칭에 '우' 포함)
    if not code_str.endswith('0'):
        return False
    if name_str.endswith('우') or ('우B' in name_str) or ('우C' in name_str):
        return False

    # 2. 스팩(SPAC) 배제
    if '스팩' in name_str:
        return False

    # 3. ETF / ETN 배제
    etf_prefixes = ['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'SOL', 'HANARO', 'KOSEF', 'ARIRANG', 'PLUS', 'TIMEFOLIO']
    for prefix in etf_prefixes:
        if name_str.startswith(prefix):
            return False

    # 4. 리츠, 인프라투융자회사 배제
    if name_str.endswith('리츠') or '투융자' in name_str:
        return False

    return True


def format_marcap(val) -> str:
    """
    시가총액(원 단위 숫자)을 'X조 Y,ZZZ억원' 또는 'Z,ZZZ억원' 문자열로 포맷팅
    """
    if pd.isna(val) or val <= 0:
        return "-"

    if val >= 1_000_000_000:
        marcap_won = val
    else:
        marcap_won = val * 100_000_000

    eok = marcap_won / 100_000_000
    if eok >= 10_000:
        jo = int(eok // 10_000)
        rem_eok = int(eok % 10_000)
        if rem_eok > 0:
            return f"{jo:,}조 {rem_eok:,}억원"
        return f"{jo:,}조원"
    else:
        return f"{int(eok):,}억원"


def get_krx_raw_listing(m: str = "ALL") -> pd.DataFrame:
    """
    KRX 상장 종목 목록 수집 (3단계 안전 폴백)
    1단계: fdr 직접 시도
    2단계: fdr KOSPI+KOSDAQ 교차 호출
    3단계: GitHub fdr_krx_data_cache 공식 백업 저장소 파싱
    """
    global _CACHED_KRX_LISTING_DF
    m_upper = m.upper() if m else "ALL"
    is_all = "ALL" in m_upper or "전체" in m

    # 1단계: fdr 직접 호출
    try:
        if is_all:
            df = fdr.StockListing("KRX")
        else:
            target_market = "KOSPI" if "KOSPI" in m_upper or "코스피" in m else "KOSDAQ"
            df = fdr.StockListing(target_market)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    # 2단계: fdr 교차 호출
    try:
        if is_all:
            df_k = fdr.StockListing("KOSPI")
            df_q = fdr.StockListing("KOSDAQ")
            df_combined = pd.concat([df_k, df_q], ignore_index=True)
            if not df_combined.empty:
                return df_combined
        else:
            target_market = "KOSPI" if "KOSPI" in m_upper or "코스피" in m else "KOSDAQ"
            df_all = fdr.StockListing("KRX")
            if df_all is not None and not df_all.empty:
                target_id = "STK" if target_market == "KOSPI" else "KSQ"
                if "Market" in df_all.columns:
                    df = df_all[df_all["Market"].str.upper().str.contains(target_market)].copy()
                elif "MarketId" in df_all.columns:
                    df = df_all[df_all["MarketId"] == target_id].copy()
                else:
                    df = df_all.copy()
                if not df.empty:
                    return df
    except Exception:
        pass

    # 3단계: GitHub fdr_krx_data_cache 공식 백업 저장소
    if _CACHED_KRX_LISTING_DF is None or _CACHED_KRX_LISTING_DF.empty:
        base_url = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/"
        today = get_now_kst()
        for days_back in range(0, 11):
            target_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
            url = f"{base_url}{target_date}.csv"
            try:
                resp = requests.get(url, timeout=3.5)
                if resp.status_code == 200 and resp.text:
                    df_raw = pd.read_csv(io.StringIO(resp.text), dtype={"Code": str, "ISU_SRT_CD": str}, low_memory=False)
                    if df_raw is not None and not df_raw.empty:
                        _CACHED_KRX_LISTING_DF = df_raw
                        break
            except Exception:
                continue

    if _CACHED_KRX_LISTING_DF is not None and not _CACHED_KRX_LISTING_DF.empty:
        df_all = _CACHED_KRX_LISTING_DF.copy()
        if is_all:
            return df_all
        target_market = "KOSPI" if "KOSPI" in m_upper or "코스피" in m else "KOSDAQ"
        target_id = "STK" if target_market == "KOSPI" else "KSQ"
        if "Market" in df_all.columns:
            df = df_all[df_all["Market"].str.upper().str.contains(target_market)].copy()
        elif "MarketId" in df_all.columns:
            df = df_all[df_all["MarketId"] == target_id].copy()
        else:
            df = df_all.copy()
        return df

    return pd.DataFrame()


def get_fallback_marcap_map() -> dict:
    """시가총액 결측치 보정을 위한 최근 10영업일 백업 맵"""
    global _CACHED_FALLBACK_MARCAP, _CACHED_KRX_LISTING_DF
    if _CACHED_FALLBACK_MARCAP is not None and len(_CACHED_FALLBACK_MARCAP) > 0:
        return _CACHED_FALLBACK_MARCAP

    if _CACHED_KRX_LISTING_DF is not None and not _CACHED_KRX_LISTING_DF.empty:
        code_col = "Code" if "Code" in _CACHED_KRX_LISTING_DF.columns else "ISU_SRT_CD"
        marcap_col = None
        for col in ["Marcap", "MKTCAP", "시가총액"]:
            if col in _CACHED_KRX_LISTING_DF.columns:
                marcap_col = col
                break
        if marcap_col and code_col in _CACHED_KRX_LISTING_DF.columns:
            valid_series = pd.to_numeric(_CACHED_KRX_LISTING_DF[marcap_col], errors="coerce")
            if valid_series.notna().sum() > 500:
                _CACHED_FALLBACK_MARCAP = dict(
                    zip(_CACHED_KRX_LISTING_DF[code_col].astype(str).str.zfill(6), valid_series.fillna(0))
                )
                return _CACHED_FALLBACK_MARCAP

    base_url = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/"
    today = get_now_kst()
    for days_back in range(0, 11):
        target_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"{base_url}{target_date}.csv"
        try:
            resp = requests.get(url, timeout=3.0)
            if resp.status_code != 200:
                continue
            df = pd.read_csv(io.StringIO(resp.text), dtype={"Code": str, "ISU_SRT_CD": str}, low_memory=False)
            code_col = "Code" if "Code" in df.columns else "ISU_SRT_CD"
            marcap_col = None
            for col in ["Marcap", "MKTCAP", "시가총액"]:
                if col in df.columns:
                    marcap_col = col
                    break
            if marcap_col and code_col in df.columns:
                valid_series = pd.to_numeric(df[marcap_col], errors="coerce")
                if valid_series.notna().sum() > 500:
                    df["clean_code"] = df[code_col].astype(str).str.zfill(6)
                    df["clean_marcap"] = valid_series.fillna(0)
                    _CACHED_FALLBACK_MARCAP = dict(zip(df["clean_code"], df["clean_marcap"]))
                    return _CACHED_FALLBACK_MARCAP
        except Exception:
            continue

    return {}


def get_market_universe(
    market: str = "코스피 (KOSPI)",
    scope: str = "시총 상위 200 (쾌속 모드)",
    min_marcap_eok: int = 0,
    **kwargs
) -> pd.DataFrame:
    """
    지정된 시장과 범위, 최소 시가총액을 만족하는 종목 유니버스 반환
    """
    m_clean = "ALL"
    if "코스피" in market or "KOSPI" in market.upper():
        if "코스닥" not in market and "전체" not in market and "ALL" not in market.upper():
            m_clean = "KOSPI"
    elif "코스닥" in market or "KOSDAQ" in market.upper():
        m_clean = "KOSDAQ"

    df_listing = get_krx_raw_listing(m_clean)
    if df_listing is None or df_listing.empty:
        return pd.DataFrame()

    # 필수 컬럼 정리
    if "Code" not in df_listing.columns and "Symbol" in df_listing.columns:
        df_listing["Code"] = df_listing["Symbol"]
    if "Code" not in df_listing.columns and "ISU_SRT_CD" in df_listing.columns:
        df_listing["Code"] = df_listing["ISU_SRT_CD"]

    df_listing["Code"] = df_listing["Code"].astype(str).str.zfill(6)

    # 시장 필터
    if m_clean != "ALL":
        if "MarketId" in df_listing.columns:
            target_id = "STK" if m_clean == "KOSPI" else "KSQ"
            if (df_listing["MarketId"] == target_id).any():
                df_listing = df_listing[df_listing["MarketId"] == target_id].copy()
        elif "Market" in df_listing.columns:
            if (df_listing["Market"].str.upper() == m_clean).any():
                df_listing = df_listing[df_listing["Market"].str.upper() == m_clean].copy()
    else:
        # ALL: KONEX 등 기타 시장 배제
        if "Market" in df_listing.columns:
            m_upper = df_listing["Market"].str.upper()
            mask = m_upper.str.contains("KOSPI") | m_upper.str.contains("KOSDAQ")
            if mask.any():
                df_listing = df_listing[mask].copy()
        elif "MarketId" in df_listing.columns:
            mask = df_listing["MarketId"].isin(["STK", "KSQ"])
            if mask.any():
                df_listing = df_listing[mask].copy()

    # 노이즈 종목 제거
    valid_mask = df_listing.apply(lambda r: is_valid_screening_stock(r["Code"], r["Name"]), axis=1)
    df_filtered = df_listing[valid_mask].copy()

    # 시가총액 산출
    marcap_col = None
    for col in ["Marcap", "MKTCAP", "시가총액", "MarketCap"]:
        if col in df_filtered.columns:
            marcap_col = col
            break

    if marcap_col:
        df_filtered["Marcap_Num"] = pd.to_numeric(df_filtered[marcap_col], errors="coerce").fillna(0)
    else:
        df_filtered["Marcap_Num"] = 0

    valid_marcap_count = (df_filtered["Marcap_Num"] > 0).sum()
    if valid_marcap_count < max(10, len(df_filtered) * 0.5):
        fallback_map = get_fallback_marcap_map()
        if fallback_map:
            fallback_series = df_filtered["Code"].map(fallback_map).fillna(0)
            df_filtered["Marcap_Num"] = np.where(
                df_filtered["Marcap_Num"] > 0,
                df_filtered["Marcap_Num"],
                fallback_series
            )

    # 시가총액 내림차순 정렬
    df_sorted = df_filtered.sort_values(by="Marcap_Num", ascending=False).reset_index(drop=True)

    # 최소 시가총액 필터 적용 (단위: 억원)
    if min_marcap_eok > 0 and (df_sorted["Marcap_Num"] > 0).any():
        min_won = min_marcap_eok * 100_000_000
        df_sorted = df_sorted[df_sorted["Marcap_Num"] >= min_won].reset_index(drop=True)

    # 대상 범위(Scope) 필터링
    scope_str = str(scope)
    if "200" in scope_str and "쾌속" in scope_str:
        df_result = df_sorted.head(200)
    elif "500" in scope_str and "확장" in scope_str:
        df_result = df_sorted.head(500)
    elif "200" in scope_str and "150" in scope_str:
        # 코스피 200 / 코스닥 150
        if m_clean == "KOSPI":
            df_result = df_sorted.head(200)
        elif m_clean == "KOSDAQ":
            df_result = df_sorted.head(150)
        else:
            m_col = "Market" if "Market" in df_sorted.columns else "MarketId"
            if m_col in df_sorted.columns:
                is_ks = df_sorted[m_col].astype(str).str.upper().str.contains("KOSPI|STK")
                df_ks = df_sorted[is_ks].head(200)
                df_kq = df_sorted[~is_ks].head(150)
                df_result = pd.concat([df_ks, df_kq], ignore_index=True)
            else:
                df_result = df_sorted.head(350)
    else:  # 전체 모드
        df_result = df_sorted

    return df_result
