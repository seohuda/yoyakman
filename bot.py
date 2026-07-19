import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import google.generativeai as genai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")




async def summarize_with_ai(chat_text: str) -> str:
    prompt = f"""[SYSTEM]
Role: Advanced Chat Summarizer
Goal: Parse the chat log, analyze context, and provide a highly accurate, structured summary.
Constraints:
- Maintain a factual, concise tone. Do not use AI-like conversational filler (e.g., "요약해 드리겠습니다").
- Output MUST perfectly match the specified template.
- Identify the core context and omit irrelevant small talk.

[RULES]
1. Core Summary (📌 전체적인 흐름 요약): 2~4 sentences. Seamlessly integrate the nicknames of key participants.
2. Keywords (🧩 핵심 키워드): Extract exactly 3~4 keywords, formatted as hashtags.
3. User Summary (💬 누가 무슨 말을 했을까?): 1 sentence per significant participant. Omit lurkers or irrelevant messages.

[TEMPLATE]
📌 전체적인 흐름 요약
- (Contextual summary here)

🧩 핵심 키워드
#Keyword1 #Keyword2 #Keyword3

💬 누가 무슨 말을 했을까?
- Nickname: (Action/Statement)
- Nickname: (Action/Statement)

[INPUT_CHAT_LOG]
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
    print(f"봇 로그인 완료: {bot.user} (ID: {bot.user.id})")
    print(f"연결된 서버 수: {len(bot.guilds)}개")
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

    # 사용 제한 없음

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

        header = (
            f"🗂️ **채팅 요약 결과** | 수집된 메시지: **{len(collected)}개**\n"
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
