import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.shared.domain.exceptions import ValidationError, NotFoundError, ConflictError, UnauthorizedError, ForbiddenError
from backend.database import get_db
from backend.auth.guards import require_admin, require_user
from backend.schemas.error import error_responses
from backend.schemas.auth import LoginRequest
from backend.schemas.guest import GuestTokenPairOut, GuestAccessTokenOut, GuestRefreshRequest
from backend.schemas.user import (
    UserOut, UserProfileOut, UserProfileUpdate, PasswordChangeRequest,
    RegisterCredentialsRequest, RegisterGoogleRequest,
    AdminCreateUserRequest, AdminUpdateUserRequest, GoogleAuthorizeRequest,
    LinkGoogleRequest,
)
from backend.services.auth_service import (
    get_user_by_username as _get_user_by_username,
    get_user_by_email as _get_user_by_email,
    get_user_by_google_id as _get_user_by_google_id,
    get_user_by_id as _get_user_by_id,
    list_users as _list_users,
    create_user as _create_user,
    update_user as _update_user,
    delete_user as _delete_user,
    update_google_id as _update_google_id,
    hash_password,
    verify_password,
    compute_guest_id,
    create_guest_access_token,
    create_guest_refresh_token,
    decode_guest_refresh_token,
    GUEST_ACCESS_TOKEN_TTL_SECONDS,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify", responses=error_responses(401, 403))
def verify_credentials(data: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_username(db, data.username)
    if not user:
        raise UnauthorizedError("Invalid credentials")
    if not verify_password(data.password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")
    if not user.is_allowed:
        raise ForbiddenError("Account disabled")
    return {"id": str(user.id), "username": user.username, "email": user.email,
            "name": user.name, "role": user.role}


@router.post("/register", response_model=UserOut, status_code=201, responses=error_responses(400, 409))
def register(data: dict, db: Session = Depends(get_db)):
    try:
        if "google_id" in data:
            req = RegisterGoogleRequest(**data)
            new_user = _create_user(
                db, id=_uuid.uuid4(), email=req.email, name=req.name,
                google_id=req.google_id, role='user', is_allowed=True,
            )
        else:
            req = RegisterCredentialsRequest(**data)
            new_user = _create_user(
                db, id=_uuid.uuid4(), email=req.email, name=req.name,
                username=req.username, hashed_password=hash_password(req.password),
                role='user', is_allowed=True,
            )
        return new_user
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise ConflictError("Email or username already taken")
        raise ValidationError(str(e))


@router.post("/google/authorize", response_model=UserOut, responses=error_responses(403, 404, 409))
def google_authorize(data: GoogleAuthorizeRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, data.email)
    if not user:
        raise NotFoundError("Email not registered")
    if not user.is_allowed:
        raise ForbiddenError("Account disabled")
    if not user.google_id:
        raise ConflictError("Google account not linked")
    return user


@router.get("/users", response_model=list[UserOut], responses=error_responses(401, 403))
def list_users_endpoint(db: Session = Depends(get_db), _=Depends(require_admin)):
    return _list_users(db)


@router.post("/users", response_model=UserOut, status_code=201, responses=error_responses(400, 401, 403, 409))
def admin_create_user(data: AdminCreateUserRequest, db: Session = Depends(get_db),
                      _=Depends(require_admin)):
    if not data.email and not data.username:
        raise ValidationError("email or username required")
    kwargs = {
        "id": _uuid.uuid4(), "email": data.email, "name": data.name,
        "role": data.role, "is_allowed": True,
    }
    if data.username and data.password:
        kwargs["username"] = data.username
        kwargs["hashed_password"] = hash_password(data.password)
    try:
        return _create_user(db, **kwargs)
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise ConflictError("Email or username already taken")
        raise


@router.patch("/users/{user_id}", response_model=UserOut, responses=error_responses(401, 403, 404))
def update_user_endpoint(user_id: UUID, data: AdminUpdateUserRequest,
                         db: Session = Depends(get_db), _=Depends(require_admin)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    return _update_user(db, user, data)


@router.delete("/users/{user_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_user_endpoint(user_id: UUID, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    _delete_user(db, user)
    return Response(status_code=204)


@router.get("/me", response_model=UserProfileOut, responses=error_responses(401, 404))
def get_me(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise NotFoundError("User not found")
    return user


@router.patch("/me", response_model=UserProfileOut, responses=error_responses(401, 404))
def update_me(data: UserProfileUpdate, payload: dict = Depends(require_user),
              db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise NotFoundError("User not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", status_code=204, responses=error_responses(400, 401, 404))
def change_password(data: PasswordChangeRequest, payload: dict = Depends(require_user),
                    db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise NotFoundError("User not found")
    if not user.hashed_password:
        raise ValidationError("Password change not available for this account")
    if not verify_password(data.current_password, user.hashed_password):
        raise ValidationError("Current password incorrect")
    user.hashed_password = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


@router.delete("/me", status_code=204, responses=error_responses(401, 404))
def delete_me(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise NotFoundError("User not found")
    _delete_user(db, user)
    return Response(status_code=204)


@router.post("/me/link-google", status_code=204, responses=error_responses(400, 401, 404, 409))
def link_google(data: LinkGoogleRequest, payload: dict = Depends(require_user),
                db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise NotFoundError("User not found")
    if user.google_id:
        raise ValidationError("Google account already linked")
    if _get_user_by_google_id(db, data.google_id):
        raise ConflictError("Google account already in use")
    _update_google_id(db, user, data.google_id)
    return Response(status_code=204)


@router.delete("/me/link-google", status_code=204, responses=error_responses(400, 401, 404))
def unlink_google(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise NotFoundError("User not found")
    if not user.username:
        raise ValidationError("Cannot unlink Google from a Google-only account")
    user.google_id = None
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


@router.post("/guest", response_model=GuestTokenPairOut)
def issue_guest_token(request: Request):
    guest_id = compute_guest_id(request)
    return GuestTokenPairOut(
        access_token=create_guest_access_token(guest_id),
        refresh_token=create_guest_refresh_token(guest_id),
        expires_in=GUEST_ACCESS_TOKEN_TTL_SECONDS,
    )


@router.post("/guest/refresh", response_model=GuestAccessTokenOut, responses=error_responses(401))
def refresh_guest_token(data: GuestRefreshRequest):
    payload = decode_guest_refresh_token(data.refresh_token)
    return GuestAccessTokenOut(
        access_token=create_guest_access_token(payload["guest_id"]),
        expires_in=GUEST_ACCESS_TOKEN_TTL_SECONDS,
    )
