import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import google.generativeai as genai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config=genai.types.GenerationConfig(
        temperature=0.2,
        top_p=0.9,
    ),
)




async def summarize_with_ai(chat_text: str) -> str:
    prompt = f"""[SYSTEM]
Role: 한국어 디스코드 채팅 로그 전문 요약가
Goal: 채팅 로그를 정밀하게 분석해, 읽지 않은 사람도 대화의 맥락과 결론을 한눈에 파악할 수 있는 정확한 구조화 요약을 작성한다.

[INPUT FORMAT]
- [INPUT_CHAT_LOG]의 각 줄은 "닉네임: 메시지" 형식이며 시간순으로 정렬되어 있다.
- "닉네임 (아무개에게 답장): ..."은 아무개의 발언에 대한 답장이다. 이 관계를 화자 귀속과 대화 흐름 파악에 활용하라.
- "(첨부파일 N개)", "(스티커)"는 이미지·파일 등을 보냈다는 표시다. 내용은 알 수 없으므로 추측하지 말고, 필요하면 "사진을 공유했음" 정도로만 언급하라.
- 한 사람이 연속으로 여러 줄을 보내 하나의 발언을 이어가는 경우가 흔하다. 연속된 같은 닉네임의 줄은 하나의 발언으로 묶어서 해석하라.
- 디스코드 채팅 특성상 오타, 초성체(ㅇㅇ, ㅋㅋ), 신조어, 반말이 섞여 있다. 표면 표현이 아니라 실제 의도를 파악해 요약하라.

[ANALYSIS STEPS] (내부적으로 수행하고, 출력에는 결과만 반영)
1. 대화를 주제 단위로 구분한다. 주제가 여러 개면 각각 파악하고, 어떤 주제가 중심인지 판단한다.
2. 각 발언의 화자를 정확히 귀속시킨다. A가 한 말을 B가 한 것으로 절대 바꾸지 않는다.
3. 질문과 답변, 제안과 반응, 합의된 결론이나 결정 사항을 짝지어 파악한다.
4. 농담, 비꼼, 인용, 가정법("~라면")은 문자 그대로의 사실로 보고하지 않고 그 뉘앙스대로 정리한다.

[ACCURACY RULES] — 가장 중요
- 로그에 없는 사실, 인물, 의견, 결론을 절대 만들어내지 않는다. 불확실하면 쓰지 않는다.
- 닉네임은 로그에 나온 표기 그대로 사용한다. 줄이거나 번역하지 않는다.
- 날짜, 시간, 장소, 숫자, 링크 관련 내용은 로그에 있는 그대로만 옮긴다.
- 대화에서 결정된 사항(약속, 일정, 합의)이 있으면 반드시 요약에 포함한다.

[STYLE RULES]
- 출력 언어: 한국어. 문체는 "~했음", "~하는 중" 같은 간결한 개조식 또는 짧은 평서문.
- "요약해 드리겠습니다" 같은 AI 인사말·설명·마무리 멘트를 절대 붙이지 않는다.
- 출력은 아래 [TEMPLATE] 구조를 정확히 따른다. 템플릿 외의 섹션을 추가하지 않는다.

[SECTION RULES]
1. 📌 전체적인 흐름 요약: 2~4문장. 대화의 시작 → 전개 → 결론(있다면) 순서로, 핵심 참여자 닉네임을 자연스럽게 녹여서 서술.
2. 🧩 핵심 키워드: 대화의 실제 주제를 나타내는 구체적인 명사 3~4개를 해시태그로. "#대화", "#채팅" 같은 무의미한 키워드 금지.
3. 💬 누가 무슨 말을 했을까?: 유의미한 발언을 한 참여자만, 발언량이 많은 순서로 1인당 1문장. 한두 마디만 한 사람이나 리액션만 한 사람은 생략. 여러 명이 같은 의견이면 "A, B: ~에 동의했음"처럼 한 줄로 묶는다.

[TEMPLATE]
📌 전체적인 흐름 요약
- (요약 내용)

🧩 핵심 키워드
#키워드1 #키워드2 #키워드3

💬 누가 무슨 말을 했을까?
- 닉네임: (발언/행동 요약)
- 닉네임: (발언/행동 요약)

[INPUT_CHAT_LOG]
{chat_text}"""

    response = await gemini_model.generate_content_async(prompt)

    if not response.candidates or response.candidates[0].finish_reason not in (1, "STOP"):
        reason = response.candidates[0].finish_reason if response.candidates else "NO_CANDIDATES"
        raise ValueError(f"AI가 응답을 생성하지 못했습니다 (finish_reason={reason}).")

    return response.text


def format_message(msg: discord.Message) -> str | None:
    parts = []
    if msg.clean_content:
        parts.append(msg.clean_content)
    if msg.attachments:
        parts.append(f"(첨부파일 {len(msg.attachments)}개)")
    if msg.stickers:
        parts.append("(스티커)")
    if not parts:
        return None

    reply_to = ""
    resolved = msg.reference.resolved if msg.reference else None
    if isinstance(resolved, discord.Message):
        reply_to = f" ({resolved.author.display_name}에게 답장)"

    return f"{msg.author.display_name}{reply_to}: {' '.join(parts)}"


async def collect_messages(
    channel: discord.TextChannel,
    start_message: discord.Message,
    exclude_message_id: int,
    limit: int = 100,
) -> list[str]:
    messages = []

    if not start_message.author.bot:
        formatted = format_message(start_message)
        if formatted:
            messages.append(formatted)

    async for msg in channel.history(after=start_message, limit=limit, oldest_first=True):
        if msg.author.bot or msg.id == exclude_message_id:
            continue
        formatted = format_message(msg)
        if formatted:
            messages.append(formatted)
    return messages


def split_for_discord(text: str, limit: int = 2000) -> list[str]:
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)
    return chunks


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"봇 로그인 완료: {bot.user} (ID: {bot.user.id})")
    print(f"연결된 서버 수: {len(bot.guilds)}개")
    print("사용법: 요약할 메시지에 답장 → !요약 입력")


@bot.command(name="요약")
@commands.cooldown(3, 60, commands.BucketType.user)
async def summarize_command(ctx: commands.Context):
    if ctx.message.reference is None:
        await ctx.reply(
            "⚠️ **어디서부터 요약할지 알려주세요!**\n"
            "요약을 시작할 메시지에 **답장(Reply)** 을 걸고 `!요약`을 입력하면, 그 메시지 이후의 대화를 요약해드려요."
        )
        return

    processing_msg = await ctx.reply("⏳ 채팅을 수집해서 요약하고 있어요. 잠시만 기다려주세요...")

    try:
        start_message_id = ctx.message.reference.message_id
        start_message = await ctx.channel.fetch_message(start_message_id)

        collected = await collect_messages(
            channel=ctx.channel,
            start_message=start_message,
            exclude_message_id=ctx.message.id,
            limit=100,
        )

        if not collected:
            await processing_msg.edit(content="📭 기준 메시지 이후에 요약할 대화가 없어요. 대화가 더 쌓인 뒤에 다시 시도해주세요.")
            return

        chat_text = "\n".join(collected)
        summary = await asyncio.wait_for(summarize_with_ai(chat_text), timeout=90)

        header = (
            f"🗂️ **채팅 요약** · 메시지 **{len(collected)}개** 분석\n"
            f"{'─' * 30}\n"
        )
        first, *rest = split_for_discord(header + summary)
        await processing_msg.edit(content=first)
        for chunk in rest:
            await ctx.send(chunk)

    except asyncio.TimeoutError:
        await processing_msg.edit(content="⌛ 요약 생성이 너무 오래 걸려 중단했어요. 잠시 후 다시 시도해주세요.")
    except discord.NotFound:
        await processing_msg.edit(content="❌ 답장한 메시지를 찾을 수 없어요. 삭제된 메시지일 수 있으니 다른 메시지에 답장해서 다시 시도해주세요.")
    except discord.Forbidden:
        await processing_msg.edit(content="❌ 봇에게 이 채널의 메시지를 읽을 권한이 없어요. 서버 관리자에게 권한 설정을 요청해주세요.")
    except Exception as e:
        print(f"[ERROR] !요약 처리 중 오류: {e}")
        await processing_msg.edit(content="❌ 요약 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.")


@summarize_command.error
async def summarize_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"🚦 **잠시 쉬어가는 중이에요!** {error.retry_after:.0f}초 후에 다시 사용할 수 있어요. (1분에 최대 3회)")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ .env 파일에 DISCORD_TOKEN이 없습니다!")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ .env 파일에 GEMINI_API_KEY가 없습니다!")
        exit(1)

    bot.run(DISCORD_TOKEN)
