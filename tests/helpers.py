import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def fake_message(
    author_name="사람",
    content="내용",
    *,
    bot=False,
    attachments=(),
    stickers=(),
    reference=None,
    msg_id=0,
):
    return SimpleNamespace(
        id=msg_id,
        author=SimpleNamespace(display_name=author_name, bot=bot),
        clean_content=content,
        attachments=list(attachments),
        stickers=list(stickers),
        reference=reference,
        channel=SimpleNamespace(),
    )


class FakeChannel:
    """discord.py처럼 limit 생략 시 원본 100개까지만 반환한다."""

    def __init__(self, messages=(), *, delay=0, error=None):
        self.messages = list(messages)
        self.calls = []
        self.delay = delay
        self.error = error

    async def history(self, *, limit=100, after=None, oldest_first=None):
        self.calls.append({"limit": limit, "after": after, "oldest_first": oldest_first})
        if self.error:
            raise self.error
        if oldest_first is None:
            oldest_first = after is not None
        messages = sorted(
            (msg for msg in self.messages if after is None or msg.id > after.id),
            key=lambda msg: msg.id,
            reverse=not oldest_first,
        )
        for message in messages if limit is None else messages[:limit]:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield message


def interaction(*, done=True, user_id=1, interaction_id=1):
    obj = MagicMock()
    obj.id = interaction_id
    obj.user.id = user_id
    obj.extras = {}
    obj.response.is_done.return_value = done
    obj.response.send_message = AsyncMock()
    obj.response.defer = AsyncMock()
    obj.followup.send = AsyncMock()
    obj.edit_original_response = AsyncMock()
    return obj
