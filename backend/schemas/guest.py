from pydantic import BaseModel


class GuestTokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class GuestAccessTokenOut(BaseModel):
    access_token: str
    expires_in: int


class GuestRefreshRequest(BaseModel):
    refresh_token: str
