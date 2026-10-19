"""비밀정보와 네트워크 없이 읽고 검증할 수 있는 실행 설정."""

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model: str = "gemini-2.5-flash"
    max_messages: int = 300
    max_history_messages: int = 3000
    collection_timeout: float = 15.0
    max_log_chars: int = 200_000
    summary_timeout: float = 120.0
    max_concurrent_summaries: int = 2
    api_max_attempts: int = 3
    max_response_messages: int = 4

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("GEMINI_MODEL은 비어 있을 수 없습니다.")
        bounds = {
            "max_messages": (1, 300),
            "max_history_messages": (1, 30_000),
            "collection_timeout": (0, 60),
            "max_log_chars": (1, 1_000_000),
            "summary_timeout": (0, 600),
            "max_concurrent_summaries": (1, 16),
            "api_max_attempts": (1, 5),
            "max_response_messages": (1, 5),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if not math.isfinite(value) or not low <= value <= high or value <= 0:
                raise ValueError(f"{name} 설정이 허용 범위를 벗어났습니다.")
        if self.max_history_messages < self.max_messages:
            raise ValueError("MAX_HISTORY_MESSAGES는 MAX_MESSAGES 이상이어야 합니다.")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        defaults = cls()
        values = {}
        for field in cls.__dataclass_fields__:
            key = "GEMINI_MODEL" if field == "model" else field.upper()
            default = getattr(defaults, field)
            try:
                values[field] = type(default)(source.get(key, default))
            except (TypeError, ValueError):
                # 환경 변수 값 자체에는 비밀정보가 들어 있을 수 있다.
                raise ValueError(f"{key} 설정 형식이 올바르지 않습니다.") from None
        return cls(**values)
