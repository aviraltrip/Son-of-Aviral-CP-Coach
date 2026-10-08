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
