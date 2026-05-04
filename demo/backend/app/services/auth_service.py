"""
Authentication Service.
Handles Registration (with invite codes) and Login logic.
"""
import logging
from typing import Optional
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import AuthenticationError, StateError
from app.infra.persistence.repositories import AuthRepository
from app.infra.persistence.models import UserDB

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, auth_repo: AuthRepository):
        self.repo = auth_repo

    async def register(self, email: str, password: str, invite_code: Optional[str] = None) -> UserDB:
        """
        Registers a new user, optionally guarded by invite code policy.
        Checks for existing email. Hashes password.
        """
        existing = await self.repo.get_user_by_email(email)
        if existing:
            raise StateError("Email already registered.")

        hashed_pw = get_password_hash(password)

        try:
            if settings.REQUIRE_INVITE_CODE:
                if not invite_code:
                    raise StateError("Invitation code is required.")
                user = await self.repo.create_user_with_invite(email, hashed_pw, invite_code)
                logger.info(f"Registered new user: {email} with code {invite_code}")
            else:
                user = await self.repo.create_user(email, hashed_pw)
                logger.info(f"Registered new local user: {email}")
            return user
        except StateError as e:
            raise e
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise StateError("Registration failed due to system error.")

    async def authenticate(self, email: str, password: str) -> UserDB:
        """
        Verifies credentials for login.
        """
        user = await self.repo.get_user_by_email(email)
        if not user:
            # Prevent timing attacks by mimicking work? (Optional for this scope)
            raise AuthenticationError("Incorrect email or password")
        
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password")
            
        if not user.is_active:
            raise AuthenticationError("Account is inactive.")
            
        return user
