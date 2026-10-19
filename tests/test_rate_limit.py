import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from yoyakman.rate_limit import CooldownExceeded, SummaryRateLimiter, cooldown_window_phrase


def test_per_user_three_per_minute_uses_monotonic_sliding_window():
    clock = [0.0]
    limiter = SummaryRateLimiter(clock=lambda: clock[0])
    for timestamp in (0, 10, 20):
        clock[0] = timestamp
        limiter.reserve(1)
    with pytest.raises(CooldownExceeded) as error:
        limiter.reserve(1)
    assert error.value.retry_after == 40
    limiter.reserve(2)
    clock[0] = 60
    limiter.reserve(1)
    with pytest.raises(CooldownExceeded) as error:
        limiter.reserve(1)
    assert error.value.retry_after == 10


def test_refund_is_specific_idempotent_and_cannot_refund_a_different_request():
    limiter = SummaryRateLimiter()
    one, two, three = [limiter.reserve(1) for _ in range(3)]
    limiter.refund(two)
    limiter.refund(two)
    limiter.reserve(1)
    with pytest.raises(CooldownExceeded):
        limiter.reserve(1)
    limiter.refund(one)
    limiter.refund(three)
    limiter.reserve(1)
    limiter.reserve(1)


def test_expired_buckets_and_stale_refunds_are_cleaned():
    clock = [0.0]
    limiter = SummaryRateLimiter(clock=lambda: clock[0])
    old = limiter.reserve(1)
    limiter.reserve(2)
    clock[0] = 60
    assert limiter.bucket_count == 0
    for _ in range(3):
        limiter.reserve(1)
    limiter.refund(old)
    with pytest.raises(CooldownExceeded):
        limiter.reserve(1)


def test_concurrent_async_requests_share_one_user_limit():
    limiter = SummaryRateLimiter()

    async def reserve():
        await asyncio.sleep(0)
        try:
            limiter.reserve(1)
            return True
        except CooldownExceeded:
            return False

    async def run():
        assert sum(await asyncio.gather(*(reserve() for _ in range(30)))) == 3

    asyncio.run(run())


def test_simultaneous_threads_cannot_overdraw_a_bucket():
    limiter = SummaryRateLimiter()

    def reserve(_):
        try:
            limiter.reserve(1)
            return True
        except CooldownExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reserve, range(30))) == 3


@pytest.mark.parametrize("seconds,phrase", [(60, "1분에"), (120, "2분에"), (45, "45초에")])
def test_cooldown_phrase_tracks_configuration(seconds, phrase):
    assert cooldown_window_phrase(seconds) == phrase
