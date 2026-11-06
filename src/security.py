import bcrypt
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from src.models import TokenData
from src.db import get_connection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(password: str) -> str:
    # Hash password with a generated salt using pure bcrypt
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify candidate password against stored hash
    plain_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, role=role)
    except JWTError:
        raise credentials_exception

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, full_name, role, created_at FROM users WHERE id = %s;",
                (token_data.user_id,)
            )
            user = cur.fetchone()
            if user is None:
                raise credentials_exception

    return {
        "id": user[0],
        "email": user[1],
        "full_name": user[2],
        "role": user[3],
        "created_at": user[4]
    }

def require_role(*allowed_roles: str):
    """Dependency factory to enforce role-based access."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for your role"
            )
        return current_user
    return role_checker 