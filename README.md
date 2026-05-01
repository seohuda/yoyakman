# Discord 채팅 요약 봇

요약을 시작할 메시지에 답장으로 `!요약`을 입력하면, 해당 메시지 이후 대화를 Google Gemini가 요약해줍니다.

## 사전 준비

**Discord 봇 토큰**
1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. New Application → Bot 탭 → Reset Token으로 토큰 복사
3. Privileged Gateway Intents에서 **Message Content Intent** 활성화

**봇 서버 초대**
1. OAuth2 → URL Generator 탭
2. Scopes: `bot` / Bot Permissions: `Read Messages`, `Send Messages`, `Read Message History`
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

1. 요약을 시작할 메시지에 **답장(Reply)** 선택
2. `!요약` 입력 후 전송
3. 봇이 해당 메시지 이후 채팅 최대 100개를 수집해 요약 반환

하루 사용 제한: 전체 20회 / 1인당 2회 (자정 초기화) (무료 요금제 이슈)


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
