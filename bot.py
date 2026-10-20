"""메시지 우클릭 → 앱 → 요약. 외부 연결은 실행 시에만 생성한다."""

import logging
import math
import os

import aiohttp
import discord
from discord import app_commands
from discord.app_commands.checks import Cooldown
from dotenv import load_dotenv

from yoyakman.collector import collect_below_message
from yoyakman.config import Settings
from yoyakman.formatter import (
    append_discord_notice,
    format_if_human,
    summary_chunks,
    trim_oldest_to_char_limit,
)
from yoyakman.rate_limit import (
    CooldownExceeded,
    SummaryRateLimiter,
    cooldown_window_phrase,
)
from yoyakman.summarizer import GeminiSummarizer, SummaryError

load_dotenv()
SETTINGS = Settings.from_env()
logger = logging.getLogger(__name__)
NO_MENTIONS = discord.AllowedMentions.none()
_DELIVERY_ERRORS = (discord.HTTPException, aiohttp.ClientError, OSError)
_RESERVATION_KEY = "summary_reservation"
_STARTED_KEY = "summary_started"
summary_limiter = SummaryRateLimiter()


def log_failure(
    event: str,
    interaction: discord.Interaction,
    error: BaseException,
    *,
    sent: int = 0,
    total: int = 0,
) -> None:
    # 오류 본문/traceback에는 요청 데이터나 키가 섞일 수 있어 타입·상태·ID만 기록한다.
    logger.warning(
        "%s interaction=%s error_type=%s status=%s sent=%s total=%s",
        event,
        interaction.id,
        type(error).__name__,
        getattr(error, "status", None),
        sent,
        total,
    )


async def reply(
    interaction: discord.Interaction,
    content: str,
    *,
    ephemeral: bool = False,
    recover_original: bool = True,
) -> bool:
    content = discord.utils.escape_mentions(content)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                content, ephemeral=ephemeral, allowed_mentions=NO_MENTIONS
            )
        else:
            await interaction.response.send_message(
                content, ephemeral=ephemeral, allowed_mentions=NO_MENTIONS
            )
        return True
    except _DELIVERY_ERRORS as error:
        log_failure("reply_send_failed", interaction, error)
    if recover_original and interaction.response.is_done():
        try:
            await interaction.edit_original_response(content=content, allowed_mentions=NO_MENTIONS)
            return True
        except _DELIVERY_ERRORS as error:
            log_failure("reply_recovery_failed", interaction, error)
    logger.error("reply_undelivered interaction=%s", interaction.id)
    return False


async def check_summary_cooldown(interaction: discord.Interaction) -> bool:
    # 모든 요약 진입점은 공유 manager를 사용한다. 같은 interaction의 재검사는 중복 차감하지 않는다.
    if _RESERVATION_KEY not in interaction.extras:
        try:
            interaction.extras[_RESERVATION_KEY] = summary_limiter.reserve(interaction.user.id)
        except CooldownExceeded as error:
            raise app_commands.CommandOnCooldown(
                Cooldown(summary_limiter.rate, summary_limiter.per), error.retry_after
            ) from None
    return True


def refund_summary_cooldown(interaction: discord.Interaction) -> None:
    reservation = interaction.extras.pop(_RESERVATION_KEY, None)
    if reservation is not None:
        summary_limiter.refund(reservation)


async def summarize_with_ai(chat_text: str) -> str:
    if bot.summarizer is None:
        raise SummaryError("configuration")
    return await bot.summarizer.summarize(chat_text)


async def respond_with_summary(
    interaction: discord.Interaction, collected: list[str], notice: str = ""
) -> None:
    if not collected:
        refund_summary_cooldown(interaction)
        await reply(
            interaction,
            f"{notice}요약할 대화를 찾지 못했어요. 대화가 더 쌓인 뒤에 다시 시도해주세요.",
        )
        return
    trimmed = trim_oldest_to_char_limit(collected, SETTINGS.max_log_chars)
    if trimmed != collected:
        dropped = len(collected) - len(trimmed)
        if dropped:
            notice += f"-# 입력 문자 수 제한으로 오래된 메시지 {dropped}개를 제외했어요.\n"
        if len(trimmed[-1]) < len(collected[-1]):
            notice += "-# 입력 문자 수 제한으로 남은 메시지 본문 일부만 분석했어요.\n"
    # 생성 단계의 동시 요청 대기·API 실패·취소·전송 실패는 차감 유지한다.
    interaction.extras[_STARTED_KEY] = True
    try:
        summary = await summarize_with_ai("\n".join(trimmed))
    except SummaryError as error:
        logger.warning("summary_failed interaction=%s kind=%s", interaction.id, error.kind)
        await reply(interaction, str(error))
        return
    except Exception as error:  # noqa: BLE001 - 외부 서비스의 예기치 않은 오류도 안전하게 안내한다.
        log_failure("summary_unexpected_failure", interaction, error)
        await reply(interaction, "요약 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.")
        return

    header = f"**채팅 요약** · 메시지 **{len(trimmed)}개** 분석\n{notice}{'─' * 30}\n"
    chunks = summary_chunks(header + summary, SETTINGS.max_response_messages)
    sent = 0
    last_message = None
    for chunk in chunks:
        try:
            last_message = await interaction.followup.send(
                chunk, wait=True, allowed_mentions=NO_MENTIONS
            )
        except _DELIVERY_ERRORS as error:
            log_failure("summary_send_failed", interaction, error, sent=sent, total=len(chunks))
            if sent == 0:
                try:
                    await interaction.edit_original_response(
                        content=chunk, allowed_mentions=NO_MENTIONS
                    )
                    sent += 1
                    continue
                except _DELIVERY_ERRORS as recovery_error:
                    log_failure(
                        "summary_first_chunk_recovery_failed",
                        interaction,
                        recovery_error,
                        total=len(chunks),
                    )
                await reply(
                    interaction, "요약은 생성했지만 전송하지 못했어요. 잠시 후 다시 시도해주세요."
                )
            else:
                status = f"\n\n-# 전송 오류로 요약 일부만 전달했어요 ({sent}/{len(chunks)}개). 잠시 후 다시 시도해주세요."
                try:
                    annotated = append_discord_notice(chunks[sent - 1], status)
                    if last_message is not None:
                        await last_message.edit(content=annotated, allowed_mentions=NO_MENTIONS)
                    else:
                        await interaction.edit_original_response(
                            content=annotated, allowed_mentions=NO_MENTIONS
                        )
                except _DELIVERY_ERRORS as recovery_error:
                    log_failure(
                        "summary_partial_status_failed",
                        interaction,
                        recovery_error,
                        sent=sent,
                        total=len(chunks),
                    )
                    if not await reply(interaction, status, ephemeral=True, recover_original=False):
                        logger.error(
                            "summary_partial_undelivered interaction=%s sent=%s total=%s",
                            interaction.id,
                            sent,
                            len(chunks),
                        )
            return
        sent += 1


class SummaryBot(discord.Client):
    summarizer: GeminiSummarizer | None = None

    async def close(self) -> None:
        try:
            if self.summarizer is not None:
                await self.summarizer.aclose()
                self.summarizer = None
        finally:
            await super().close()


intents = discord.Intents.default()
intents.message_content = True
bot = SummaryBot(intents=intents, allowed_mentions=NO_MENTIONS, max_messages=None)
tree = app_commands.CommandTree(bot)


@bot.event
async def setup_hook() -> None:
    bot.summarizer = GeminiSummarizer(SETTINGS, api_key=os.getenv("GEMINI_API_KEY"))
    try:
        synced = await tree.sync()
        logger.info("앱 명령 동기화 완료: %s개", len(synced))
    except Exception as error:  # noqa: BLE001 - 동기화 실패가 봇 시작을 막지 않게 한다.
        logger.warning("앱 명령 동기화 실패, 기존 등록 유지 error_type=%s", type(error).__name__)


@bot.event
async def on_ready() -> None:
    logger.info("봇 연결 완료: 서버 %s개 / 메시지 우클릭 → 앱 → 요약", len(bot.guilds))


@tree.context_menu(name="요약")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.check(check_summary_cooldown)
async def summarize_from_message(
    interaction: discord.Interaction, message: discord.Message
) -> None:
    try:
        await interaction.response.defer(thinking=True)
        try:
            result = await collect_below_message(
                message,
                limit=SETTINGS.max_messages,
                max_scan=SETTINGS.max_history_messages,
                timeout=SETTINGS.collection_timeout,
            )
            collected = result.messages
            notice = result.notice(SETTINGS.max_messages)
        except (discord.Forbidden, discord.NotFound) as error:
            log_failure("history_unavailable_selected_message_fallback", interaction, error)
            formatted = format_if_human(message)
            collected = [formatted] if formatted else []
            notice = "-# 채널 기록에 접근할 수 없어 선택한 메시지만 읽었어요.\n"
        await respond_with_summary(interaction, collected, notice)
    finally:
        if not interaction.extras.get(_STARTED_KEY):
            refund_summary_cooldown(interaction)


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.CommandOnCooldown):
        await reply(
            interaction,
            f"**잠시 쉬어가는 중이에요!** {math.ceil(error.retry_after)}초 후에 다시 사용할 수 있어요. "
            f"({cooldown_window_phrase(int(summary_limiter.per))} 최대 {summary_limiter.rate}회)",
            ephemeral=True,
        )
        return
    if not interaction.extras.get(_STARTED_KEY):
        refund_summary_cooldown(interaction)
    original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
    log_failure("command_failed", interaction, original)
    if isinstance(original, discord.HTTPException):
        content = "Discord 채널 기록을 읽거나 응답하는 데 실패했어요. 잠시 후 다시 시도해주세요."
    else:
        content = "문제가 발생했어요. 잠시 후 다시 시도해주세요."
    await reply(interaction, content, ephemeral=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    token = os.getenv("DISCORD_TOKEN")
    if not token or not os.getenv("GEMINI_API_KEY"):
        raise SystemExit(".env 파일에 DISCORD_TOKEN과 GEMINI_API_KEY를 설정해주세요.")
    bot.run(token, log_handler=None)
