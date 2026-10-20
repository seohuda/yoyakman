"""화자 구분, 프롬프트 경계와 Discord 전송 길이를 안전하게 유지한다."""

import discord

CHAT_LOG_FENCE = "-----CHAT_LOG_BOUNDARY_a41f7c-----"
OUTPUT_TRUNCATED_NOTICE = "\n\n-# 출력 길이 제한으로 요약 뒷부분을 생략했어요."
_BIDI_CONTROLS = str.maketrans(
    "", "", "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)


def sanitize(text: str) -> str:
    return text.replace(CHAT_LOG_FENCE, "[제거됨]").translate(_BIDI_CONTROLS)


def flatten_body(text: str) -> str:
    return " ⏎ ".join(text.splitlines()).replace("\x00", "")


def sanitize_speaker(name: str) -> str:
    name = flatten_body(sanitize(name)).translate(str.maketrans(":()", "：（）"))
    return discord.utils.escape_mentions(name)


def display_name_of(user: discord.User | discord.Member) -> str:
    return sanitize_speaker(user.display_name)


def format_message(msg: discord.Message) -> str | None:
    parts = []
    if msg.clean_content.strip():
        parts.append(discord.utils.escape_mentions(sanitize(flatten_body(msg.clean_content))))
    if msg.attachments:
        parts.append(f"(첨부파일 {len(msg.attachments)}개)")
    if msg.stickers:
        parts.append("(스티커)")
    if not parts:
        return None
    reply_to = ""
    resolved = msg.reference.resolved if msg.reference else None
    if isinstance(resolved, discord.Message):
        reply_to = f" ({display_name_of(resolved.author)}에게 답장)"
    return f"{display_name_of(msg.author)}{reply_to}: {' '.join(parts)}"


def format_if_human(msg: discord.Message) -> str | None:
    return None if msg.author.bot else format_message(msg)


def trim_oldest_to_char_limit(lines: list[str], limit: int = 200_000) -> list[str]:
    """오래된 발언부터 제외한다. 한 줄도 상한보다 길면 그 줄의 앞부분만 남긴다."""
    if limit < 1:
        raise ValueError("limit은 양수여야 합니다.")
    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        if not kept and len(line) > limit:
            return [line[:limit]]
        extra = len(line) + bool(kept)
        if total + extra > limit:
            break
        kept.append(line)
        total += extra
    return list(reversed(kept))


def discord_length(text: str) -> int:
    """UTF-16 길이를 사용해 보조 평면 이모지도 2,000자 안에 넣는다."""
    return len(text.encode("utf-16-le")) // 2


def _prefix(text: str, limit: int) -> str:
    units = 0
    for index, char in enumerate(text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > limit:
            return text[:index]
    return text


def split_for_discord(text: str, limit: int = 2000) -> list[str]:
    if limit < 2:
        raise ValueError("limit은 2 이상이어야 합니다.")
    chunks = []
    text = text.strip()
    while text:
        prefix = _prefix(text, limit)
        cut = len(prefix)
        if cut < len(text):
            newline = prefix.rfind("\n")
            # 헤더 뒤에 아주 긴 URL/단어가 와도 헤더만 별도 메시지로 보내지 않는다.
            if newline >= len(prefix) // 2 and newline > 0:
                cut = newline
        chunk = text[:cut].strip()
        if chunk:
            chunks.append(chunk)
        text = text[cut:].lstrip()
    return chunks


def summary_chunks(text: str, max_messages: int = 4) -> list[str]:
    """멘션을 이스케이프하고 전송 개수를 제한한다. 실제 핑은 AllowedMentions로도 막는다."""
    if max_messages < 1:
        raise ValueError("max_messages는 양수여야 합니다.")
    # SDK가 비정상적으로 긴 텍스트를 돌려줘도 전체를 분할하지 않는다.
    escaped = discord.utils.escape_mentions(text)
    bounded = _prefix(escaped, 2000 * max_messages + 2)
    chunks = split_for_discord(bounded)
    if not chunks:
        return []
    if len(bounded) < len(escaped) or len(chunks) > max_messages:
        chunks = chunks[:max_messages]
        remaining = 2000 - discord_length(OUTPUT_TRUNCATED_NOTICE)
        chunks[-1] = _prefix(chunks[-1], remaining).rstrip() + OUTPUT_TRUNCATED_NOTICE
    return chunks


def append_discord_notice(text: str, notice: str) -> str:
    return _prefix(text, 2000 - discord_length(notice)).rstrip() + notice
