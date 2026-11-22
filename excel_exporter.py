"""
excel_exporter.py
스크리닝된 눌림목 종목 분석 데이터를 전문가용 엑셀(.xlsx) 및 CSV 형식으로
서식화하여 내보내는 모듈 (가이드 01 다운로드 표준 준수)
"""

import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


EXPORT_HEADERS = [
    "종목코드",
    "종목명",
    "시장",
    "시가총액(억원)",
    "현재가(원)",
    "등락률(%)",
    "5일평균거래대금(억원)",
    "20일선 이격도(%)",
    "IBS",
    "RSI(14)",
    "볼린저 %B",
    "거래량 비율(%)",
    "적합도 점수",
    "투자의견"
]


def prepare_export_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    스크리닝 결과 데이터프레임을 엑셀 및 CSV 출력용 표준 형식으로 정제
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=EXPORT_HEADERS)

    df_out = pd.DataFrame()
    df_out["종목코드"] = df["종목코드"].astype(str).str.zfill(6) if "종목코드" in df else ""
    df_out["종목명"] = df.get("종목명", "")
    df_out["시장"] = df.get("시장", "")
    df_out["시가총액(억원)"] = pd.to_numeric(df.get("시가총액", 0), errors="coerce").fillna(0).astype(int)
    df_out["현재가(원)"] = pd.to_numeric(df.get("현재가", 0), errors="coerce").fillna(0).astype(int)
    df_out["등락률(%)"] = pd.to_numeric(df.get("등락률", 0.0), errors="coerce").round(2)
    df_out["5일평균거래대금(억원)"] = pd.to_numeric(df.get("5일평균거래대금", 0.0), errors="coerce").round(1)
    df_out["20일선 이격도(%)"] = pd.to_numeric(df.get("20일선 이격도", 100.0), errors="coerce").round(1)
    df_out["IBS"] = pd.to_numeric(df.get("IBS", 0.5), errors="coerce").round(2)
    df_out["RSI(14)"] = pd.to_numeric(df.get("RSI(14)", 50.0), errors="coerce").round(1)
    df_out["볼린저 %B"] = pd.to_numeric(df.get("볼린저 %B", 0.5), errors="coerce").round(2)
    df_out["거래량 비율(%)"] = pd.to_numeric(df.get("거래량 비율", 100.0), errors="coerce").round(1)
    df_out["적합도 점수"] = pd.to_numeric(df.get("적합도 점수", 0), errors="coerce").fillna(0).astype(int)
    df_out["투자의견"] = df.get("투자의견", "")

    return df_out


def create_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    전문가용 서식(헤더 다크 슬레이트, 점수 조건부 강조, 자동 필터 토글)이 적용된 .xlsx 바이너리 반환
    """
    df_export = prepare_export_dataframe(df)

    wb = Workbook()
    ws = wb.active
    ws.title = "눌림목_전략_스크리닝"

    # 스타일 정의
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")

    data_font = Font(name="맑은 고딕", size=9)
    bold_data_font = Font(name="맑은 고딕", size=9, bold=True)

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    strong_buy_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")  # 연녹색
    strong_buy_font = Font(name="맑은 고딕", size=9, bold=True, color="166534")

    buy_fill = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")  # 연하늘색
    buy_font = Font(name="맑은 고딕", size=9, bold=True, color="0369A1")

    # 헤더 작성
    headers = list(df_export.columns)
    ws.append(headers)

    ws.row_dimensions[1].height = 26
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center
        cell.border = thin_border

    # 데이터 행 작성
    for row_idx, row in df_export.iterrows():
        ws_row_idx = row_idx + 2
        ws.row_dimensions[ws_row_idx].height = 20

        row_data = list(row.values)
        ws.append(row_data)

        opinion = str(row.get("투자의견", ""))

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=ws_row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border

            header_name = headers[col_idx - 1]

            # 정렬 및 서식
            if header_name in ["종목코드", "시장", "투자의견"]:
                cell.alignment = align_center
            elif header_name in ["종목명"]:
                cell.alignment = align_left
            else:
                cell.alignment = align_right

            # 숫자 서식 (단위 글자 없이 순수 숫자로 포맷팅)
            if header_name in ["현재가", "현재가(원)", "시가총액(억원)"]:
                cell.number_format = "#,##0"
            elif header_name in ["5일평균거래대금(억원)"]:
                cell.number_format = "#,##0.0"
            elif header_name in ["등락률(%)", "20일선 이격도(%)", "IBS", "RSI(14)", "볼린저 %B", "거래량 비율(%)"]:
                cell.number_format = "#,##0.00"

            # 강조
            if "STRONG BUY" in opinion:
                cell.fill = strong_buy_fill
                if header_name in ["적합도 점수", "투자의견"]:
                    cell.font = strong_buy_font
            elif "BUY" in opinion:
                cell.fill = buy_fill
                if header_name in ["적합도 점수", "투자의견"]:
                    cell.font = buy_font

    # 자동 필터 적용
    ws.auto_filter.ref = ws.dimensions

    # 열 너비 자동 최적화
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            # 한글 너비 보정
            val_len = sum(2 if ord(c) > 127 else 1 for c in val_str)
            if val_len > max_len:
                max_len = val_len
        ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
