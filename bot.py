import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import date

import google.generativeai as genai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

DAILY_LIMIT_TOTAL = 20
DAILY_LIMIT_USER = 2
USAGE_FILE = "usage.json"


def load_usage() -> dict:
    today = str(date.today())
    try:
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") != today:
            return {"date": today, "total": 0, "users": {}}
        return data
    except:
        return {"date": today, "total": 0, "users": {}}


def save_usage(data: dict):
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def summarize_with_ai(chat_text: str) -> str:
    prompt = f"""너는 대화 요약 AI다.
다음 채팅을 카카오톡 AI 요약처럼 정리해라.

규칙:
- 핵심 요약은 2~3줄, 각 줄마다 닉네임을 문장 안에 자연스럽게 포함
- 예시: "치즈님이 멀티 게임을 하자고 제안했고, 골프님은 미연시 게임을 추천했습니다."
- 키워드는 3~4개만
- 사용자별 요약은 닉네임 명시, 1인당 1줄로 제한
- 불필요한 설명 금지, 최대한 짧고 자연스럽게

형식:
📌 핵심 요약
- (닉네임 포함 2~3줄)

🧩 키워드
#키워드1 #키워드2 #키워드3

💬 사용자별 요약
- 닉네임: 한 줄 요약
- 닉네임: 한 줄 요약

채팅:
{chat_text}"""

    response = await gemini_model.generate_content_async(prompt)
    return response.text


async def collect_messages(
    channel: discord.TextChannel,
    after_message: discord.Message,
    limit: int = 100,
) -> list[str]:
    messages = []
    async for msg in channel.history(after=after_message, limit=limit, oldest_first=True):
        if msg.author.bot:
            continue
        messages.append(f"{msg.author.display_name}: {msg.content}")
    return messages


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    usage = load_usage()
    print(f"봇 로그인 완료: {bot.user} (ID: {bot.user.id})")
    print(f"연결된 서버 수: {len(bot.guilds)}개")
    print(f"오늘 전체 남은 횟수: {DAILY_LIMIT_TOTAL - usage['total']}/{DAILY_LIMIT_TOTAL}")
    print("사용법: 요약할 메시지에 답장 → !요약 입력")


@bot.command(name="요약")
async def summarize_command(ctx: commands.Context):
    user_id = str(ctx.author.id)

    if ctx.message.reference is None:
        await ctx.reply(
            "⚠️ **요약할 메시지에 답장으로 명령어를 사용해주세요.**\n"
            "사용법: 요약을 시작할 메시지에 답장 → `!요약` 입력"
        )
        return

    usage = load_usage()
    user_count = usage["users"].get(user_id, 0)
    total_count = usage["total"]

    if total_count >= DAILY_LIMIT_TOTAL:
        await ctx.reply(
            f"❌ **오늘 전체 요약 횟수를 모두 사용했습니다! (0/{DAILY_LIMIT_TOTAL})**\n"
            "내일 자정에 초기화됩니다. "
        )
        return

    if user_count >= DAILY_LIMIT_USER:
        remaining_total = DAILY_LIMIT_TOTAL - total_count
        await ctx.reply(
            f"❌ **{ctx.author.display_name}님은 오늘 요약을 모두 사용했습니다! (0/{DAILY_LIMIT_USER})**\n"
            f"전체 잔여 횟수: {remaining_total}/{DAILY_LIMIT_TOTAL} | 내일 자정에 초기화됩니다. "
        )
        return

    processing_msg = await ctx.reply("⏳ 채팅을 수집하고 요약 중입니다...")

    try:
        start_message_id = ctx.message.reference.message_id
        start_message = await ctx.channel.fetch_message(start_message_id)

        collected = await collect_messages(
            channel=ctx.channel,
            after_message=start_message,
            limit=100,
        )
        collected = [m for m in collected if not m.endswith("!요약")]

        if not collected:
            await processing_msg.edit(content="📭 기준 메시지 이후에 요약할 채팅이 없습니다.")
            return

        chat_text = "\n".join(collected)
        summary = await summarize_with_ai(chat_text)

        usage["total"] += 1
        usage["users"][user_id] = user_count + 1
        save_usage(usage)

        remaining_total = DAILY_LIMIT_TOTAL - usage["total"]
        remaining_user = DAILY_LIMIT_USER - usage["users"][user_id]

        header = (
            f"🗂️ **채팅 요약 결과** | 수집된 메시지: **{len(collected)}개**\n"
            f"🔋 전체 남은 횟수: **{remaining_total}/{DAILY_LIMIT_TOTAL}** "
            f"| {ctx.author.display_name}님 남은 횟수: **{remaining_user}/{DAILY_LIMIT_USER}**\n"
            f"{'─' * 40}\n"
        )
        await processing_msg.edit(content=header + summary)

    except discord.NotFound:
        await processing_msg.edit(content="❌ 답장 대상 메시지를 찾을 수 없습니다. 삭제된 메시지일 수 있습니다.")
    except discord.Forbidden:
        await processing_msg.edit(content="❌ 봇이 이 채널의 메시지를 읽을 권한이 없습니다.")
    except Exception as e:
        print(f"[ERROR] !요약 처리 중 오류: {e}")
        await processing_msg.edit(content=f"❌ 요약 중 오류가 발생했습니다.\n```{str(e)}```")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ .env 파일에 DISCORD_TOKEN이 없습니다!")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ .env 파일에 GEMINI_API_KEY가 없습니다!")
        exit(1)

    bot.run(DISCORD_TOKEN)
