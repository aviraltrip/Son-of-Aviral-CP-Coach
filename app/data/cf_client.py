"""Codeforces API client with polite rate limiting, disk caching, and error resilience."""
import os
import time
import json
import logging
import requests
from typing import Any, Tuple

logger = logging.getLogger(__name__)

class CFAPIError(Exception):
    """Base exception for Codeforces API errors."""
    pass

class CFUserNotFoundError(CFAPIError):
    """Raised when a user handle does not exist on Codeforces."""
    pass

class CFRateLimitError(CFAPIError):
    """Raised when Codeforces rate limit (HTTP 429) is hit."""
    pass

class PoliteRateLimiter:
    """Ensures at least min_interval_seconds elapse between consecutive API calls."""
    def __init__(self, min_interval_seconds: float = 2.0):
        self.min_interval = min_interval_seconds
        self.last_call_time = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()

rate_limiter = PoliteRateLimiter(min_interval_seconds=2.0)

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "cp_coach")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cached_response(cache_key: str, ttl_seconds: int = 300) -> Any | None:
    """Retrieve response from local disk cache if still fresh."""
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            cached_at = data.get("_cached_at", 0)
            if time.time() - cached_at < ttl_seconds:
                return data.get("payload")
    except Exception as e:
        logger.warning(f"Failed to read cache {cache_key}: {e}")
    return None

def set_cached_response(cache_key: str, payload: Any) -> None:
    """Write API response payload to local disk cache."""
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as fp:
            json.dump({"_cached_at": time.time(), "payload": payload}, fp)
    except Exception as e:
        logger.warning(f"Failed to write cache {cache_key}: {e}")

BASE_URL = "https://codeforces.com/api"

def _make_api_request(endpoint: str, params: dict[str, Any] | None = None, max_retries: int = 3) -> Any:
    """Execute API request with rate limiting and exponential backoff retry."""
    url = f"{BASE_URL}/{endpoint}"
    params = params or {}
    
    for attempt in range(max_retries):
        rate_limiter.wait()
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "OK":
                    return data.get("result")
                comment = data.get("comment", "Unknown API error")
                if "not found" in comment.lower():
                    raise CFUserNotFoundError(comment)
                raise CFAPIError(comment)
            elif resp.status_code == 400:
                data = resp.json()
                comment = data.get("comment", "")
                if "not found" in comment.lower():
                    raise CFUserNotFoundError(comment)
                raise CFAPIError(f"Bad Request: {comment}")
            elif resp.status_code in (429, 503):
                time.sleep(2.0 * (attempt + 1))
                continue
            else:
                resp.raise_for_status()
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise CFAPIError(f"Network error accessing {url}: {e}")
            time.sleep(1.5 * (attempt + 1))
            
    raise CFAPIError(f"Failed after {max_retries} attempts.")

def get_user_info(handle: str, ttl_seconds: int = 300) -> dict[str, Any]:
    """Fetch user profile information from user.info."""
    cache_key = f"user_info_{handle.lower()}"
    cached = get_cached_response(cache_key, ttl_seconds=ttl_seconds)
    if cached:
        return cached
        
    result = _make_api_request("user.info", {"handles": handle})
    if isinstance(result, list) and len(result) > 0:
        user_data = result[0]
        set_cached_response(cache_key, user_data)
        return user_data
    raise CFUserNotFoundError(f"User {handle} not found.")

def get_user_status(handle: str, count: int = 500, ttl_seconds: int = 60) -> list[dict[str, Any]]:
    """Fetch recent submissions for a user from user.status."""
    cache_key = f"user_status_{handle.lower()}_{count}"
    cached = get_cached_response(cache_key, ttl_seconds=ttl_seconds)
    if cached:
        return cached
        
    result = _make_api_request("user.status", {"handle": handle, "from": 1, "count": count})
    if isinstance(result, list):
        set_cached_response(cache_key, result)
        return result
    return []
