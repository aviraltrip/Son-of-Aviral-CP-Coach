"""Unit tests for Codeforces client and rate limiting."""
from unittest.mock import patch
from app.data.cf_client import (
    PoliteRateLimiter,
    get_cached_response,
    set_cached_response,
    get_user_info,
    sync_user_data
)
from app.data.db import init_db, get_user, get_user_submissions

def test_rate_limiter():
    limiter = PoliteRateLimiter(min_interval_seconds=0.01)
    limiter.wait()
    assert limiter.last_call_time > 0

def test_disk_cache(tmp_path):
    set_cached_response("test_key", {"score": 42})
    res = get_cached_response("test_key", ttl_seconds=60)
    assert res == {"score": 42}

@patch("app.data.cf_client._make_api_request")
def test_get_user_info_success(mock_req):
    mock_req.return_value = [{"handle": "tourist_mock", "rating": 3800, "maxRating": 3900}]
    info = get_user_info("mock_tourist_unique", ttl_seconds=0)
    assert info["handle"] == "tourist_mock"
    assert info["rating"] == 3800

@patch("app.data.cf_client._make_api_request")
def test_sync_user_data_pipeline(mock_req, tmp_path):
    db_file = str(tmp_path / "sync_test.db")
    init_db(db_file)
    
    mock_req.side_effect = [
        [{"handle": "tourist_mock_test", "rating": 3800, "maxRating": 3900}],
        [
            {
                "id": 555,
                "problem": {"contestId": 1800, "index": "B", "name": "Count Pairs", "rating": 1000, "tags": ["strings"]},
                "verdict": "OK",
                "creationTimeSeconds": 1700000000
            }
        ]
    ]
    
    info, inserted = sync_user_data("tourist_mock_test", max_submissions=10, ttl_seconds=0, db_path=db_file)
    assert info["rating"] == 3800
    assert inserted == 1
    
    u = get_user("tourist_mock_test", db_path=db_file)
    assert u["current_rating"] == 3800
    subs = get_user_submissions("tourist_mock_test", db_path=db_file)
    assert len(subs) == 1

def test_normalize_tags():
    from app.data.cf_client import normalize_tags
    raw = [" dp ", "  trees", "", "  ", "graphs"]
    cleaned = normalize_tags(raw)
    assert cleaned == ["dp", "trees", "graphs"]
    assert normalize_tags([]) == []
