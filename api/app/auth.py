"""WorkOS AuthKit authentication dependencies."""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

# Type alias for the authenticated user dict returned by verify_token.
CurrentUser = dict[str, str | None]

WORKOS_USER_MGMT_URL = "https://api.workos.com/user_management"


async def _get_session_user(token: str, settings: Settings) -> CurrentUser:
    """Call WorkOS API to verify a session token and return user info.

    Raises HTTPException 401 if the token is invalid or the request fails.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{WORKOS_USER_MGMT_URL}/sessions/token/introspect",
            headers={
                "Authorization": f"Bearer {settings.WORKOS_API_KEY}",
                "Content-Type": "application/json",
            },
            params={"session_token": token},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    data = response.json()
    user = data.get("user", data)

    return {
        "id": user.get("id", ""),
        "email": user.get("email", ""),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
    }


async def verify_token(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    """FastAPI dependency that requires a valid WorkOS session token.

    Expects an ``Authorization: Bearer <token>`` header.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    return await _get_session_user(token, settings)


async def optional_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser | None:
    """FastAPI dependency that returns the user if authenticated, or None.

    Use this for endpoints that are publicly readable but can personalise
    the response when a user is logged in.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        return await _get_session_user(token, settings)
    except HTTPException:
        return None
