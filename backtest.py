"""
backtest.py
간이 백테스팅(Quick Backtest) 모듈
- 특정 종목의 과거 시계열(1~2년)에서 사용자가 설정한 전략 조건으로 매수 신호가 발생했던 과거 시점들을 탐색
- 5일, 10일, 20일 보유 후의 수익률, 승률, 평균 손익비, 최대 낙폭(MDD) 등 핵심 퀀트 성과 지표 계산
"""

import pandas as pd
import numpy as np
from strategy_pullback import evaluate_pullback_at_bar


def run_quick_backtest(df: pd.DataFrame, params: dict = None, holding_days: int = 10, stop_loss_pct: float = -3.5, take_profit_pct: float = 7.0) -> dict:
    """
    단일 종목의 전체 일봉 데이터에서 과거 눌림목 매수 신호를 전수 조사하여 백테스팅 성과를 산출합니다.
    """
    if df is None or len(df) < 50:
        return {
            "has_data": False,
            "message": "데이터가 부족하여 백테스팅을 수행할 수 없습니다 (최소 50봉 필요)."
        }

    signals = []
    trade_logs = []

    # 지표 계산에 필요한 최소 봉 수(30봉) 이후부터 탐색
    start_bar = 35
    total_bars = len(df)

    for i in range(start_bar, total_bars - 1):
        res = evaluate_pullback_at_bar(df, idx=i, params=params)
        if res and res["is_buy"]:
            signal_date = df.index[i].strftime("%Y-%m-%d") if hasattr(df.index[i], "strftime") else str(df.index[i])[:10]
            entry_price = float(df["Close"].iloc[i])

            # 보유 기간 동안의 주가 경로 추적
            max_forward = min(holding_days, total_bars - 1 - i)
            if max_forward <= 0:
                continue

            forward_slice = df.iloc[i + 1 : i + 1 + max_forward]
            exit_price = float(forward_slice["Close"].iloc[-1])
            highest_price = float(forward_slice["High"].max())
            lowest_price = float(forward_slice["Low"].min())

            # 손익률 계산
            final_return = ((exit_price - entry_price) / entry_price) * 100.0
            max_gain = ((highest_price - entry_price) / entry_price) * 100.0
            max_loss = ((lowest_price - entry_price) / entry_price) * 100.0

            # 익절/손절 체크
            is_win = final_return > 0
            is_stopped = max_loss <= stop_loss_pct
            is_profited = max_gain >= take_profit_pct

            # 5일, 10일, 20일 수익률
            ret_5d = None
            if i + 5 < total_bars:
                ret_5d = ((float(df["Close"].iloc[i + 5]) - entry_price) / entry_price) * 100.0
            ret_10d = None
            if i + 10 < total_bars:
                ret_10d = ((float(df["Close"].iloc[i + 10]) - entry_price) / entry_price) * 100.0
            ret_20d = None
            if i + 20 < total_bars:
                ret_20d = ((float(df["Close"].iloc[i + 20]) - entry_price) / entry_price) * 100.0

            trade_log = {
                "신호일자": signal_date,
                "진입가": int(round(entry_price)),
                "청산가": int(round(exit_price)),
                "수익률(%)": round(final_return, 2),
                "최고수익률(%)": round(max_gain, 2),
                "최대손실률(%)": round(max_loss, 2),
                "5일후(%)": round(ret_5d, 2) if ret_5d is not None else "-",
                "10일후(%)": round(ret_10d, 2) if ret_10d is not None else "-",
                "20일후(%)": round(ret_20d, 2) if ret_20d is not None else "-",
                "결과": "성공(Win)" if is_win else "실패(Loss)"
            }
            trade_logs.append(trade_log)
            signals.append(final_return)

    if not trade_logs:
        return {
            "has_data": False,
            "message": "과거 해당 기간 동안 조건에 부합하는 매수 신호가 발생하지 않았습니다."
        }

    # 통계 집계
    returns_arr = np.array(signals)
    total_trades = len(returns_arr)
    win_trades = int(np.sum(returns_arr > 0))
    loss_trades = int(np.sum(returns_arr <= 0))
    win_rate = (win_trades / total_trades) * 100.0 if total_trades > 0 else 0.0

    avg_return = float(np.mean(returns_arr))
    median_return = float(np.median(returns_arr))

    win_returns = returns_arr[returns_arr > 0]
    loss_returns = returns_arr[returns_arr < 0]
    avg_win = float(np.mean(win_returns)) if len(win_returns) > 0 else 0.0
    avg_loss = float(np.mean(np.abs(loss_returns))) if len(loss_returns) > 0 else 0.0
    profit_factor = (avg_win / avg_loss) if avg_loss > 0 else (avg_win if avg_win > 0 else 1.0)

    max_single_gain = float(np.max(returns_arr))
    max_single_loss = float(np.min(returns_arr))

    # 누적 수익 곡선 계산
    cumulative_returns = np.cumprod(1 + returns_arr / 100.0) - 1.0
    total_cumulative_return = float(cumulative_returns[-1] * 100.0) if len(cumulative_returns) > 0 else 0.0

    df_logs = pd.DataFrame(trade_logs)

    return {
        "has_data": True,
        "total_trades": total_trades,
        "win_trades": win_trades,
        "loss_trades": loss_trades,
        "win_rate": round(win_rate, 1),
        "avg_return": round(avg_return, 2),
        "median_return": round(median_return, 2),
        "profit_factor": round(profit_factor, 2),
        "max_gain": round(max_single_gain, 2),
        "max_loss": round(max_single_loss, 2),
        "total_cum_return": round(total_cumulative_return, 2),
        "df_logs": df_logs
    }
