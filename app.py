"""
app.py
Trading Strategy & Screening Parameters
투자 전략에 따른 조건 검색을 통해 전략에 맞는 매수(BUY) 종목을 발굴하고
간이 백테스팅 및 멀티 보조지표 차트를 제공하는 퀀트 웹 애플리케이션
"""

import os
import sys
import importlib
from datetime import datetime, date, timedelta

import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image

# 보조 모듈 import 및 강제 리로드 의무화 (가이드 05 준수: Zero Stale Module Freezing)
import data_loader
importlib.reload(data_loader)

import strategy_pullback
importlib.reload(strategy_pullback)

import engine
importlib.reload(engine)

import backtest
importlib.reload(backtest)

import charts
importlib.reload(charts)

import excel_exporter
importlib.reload(excel_exporter)

from data_loader import (
    KST, get_now_kst, is_krx_trading_day, get_latest_expected_trading_day,
    format_marcap
)
from strategy_pullback import PULLBACK_PRESETS, calculate_pullback_indicators
from engine import run_strategy_screening, fetch_stock_history_cached
from charts import create_pullback_chart, create_backtest_cumulative_chart, STANDARD_CHART_THEME
from backtest import run_quick_backtest
from excel_exporter import create_excel_bytes, prepare_export_dataframe

# ================================================================================
# 1. 페이지 기본 설정 (가이드 01 준수: 탭 파비콘 favicon.png 적용)
# ================================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAVICON_PATH = os.path.join(BASE_DIR, "favicon.png")
try:
    if os.path.exists(FAVICON_PATH):
        PAGE_ICON = Image.open(FAVICON_PATH)
    else:
        PAGE_ICON = "📈"
except Exception:
    PAGE_ICON = "📈"

st.set_page_config(
    page_title="Trading Strategy & Screening Parameters",
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================================================================================
# 2. 글로벌 다크 테마 & UI/UX CSS 주입 (가이드 01, 02 준수)
# ================================================================================
st.markdown(
    """
    <style>
    /* 상단 고정 헤더 배경 투명화 및 패딩 표준화 (2.0rem) */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-top: 2.0rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 100% !important;
    }

    /* 사이드바 다크 네이비 테마 & 테두리 */
    section[data-testid="stSidebar"], [data-testid="stSidebar"] {
        background-color: #1e293b !important;
        border-right: 1px solid #334155 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #f8fafc !important;
        -webkit-text-fill-color: #f8fafc !important;
    }

    /* 사이드바 접기/열기 버튼 시인성 보강 */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapsedControl"] button {
        background-color: #1e293b !important;
        border: 1.5px solid #38bdf8 !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 6px rgba(56, 189, 248, 0.2) !important;
    }
    [data-testid="stSidebarCollapseButton"] button *,
    [data-testid="stSidebarCollapsedControl"] button * {
        color: #38bdf8 !important;
        fill: #38bdf8 !important;
    }

    /* 프라이머리 버튼 스타일 (스카이블루 / 인디고 하이라이트) */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        padding: 0.5rem 1.5rem !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35) !important;
        transition: all 0.2s ease-in-out !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.5) !important;
        transform: translateY(-1px);
    }

    /* 세컨더리 버튼 스타일 */
    div.stButton > button[kind="secondary"] {
        background-color: #334155 !important;
        color: #f8fafc !important;
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }

    /* 다운로드 버튼 통일 규격 (Slate-700 다크 네이비, 호버 시 스카이블루) */
    div[data-testid="stDownloadButton"] > button,
    .stDownloadButton > button {
        background-color: #334155 !important;
        color: #f8fafc !important;
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
        font-size: 0.875rem !important;
        font-weight: 600 !important;
        height: 40px !important;
        padding: 0 16px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease-in-out !important;
    }
    div[data-testid="stDownloadButton"] > button:hover,
    .stDownloadButton > button:hover {
        background-color: #475569 !important;
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.25) !important;
    }

    /* 카드 컨테이너 */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.55rem;
        font-weight: 800;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #38bdf8;
        margin-top: 2px;
    }

    /* 탭 디자인 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1e293b;
        border-radius: 6px 6px 0 0;
        padding: 8px 18px;
        color: #94a3b8;
        font-weight: 600;
        border: 1px solid #334155;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #334155 !important;
        color: #38bdf8 !important;
        border-top: 2px solid #38bdf8 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ================================================================================
# 3. 세션 상태(Session State) 초기화
# ================================================================================
if "screening_results" not in st.session_state:
    st.session_state["screening_results"] = None

if "preset_choice" not in st.session_state:
    st.session_state["preset_choice"] = "Type A (보수적·안정적 지지 반등)"

# 기본 프리셋 값 로드
def apply_preset_to_state(preset_name):
    cfg = PULLBACK_PRESETS.get(preset_name, PULLBACK_PRESETS["Type A (보수적·안정적 지지 반등)"])
    st.session_state["cfg_long_ma"] = cfg["long_ma"]
    st.session_state["cfg_require_ma_align"] = cfg["require_ma_align"]
    st.session_state["cfg_disparity_min"] = float(cfg["disparity_min"])
    st.session_state["cfg_disparity_max"] = float(cfg["disparity_max"])
    st.session_state["cfg_touch_ma20"] = cfg["touch_ma20"]
    st.session_state["cfg_vol_ratio_max"] = float(cfg["vol_ratio_max"])
    st.session_state["cfg_ibs_min"] = float(cfg["ibs_min"])
    st.session_state["cfg_rsi_min"] = float(cfg["rsi_min"])
    st.session_state["cfg_rsi_max"] = float(cfg["rsi_max"])
    st.session_state["cfg_bb_pct_min"] = float(cfg["bb_pct_min"])
    st.session_state["cfg_bb_pct_max"] = float(cfg["bb_pct_max"])
    st.session_state["cfg_macd_turnaround"] = cfg["macd_turnaround"]
    st.session_state["cfg_min_score"] = int(cfg["min_score"])

if "cfg_long_ma" not in st.session_state:
    apply_preset_to_state(st.session_state["preset_choice"])

# ================================================================================
# 4. 사이드바 구성 (사용자 첨부 이미지 1 및 가이드 02 준수)
# ================================================================================
with st.sidebar:
    # [1단계] 최상단 표준 헤더 카드
    st.markdown(
        """
        <div style='padding: 2px 0 12px 0;'>
            <div style='font-size: 1.25rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em; display: flex; align-items: center; gap: 8px;'>
                <span>⚙️</span> 시장/필터 설정
            </div>
            <div style='font-size: 0.82rem; color: #94a3b8; margin-top: 4px; line-height: 1.4;'>
                분석 대상 시장과 기본 유동성 필터를 설정합니다.
            </div>
        </div>
        <hr style='border: 0; height: 1px; background-color: #334155; margin: 10px 0 16px 0;'>
        """,
        unsafe_allow_html=True
    )

    # [2단계] 시장 선택 (옵션 3개: st.radio horizontal=True)
    st.markdown("<div style='font-size: 0.95rem; font-weight: 700; color: #e2e8f0; margin-bottom: 6px;'>🏛️ 시장 선택</div>", unsafe_allow_html=True)
    market_choice = st.radio(
        "시장 선택",
        ["코스피 (KOSPI)", "코스닥 (KOSDAQ)", "전체 (ALL)"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # 구분선
    st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 16px 0;'>", unsafe_allow_html=True)

    # [3단계] 대상 범위 (Scope)
    st.markdown("<div style='font-size: 0.95rem; font-weight: 700; color: #e2e8f0; margin-bottom: 6px;'>🎯 대상 범위 (Scope)</div>", unsafe_allow_html=True)
    scope_choice = st.selectbox(
        "대상 범위",
        [
            "시총 상위 200 (쾌속 모드)",
            "시총 상위 500 (확장 모드)",
            "코스피 200 / 코스닥 150",
            "시장 전체 종목 (전체 모드)"
        ],
        index=0,
        label_visibility="collapsed"
    )

    # 구분선
    st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 16px 0;'>", unsafe_allow_html=True)

    # [4단계] 유동성 필터 (시가총액 & 5일 평균 거래대금)
    st.markdown("<div style='font-size: 0.95rem; font-weight: 700; color: #e2e8f0; margin-bottom: 6px;'>💰 유동성 필터</div>", unsafe_allow_html=True)

    min_marcap_eok = st.slider(
        "최소 시가총액 (억 원)",
        min_value=0,
        max_value=10000,
        value=5000,
        step=100,
        help="설정한 시가총액 이상의 우량 종목만 스크리닝 대상에 포함합니다 (기본값: 5,000억 원)."
    )

    min_trading_val_eok = st.slider(
        "최소 5일 평균 거래대금 (억 원)",
        min_value=0,
        max_value=1000,
        value=30,
        step=5,
        help="퀀트 추천 기본값: 30억 원. 슬리피지(체결 오차)를 방지하면서도 눌림목 조정기의 거래량 수축 우량주를 안전하게 포착하는 최적 기준입니다."
    )

    # [5단계] 하단 액션 버튼
    st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 16px 0;'>", unsafe_allow_html=True)
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🔄 Update", use_container_width=True, help="캐시를 초기화하고 최신 종목 목록을 다시 수집합니다."):
            st.cache_data.clear()
            st.success("캐시 초기화 완료!")
            st.rerun()
    with btn_col2:
        if st.button("🔍 필터 적용", type="primary", use_container_width=True, help="설정한 유니버스 범위를 적용합니다."):
            st.rerun()

# ================================================================================
# 5. 메인 페이지 타이틀 영역 (사용자 첨부 이미지 2 및 가이드 01 준수)
# ================================================================================
st.markdown(
    """
    <div style='text-align: center; padding-top: 0.5rem;'>
        <h1 style='color: #8AB4F8; font-size: 2.0rem; font-weight: 800; margin-bottom: 6px;'>
            Trading Strategy & Screening Parameters
        </h1>
        <p style='color: #94a3b8; font-size: 0.95rem; margin-bottom: 16px;'>
            투자 전략에 따른 조건 검색을 통해 전략에 맞는 매수(BUY) 종목을 발굴합니다.
        </p>
        <hr style='border: 0; height: 1px; background-color: #334155; margin: 14px 0 20px 0;'>
    </div>
    """,
    unsafe_allow_html=True
)

# ================================================================================
# 6. 전략 선택 및 지표 설정 영역
# ================================================================================

# [메인 섹터 제목 - Level 2]
st.markdown(
    """
    <div style='font-size: 1.20rem; font-weight: 700; color: #8AB4F8; margin: 10px 0 12px 0; display: flex; align-items: center; gap: 8px;'>
        <span>🎯</span> 전략 선택 및 지표 파라미터 설정
    </div>
    """,
    unsafe_allow_html=True
)

# 전략 선택 및 프리셋 선택 행
col_strat, col_preset = st.columns([1, 1.3])

with col_strat:
    st.markdown("<div style='font-size: 0.92rem; font-weight: 600; color: #e2e8f0; margin-bottom: 4px;'>전략 선택</div>", unsafe_allow_html=True)
    strategy_choice = st.selectbox(
        "전략 선택",
        ["전략 A (눌림목)"],  # 향후 "전략 B (추세추종 돌파)", "전략 C (역추세 반등)" 확장
        index=0,
        label_visibility="collapsed"
    )

with col_preset:
    st.markdown("<div style='font-size: 0.92rem; font-weight: 600; color: #e2e8f0; margin-bottom: 4px;'>전략 프리셋 (Preset)</div>", unsafe_allow_html=True)
    preset_selected = st.selectbox(
        "전략 프리셋",
        ["Type A (보수적·안정적 지지 반등)", "Type B (공격적·과매도 터치 반등)"],
        index=0 if st.session_state["preset_choice"] == "Type A (보수적·안정적 지지 반등)" else 1,
        label_visibility="collapsed"
    )

    # 프리셋 변경 감지 시 세션 상태 자동 업데이트
    if preset_selected != st.session_state["preset_choice"]:
        st.session_state["preset_choice"] = preset_selected
        apply_preset_to_state(preset_selected)
        st.rerun()

# 프리셋 설명 박스
preset_info = PULLBACK_PRESETS[preset_selected]["description"]
st.markdown(
    f"""
    <div style='background-color: #1e293b; border-left: 4px solid #38bdf8; padding: 10px 14px; border-radius: 4px; margin: 8px 0 16px 0; font-size: 0.85rem; color: #cbd5e1;'>
        💡 <b>{preset_selected} 전략 메커니즘</b>: {preset_info}
    </div>
    """,
    unsafe_allow_html=True
)

# 세부 지표 파라미터 커스텀 튜닝 (Expander & Interactive Controls)
with st.expander("🛠️ 지표 설정 세부 조절 (발굴 종목 수 조절 및 조건 미세 조정)", expanded=True):
    st.markdown("<div style='font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;'>※ 전략 프리셋을 기반으로 자동 설정된 지표값이며, 시장 상황에 맞춰 슬라이더를 조절하여 발굴 종목 수를 조절할 수 있습니다.</div>", unsafe_allow_html=True)

    g1, g2, g3 = st.columns(3)

    with g1:
        st.markdown("<div style='font-size: 0.90rem; font-weight: 700; color: #38bdf8; margin-bottom: 6px;'>1. 추세 및 이평선 필터</div>", unsafe_allow_html=True)
        long_ma_choice = st.selectbox(
            "장기 추세선 (Close > MA)",
            [120, 200, 60],
            index=[120, 200, 60].index(st.session_state["cfg_long_ma"]),
            help="종가가 이 이동평균선 위에 위치해야 상승 추세로 판정합니다."
        )
        require_align = st.checkbox(
            "중기 정배열 (20MA > 60MA) 필수",
            value=st.session_state["cfg_require_ma_align"]
        )
        touch_ma20 = st.checkbox(
            "20일선 지지/터치 여부 확인",
            value=st.session_state["cfg_touch_ma20"]
        )
        disp_range = st.slider(
            "20일선 이격도 허용 범위 (%)",
            min_value=85.0,
            max_value=110.0,
            value=(st.session_state["cfg_disparity_min"], st.session_state["cfg_disparity_max"]),
            step=0.5,
            help="20일선 대비 종가의 이격도 비율입니다 (100% = 20일선 일치)."
        )

    with g2:
        st.markdown("<div style='font-size: 0.90rem; font-weight: 700; color: #38bdf8; margin-bottom: 6px;'>2. 거래량 & IBS 필터</div>", unsafe_allow_html=True)
        vol_ratio_max = st.slider(
            "최대 거래량 수축비 (% of VMA20)",
            min_value=30.0,
            max_value=200.0,
            value=st.session_state["cfg_vol_ratio_max"],
            step=5.0,
            help="눌림목 조정 시 매도세가 마르는 현상을 포착합니다 (20일 평균 거래량 대비 당일 거래량 비율)."
        )
        ibs_min = st.slider(
            "IBS 최소 기준값 ((C - L) / (H - L))",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state["cfg_ibs_min"],
            step=0.05,
            help="당일 캔들에서 종가가 저가 대비 얼마나 높은 위치에서 마감했는지(하방 지지력 및 아래꼬리 강도)를 측정합니다. 0.5 이상이면 당일 캔들의 상반부 마감입니다."
        )
        min_score = st.slider(
            "최소 적합도 점수 (Score Cutoff)",
            min_value=40,
            max_value=90,
            value=st.session_state["cfg_min_score"],
            step=5,
            help="종합 눌림목 점수(0~100점)의 최소 기준선입니다. 점수가 높을수록 엄격한 종목만 발굴됩니다."
        )

    with g3:
        st.markdown("<div style='font-size: 0.90rem; font-weight: 700; color: #38bdf8; margin-bottom: 6px;'>3. 오실레이터 & 밴드 필터</div>", unsafe_allow_html=True)
        rsi_range = st.slider(
            "RSI(14) 허용 구간",
            min_value=15.0,
            max_value=70.0,
            value=(st.session_state["cfg_rsi_min"], st.session_state["cfg_rsi_max"]),
            step=1.0,
            help="상승 추세 속 눌림목의 경우 40~55선, 급락 후 과매도의 경우 30선 이하가 유효합니다."
        )
        bb_pct_range = st.slider(
            "볼린저밴드 %B 허용 구간",
            min_value=0.0,
            max_value=1.0,
            value=(st.session_state["cfg_bb_pct_min"], st.session_state["cfg_bb_pct_max"]),
            step=0.05,
            help="0.5는 볼린저 밴드 중심선(20MA), 0.0은 하단선(-2σ)입니다."
        )
        macd_turn = st.checkbox(
            "MACD 히스토그램 하락세 둔화/반등 확인",
            value=st.session_state["cfg_macd_turnaround"]
        )

# 활성화된 실행 파라미터 패키징
active_params = {
    "long_ma": long_ma_choice,
    "require_ma_align": require_align,
    "disparity_min": disp_range[0],
    "disparity_max": disp_range[1],
    "touch_ma20": touch_ma20,
    "vol_ratio_max": vol_ratio_max,
    "ibs_min": ibs_min,
    "rsi_min": rsi_range[0],
    "rsi_max": rsi_range[1],
    "bb_pct_min": bb_pct_range[0],
    "bb_pct_max": bb_pct_range[1],
    "macd_turnaround": macd_turn,
    "min_score": min_score
}

# ================================================================================
# 7. 캘린더 & 스크리닝 시작 버튼 영역 (사용자 첨부 이미지 2)
# ================================================================================
st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 16px 0 18px 0;'>", unsafe_allow_html=True)

col_cal, col_btn = st.columns([1, 1.8])

# 최근 실제 마감 거래일 산출 (가이드 04 준수)
latest_biz_str = get_latest_expected_trading_day()
latest_biz_date = datetime.strptime(latest_biz_str, "%Y-%m-%d").date()

with col_cal:
    st.markdown("<div style='font-size: 0.92rem; font-weight: 600; color: #e2e8f0; margin-bottom: 4px;'>📅 스크리닝 기준일</div>", unsafe_allow_html=True)
    screening_date = st.date_input(
        "스크리닝 기준일",
        value=latest_biz_date,
        max_value=get_now_kst().date(),
        label_visibility="collapsed"
    )

with col_btn:
    st.markdown("<div style='font-size: 0.92rem; font-weight: 600; color: #e2e8f0; margin-bottom: 4px;'>&nbsp;</div>", unsafe_allow_html=True)
    start_btn = st.button("🔍 스크리닝 시작", type="primary", use_container_width=True)

# ================================================================================
# 8. 스크리닝 엔진 실행 로직
# ================================================================================
if start_btn:
    target_date_str = screening_date.strftime("%Y-%m-%d")

    # 휴장일 자동 보정 안내
    if not is_krx_trading_day(screening_date):
        adj_target_str = get_latest_expected_trading_day(target_date_str)
        st.info(f"💡 선택하신 {target_date_str}은 거래소 휴장일이므로, 직전 실제 거래일인 **{adj_target_str}** 기준으로 스크리닝합니다.")
        target_date_str = adj_target_str

    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(current, total):
        pct = int((current / total) * 100) if total > 0 else 0
        progress_bar.progress(min(pct, 100))
        status_text.markdown(f"<span style='color: #94a3b8; font-size: 0.85rem;'>전략 조건 검색 진행 중: <b>{current} / {total}</b> 종목 분석 완료 ({pct}%)</span>", unsafe_allow_html=True)

    with st.spinner("빅데이터 병렬 퀀트 스크리닝 연산 중..."):
        df_result = run_strategy_screening(
            market=market_choice,
            scope=scope_choice,
            min_marcap_eok=min_marcap_eok,
            min_trading_val_eok=min_trading_val_eok,
            target_date_str=target_date_str,
            params=active_params,
            max_workers=20,
            progress_callback=update_progress
        )

    progress_bar.empty()
    status_text.empty()

    st.session_state["screening_results"] = df_result
    st.session_state["last_screening_date"] = target_date_str

# ================================================================================
# 9. 검색 결과 영역 (테이블 & 메트릭 카드 & 엑셀 다운로드)
# ================================================================================
df_results = st.session_state.get("screening_results")

if df_results is not None:
    st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 24px 0 16px 0;'>", unsafe_allow_html=True)

    # [Level 2 메인 섹터 제목]
    st.markdown(
        f"""
        <div style='font-size: 1.20rem; font-weight: 700; color: #8AB4F8; margin: 10px 0 14px 0; display: flex; align-items: center; justify-content: space-between;'>
            <div style='display: flex; align-items: center; gap: 8px;'>
                <span>📊</span> 전략 조건 검색 결과
                <span style='font-size: 0.85rem; font-weight: normal; color: #94a3b8;'>({st.session_state.get('last_screening_date', '')} 기준)</span>
            </div>
            <div style='font-size: 0.90rem; color: #38bdf8; font-weight: 600;'>
                발굴된 종목: {len(df_results)}개
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if df_results.empty:
        st.warning("⚠️ 현재 설정된 전략 조건에 부합하는 종목이 없습니다. '지표 설정'에서 이격도 범위나 IBS, 최소 점수 기준을 완화하여 다시 검색해 보세요.")
    else:
        # 요약 메트릭 카드 4개 배치
        m1, m2, m3, m4 = st.columns(4)
        strong_count = len(df_results[df_results["투자의견"] == "강력 매수"])
        buy_count = len(df_results[df_results["투자의견"] == "매수"])
        avg_score = round(df_results["적합도 점수"].mean(), 1)
        avg_chg = round(df_results["등락률"].mean(), 2)
        ks_cnt = len(df_results[df_results["시장"] == "KOSPI"])
        kq_cnt = len(df_results[df_results["시장"] == "KOSDAQ"])

        with m1:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-title'>총 발굴 종목</div>
                    <div class='metric-value'>{len(df_results)}<span style='font-size: 1.0rem; color: #94a3b8;'> 종목</span></div>
                    <div class='metric-sub'>KOSPI {ks_cnt} / KOSDAQ {kq_cnt}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m2:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-title'>강력 매수 (Strong Buy)</div>
                    <div class='metric-value' style='color: #4ade80;'>{strong_count}<span style='font-size: 1.0rem; color: #94a3b8;'> 종목</span></div>
                    <div class='metric-sub'>일반 매수: {buy_count}개</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m3:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-title'>평균 전략 적합도</div>
                    <div class='metric-value' style='color: #38bdf8;'>{avg_score}<span style='font-size: 1.0rem; color: #94a3b8;'> / 100점</span></div>
                    <div class='metric-sub'>최고 점수: {df_results['적합도 점수'].max()}점</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m4:
            chg_color = "#f87171" if avg_chg >= 0 else "#60a5fa"
            chg_sign = "+" if avg_chg >= 0 else ""
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-title'>당일 평균 등락률</div>
                    <div class='metric-value' style='color: {chg_color};'>{chg_sign}{avg_chg}%</div>
                    <div class='metric-sub'>눌림목 하방 경직성 반영</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # 표시용 정제 데이터프레임 구성
        display_cols = [
            "종목코드", "종목명", "시장", "현재가", "등락률", "시가총액",
            "5일평균거래대금", "20일선 이격도", "IBS", "RSI(14)", "볼린저 %B",
            "거래량 비율", "적합도 점수", "투자의견"
        ]
        df_show = df_results[[c for c in display_cols if c in df_results.columns]].copy()

        # 데이터프레임 렌더링
        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "종목코드": st.column_config.TextColumn("코드", width="small"),
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "시장": st.column_config.TextColumn("시장", width="small"),
                "현재가": st.column_config.NumberColumn("현재가(원)", format="%d원"),
                "등락률": st.column_config.NumberColumn("등락률(%)", format="%.2f%%"),
                "시가총액": st.column_config.NumberColumn("시총(억원)", format="%d억원"),
                "5일평균거래대금": st.column_config.NumberColumn("5일거래대금(억)", format="%.1f억"),
                "20일선 이격도": st.column_config.NumberColumn("20일이격도(%)", format="%.1f%%"),
                "IBS": st.column_config.NumberColumn("IBS(0~1)", format="%.2f"),
                "RSI(14)": st.column_config.NumberColumn("RSI", format="%.1f"),
                "볼린저 %B": st.column_config.NumberColumn("BB %B", format="%.2f"),
                "거래량 비율": st.column_config.NumberColumn("거래량비율(%)", format="%.1f%%"),
                "적합도 점수": st.column_config.ProgressColumn("적합도", format="%d점", min_value=0, max_value=100),
                "투자의견": st.column_config.TextColumn("투자의견", width="small")
            }
        )

        # 다운로드 버튼 영역 (가이드 01 표준 2열 배치)
        export_df = prepare_export_dataframe(df_results)
        csv_data = export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        excel_data = create_excel_bytes(df_results)
        file_suffix = st.session_state.get('last_screening_date', '').replace('-', '')

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="📥 CSV 파일 다운로드",
                data=csv_data,
                file_name=f"눌림목전략_스크리닝_{file_suffix}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_dl2:
            st.download_button(
                label="📥 엑셀 파일 다운로드",
                data=excel_data,
                file_name=f"눌림목전략_스크리닝_{file_suffix}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        # ================================================================================
        # 10. 차트 및 간이 백테스팅 상세 분석 영역
        # ================================================================================
        st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 28px 0 16px 0;'>", unsafe_allow_html=True)

        # [Level 2 메인 섹터 제목]
        st.markdown(
            """
            <div style='font-size: 1.20rem; font-weight: 700; color: #8AB4F8; margin: 10px 0 14px 0; display: flex; align-items: center; gap: 8px;'>
                <span>📈</span> 개별 종목 정밀 차트 & 간이 백테스팅 시뮬레이션
            </div>
            """,
            unsafe_allow_html=True
        )

        stock_options = [f"{row['종목명']} ({row['종목코드']}) - {row['적합도 점수']}점" for _, row in df_results.iterrows()]
        selected_stock_label = st.selectbox(
            "분석 대상 종목 선택",
            stock_options,
            index=0,
            help="차트 시각화 및 과거 백테스팅을 확인할 종목을 선택하세요."
        )

        # 선택 종목 코드 추출
        selected_code = selected_stock_label.split('(')[1].split(')')[0].strip()
        selected_name = selected_stock_label.split('(')[0].strip()

        # 데이터 로드
        start_date_hist = (get_now_kst() - timedelta(days=500)).strftime("%Y-%m-%d")
        df_stock_hist = fetch_stock_history_cached(selected_code, start_date_hist)

        if df_stock_hist is not None and not df_stock_hist.empty:
            tab_chart, tab_bt, tab_check = st.tabs([
                "📊 인터랙티브 6대 보조지표 차트",
                "🧪 간이 백테스팅 성과 시뮬레이션",
                "📋 전략 조건 검증 체크리스트"
            ])

            with tab_chart:
                fig_chart = create_pullback_chart(df_stock_hist, selected_name, selected_code)
                st.plotly_chart(fig_chart, use_container_width=True)

            with tab_bt:
                st.markdown("<div style='font-size: 0.95rem; font-weight: 600; color: #e2e8f0; margin-bottom: 8px;'>🎯 해당 종목 과거 눌림목 매수 신호 성과 분석</div>", unsafe_allow_html=True)
                
                # 백테스트 파라미터 조절
                bt_col1, bt_col2, bt_col3 = st.columns(3)
                with bt_col1:
                    holding_days = st.slider("보유 기간 (영업일)", min_value=3, max_value=30, value=10, step=1)
                with bt_col2:
                    stop_loss_pct = st.slider("손절선 설정 (%)", min_value=-10.0, max_value=-1.0, value=-3.5, step=0.5)
                with bt_col3:
                    take_profit_pct = st.slider("익절 목표선 설정 (%)", min_value=2.0, max_value=20.0, value=7.0, step=0.5)

                bt_res = run_quick_backtest(
                    df_stock_hist,
                    params=active_params,
                    holding_days=holding_days,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct
                )

                if bt_res.get("has_data", False):
                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        st.markdown(
                            f"""
                            <div class='metric-card'>
                                <div class='metric-title'>총 매수 신호 횟수</div>
                                <div class='metric-value'>{bt_res['total_trades']}<span style='font-size: 1.0rem; color: #94a3b8;'> 회</span></div>
                                <div class='metric-sub'>승 {bt_res['win_trades']}회 / 패 {bt_res['loss_trades']}회</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with b2:
                        wr_color = "#4ade80" if bt_res['win_rate'] >= 60 else "#f87171"
                        st.markdown(
                            f"""
                            <div class='metric-card'>
                                <div class='metric-title'>백테스팅 승률 (Win Rate)</div>
                                <div class='metric-value' style='color: {wr_color};'>{bt_res['win_rate']}%</div>
                                <div class='metric-sub'>손익비: {bt_res['profit_factor']}:1</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with b3:
                        ret_color = "#4ade80" if bt_res['avg_return'] >= 0 else "#60a5fa"
                        st.markdown(
                            f"""
                            <div class='metric-card'>
                                <div class='metric-title'>신호당 평균 수익률</div>
                                <div class='metric-value' style='color: {ret_color};'>{bt_res['avg_return']:+0.2f}%</div>
                                <div class='metric-sub'>중간값: {bt_res['median_return']:+0.2f}%</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with b4:
                        cum_color = "#4ade80" if bt_res['total_cum_return'] >= 0 else "#60a5fa"
                        st.markdown(
                            f"""
                            <div class='metric-card'>
                                <div class='metric-title'>누적 복리 수익률</div>
                                <div class='metric-value' style='color: {cum_color};'>{bt_res['total_cum_return']:+0.2f}%</div>
                                <div class='metric-sub'>최대수익: +{bt_res['max_gain']}% / 최대손실: {bt_res['max_loss']}%</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    # 누적 수익률 차트
                    fig_cum = create_backtest_cumulative_chart(bt_res["df_logs"], selected_name)
                    st.plotly_chart(fig_cum, use_container_width=True)

                    # 신호별 상세 거래 내역
                    st.markdown("<div style='font-size: 0.90rem; font-weight: 600; color: #cbd5e1; margin: 12px 0 6px 0;'>신호별 상세 트레이딩 내역</div>", unsafe_allow_html=True)
                    st.dataframe(bt_res["df_logs"], use_container_width=True, hide_index=True)
                else:
                    st.info(f"💡 {bt_res.get('message', '과거 신호가 없습니다.')}")

            with tab_check:
                # 선택 종목의 실시간 체크리스트 카드
                stock_row = df_results[df_results["종목코드"] == selected_code].iloc[0]
                checks_dict = stock_row.get("checks", {})

                st.markdown(f"<div style='font-size: 1.05rem; font-weight: 700; color: #8AB4F8; margin-bottom: 12px;'>🔍 {selected_name} ({selected_code}) 눌림목 조건 검증표</div>", unsafe_allow_html=True)

                chk_cols = st.columns(2)
                idx_c = 0
                for cond_name, is_pass in checks_dict.items():
                    target_col = chk_cols[idx_c % 2]
                    badge = "✅ 통과 (PASS)" if is_pass else "❌ 미흡 (FAIL)"
                    badge_color = "#4ade80" if is_pass else "#f87171"
                    with target_col:
                        st.markdown(
                            f"""
                            <div style='background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;'>
                                <div style='font-size: 0.82rem; color: #94a3b8;'>조건 항목</div>
                                <div style='font-size: 0.95rem; font-weight: 600; color: #f8fafc; margin-top: 2px;'>{cond_name}</div>
                                <div style='font-size: 0.85rem; font-weight: 700; color: {badge_color}; margin-top: 4px;'>{badge}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    idx_c += 1

# ================================================================================
# 11. 최하단 법적 책임 및 투자 유의사항 고지 푸터 (가이드 01 준수)
# ================================================================================
st.markdown("<hr style='border: 0; height: 1px; background-color: #334155; margin: 40px 0 10px 0;'>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align: center; color: #64748b; font-size: 0.8rem; margin-top: 8px; margin-bottom: 24px; line-height: 1.6;'>"
    "⚠️ 본 서비스에서 제공하는 모든 정보는 투자 참고용이며, 투자의 최종 결정과 책임은 투자자 본인에게 있습니다."
    "</div>",
    unsafe_allow_html=True
)
