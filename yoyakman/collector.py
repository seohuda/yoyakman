"""선택 메시지 이후만 페이지 단위로 읽는다. 필터와 조회 상한은 별개다."""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

import discord

from .formatter import format_if_human

HISTORY_PAGE_SIZE = 100


@dataclass
class CollectionResult:
    messages: list[str] = field(default_factory=list)
    scanned_messages: int = 1  # 선택 메시지도 원본 조회 상한에 포함한다.
    stop_reason: Literal["complete", "message_limit", "scan_limit", "timeout"] = "complete"

    def notice(self, limit: int) -> str:
        if self.stop_reason == "message_limit":
            return (
                f"-# 추가 요약 대상 메시지가 있어 선택한 메시지부터 앞쪽 {limit}개만 수집했어요.\n"
            )
        if self.stop_reason == "scan_limit":
            return (
                f"-# 원본 메시지 {self.scanned_messages}개 조회 상한에 도달했어요. "
                "이후 대화는 확인하지 못했어요.\n"
            )
        if self.stop_reason == "timeout":
            return "-# 기록 조회 시간이 초과되어 지금까지 수집한 대화만 사용해요. 이후 대화는 확인하지 못했어요.\n"
        return ""


async def collect_from_message(
    channel: discord.abc.Messageable,
    start_message: discord.Message,
    limit: int = 300,
    *,
    max_scan: int = 3000,
    timeout: float = 15.0,  # noqa: ASYNC109 - asyncio.timeout으로 제한하고 부분 수집 결과를 반환한다.
) -> CollectionResult:
    if not 1 <= limit <= 300 or max_scan < limit or timeout <= 0:
        raise ValueError("메시지 수집 설정이 올바르지 않습니다.")
    result = CollectionResult()
    formatted = format_if_human(start_message)
    if formatted:
        result.messages.append(formatted)
    cursor = start_message.id
    try:
        async with asyncio.timeout(timeout):
            while result.scanned_messages < max_scan:
                page_limit = min(HISTORY_PAGE_SIZE, max_scan - result.scanned_messages)
                page_count = 0
                previous_cursor = cursor
                async for msg in channel.history(
                    limit=page_limit, after=discord.Object(id=cursor), oldest_first=True
                ):
                    page_count += 1
                    result.scanned_messages += 1
                    if msg.id <= cursor:
                        continue
                    cursor = msg.id
                    formatted = format_if_human(msg)
                    if not formatted:
                        continue
                    # 상한에 도달한 것만으로 초과라고 단정하지 않는다.
                    # 다음 유효 발언을 실제로 확인한 경우에만 누락을 알린다.
                    if len(result.messages) == limit:
                        result.stop_reason = "message_limit"
                        return result
                    result.messages.append(formatted)
                if page_count < page_limit:
                    return result
                if cursor <= previous_cursor:
                    break  # 비정상 페이지가 반복되어도 무제한 조회하지 않는다.
            result.stop_reason = "scan_limit"
    except TimeoutError:
        result.stop_reason = "timeout"
    return result


async def collect_below_message(
    start_message: discord.Message,
    *,
    limit: int = 300,
    max_scan: int = 3000,
    timeout: float = 15.0,  # noqa: ASYNC109 - 수집기의 공유 시간 예산을 전달한다.
) -> CollectionResult:
    return await collect_from_message(
        start_message.channel, start_message, limit, max_scan=max_scan, timeout=timeout
    )
