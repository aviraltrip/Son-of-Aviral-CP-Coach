"""Token-bucket rate limiter for protecting LLM costs and server compute resources."""
import time
import threading

class RateLimiterBucket:
    """Represents a token bucket with fixed capacity and replenishment rate."""
    def __init__(self, capacity: int, refill_interval_seconds: float):
        self.capacity = capacity
        self.refill_interval = refill_interval_seconds
        self.tokens = float(capacity)
        self.last_update = time.time()

    def update(self) -> None:
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(float(self.capacity), self.tokens + (elapsed / self.refill_interval))
        self.last_update = now

    def can_consume(self, cost: float = 1.0) -> tuple[bool, float]:
        self.update()
        if self.tokens >= cost:
            return True, 0.0
        needed = cost - self.tokens
        wait_seconds = max(0.0, needed * self.refill_interval)
        return False, wait_seconds

    def consume(self, cost: float = 1.0) -> bool:
        allowed, _ = self.can_consume(cost)
        if allowed:
            self.tokens -= cost
            return True
        return False

DEFAULT_LIMITS: dict[str, tuple[int, float]] = {
    "hint": (5, 90.0),
    "judge": (4, 25.0),
    "fuzzer": (2, 180.0),
}

class ActionRateLimiter:
    """Thread-safe multi-client token-bucket rate limiter."""
    def __init__(self, limits: dict[str, tuple[int, float]] | None = None):
        self.limits = limits or DEFAULT_LIMITS
        self.buckets: dict[tuple[str, str], RateLimiterBucket] = {}
        self.lock = threading.Lock()

    def _get_bucket(self, action: str, client_id: str) -> RateLimiterBucket:
        key = (action, client_id)
        if key not in self.buckets:
            cap, refill_sec = self.limits.get(action, (5, 60.0))
            self.buckets[key] = RateLimiterBucket(cap, refill_sec)
        return self.buckets[key]

    def check(self, action: str, client_id: str, cost: float = 1.0) -> tuple[bool, float]:
        """Check if action is allowed without consuming token. Returns (allowed, wait_seconds)."""
        with self.lock:
            bucket = self._get_bucket(action, client_id)
            return bucket.can_consume(cost)

    def consume(self, action: str, client_id: str, cost: float = 1.0) -> tuple[bool, float]:
        """Attempt to consume token for action. Returns (allowed, wait_seconds)."""
        with self.lock:
            bucket = self._get_bucket(action, client_id)
            allowed, wait_sec = bucket.can_consume(cost)
            if allowed:
                bucket.tokens -= cost
                return True, 0.0
            return False, wait_sec

    def remaining(self, action: str, client_id: str) -> int:
        """Get remaining available tokens for action and client."""
        with self.lock:
            bucket = self._get_bucket(action, client_id)
            bucket.update()
            return max(0, int(bucket.tokens))

rate_limiter = ActionRateLimiter()
