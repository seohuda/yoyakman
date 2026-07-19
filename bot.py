import asyncio
import os

import discord
from discord import app_commands
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
- 출력은 아래 [TEMPLATE] 구조를 정확히 따른다. 템플릿 외의 섹션이나 이모지를 추가하지 않는다.

[SECTION RULES]
1. 전체적인 흐름 요약: 2~4문장. 대화의 시작 → 전개 → 결론(있다면) 순서로, 핵심 참여자 닉네임을 자연스럽게 녹여서 서술.
2. 핵심 키워드: 대화의 실제 주제를 나타내는 구체적인 명사 3~4개를 해시태그로. "#대화", "#채팅" 같은 무의미한 키워드 금지.
3. 누가 무슨 말을 했을까?: 유의미한 발언을 한 참여자만, 발언량이 많은 순서로 1인당 1문장. 한두 마디만 한 사람이나 리액션만 한 사람은 생략. 여러 명이 같은 의견이면 "A, B: ~에 동의했음"처럼 한 줄로 묶는다.

[TEMPLATE]
**전체적인 흐름 요약**
- (요약 내용)

**핵심 키워드**
#키워드1 #키워드2 #키워드3

**누가 무슨 말을 했을까?**
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


async def collect_from_message(
    channel: discord.abc.Messageable,
    start_message: discord.Message,
    limit: int = 100,
) -> list[str]:
    messages = []

    if not start_message.author.bot:
        formatted = format_message(start_message)
        if formatted:
            messages.append(formatted)

    async for msg in channel.history(after=start_message, limit=limit, oldest_first=True):
        if msg.author.bot:
            continue
        formatted = format_message(msg)
        if formatted:
            messages.append(formatted)
    return messages


async def collect_recent(
    channel: discord.abc.Messageable,
    count: int,
) -> list[str]:
    messages = []
    async for msg in channel.history(limit=count):
        if msg.author.bot:
            continue
        formatted = format_message(msg)
        if formatted:
            messages.append(formatted)
    messages.reverse()
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


async def respond_with_summary(interaction: discord.Interaction, collected: list[str], notice: str = ""):
    if not collected:
        await interaction.followup.send("요약할 대화가 없어요. 대화가 더 쌓인 뒤에 다시 시도해주세요.")
        return

    try:
        chat_text = "\n".join(collected)
        summary = await asyncio.wait_for(summarize_with_ai(chat_text), timeout=90)

        header = (
            f"**채팅 요약** · 메시지 **{len(collected)}개** 분석\n"
            f"{notice}"
            f"{'─' * 30}\n"
        )
        for chunk in split_for_discord(header + summary):
            await interaction.followup.send(chunk)

    except asyncio.TimeoutError:
        await interaction.followup.send("요약 생성이 너무 오래 걸려 중단했어요. 잠시 후 다시 시도해주세요.")
    except Exception as e:
        print(f"[ERROR] 요약 처리 중 오류: {e}")
        await interaction.followup.send("요약 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    synced = await bot.tree.sync()
    print(f"슬래시 커맨드 동기화 완료: {len(synced)}개")


@bot.event
async def on_ready():
    print(f"봇 로그인 완료: {bot.user} (ID: {bot.user.id})")
    print(f"연결된 서버 수: {len(bot.guilds)}개")
    print("사용법: /요약 또는 메시지 우클릭 → 앱 → 이 메시지부터 요약")


@bot.tree.command(name="요약", description="이 채널의 최근 대화를 최대 100개까지 요약해요")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.checks.cooldown(3, 60)
async def summarize_recent(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        collected = await collect_recent(interaction.channel, count=100)
    except (discord.Forbidden, discord.HTTPException):
        await interaction.followup.send(
            "이 채널의 대화 기록을 읽을 수 없어요.\n"
            "봇이 초대되지 않은 서버에서는 메시지 우클릭 → 앱 → **이 메시지부터 요약**으로 선택한 메시지만 요약할 수 있어요."
        )
        return

    await respond_with_summary(interaction, collected)


@bot.tree.context_menu(name="이 메시지부터 요약")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.checks.cooldown(3, 60)
async def summarize_from_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)

    notice = ""
    try:
        collected = await collect_from_message(
            channel=interaction.channel,
            start_message=message,
            limit=100,
        )
    except (discord.Forbidden, discord.HTTPException):
        formatted = format_message(message)
        collected = [formatted] if formatted else []
        notice = "-# 봇이 없는 곳이라 채널 기록을 읽을 수 없어, 선택한 메시지만 요약했어요.\n"

    await respond_with_summary(interaction, collected, notice=notice)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"**잠시 쉬어가는 중이에요!** {error.retry_after:.0f}초 후에 다시 사용할 수 있어요. (1분에 최대 3회)",
            ephemeral=True,
        )
        return
    print(f"[ERROR] 커맨드 처리 중 오류: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message("문제가 발생했어요. 잠시 후 다시 시도해주세요.", ephemeral=True)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print(".env 파일에 DISCORD_TOKEN이 없습니다!")
        exit(1)
    if not GEMINI_API_KEY:
        print(".env 파일에 GEMINI_API_KEY가 없습니다!")
        exit(1)

    bot.run(DISCORD_TOKEN)
