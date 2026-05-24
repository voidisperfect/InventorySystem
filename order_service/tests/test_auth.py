import pytest
from datetime import timedelta
from fastapi import HTTPException, status
from order_app.auth import create_access_token, get_current_user


@pytest.mark.asyncio
async def test_jwt_valid_token():
    """Verify that a valid JWT token is successfully decoded and returns the correct claims."""
    user_data = {"sub": "john_doe", "email": "john@example.com"}
    token = create_access_token(data=user_data)

    # We call get_current_user directly with the token
    user = await get_current_user(token=token)
    assert user["user_id"] == "john_doe"
    assert user["email"] == "john@example.com"


@pytest.mark.asyncio
async def test_jwt_expired_token():
    """Verify that an expired JWT token (negative timedelta) raises HTTP 401."""
    user_data = {"sub": "john_doe", "email": "john@example.com"}
    # Generate token that expired 10 minutes ago
    token = create_access_token(data=user_data, expires_delta=timedelta(minutes=-10))

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.asyncio
async def test_jwt_invalid_claims():
    """Verify that a token with missing claims raises HTTP 401."""
    # Missing email claim
    user_data = {"sub": "john_doe"}
    token = create_access_token(data=user_data)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_jwt_malformed_token():
    """Verify that a completely malformed token string raises HTTP 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="this-is-not-a-valid-jwt-token-at-all")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
