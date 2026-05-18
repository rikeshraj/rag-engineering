"""
Auth

API key authentication for all protected routes.
The key is loaded from the API_KEY environment variable.
"""

import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

# Header name clients must send: X-API-Key: your-key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key() -> str:
    """
    Load API key from environment.
    Raises on startup if not set so the problem is caught early.
    """
    key = os.getenv("API_KEY")
    if not key:
        raise RuntimeError(
            "API_KEY environment variable is not set. "
            "Add it to your .env file: API_KEY=your-secret-key"
        )
    return key


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    FastAPI dependency — inject this into any route to protect it.

    Usage:
        @app.post("/scores")
        def create_score(body: ScoreRequest, key: str = Security(verify_api_key)):
            ...
    """
    expected = get_api_key()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )

    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_key
