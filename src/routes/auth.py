from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from src.models import UserCreate, UserResponse, Token
from src.security import hash_password, verify_password, create_access_token, get_current_user
from src.db import get_connection

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (user.email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            hashed = hash_password(user.password)
            cur.execute(
                """
                INSERT INTO users (email, full_name, hashed_password, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, full_name, role, created_at;
                """,
                (user.email, user.full_name, hashed, user.role)
            )
            new_user = cur.fetchone()

    return {
        "id": new_user[0],
        "email": new_user[1],
        "full_name": new_user[2],
        "role": new_user[3],
        "created_at": new_user[4]
    }

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, hashed_password, role FROM users WHERE email = %s;",
                (form_data.username,)
            )
            user = cur.fetchone()

    if not user or not verify_password(form_data.password, user[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user[0]), "role": user[2]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user