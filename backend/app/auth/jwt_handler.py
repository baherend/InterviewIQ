from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> int:
    """Low-level: decodes the JWT and returns the raw `sub` claim as an int.

    Does NOT touch the database, so a token for a since-deleted user would
    still pass this check alone. Routes should depend on `get_current_user`
    (below) instead; this exists for internal composition and for any
    caller that genuinely only needs the id without a DB round-trip.
    """
    if credentials is None:
        # HTTPBearer is constructed with auto_error=False above so that a
        # missing Authorization header is consistently a 401 here, rather
        # than FastAPI's HTTPBearer default of 403 for "no credentials at
        # all" vs 401 for "credentials present but invalid".
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return int(user_id)


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    """Database-backed authorization primitive.

    Loads the current `User` row from PostgreSQL by the JWT's `sub` claim.
    The database is always the source of truth for the user's role and
    identity — the JWT payload carries no role claim and role/permission
    decisions must never be made from the token alone. Rejects with 401 if
    the token references a user that no longer exists.

    A suspended (`is_active=False`) user is rejected with 403, not 401:
    the token itself is genuinely valid and correctly identifies a real
    user — this is an authorization decision ("this identity is not
    currently permitted"), the same class of failure as a role/membership
    check failing, not an authentication failure. This applies uniformly
    to every endpoint that depends on `get_current_user` (including
    `/api/auth/me`), so a suspended user's existing token stops working
    everywhere immediately, without any separate token-blocklist
    mechanism — there is nothing to revoke, the very next authorization
    check simply fails.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Token references a user that no longer exists")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been suspended")
    return user
