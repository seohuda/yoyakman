"""단일 프로세스용 사용자별 sliding window. 예약별 반환으로 동시 요청을 구별한다."""

import itertools
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

COOLDOWN_RATE = 3
COOLDOWN_PER = 60


@dataclass(frozen=True)
class Reservation:
    user_id: int
    sequence: int
    created_at: float


class CooldownExceeded(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__("summary cooldown")


class SummaryRateLimiter:
    def __init__(
        self,
        rate: int = COOLDOWN_RATE,
        per: float = COOLDOWN_PER,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate < 1 or per <= 0:
            raise ValueError("쿨다운 설정은 양수여야 합니다.")
        self.rate = rate
        self.per = per
        self._clock = clock
        self._buckets: dict[int, deque[Reservation]] = {}
        self._sequence = itertools.count()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        for user_id, bucket in list(self._buckets.items()):
            while bucket and bucket[0].created_at <= now - self.per:
                bucket.popleft()
            if not bucket:
                del self._buckets[user_id]

    def reserve(self, user_id: int) -> Reservation:
        with self._lock:
            now = self._clock()
            self._prune(now)
            bucket = self._buckets.setdefault(user_id, deque())
            if len(bucket) >= self.rate:
                raise CooldownExceeded(bucket[0].created_at + self.per - now)
            reservation = Reservation(user_id, next(self._sequence), now)
            bucket.append(reservation)
            return reservation

    def refund(self, reservation: Reservation) -> None:
        with self._lock:
            bucket = self._buckets.get(reservation.user_id)
            if bucket and reservation in bucket:
                bucket.remove(reservation)
                if not bucket:
                    del self._buckets[reservation.user_id]

    @property
    def bucket_count(self) -> int:
        with self._lock:
            self._prune(self._clock())
            return len(self._buckets)


def cooldown_window_phrase(seconds: int) -> str:
    return f"{seconds // 60}분에" if seconds % 60 == 0 else f"{seconds}초에"
