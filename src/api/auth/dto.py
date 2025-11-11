from typing import Optional

from pydantic import BaseModel, Field


class TokenData(BaseModel):
    sub: Optional[str] = None  # User ID (as string)
    version: Optional[int] = None  # Token version for invalidation
    email: Optional[str] = None
    phone_number: Optional[str] = None
    exp: Optional[int] = None  # Expiration time
    # Add other fields as needed (e.g., roles, permissions)


class TokenCreationData(BaseModel):
    sub: str  # User ID (as string)
    version: int  # Token version for invalidation
    email: Optional[str] = None
    phone_number: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = Field(default_factory=lambda: "bearer")


class UserCreate(BaseModel):
    email: str
    password: str
    test_id: Optional[str] = None  # Optional field for testing purposes


class TokenRequest(BaseModel):  # New Pydantic model
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    user_id: str
