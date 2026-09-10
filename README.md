# 퇴직연금 주요 이슈 데일리 대시보드

매일 아침 퇴직연금·연금 주요 이슈 10건을 수집·요약해 보여주는 화면.

## 보는 방법

- **PC** — 이 폴더의 `index.html` 더블클릭
- **웹·휴대폰** — https://claude.ai/code/artifact/193698ba-0ed1-4069-8493-efd6cc70b3c2
  (비공개. 공유하려면 페이지의 공유 메뉴를 쓴다. 매일 같은 주소가 갱신된다.)

## 화면

일간 / 주간 / 월간 / 연간 4개 탭. 각 탭에 최대 10건.

- 상단 기간 축에서 탭을 고른다. 오른쪽으로 갈수록 보는 기간이 넓어진다.
- 분야(제도·규제 / 업계·경쟁사 / 가입자·사회)로 걸러 볼 수 있다.
- `원문 보기`로 기사 전문으로 이동한다.
- 주간 이상 탭에서는 같은 사건을 다룬 기사가 `관련 기사 N건`으로 접혀 있다.
- 게재일은 `오늘`·`어제`·`3일 전`처럼 기준일 대비로 표시된다.

## 매일 자동 갱신

Windows 작업 스케줄러에 **`퇴직연금 주요 이슈 데일리`** 작업이 등록돼 있다.
매일 **07:40**에 `run_daily.ps1`이 실행되어 수집 → 요약 → 빌드 → 웹 게시까지 처리한다.

- 그 시각에 PC가 꺼져 있었으면, 다음에 켤 때 이어서 실행된다.
- 실행 기록은 `logs/daily-YYYY-MM.log`에 쌓인다.
- 작업을 끄거나 시간을 바꾸려면 `작업 스케줄러`(taskschd.msc)에서 같은 이름의 작업을 연다.

클라우드 예약 에이전트를 쓰지 않은 이유: 클라우드 세션은 이 PC의 `data/` 폴더에
접근할 수 없어 과거 데이터 누적과 기간별 집계가 불가능하다.

## 직접 갱신하기

Claude Code를 열고 `오늘 이슈 갱신해줘`라고 하면 된다.
수집·요약 절차는 `daily_update.md`에 있다.

명령을 직접 실행하려면:

```bash
python -X utf8 rollup.py    # 일간 파일들 → 주간/월간/연간 재집계
python -X utf8 build.py     # 데이터 → index.html, artifact.html
```

## 구조

| 파일 | 역할 |
|---|---|
| `periods.py` | 일간/주간/월간/연간 기간 키와 범위 계산 |
| `store.py` | 기간 파일(JSON) 검증과 입출력 |
| `dedupe.py` | 중복·후속 기사 묶기 |
| `rollup.py` | 일간 파일 → 기간별 TOP 10 |
| `build.py` | 기간 파일 → `index.html`(로컬용) + `artifact.html`(웹 게시용) |
| `template.html` | 화면 뼈대. 데이터가 인라인으로 주입된다 |
| `daily_update.md` | 매일 수행하는 수집 절차 |
| `data/` | 날짜별 원본 데이터. 지우면 과거 이슈가 사라진다 |

`index.html`과 `artifact.html`은 `build.py`가 만드는 결과물이라 직접 고치지 않는다.
화면을 바꾸려면 `template.html`을 고친다.

## 테스트

```bash
python -X utf8 -m unittest discover -s tests -t . -v
```

## 설계 문서

- 설계: `docs/superpowers/specs/2026-09-10-pension-daily-dashboard-design.md`
- 구현 계획: `docs/superpowers/plans/2026-09-10-pension-daily-dashboard.md`
