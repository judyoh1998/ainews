from fastapi import APIRouter, Depends
from app.auth import authenticate_user, create_token, create_user, get_current_user
from app.database import get_db
from app.models import AuthResponse, LoginRequest, RegisterRequest, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(req: RegisterRequest, db=Depends(get_db)):
    user = create_user(db, req.username, req.email, req.password)
    token = create_token(user["id"])
    return {"token": token, "user": user}


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db=Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"])
    return {"token": token, "user": user}


@router.get("/me", response_model=UserPublic)
def me(user=Depends(get_current_user)):
    return user
