"""Discord 명령 경로와 전송 복구 회귀 테스트. 모든 외부 호출은 mock이다."""

import asyncio
import os
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands

import bot
from tests.helpers import FakeChannel, fake_message, interaction
from yoyakman.collector import CollectionResult
from yoyakman.formatter import discord_length
from yoyakman.rate_limit import SummaryRateLimiter
from yoyakman.summarizer import SummaryError


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.setattr(bot, "summary_limiter", SummaryRateLimiter())


def http_error(status=429):
    cls = {403: discord.Forbidden, 404: discord.NotFound}.get(status, discord.HTTPException)
    return cls(SimpleNamespace(status=status, reason="ERROR"), "secret-placeholder")


def install_summary(monkeypatch, result="요약 본문", error=None):
    summary = AsyncMock(return_value=result, side_effect=error)
    monkeypatch.setattr(bot, "summarize_with_ai", summary)
    return summary


def test_import_requires_neither_api_keys_nor_sdk_client_construction():
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("DISCORD_TOKEN", "GEMINI_API_KEY", "GOOGLE_API_KEY")
    }
    code = """
from unittest.mock import patch
with patch('dotenv.load_dotenv'), patch('google.genai.Client', side_effect=AssertionError('import created client')):
    import bot
    assert bot.bot.summarizer is None
    from yoyakman.formatter import split_for_discord
    assert split_for_discord('한글🙂') == ['한글🙂']
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_only_message_context_menu_is_registered_with_both_install_types():
    commands = bot.tree.get_commands()
    assert len(commands) == 1
    command = commands[0]
    assert command.name == "요약"
    assert command.type == discord.AppCommandType.message
    assert command.allowed_installs.guild and command.allowed_installs.user
    assert (
        command.allowed_contexts.guild
        and command.allowed_contexts.dm_channel
        and command.allowed_contexts.private_channel
    )
    assert bot.bot.allowed_mentions.to_dict()["parse"] == []


def test_reply_forwards_ephemeral_and_blocks_mentions_after_defer():
    obj = interaction()
    assert asyncio.run(bot.reply(obj, "문제가 발생했어요.", ephemeral=True))
    obj.followup.send.assert_awaited_once_with(
        "문제가 발생했어요.", ephemeral=True, allowed_mentions=bot.NO_MENTIONS
    )


def test_reply_recovers_via_original_response_after_followup_failure():
    obj = interaction()
    obj.followup.send.side_effect = http_error()
    assert asyncio.run(bot.reply(obj, "@everyone 오류"))
    kwargs = obj.edit_original_response.await_args.kwargs
    assert "@everyone" not in kwargs["content"]
    assert kwargs["allowed_mentions"].to_dict()["parse"] == []


def test_reply_failure_logs_diagnostics_without_error_contents(caplog):
    obj = interaction(interaction_id=456)
    obj.followup.send.side_effect = http_error()
    obj.edit_original_response.side_effect = http_error(404)
    assert not asyncio.run(bot.reply(obj, "비공개 대화 원문"))
    assert "reply_undelivered interaction=456" in caplog.text
    assert "secret-placeholder" not in caplog.text
    assert "비공개 대화 원문" not in caplog.text


def test_initial_response_failures_are_logged_without_editing_nonexistent_original(caplog):
    obj = interaction(done=False)
    obj.response.send_message.side_effect = http_error()
    assert not asyncio.run(bot.reply(obj, "오류", ephemeral=True))
    obj.edit_original_response.assert_not_awaited()
    assert "reply_undelivered" in caplog.text


def test_general_error_handler_is_ephemeral_and_hides_exception_content():
    obj = interaction(done=False)
    asyncio.run(bot.on_app_command_error(obj, RuntimeError("secret-placeholder")))
    kwargs = obj.response.send_message.await_args.kwargs
    assert kwargs["ephemeral"] is True
    assert "secret-placeholder" not in obj.response.send_message.await_args.args[0]


def test_cooldown_error_copy_uses_actual_limiter_settings(monkeypatch):
    monkeypatch.setattr(bot, "summary_limiter", SummaryRateLimiter(rate=4, per=120))
    obj = interaction(done=False)
    error = app_commands.CommandOnCooldown(MagicMock(), 7.2)
    asyncio.run(bot.on_app_command_error(obj, error))
    text = obj.response.send_message.await_args.args[0]
    assert "2분에 최대 4회" in text
    assert "8초" in text


def test_shared_cooldown_reservation_is_not_recharged_by_another_check():
    async def run():
        obj = interaction(user_id=99)
        await bot.check_summary_cooldown(obj)
        await bot.check_summary_cooldown(obj)
        await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=2))
        await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=3))
        with pytest.raises(app_commands.CommandOnCooldown):
            await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=4))

    asyncio.run(run())


def test_empty_collection_refunds_its_own_request_and_keeps_context_notice(monkeypatch):
    summary = install_summary(monkeypatch)
    obj = interaction(user_id=99)

    async def run():
        await bot.check_summary_cooldown(obj)
        await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=2))
        await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=3))
        await bot.respond_with_summary(obj, [], notice="기록 접근 불가. ")
        await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=4))
        with pytest.raises(app_commands.CommandOnCooldown):
            await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=5))

    asyncio.run(run())
    summary.assert_not_awaited()
    assert "기록 접근 불가" in obj.followup.send.await_args.args[0]


def test_actual_api_failure_is_charged_according_to_documented_policy(monkeypatch):
    install_summary(monkeypatch, error=SummaryError("quota"))

    async def run():
        for i in range(3):
            obj = interaction(user_id=99, interaction_id=i)
            await bot.check_summary_cooldown(obj)
            await bot.respond_with_summary(obj, ["사람: 내용"])
            assert "사용량 제한" in obj.followup.send.await_args.args[0]
        with pytest.raises(app_commands.CommandOnCooldown):
            await bot.check_summary_cooldown(interaction(user_id=99, interaction_id=4))

    asyncio.run(run())


def test_char_truncation_discloses_dropped_input_and_accurate_analysis_count(monkeypatch):
    monkeypatch.setattr(bot, "SETTINGS", replace(bot.SETTINGS, max_log_chars=10))
    summary = install_summary(monkeypatch)
    obj = interaction()
    asyncio.run(
        bot.respond_with_summary(
            obj, ["오래된: 발언발언발언", "나: 안녕", "너: 안녕"], notice="수집 상한 안내.\n"
        )
    )
    summary.assert_awaited_once_with("너: 안녕")
    text = obj.followup.send.await_args.args[0]
    assert "메시지 **1개** 분석" in text
    assert "입력 문자 수 제한으로 오래된 메시지 2개" in text
    assert "수집 상한 안내" in text


def test_single_oversized_input_is_bounded_and_disclosed(monkeypatch):
    monkeypatch.setattr(bot, "SETTINGS", replace(bot.SETTINGS, max_log_chars=10))
    summary = install_summary(monkeypatch)
    obj = interaction()
    asyncio.run(bot.respond_with_summary(obj, ["나: " + "긴본문" * 20]))
    assert len(summary.await_args.args[0]) == 10
    text = obj.followup.send.await_args.args[0]
    assert "본문 일부만 분석" in text
    assert "메시지 **1개** 분석" in text


def test_success_is_public_bounded_and_cannot_ping(monkeypatch):
    install_summary(
        monkeypatch,
        result="@everyone <@123456789012345678> <@&123456789012345678> " + "한글🙂" * 10_000,
    )
    obj = interaction()
    asyncio.run(bot.respond_with_summary(obj, ["나: 안녕"]))
    assert obj.followup.send.await_count == 4
    for call in obj.followup.send.await_args_list:
        assert discord_length(call.args[0]) <= 2000
        assert call.args[0].strip()
        assert call.kwargs.get("ephemeral", False) is False
        assert call.kwargs["allowed_mentions"].to_dict()["parse"] == []
        assert "@everyone" not in call.args[0]
        assert "<@123" not in call.args[0] and "<@&123" not in call.args[0]
    assert "출력 길이 제한" in obj.followup.send.await_args.args[0]


def test_first_chunk_send_failure_recovers_the_summary_in_original(monkeypatch):
    install_summary(monkeypatch)
    obj = interaction()
    obj.followup.send.side_effect = http_error()
    asyncio.run(bot.respond_with_summary(obj, ["alice: hi"]))
    obj.edit_original_response.assert_awaited_once()
    assert "요약 본문" in obj.edit_original_response.await_args.kwargs["content"]
    assert obj.followup.send.await_count == 1


def test_partial_chunk_send_failure_annotates_last_delivered_chunk(monkeypatch):
    install_summary(monkeypatch, result="가" * 3500)
    obj = interaction()
    last_message = SimpleNamespace(edit=AsyncMock())
    obj.followup.send.side_effect = [last_message, http_error()]
    asyncio.run(bot.respond_with_summary(obj, ["alice: hi"]))
    assert obj.followup.send.await_count == 2
    text = last_message.edit.await_args.kwargs["content"]
    assert "일부만 전달" in text and "1/2개" in text
    assert discord_length(text) <= 2000
    assert "요약 중 문제가" not in text
    obj.edit_original_response.assert_not_awaited()


def test_first_chunk_fallback_then_later_failure_edits_original_status(monkeypatch):
    install_summary(monkeypatch, result="가" * 3500)
    obj = interaction()
    obj.followup.send.side_effect = http_error()
    asyncio.run(bot.respond_with_summary(obj, ["alice: hi"]))
    assert obj.edit_original_response.await_count == 2
    assert "1/2개" in obj.edit_original_response.await_args.kwargs["content"]


def test_failed_partial_annotation_uses_ephemeral_status(monkeypatch):
    install_summary(monkeypatch, result="가" * 3500)
    obj = interaction()
    last_message = SimpleNamespace(edit=AsyncMock(side_effect=http_error()))
    obj.followup.send.side_effect = [last_message, http_error(), None]
    asyncio.run(bot.respond_with_summary(obj, ["alice: hi"]))
    assert obj.followup.send.await_args.kwargs["ephemeral"] is True
    assert "1/2개" in obj.followup.send.await_args.args[0]


def test_all_partial_recoveries_fail_with_diagnostic_counts(monkeypatch, caplog):
    install_summary(monkeypatch, result="가" * 3500)
    obj = interaction(interaction_id=333)
    last_message = SimpleNamespace(edit=AsyncMock(side_effect=http_error()))
    obj.followup.send.side_effect = [last_message, http_error(), http_error()]
    asyncio.run(bot.respond_with_summary(obj, ["비공개 원문"]))
    assert "summary_partial_undelivered interaction=333 sent=1 total=2" in caplog.text
    assert "secret-placeholder" not in caplog.text and "비공개 원문" not in caplog.text


def test_all_first_chunk_deliveries_fail_without_misreporting_ai_failure(monkeypatch, caplog):
    install_summary(monkeypatch)
    obj = interaction()
    obj.followup.send.side_effect = http_error()
    obj.edit_original_response.side_effect = http_error()
    asyncio.run(bot.respond_with_summary(obj, ["alice: hi"]))
    sent = [call.args[0] for call in obj.followup.send.await_args_list]
    assert not any("요약 중 문제가 발생했어요" in text for text in sent)
    assert any("요약은 생성했지만 전송하지 못" in text for text in sent)
    assert "reply_undelivered" in caplog.text


@pytest.mark.parametrize(
    "kind,phrase",
    [
        ("authentication", "인증"),
        ("permission", "권한"),
        ("quota", "사용량"),
        ("timeout", "오래"),
        ("blocked", "안전 정책"),
        ("empty", "빈 응답"),
    ],
)
def test_error_categories_have_distinct_korean_guidance(monkeypatch, kind, phrase):
    install_summary(monkeypatch, error=SummaryError(kind))
    obj = interaction()
    asyncio.run(bot.respond_with_summary(obj, ["나: 안녕"]))
    assert phrase in obj.followup.send.await_args.args[0]


def test_unexpected_summary_error_is_logged_without_raw_data(monkeypatch, caplog):
    install_summary(monkeypatch, error=RuntimeError("secret-placeholder"))
    obj = interaction()
    asyncio.run(bot.respond_with_summary(obj, ["민감한 원문"]))
    assert "summary_unexpected_failure" in caplog.text
    assert "secret-placeholder" not in caplog.text and "민감한 원문" not in caplog.text


def test_command_collects_300_beyond_default_100_without_false_overflow(monkeypatch):
    summary = install_summary(monkeypatch)
    messages = [fake_message(content=f"본문{i}", msg_id=i) for i in range(300)]
    messages[0].channel = FakeChannel(messages)
    obj = interaction()
    asyncio.run(bot.summarize_from_message.callback(obj, messages[0]))
    assert len(summary.await_args.args[0].splitlines()) == 300
    text = obj.followup.send.await_args.args[0]
    assert "메시지 **300개** 분석" in text
    assert "추가 요약 대상" not in text
    obj.response.defer.assert_awaited_once_with(thinking=True)


def test_command_discloses_confirmed_message_overflow(monkeypatch):
    install_summary(monkeypatch)
    messages = [fake_message(msg_id=i) for i in range(301)]
    messages[0].channel = FakeChannel(messages)
    obj = interaction()
    asyncio.run(bot.summarize_from_message.callback(obj, messages[0]))
    assert "추가 요약 대상 메시지가 있어" in obj.followup.send.await_args.args[0]


@pytest.mark.parametrize("status", [403, 404])
def test_user_install_without_history_access_only_summarizes_selected_message(monkeypatch, status):
    summary = install_summary(monkeypatch)
    message = fake_message("선택화자", "선택본문")
    message.channel = FakeChannel(error=http_error(status))
    obj = interaction()
    asyncio.run(bot.summarize_from_message.callback(obj, message))
    summary.assert_awaited_once_with("선택화자: 선택본문")
    assert "채널 기록에 접근할 수 없어 선택한 메시지만" in obj.followup.send.await_args.args[0]


def test_fallback_still_filters_bot_messages_and_refunds_empty_input(monkeypatch):
    summary = install_summary(monkeypatch)
    message = fake_message(bot=True)
    message.channel = FakeChannel(error=http_error(403))
    obj = interaction()

    async def run():
        await bot.check_summary_cooldown(obj)
        await bot.summarize_from_message.callback(obj, message)
        assert bot.summary_limiter.bucket_count == 0

    asyncio.run(run())
    summary.assert_not_awaited()
    assert "선택한 메시지만" in obj.followup.send.await_args.args[0]
    assert "요약할 대화를 찾지 못" in obj.followup.send.await_args.args[0]


def test_temporary_history_http_error_does_not_silently_fallback_and_refunds(monkeypatch):
    summary = install_summary(monkeypatch)
    message = fake_message()
    message.channel = FakeChannel(error=http_error(503))
    obj = interaction()

    async def run():
        await bot.check_summary_cooldown(obj)
        with pytest.raises(discord.HTTPException):
            await bot.summarize_from_message.callback(obj, message)
        assert bot.summary_limiter.bucket_count == 0

    asyncio.run(run())
    summary.assert_not_awaited()


def test_cancelled_collection_refunds_and_propagates_cancellation(monkeypatch):
    message = fake_message()
    message.channel = FakeChannel([fake_message(msg_id=1)], delay=10)
    obj = interaction()

    async def run():
        await bot.check_summary_cooldown(obj)
        task = asyncio.create_task(bot.summarize_from_message.callback(obj, message))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert bot.summary_limiter.bucket_count == 0

    asyncio.run(run())


def test_cancelled_generation_propagates_without_refund(monkeypatch):
    install_summary(monkeypatch, error=asyncio.CancelledError())
    monkeypatch.setattr(
        bot,
        "collect_below_message",
        AsyncMock(return_value=CollectionResult(messages=["사람: 내용"])),
    )
    obj = interaction()

    async def run():
        await bot.check_summary_cooldown(obj)
        with pytest.raises(asyncio.CancelledError):
            await bot.summarize_from_message.callback(obj, fake_message())
        assert bot.summary_limiter.bucket_count == 1

    asyncio.run(run())
    obj.followup.send.assert_not_awaited()


def test_setup_hook_survives_sync_oserror_without_calling_gemini(monkeypatch):
    monkeypatch.setattr(bot.tree, "sync", AsyncMock(side_effect=OSError("dns")))
    monkeypatch.setattr(bot.bot, "summarizer", None)
    asyncio.run(bot.setup_hook())
    assert bot.bot.summarizer is not None


def test_bot_shutdown_closes_summarizer():
    client = bot.SummaryBot(intents=discord.Intents.none())
    summarizer = SimpleNamespace(aclose=AsyncMock())
    client.summarizer = summarizer
    asyncio.run(client.close())
    summarizer.aclose.assert_awaited_once()
    assert client.summarizer is None
