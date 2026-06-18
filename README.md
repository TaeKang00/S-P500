# S&P 500 Watchlist Terminal

S&P500 전체 종목을 시가총액 순으로 보여주고, 관심 종목에 대해 **개별 펀더멘털 점수 + 시장 타이밍(매크로) 가산점**을 결합한 매매 시그널을 제공하는 풀스택 대시보드.

기획안의 모든 스코어링 룰(섹션 7의 A·B 표)을 그대로 구현했으며, FWD PE 3년 평균은 일일 누적 스냅샷을 기반으로 자동 계산됩니다.

---

## 폴더 구조

```
sp500-watchlist/
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── run.py                      # 진입점 (앱 실행 + 최초 시드)
│   └── app/
│       ├── main.py                 # FastAPI 인스턴스
│       ├── config.py               # 환경설정
│       ├── database.py             # SQLAlchemy 세션
│       ├── models.py               # Stock / WatchlistItem / FwdPEHistory / MarketTiming
│       ├── schemas.py              # Pydantic 응답 스키마
│       ├── scheduler.py            # APScheduler — 매일 새벽 1시 갱신
│       ├── api/
│       │   ├── stocks.py           # GET /api/stocks, /api/stocks/sectors
│       │   ├── watchlist.py        # GET/POST/DELETE /api/watchlist
│       │   └── market.py           # GET /api/market/timing
│       └── services/
│           ├── wikipedia.py        # S&P500 구성종목 스크레이퍼
│           ├── yfinance_svc.py     # 시총·가격·재무 수집기 + SPY/VIX
│           ├── market_data.py      # CNN Fear & Greed
│           ├── scoring.py          # 점수 계산 엔진 (A + B + 최종 등급)
│           └── updater.py          # 일일 갱신 오케스트레이터 (FWD PE 누적 포함)
└── frontend/
    ├── package.json
    ├── vite.config.js              # /api → :8000 프록시
    ├── tailwind.config.js          # 다크 팔레트 + 모노 폰트
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                 # 라우팅 + 상단 네비
        ├── index.css
        ├── api/client.js
        ├── lib/format.js           # 숫자 포매터, 트렌드 색상
        ├── components/
        │   ├── MarketTimingBar.jsx # 상단 매크로 지표 스트립
        │   └── SignalBadge.jsx
        └── pages/
            ├── ListPage.jsx        # 500종목 + 검색/섹터 필터
            └── WatchlistPage.jsx   # 관심종목 + 점수/시그널 + 상세 모달
```

---

## 실행 방법

### 0. 요구사항
- Python 3.10+
- Node.js 18+

### 1. 백엔드

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

**최초 실행 시**: DB가 비어 있으면 자동으로 시드 잡(`run_daily_update`)이 돕니다. Wikipedia에서 500개 종목 목록을 받고 yfinance로 시총을 가져오는 데 **2~5분** 정도 걸립니다. 시드 중에도 API는 곧바로 뜨고, 데이터는 점진적으로 채워집니다.

수동으로 시드만 돌리고 싶다면:
```bash
python run.py --seed
```

- API 문서: <http://localhost:8000/docs>
- 헬스체크: <http://localhost:8000/api/health>

### 2. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 <http://localhost:5173>

---

## 점수 계산 시스템

### A. 개별 종목 (관심종목에서만 수집)

| 지표 | 구간 | 점수 |
|---|---|---|
| 52주 고점 대비 하락률 | ≥ −5% / [−15, −5) / [−30, −15) / < −30 | 0 / +1 / +2 / +3 |
| 200일 이동평균 괴리율 | > +20 / [+10, +20] / [−5, +10) / [−15, −5) / < −15 | −2 / −1 / 0 / +1 / +2 |
| 3년 평균 FWD PE 대비 | > +15 / [+5, +15] / [−5, +5) / [−15, −5) / < −15 | −2 / −1 / 0 / +1 / +2 |
| EPS Growth | ≥ +20 / [+5, +20) / [−5, +5) / [−20, −5) / < −20 | +2 / +1 / 0 / −1 / −2 |
| RSI(14) | ≤25 / 25–75 / ≥75 | +1 / 0 / −1 |
| Debt/Equity | ≤0.3 / >0.3 | +1 / 0 |

### B. 시장 타이밍 (전 종목 공통 가산점)

| 지표 | 구간 | 점수 |
|---|---|---|
| SPY 52주 하락률 | ≥−5 / [−10, −5) / [−20, −10) / < −20 | −1 / 0 / +1 / +3 |
| VIX | >30 / [20, 30] / [15, 20) / <15 | +2 / +1 / 0 / −1 |
| Fear & Greed | ≤10 / (10, 30] / (30, 70) / ≥70 | +2 / +1 / 0 / −1 |

### 최종 시그널 (A + B 합산)

| 합산 점수 | 등급 |
|---|---|
| ≥ 8 | 🟢 매수 (강한 시그널) |
| 4 ~ 7 | 🟢 매수 대기 |
| −1 ~ 3 | ⚪ 관망 |
| −5 ~ −2 | 🟠 매도 대기 |
| ≤ −6 | 🔴 매도 |

---

## API 요약

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/stocks?q=&sector=` | 500종목 (시총 순). DB-only. |
| GET | `/api/stocks/sectors` | 섹터 목록 |
| GET | `/api/watchlist` | 관심종목 + 점수 + 시그널 |
| POST | `/api/watchlist` `{ticker}` | 관심종목 추가 (즉시 1회 디테일 수집) |
| DELETE | `/api/watchlist/{ticker}` | 관심종목 삭제 |
| POST | `/api/watchlist/refresh` | 관심종목 디테일만 즉시 갱신 |
| GET | `/api/market/timing` | 매크로 지표 스냅샷 + 가산점 |
| POST | `/api/market/timing/refresh` | 매크로만 갱신 |
| POST | `/api/market/full-refresh` | Wikipedia + 시총 + 관심종목 + 매크로 전체 |

> **중요**: 프론트엔드는 외부 API를 직접 호출하지 않습니다. 모든 시세/지표 데이터는 백엔드가 SQLite에 적재한 값을 읽어옵니다.

---

## SQLite 스키마

```
stocks                  S&P500 전 종목 (시총, rank 포함)
watchlist               관심종목 + 재무/기술 지표
fwd_pe_history          FWD PE 일일 스냅샷 → 3년 평균 계산용
market_timing           SPY/VIX/F&G 최신 스냅샷 (id=1, 단일 행)
```

DB 파일은 `backend/app/data/sp500.db` 에 생성됩니다.

---

## 자동 업데이트

`APScheduler` 가 기본적으로 **매일 UTC 01:00** 에 `run_daily_update()` 를 실행합니다:

1. Wikipedia 구성종목 목록 갱신 (편입/편출 반영, 편출은 비활성 처리만)
2. 전 종목 시총 갱신 → 시총 순 `rank` 재계산
3. 관심종목 디테일 (RSI, 52w↓, MA200, FWD PE, D/E, EPS Growth) 갱신
4. FWD PE 스냅샷을 `fwd_pe_history` 에 1일 1행 추가 → 최근 3년치 평균 재계산
5. SPY/VIX/F&G 최신값 수집 → `market_timing` 단일 행 업데이트

스케줄을 바꾸려면 `UPDATE_HOUR`, `UPDATE_MINUTE` 환경변수로 조정할 수 있습니다.

---

## 디자인 메모

- 색상: `#0a0e14` 잉크 배경, 데이터값은 JetBrains Mono로 `tabular-nums` 정렬, 등락은 emerald/red 외 단색만 사용 (Bloomberg 터미널 느낌).
- 시장 타이밍 스트립을 상단에 상시 표시해 모든 페이지에서 매크로 컨텍스트를 잃지 않게 했습니다.
- 점수 셀을 클릭(또는 "상세")하면 A·B 항목별 점수가 풀어져 나와 *왜 이 시그널인지* 추적 가능합니다.

---

## 면책

본 도구는 정량 모델 기반의 정보 제공 용도이며, 투자 자문이나 매매 추천이 아닙니다. 모든 의사결정의 책임은 사용자에게 있습니다.
