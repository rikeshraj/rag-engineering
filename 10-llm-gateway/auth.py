"""Auth — API key authentication. Same pattern as previous projects."""

import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

 
def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    expected = os.getenv("API_KEY")
    if not expected:
        raise RuntimeError("API_KEY environment variable is not set.")
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
