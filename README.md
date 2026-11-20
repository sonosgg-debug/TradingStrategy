# 📈 Trading Strategy & Screening Parameters
> **투자 전략에 따른 조건 검색을 통해 전략에 맞는 매수(BUY) 종목을 발굴하고, 간이 백테스팅 및 6대 기술적 지표 멀티 차트를 제공하는 퀀트 웹 애플리케이션**

---

## 📌 주요 기능 및 특징

1. **전략 기반 스마트 스크리닝 (Strategy Screening Engine)**:
   - **전략 A (눌림목)**: 대세 상승 추세 속에서 일시적인 건전한 조정을 거쳐 지지선에서 반등하는 고승률 타점 발굴.
   - **2가지 기본 프리셋 제공**:
     - `Type A (보수적·안정적 지지 반등)`: 중장기 정배열 우량주 + 20일선 수렴 + 거래량 급감 + IBS 반등 확인
     - `Type B (공격적·과매도 터치 반등)`: 장기 추세 내 단기 급락 + 볼린저 밴드 하단 및 RSI 과매도 구간 터치 후 반등
   - **유연한 확장 아키텍처**: 추후 `전략 B (추세추종 돌파)`, `전략 C (역추세 반등)` 등을 모듈식으로 추가 가능.

2. **6대 핵심 보조지표 & 커스텀 미세 조절 (Customizable Parameters)**:
   - **추세 및 이평선**: 장기 추세선(120MA/200MA), 20MA > 60MA 정배열 여부, 20일선 이격도(Disparity) 범위
   - **거래량 및 수급**: 20일 거래량 이평 대비 당일 수축 비율 (조정 시 거래량 급감 포착)
   - **IBS (Internal Bar Strength)**: $(Close - Low) / (High - Low)$ - 당일 캔들 내 종가의 저가 대비 반등 위치 (아래꼬리 지지력)
   - **오실레이터 및 밴드**: RSI(14) 눌림목 구간, 볼린저 밴드 %B(20, 2), MACD 히스토그램 반등 모멘텀
   - **점수 컷오프(Score Cutoff)**: 종합 적합도 점수(0~100점) 기준을 조절하여 발굴 종목 수를 자유롭게 제어.

3. **인터랙티브 6대 보조지표 차트 (Plotly Multi-Subplot)**:
   - Tailwind Slate-800 액자형 카드 표준 테마 적용
   - 캔들스틱 + SMA(20, 60, 120, 200) + 볼린저 밴드 + 매수 시그널 마커
   - 거래량 & VMA20
   - RSI(14) & 기준선(30, 50, 70)
   - MACD, Signal, Histogram
   - IBS (0~1) & 0.5 중간선

4. **간이 백테스팅 성과 시뮬레이션 (Quick Backtest Simulation)**:
   - 해당 종목의 과거 1~2년치 시계열에서 동일 눌림목 조건 발생 시 성과 전수 조사
   - 보유 기간(N일), 익절선(%), 손절선(%) 시뮬레이션
   - 승률(Win Rate), 신호 횟수, 평균 수익률, 손익비(Profit Factor), 누적 복리 수익률 곡선 및 상세 거래 로그 제공

5. **전문가용 엑셀 및 CSV 다운로드**:
   - 다크 네이비 헤더 서식, 자동 필터, 조건부 서식(STRONG BUY 연녹색, BUY 연하늘색)이 완비된 `.xlsx` 및 `.csv` 다운로드 지원

---

## 🛠️ 프로젝트 구조

```
d:\AI Investing\28 TradingStrategy\
├── .streamlit\
│   └── config.toml          # 다크 테마 및 서버 설정 (가이드 01 표준)
├── .gitignore               # 배포 및 캐시 파일 관리
├── app.py                   # 메인 대시보드 UI/UX 엔트리포인트
├── engine.py                # 병렬 스크리닝 및 주가 수집 엔진
├── strategy_pullback.py     # 전략 A (눌림목) 정의, Type A/B 프리셋, 지표 계산 및 점수화
├── backtest.py              # 간이 백테스팅 계산 및 성과 지표 산출
├── charts.py                # Plotly 액자형 5단 서브플롯 차트 렌더러
├── data_loader.py           # 거래일 판정, KRX 공휴일 방어, 종목 유니버스 및 시총 필터
├── excel_exporter.py        # 전문가용 서식 엑셀(.xlsx) 및 CSV 익스포터
├── requirements.txt         # 종속성 패키지 명세
├── run_app.bat              # 로컬 실행 배치 파일
└── README.md                # 애플리케이션 설명서
```

---

## 🚀 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 애플리케이션 실행
run_app.bat
# 또는
python -m streamlit run app.py
```
