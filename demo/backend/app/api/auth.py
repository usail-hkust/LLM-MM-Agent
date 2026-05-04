"""
Authentication Routes - OAuth2 implementation.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.security import create_access_token
from app.core.exceptions import AuthenticationError, StateError, ResourceNotFoundError
from app.api.deps import get_auth_service
from app.services.auth_service import AuthService
from app.api.schemas import RegisterRequest, TokenResponse, UserResponse

router = APIRouter()

@router.post("/register", status_code=201, response_model=UserResponse)
async def register(
    req: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user. Invite codes are optional in local open-source mode.
    """
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(status_code=403, detail="Public registration is disabled.")

    # Backend double-check: ensure terms are agreed
    if not req.terms_agreed:
        raise HTTPException(status_code=400, detail="You must agree to the terms to register.")
    
    try:
        user = await auth_service.register(req.email, req.password, req.invite_code)
        return UserResponse(id=user.id, email=user.email, is_active=user.is_active)
    except StateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=400, detail="Invalid invitation code.")
    except Exception as e:
        raise HTTPException(status_code=500, detail="System error during registration.")

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    try:
        user = await auth_service.authenticate(form_data.username, form_data.password)
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
