# yoyakman

디스코드 채팅을 Gemini로 요약하는 봇.

## 쓰는 법

메시지 **우클릭 → 앱 → 요약**. 고른 메시지부터 아래쪽만 읽는다 (최대 300개).

답장하면서 `/요약` 치는 건 디스코드 API가 대상 메시지를 봇에 안 넘겨서 안 된다. 우클릭 메뉴만 쓴다.

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
