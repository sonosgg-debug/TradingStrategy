"""
charts.py
Plotly 기반 주가 캔들스틱 및 눌림목 6대 보조지표(MA, BB, 거래량, RSI, MACD, IBS) 인터랙티브 차트 모듈
- Tailwind Slate-800 액자형 카드 표준 테마 (가이드 03) 준수
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 가이드 03 표준 테마 상수
STANDARD_CHART_THEME = {
    'paper_bgcolor': '#1E293B',    # Tailwind Slate-800 (외곽 카드 배경)
    'plot_bgcolor': '#0F172A',     # Tailwind Slate-900 (내부 딥 블랙 플롯)
    'text_main': '#F8FAFC',        # 타이틀/헤더 텍스트 (순백색)
    'text_body': '#E2E8F0',        # 본문 및 축 라벨 (부드러운 화이트)
    'text_muted': '#CBD5E1',       # 축 눈금 수치 텍스트 (Slate-300)
    'grid_color': '#334155',       # 그리드 격자선 (Slate-700)
    'border_color': '#475569',     # 축 기준선 (Slate-600)
    'legend_bg': 'rgba(30, 41, 59, 0.85)',
    'legend_border': '#334155',
    'hover_bg': 'rgba(15, 23, 42, 0.9)',
    'hover_border': '#334155'
}


def create_pullback_chart(df: pd.DataFrame, stock_name: str, stock_code: str, signal_idx: int = -1) -> go.Figure:
    """
    주가 캔들스틱, 이동평균선, 볼린저 밴드, 거래량, RSI, MACD, IBS가 정밀 결합된 멀티 서브플롯 차트 생성
    """
    if df is None or len(df) < 10:
        fig = go.Figure()
        fig.add_annotation(text="차트를 표시할 데이터가 부족합니다.", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # 최근 120봉(약 6개월) 데이터 슬라이싱 (가독성 극대화)
    chart_df = df.tail(120).copy()

    # 날짜 인덱스를 문자열로 변환 (휴장일 공백 제거)
    x_dates = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10] for d in chart_df.index]

    # 서브플롯 생성: 5개 행 (가격 45%, 거래량 15%, RSI 13%, MACD 14%, IBS 13%)
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.44, 0.14, 0.14, 0.14, 0.14],
        subplot_titles=(
            f"<b>{stock_name} ({stock_code})</b> 캔들스틱 및 이동평균선 / 볼린저 밴드",
            "거래량 & 20일 거래량 이평",
            "RSI (14)",
            "MACD (12, 26, 9)",
            "IBS (Internal Bar Strength, 0~1)"
        )
    )

    # 1. 캔들스틱 (한국 증시 표준: 상승 빨강 #ef4444, 하락 파랑 #3b82f6)
    fig.add_trace(
        go.Candlestick(
            x=x_dates,
            open=chart_df["Open"],
            high=chart_df["High"],
            low=chart_df["Low"],
            close=chart_df["Close"],
            name="주가",
            increasing_line_color='#ef4444',
            increasing_fillcolor='#ef4444',
            decreasing_line_color='#3b82f6',
            decreasing_fillcolor='#3b82f6',
            showlegend=False
        ),
        row=1, col=1
    )

    # 2. 이동평균선 (Row 1)
    if "SMA_5" in chart_df.columns:
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["SMA_5"], name="SMA 5", line=dict(color="#f59e0b", width=1.0)), row=1, col=1)
    if "SMA_20" in chart_df.columns:
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["SMA_20"], name="SMA 20 (생명선)", line=dict(color="#fbbf24", width=2.0)), row=1, col=1)
    if "SMA_60" in chart_df.columns:
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["SMA_60"], name="SMA 60 (수급선)", line=dict(color="#10b981", width=1.5)), row=1, col=1)
    if "SMA_120" in chart_df.columns:
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["SMA_120"], name="SMA 120 (경기선)", line=dict(color="#a855f7", width=1.5)), row=1, col=1)
    if "SMA_200" in chart_df.columns:
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["SMA_200"], name="SMA 200 (대세선)", line=dict(color="#ec4899", width=1.5, dash="dot")), row=1, col=1)

    # 볼린저 밴드 (Row 1)
    if "BB_Upper" in chart_df.columns and "BB_Lower" in chart_df.columns:
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["BB_Upper"], name="BB 상단(2σ)", line=dict(color="rgba(148, 163, 184, 0.4)", width=1, dash="dash")), row=1, col=1)
        fig.add_trace(go.Scatter(x=x_dates, y=chart_df["BB_Lower"], name="BB 하단(2σ)", line=dict(color="rgba(148, 163, 184, 0.4)", width=1, dash="dash"), fill="tonexty", fillcolor="rgba(56, 189, 248, 0.04)"), row=1, col=1)

    # 눌림목 포착 지점 마커 (최신봉 또는 신호 위치)
    last_x = x_dates[-1]
    last_low = float(chart_df["Low"].iloc[-1])
    fig.add_trace(
        go.Scatter(
            x=[last_x],
            y=[last_low * 0.985],
            mode="markers+text",
            name="스크리닝 타점",
            marker=dict(symbol="triangle-up", size=14, color="#38bdf8"),
            text=["<b>BUY SIGNAL</b>"],
            textposition="bottom center",
            textfont=dict(color="#38bdf8", size=11)
        ),
        row=1, col=1
    )

    # 3. 거래량 (Row 2)
    vol_colors = ['#ef4444' if c >= o else '#3b82f6' for c, o in zip(chart_df["Close"], chart_df["Open"])]
    fig.add_trace(
        go.Bar(
            x=x_dates,
            y=chart_df["Volume"],
            name="거래량",
            marker_color=vol_colors,
            opacity=0.75,
            showlegend=False
        ),
        row=2, col=1
    )
    if "VMA_20" in chart_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_dates,
                y=chart_df["VMA_20"],
                name="20일 평균 거래량",
                line=dict(color="#f97316", width=1.5)
            ),
            row=2, col=1
        )

    # 4. RSI (Row 3)
    if "RSI_14" in chart_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_dates,
                y=chart_df["RSI_14"],
                name="RSI(14)",
                line=dict(color="#a855f7", width=1.8)
            ),
            row=3, col=1
        )
        # 과매도(30), 중립(50), 과매수(70) 기준선
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=3, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="#64748b", line_width=1, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#38bdf8", line_width=1, row=3, col=1)

    # 5. MACD (Row 4)
    if "MACD" in chart_df.columns and "MACD_Signal" in chart_df.columns:
        fig.add_trace(
            go.Scatter(x=x_dates, y=chart_df["MACD"], name="MACD", line=dict(color="#38bdf8", width=1.5)),
            row=4, col=1
        )
        fig.add_trace(
            go.Scatter(x=x_dates, y=chart_df["MACD_Signal"], name="Signal", line=dict(color="#f59e0b", width=1.2, dash="dot")),
            row=4, col=1
        )
        hist_colors = ['#ef4444' if h >= 0 else '#3b82f6' for h in chart_df["MACD_Hist"]]
        fig.add_trace(
            go.Bar(x=x_dates, y=chart_df["MACD_Hist"], name="Histogram", marker_color=hist_colors, opacity=0.7),
            row=4, col=1
        )
        fig.add_hline(y=0, line_color="#64748b", line_width=1, row=4, col=1)

    # 6. IBS (Row 5)
    if "IBS" in chart_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_dates,
                y=chart_df["IBS"],
                name="IBS (Close-Low)/(High-Low)",
                line=dict(color="#06b6d4", width=1.5)
            ),
            row=5, col=1
        )
        # 0.5 기준선 (캔들 중간 마감 기준)
        fig.add_hline(y=0.5, line_dash="dash", line_color="#f59e0b", line_width=1.2, row=5, col=1)
        fig.add_hline(y=0.2, line_dash="dot", line_color="#3b82f6", line_width=1, row=5, col=1)
        fig.add_hline(y=0.8, line_dash="dot", line_color="#ef4444", line_width=1, row=5, col=1)

    # 레이아웃 통일 (가이드 03 준수)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=STANDARD_CHART_THEME['paper_bgcolor'],
        plot_bgcolor=STANDARD_CHART_THEME['plot_bgcolor'],
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=STANDARD_CHART_THEME['hover_bg'],
            bordercolor=STANDARD_CHART_THEME['hover_border'],
            font=dict(color="#FFFFFF", size=12)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="center",
            x=0.5,
            bgcolor=STANDARD_CHART_THEME['legend_bg'],
            bordercolor=STANDARD_CHART_THEME['legend_border'],
            borderwidth=1,
            font=dict(color=STANDARD_CHART_THEME['text_main'], size=10)
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=920,
        xaxis_rangeslider_visible=False
    )

    # 서브플롯 타이틀 폰트 스타일
    for annotation in fig['layout']['annotations']:
        annotation['font'] = dict(size=12, color=STANDARD_CHART_THEME['text_body'])

    # 축 그리드 및 틱 스타일 일괄 적용
    fig.update_xaxes(
        gridcolor=STANDARD_CHART_THEME['grid_color'],
        linecolor=STANDARD_CHART_THEME['border_color'],
        tickfont=dict(color=STANDARD_CHART_THEME['text_muted'], size=10),
        showgrid=True
    )
    fig.update_yaxes(
        gridcolor=STANDARD_CHART_THEME['grid_color'],
        linecolor=STANDARD_CHART_THEME['border_color'],
        tickfont=dict(color=STANDARD_CHART_THEME['text_muted'], size=10),
        showgrid=True
    )

    return fig


def create_backtest_cumulative_chart(df_logs: pd.DataFrame, stock_name: str) -> go.Figure:
    """
    백테스팅 신호별 누적 수익률 곡선 차트 생성
    """
    if df_logs is None or df_logs.empty:
        fig = go.Figure()
        return fig

    returns = df_logs["수익률(%)"].values
    dates = df_logs["신호일자"].values
    cum_returns = (np.cumprod(1 + returns / 100.0) - 1.0) * 100.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=cum_returns,
            mode="lines+markers",
            name="누적 수익률(%)",
            line=dict(color="#38bdf8", width=2.5),
            marker=dict(
                size=8,
                color=['#ef4444' if r > 0 else '#3b82f6' for r in returns],
                line=dict(width=1, color="#ffffff")
            )
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#64748b")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=STANDARD_CHART_THEME['paper_bgcolor'],
        plot_bgcolor=STANDARD_CHART_THEME['plot_bgcolor'],
        title=dict(
            text=f"<b>{stock_name}</b> 과거 눌림목 매수 신호 누적 수익률 추이",
            font=dict(color=STANDARD_CHART_THEME['text_main'], size=14),
            x=0.5,
            xanchor="center"
        ),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=50, b=40),
        height=320
    )

    fig.update_xaxes(
        gridcolor=STANDARD_CHART_THEME['grid_color'],
        linecolor=STANDARD_CHART_THEME['border_color'],
        tickfont=dict(color=STANDARD_CHART_THEME['text_muted'], size=10)
    )
    fig.update_yaxes(
        gridcolor=STANDARD_CHART_THEME['grid_color'],
        linecolor=STANDARD_CHART_THEME['border_color'],
        tickfont=dict(color=STANDARD_CHART_THEME['text_muted'], size=10),
        ticksuffix="%"
    )

    return fig
