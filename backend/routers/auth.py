import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin, require_user
from backend.schemas.auth import LoginRequest
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
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify")
def verify_credentials(data: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_username(db, data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Account disabled")
    return {"id": str(user.id), "username": user.username, "email": user.email,
            "name": user.name, "role": user.role}


@router.post("/register", response_model=UserOut, status_code=201)
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
            raise HTTPException(status_code=409, detail="Email or username already taken")
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/google/authorize", response_model=UserOut)
def google_authorize(data: GoogleAuthorizeRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")
    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Account disabled")
    if not user.google_id:
        raise HTTPException(status_code=409, detail="Google account not linked")
    return user


@router.get("/users", response_model=list[UserOut])
def list_users_endpoint(db: Session = Depends(get_db), _=Depends(require_admin)):
    return _list_users(db)


@router.post("/users", response_model=UserOut, status_code=201)
def admin_create_user(data: AdminCreateUserRequest, db: Session = Depends(get_db),
                      _=Depends(require_admin)):
    if not data.email and not data.username:
        raise HTTPException(status_code=422, detail="email or username required")
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
            raise HTTPException(status_code=409, detail="Email or username already taken")
        raise


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user_endpoint(user_id: UUID, data: AdminUpdateUserRequest,
                         db: Session = Depends(get_db), _=Depends(require_admin)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _update_user(db, user, data)


@router.delete("/users/{user_id}", status_code=204)
def delete_user_endpoint(user_id: UUID, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _delete_user(db, user)
    return Response(status_code=204)


@router.get("/me", response_model=UserProfileOut)
def get_me(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/me", response_model=UserProfileOut)
def update_me(data: UserProfileUpdate, payload: dict = Depends(require_user),
              db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", status_code=204)
def change_password(data: PasswordChangeRequest, payload: dict = Depends(require_user),
                    db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.hashed_password:
        raise HTTPException(status_code=400, detail="Password change not available for this account")
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    user.hashed_password = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


@router.delete("/me", status_code=204)
def delete_me(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _delete_user(db, user)
    return Response(status_code=204)


@router.post("/me/link-google", status_code=204)
def link_google(data: LinkGoogleRequest, payload: dict = Depends(require_user),
                db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.google_id:
        raise HTTPException(status_code=400, detail="Google account already linked")
    if _get_user_by_google_id(db, data.google_id):
        raise HTTPException(status_code=409, detail="Google account already in use")
    _update_google_id(db, user, data.google_id)
    return Response(status_code=204)


@router.delete("/me/link-google", status_code=204)
def unlink_google(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.username:
        raise HTTPException(status_code=400, detail="Cannot unlink Google from a Google-only account")
    user.google_id = None
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)
