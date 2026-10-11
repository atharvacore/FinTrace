from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # Plain string on purpose: format rules belong to account creation, not to login.
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 (OAuth2 token type, not a secret)
    expires_in: int
