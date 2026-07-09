# ORION MASTER PLAN

## 목표

미국 시장에서 돈이 이동하는 사건(Event)을 가장 먼저 발견하고, 그 돈이 흘러갈 한국 기업을 찾는다.

---

## 핵심 원칙

1. 뉴스가 아니라 사건(Event)을 분석한다.
2. 좋은 뉴스만 분석한다.
3. 실제 돈이 움직인 사건을 우선한다.
4. 한국 기업 연결은 직접수혜와 간접수혜를 구분한다.
5. 재무와 차트는 마지막 검증 단계다.
6. 모든 추천은 백테스트로 검증한다.

---

## 전체 구조

미국뉴스 수집
↓
Event Engine
↓
Event Intelligence
↓
Money Flow Engine
↓
Korea Mapping Engine
↓
Champion Engine
↓
Market Engine
↓
Chart Engine
↓
Telegram Report
↓
Backtest

---

## 1. News Collector

### 역할

미국 뉴스와 한국 뉴스를 최대한 많이 수집한다.

### 입력

- RSS
- 뉴스 사이트
- 경제 뉴스
- AI 뉴스
- 반도체 뉴스
- 거시경제 뉴스

### 출력

```python
[
    {
        "title": "",
        "link": "",
        "source": "",
        "market": "US",
        "published": ""
    }
]
