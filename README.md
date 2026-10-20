# yoyakman · 요약맨

Discord 채팅을 Gemini로 요약하는 봇. **메시지 우클릭 → 앱 → 요약**을 사용한다. `/요약` 슬래시 명령은 없다.

## 요약 범위와 사용 제한

- 선택 메시지를 포함해 **그 이후 대화만 시간순으로 최대 300개** 수집한다. 이전 기록이나 채널 끝의 최근 메시지를 섞지 않는다.
- 봇·공백 메시지는 제외한다. 첨부파일·스티커만 있는 메시지는 전송 사실만 표시하며 파일 내용을 추측하지 않는다.
- 필터링을 고려해 원본 최대 3,000개를 100개씩 조회한다. 기록 조회는 최대 15초다. 조회 상한·시간 제한으로 이후 대화를 확인하지 못하면 별도로 안내한다.
- 301번째 유효 발언을 실제로 확인했을 때만 300개 제한 안내를 표시한다. 입력이 200,000자를 넘으면 오래된 발언부터 제외하고 **실제 분석한 개수**와 제외 사실을 알린다. 마지막 한 발언도 너무 길면 본문 일부만 보낸다.
- 기존 한국어 템플릿(흐름 요약 / 핵심 키워드 / 발언자별 정리)을 유지한다. 결과는 메시지당 2,000자 이내, 기본 최대 4개로 나누고 생략 사실을 표시한다.
- 사용자마다 **최근 60초 동안 3회**. 모든 요약 진입점에서 같은 제한을 사용한다. 입력 없음·기록 조회 실패·생성 전 취소는 해당 요청의 횟수를 반환한다. **요약 생성 단계 진입 후에는 대기 중 시간초과, API 실패·취소·전송 실패도 차감한다.**

## 설치와 실행

Python **3.11 또는 3.12**를 사용한다.

```bash
git clone https://github.com/seohuda/yoyakman.git
cd yoyakman
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
# .env에 DISCORD_TOKEN, GEMINI_API_KEY 입력
python bot.py
```

운영에서도 같은 명령을 systemd 등 프로세스 관리자로 실행한다. 작업 디렉터리를 저장소로 지정하거나 환경 변수를 주입한다. 종료 시 진행 중인 Gemini 요청을 취소하고 클라이언트를 닫는다. 쿨다운은 메모리 기반이므로 **단일 프로세스**로 실행한다. 재시작하면 사용 이력이 초기화된다.

## Discord 앱 설정

1. [Developer Portal](https://discord.com/developers/applications)에서 앱과 봇을 만든다. Bot의 토큰을 `DISCORD_TOKEN`에 넣는다.
2. Bot → **Privileged Gateway Intents → Message Content Intent**를 켠다. 코드에서도 활성화한다. 멤버·프레즌스 Intent는 필요 없다.
3. Installation에서 필요한 설치 유형을 켠다.
   - **Guild Install**: `bot`, `applications.commands` scopes. 채널 보기(View Channel), 메시지 보내기(Send Messages), 메시지 기록 보기(Read Message History) 권한을 준다. 스레드에서는 Send Messages in Threads도 필요하다.
   - **User Install**: `applications.commands` scope로 내 계정에 추가한다. 봇이 없는 채널에서는 보통 기록 접근이 불가능해 **선택한 메시지만 요약**한다. 서버 설치에서도 기록 접근이 거절되거나 채널이 없어지면 같은 방식으로 폴백한다.
4. 설치 링크로 앱을 추가하고 봇을 실행한다. 메시지 **우클릭 → 앱 → 요약**을 선택한다.

명령이 보이지 않으면 재시작 후 Discord 클라이언트를 새로고침한다. 전역 명령 반영에는 시간이 걸릴 수 있다. 동기화가 일시적으로 실패하면 기존 등록 명령으로 계속 실행한다.

## Gemini와 환경 변수

[Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급한 키를 `GEMINI_API_KEY`에 넣는다. 공식 **google-genai** SDK의 비동기 API를 사용한다. 키가 없어도 모듈 import와 테스트는 가능하지만 봇 실행에는 두 키가 모두 필요하다.

| 환경 변수 | 기본값 | 의미 / 허용 범위 |
| --- | --- | --- |
| `DISCORD_TOKEN` | 필수 | Discord 봇 토큰 |
| `GEMINI_API_KEY` | 필수 | Gemini Developer API 키 |
| `GEMINI_MODEL` | `gemini-2.5-flash` | 접근 가능한 텍스트 생성 모델 ID |
| `MAX_MESSAGES` | `300` | 유효 요약 메시지 수, 1–300 |
| `MAX_HISTORY_MESSAGES` | `3000` | 선택 메시지를 포함한 원본 조회 수, MAX_MESSAGES 이상·30,000 이하 |
| `COLLECTION_TIMEOUT` | `15` | 기록 조회 시간(초), 0 초과·60 이하 |
| `MAX_LOG_CHARS` | `200000` | 직렬화한 입력 문자 수, 1–1,000,000 |
| `SUMMARY_TIMEOUT` | `120` | 동시 요청 대기·API 호출·재시도 전체 시간(초), 0 초과·600 이하 |
| `MAX_CONCURRENT_SUMMARIES` | `2` | 동시에 처리하는 요약 수, 1–16 |
| `API_MAX_ATTEMPTS` | `3` | 최초 호출을 포함한 최대 시도 수, 1–5 |
| `MAX_RESPONSE_MESSAGES` | `4` | 요약 결과 메시지 수, 1–5 |

2026-10-19 공식 [모델 목록](https://ai.google.dev/gemini-api/docs/models)과 [지원 종료 안내](https://ai.google.dev/gemini-api/docs/deprecations)를 확인했다. **gemini-2.5-flash는 지원 종료가 공지되지 않았지만 과거 사용 이력이 있는 사용자로 접근이 제한된다.** 기존 운영의 비용·응답 속도와 한국어 요약 동작을 유지하기 위해 기본값을 보존했다. 한국어 품질의 새 비교 실험은 수행하지 않았다. 신규 프로젝트는 공식 문서의 권장 모델인 `gemini-3.5-flash-lite` 또는 `gemini-3.8-flash` 등 실제 접근 가능한 모델을 설정한다. 모델을 바꾸면 권한·요금·응답 품질을 별도로 확인한다.

이전 SDK에서의 전환 방법은 [공식 마이그레이션 문서](https://ai.google.dev/gemini-api/docs/migrate)를 참고한다. 사고 토큰 때문에 본문 없이 잘리는 일을 피하도록 출력 토큰은 모델 기본값을 사용한다. Discord 전송 상한은 이미 생성된 AI 출력의 토큰 비용을 줄이지 않는다.

429·500·502·503 API 응답과 **연결 수립 실패(`httpx.ConnectError`)**만 제한적으로 재시도한다. Retry-After(초/HTTP 날짜)·RetryInfo와 지수 백오프·jitter를 적용한다. SDK 내부 재시도는 꺼서 시도 수가 곱해지지 않는다. 인증·권한·잘못된 설정·빈/차단 응답은 재시도하지 않으며, 서버 처리 여부가 불명확한 타임아웃 및 읽기·쓰기·프로토콜 전송 오류(`ReadError`, `WriteError`, `RemoteProtocolError` 등)도 자동 재호출하지 않는다. 연결 또는 응답 오류만으로 과금 여부를 확정할 수는 없다.

무료 티어도 요청·토큰 할당량 제한이 있다. 재시도에는 추가 비용이 발생할 수 있고, 로컬에서 취소해도 서버가 이미 처리한 요청은 과금될 수 있다. 운영자는 AI Studio/Cloud에서 사용량과 예산을 확인한다.

## 개인정보와 공개 범위

요약을 요청하면 수집한 **본문·표시 이름·답장 대상 표시 이름**을 Google Gemini API로 전송한다. 첨부파일/스티커의 실제 파일과 내용은 업로드하지 않는다. 원본 로그를 파일·DB에 저장하지 않고 Discord 메시지 캐시도 비활성화한다. 운영 로그에는 오류 유형·상태·interaction ID·전송 개수만 남긴다. Google 측 데이터 취급은 [Gemini API 약관](https://ai.google.dev/gemini-api/terms)을 따른다.

**요약 결과는 기본적으로 명령을 실행한 대화에 공개**되며 그 대화를 볼 수 있는 사람도 읽을 수 있다. 민감한 대화는 외부 전송과 공개 범위를 고려해 요청한다. 입력은 실제 시스템 지시와 분리하고, 경계선·닉네임 개행·멘션을 처리한다. 전송 시 `AllowedMentions.none()`도 사용해 실제 멘션을 막는다. 프롬프트 방어만으로 모델의 정확성을 보장할 수 없으므로 중요한 결정은 원문과 대조한다.

`.env`와 토큰은 커밋하지 않는다. 운영에서도 원본 대화나 SDK 오류 본문을 별도 로그에 추가하지 않는다.

## 개발과 검증

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q bot.py yoyakman tests
python -m ruff check .
python -m ruff format --check .
python -m mypy
git diff --check
```

GitHub Actions에서도 Python 3.11·3.12로 실행한다. 테스트는 Discord/Gemini를 mock하고 소켓 연결을 차단한다. 실제 새 SDK의 직렬화·응답 파싱도 로컬 HTTP 모의 전송으로 확인한다. 운영 API를 호출하는 종단 검증과는 다르다.

배포 전에는 테스트 서버에서 서버/사용자 설치, Message Content Intent, 실제 모델 접근·한국어 요약 품질·요금, 공개 응답과 스레드 권한을 확인한다. PR 생성만으로 실행 중인 봇이 배포되지는 않는다.

코드는 `bot.py`(명령·전송), `yoyakman/config.py`(설정), `collector.py`(수집), `formatter.py`(직렬화·길이), `summarizer.py`(Gemini·프롬프트·재시도), `rate_limit.py`(공유 쿨다운)로 나뉜다.
