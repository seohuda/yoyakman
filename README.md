# Discord 채팅 요약 봇

`/요약` 슬래시 커맨드 또는 메시지 우클릭 메뉴로 채널 대화를 Google Gemini가 요약해줍니다.

## 사전 준비

**Discord 봇 토큰**
1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. New Application → Bot 탭 → Reset Token으로 토큰 복사
3. Privileged Gateway Intents에서 **Message Content Intent** 활성화

**봇 서버 초대**
1. OAuth2 → URL Generator 탭
2. Scopes: `bot`, `applications.commands` / Bot Permissions: `Read Messages`, `Send Messages`, `Read Message History`
3. 생성된 URL로 초대

**Gemini API 키**
1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. Create API Key → 복사

## 설치 및 실행

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 토큰과 키 입력 후 실행
python bot.py
```

## 사용 방법

**최근 대화 요약**
- `/요약` 입력 → 최근 메시지 최대 100개 수집 (100개가 안 되면 있는 만큼)

**특정 메시지부터 요약**
- 요약을 시작할 메시지 **우클릭 → 앱 → 이 메시지부터 요약** (해당 메시지부터 최대 100개 수집)

사용 제한: 1인당 분당 최대 3회

## 봇 없는 서버에서도 사용하기 (유저 설치)

1. Developer Portal → Installation 탭 → **User Install** 체크
2. Install Link의 URL로 접속해 **내 계정에 추가** 선택
3. 이후 봇이 없는 서버나 DM에서도 커맨드 사용 가능
   - 단, 봇이 없는 곳에서는 채널 기록을 읽을 수 없어 **이 메시지부터 요약**으로 선택한 메시지만 요약됩니다

> 봇을 새로 초대했거나 커맨드가 안 보이면, 봇 재시작 후 디스코드 클라이언트를 새로고침(Ctrl+R)하세요. 슬래시 커맨드 전역 등록에 최대 1시간 걸릴 수 있습니다.


## 다른 AI로 교체

`bot.py`의 `summarize_with_ai()` 함수 내부만 수정하면 됩니다.

```python
# OpenAI 교체 예시
async def summarize_with_ai(chat_text: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"요약해줘:\n{chat_text}"}]
    )
    return response.choices[0].message.content
```

## 주의사항

- Message Content Intent가 없으면 메시지를 읽을 수 없습니다
- Gemini 무료 티어는 분당 요청 제한이 있습니다
