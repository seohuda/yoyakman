import asyncio

import pytest

from tests.helpers import FakeChannel, fake_message
from yoyakman.collector import collect_below_message, collect_from_message


@pytest.mark.parametrize("count", [0, 1, 100, 101, 299, 300, 301, 450])
def test_collect_valid_messages_across_history_pages(count):
    messages = [fake_message(content=f"메시지{i}", msg_id=i) for i in range(count)]
    start = messages[0] if messages else fake_message(content="", msg_id=0)
    channel = FakeChannel(messages)
    start.channel = channel
    result = asyncio.run(collect_below_message(start))
    assert len(result.messages) == min(count, 300)
    assert result.messages == [f"사람: 메시지{i}" for i in range(min(count, 300))]
    assert result.stop_reason == ("message_limit" if count > 300 else "complete")
    assert bool(result.notice(300)) == (count > 300)
    assert all(call["limit"] == 100 and call["oldest_first"] for call in channel.calls)


def test_fake_history_default_limit_is_100_raw_messages():
    channel = FakeChannel([fake_message(msg_id=i) for i in range(300)])

    async def run():
        return [msg async for msg in channel.history()]

    messages = asyncio.run(run())
    assert len(messages) == 100
    assert messages[0].id == 299


def test_filtering_advances_cursor_through_many_bots_and_empty_messages():
    messages = [fake_message(content=f"본문{i}", bot=i % 5 != 0, msg_id=i) for i in range(1501)]
    # 301명의 사람 중 한 발언은 공백뿐이다. 정확히 300개면 초과가 아니다.
    messages[500].clean_content = " \n\t"
    channel = FakeChannel(messages)
    result = asyncio.run(collect_from_message(channel, messages[0]))
    assert len(result.messages) == 300
    assert result.stop_reason == "complete"
    assert result.messages[-1] == "사람: 본문1500"
    cursors = [call["after"].id for call in channel.calls]
    assert cursors == sorted(set(cursors))
    assert len(channel.calls) > 10


def test_no_history_before_anchor_or_unrelated_channel_tail_is_mixed_in():
    messages = [fake_message(content=f"본문{i}", msg_id=i) for i in range(900)]
    channel = FakeChannel(messages)
    result = asyncio.run(collect_from_message(channel, messages[150]))
    assert result.messages == [f"사람: 본문{i}" for i in range(150, 450)]
    assert result.stop_reason == "message_limit"


def test_scan_limit_is_bounded_and_does_not_claim_300_valid_messages():
    start = fake_message(msg_id=0)
    channel = FakeChannel([fake_message(bot=True, msg_id=i) for i in range(1, 20_000)])
    result = asyncio.run(collect_from_message(channel, start, max_scan=350))
    assert result.scanned_messages == 350
    assert len(result.messages) == 1
    assert sum(call["limit"] for call in channel.calls) == 349
    assert result.stop_reason == "scan_limit"
    assert "이후 대화는 확인하지 못" in result.notice(300)
    assert "300개" not in result.notice(300)


def test_exactly_300_with_filtered_tail_does_not_claim_overflow():
    messages = [fake_message(msg_id=i) for i in range(300)]
    messages += [fake_message(bot=True, msg_id=i) for i in range(300, 600)]
    result = asyncio.run(collect_from_message(FakeChannel(messages), messages[0]))
    assert len(result.messages) == 300
    assert result.stop_reason == "complete"
    assert result.notice(300) == ""


def test_unknown_tail_at_scan_cap_is_reported_truthfully():
    messages = [fake_message(msg_id=i) for i in range(300)]
    result = asyncio.run(collect_from_message(FakeChannel(messages), messages[0], max_scan=300))
    assert len(result.messages) == 300
    assert result.stop_reason == "scan_limit"
    assert "추가 요약 대상" not in result.notice(300)


def test_collection_timeout_preserves_partial_data():
    start = fake_message(msg_id=0)
    channel = FakeChannel([fake_message(msg_id=1)], delay=1)
    result = asyncio.run(collect_from_message(channel, start, timeout=0.01))
    assert result.messages == ["사람: 내용"]
    assert result.stop_reason == "timeout"


def test_cancellation_propagates_from_history():
    async def run():
        task = asyncio.create_task(
            collect_from_message(FakeChannel([fake_message(msg_id=1)], delay=1), fake_message())
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())


def test_attachment_and_sticker_only_messages_are_valid_bots_are_not():
    messages = [
        fake_message(content="", attachments=[object()], msg_id=0),
        fake_message(content="", stickers=[object()], msg_id=1),
        fake_message(content="", msg_id=2),
        fake_message(content="", bot=True, attachments=[object()], msg_id=3),
    ]
    result = asyncio.run(collect_from_message(FakeChannel(messages), messages[0]))
    assert result.messages == ["사람: (첨부파일 1개)", "사람: (스티커)"]
