"""Unit tests for token-bucket rate limiter and authentication passkey verification."""
import time
import pytest
from app.data.rate_limiter import ActionRateLimiter, RateLimiterBucket
from app.data.auth import verify_or_register_handle, init_auth_table

def test_bucket_token_consumption_and_exhaustion():
    bucket = RateLimiterBucket(capacity=3, refill_interval_seconds=10.0)
    
    # Consume 3 tokens
    assert bucket.consume(1.0) is True
    assert bucket.consume(1.0) is True
    assert bucket.consume(1.0) is True
    
    # 4th consume must fail
    allowed, wait_sec = bucket.can_consume(1.0)
    assert allowed is False
    assert wait_sec > 0.0

def test_bucket_token_replenishment():
    bucket = RateLimiterBucket(capacity=2, refill_interval_seconds=0.1)
    bucket.consume(2.0)
    assert bucket.consume(1.0) is False

    time.sleep(0.15)
    bucket.update()
    assert bucket.tokens >= 1.0
    assert bucket.consume(1.0) is True

def test_action_rate_limiter_client_isolation():
    limiter = ActionRateLimiter(limits={"hint": (2, 60.0)})
    
    # Client 1 exhausts
    assert limiter.consume("hint", "client_1")[0] is True
    assert limiter.consume("hint", "client_1")[0] is True
    assert limiter.consume("hint", "client_1")[0] is False
    
    # Client 2 should be unaffected
    assert limiter.consume("hint", "client_2")[0] is True
    assert limiter.remaining("hint", "client_2") == 1

def test_auth_registration_and_verification(tmp_path):
    db_file = str(tmp_path / "auth_test.db")
    init_auth_table(db_file)

    # Initial registration
    ok, msg = verify_or_register_handle("tourist", "secret_pass_123", db_path=db_file)
    assert ok is True
    assert "registered" in msg.lower()

    # Successful login
    ok, msg = verify_or_register_handle("tourist", "secret_pass_123", db_path=db_file)
    assert ok is True
    assert "successful" in msg.lower()

    # Wrong password rejection
    ok, msg = verify_or_register_handle("tourist", "wrong_password", db_path=db_file)
    assert ok is False
    assert "incorrect" in msg.lower()

    # Empty handle check
    ok, msg = verify_or_register_handle("", "secret", db_path=db_file)
    assert ok is False
