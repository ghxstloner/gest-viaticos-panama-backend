from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.auth import LoginResponse, Token
from ...services.auth import AuthService
from ...api.deps import get_current_active_user
from ...models.user import Usuario

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login endpoint"""
    auth_service = AuthService(db)
    result = auth_service.login(form_data.username, form_data.password)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


@router.get("/profile")
async def get_profile(
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user profile"""
    auth_service = AuthService(db)
    profile = auth_service.get_user_profile(current_user.id_usuario)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return profile


@router.post("/logout")
async def logout(current_user: Usuario = Depends(get_current_active_user)):
    """Logout endpoint"""
    # In a real implementation with Redis or cache, you would invalidate the token here
    return {"message": "Successfully logged out"}