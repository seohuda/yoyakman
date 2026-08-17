# yoyakman

디스코드 채팅을 Gemini로 요약하는 봇.

## 쓰는 법

| 방법 | 뭐를 읽나 |
| --- | --- |
| `/요약` | 채널 맨 아래 최근 대화 (최대 300개) |
| 메시지 우클릭 → **이 메시지부터 요약** | 그 메시지부터 아래쪽만 |

둘은 다르다. 특정 지점부터 보려면 우클릭 메뉴를 써야 한다.

분당 3회 (사람당).

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # DISCORD_TOKEN, GEMINI_API_KEY
python bot.py
```

테스트:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## 봇 만들기

1. [Developer Portal](https://discord.com/developers/applications)에서 봇 생성
2. Bot → **Message Content Intent** 켜기
3. OAuth2 URL Generator: `bot` + `applications.commands`, 권한 Read/Send Messages, Read Message History
4. [Google AI Studio](https://aistudio.google.com/app/apikey)에서 API 키 발급

커맨드 안 보이면 봇 재시작 후 클라이언트 새로고침 (Ctrl+R). 전역 등록은 최대 1시간 걸릴 수 있다.

## 유저 설치 (봇 없는 서버)

Developer Portal → Installation → **User Install** → Install Link로 내 계정에 추가.

봇이 없는 채널에서는 기록을 못 읽어서, 우클릭 메뉴로 고른 메시지만 요약된다.

## AI 바꾸기

`summarize_with_ai()`만 갈아끼우면 된다.

## 기타

- Message Content Intent 없으면 메시지 못 읽음
- Gemini 무료 티어는 RPM 제한 있음
