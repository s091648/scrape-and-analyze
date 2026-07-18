from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.auth.guards import require_user

router = APIRouter(prefix="/user", tags=["user"])


def _get_user_id(user: dict) -> UUID:
    return UUID(user["sub"])


# ─── Favorites ────────────────────────────────────────────────────────────────

class FavoritesResponse(BaseModel):
    article_ids: List[str]


@router.get("/favorites", response_model=FavoritesResponse)
def get_favorites(db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserArticleFavorite
    user_id = _get_user_id(user)
    rows = db.query(UserArticleFavorite).filter(UserArticleFavorite.user_id == user_id).all()
    return FavoritesResponse(article_ids=[str(r.article_id) for r in rows])


@router.post("/favorites/{article_id}", status_code=201)
def add_favorite(article_id: UUID, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserArticleFavorite
    from sqlalchemy.dialects.postgresql import insert
    user_id = _get_user_id(user)
    stmt = (
        insert(UserArticleFavorite)
        .values(user_id=user_id, article_id=article_id)
        .on_conflict_do_nothing()
    )
    db.execute(stmt)
    db.commit()
    return {}


@router.delete("/favorites/{article_id}", status_code=204)
def remove_favorite(article_id: UUID, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserArticleFavorite
    user_id = _get_user_id(user)
    db.query(UserArticleFavorite).filter(
        UserArticleFavorite.user_id == user_id,
        UserArticleFavorite.article_id == article_id,
    ).delete()
    db.commit()
    return None


# ─── Subscriptions ────────────────────────────────────────────────────────────

class SubscriptionIn(BaseModel):
    topic_id: UUID


class SubscriptionsResponse(BaseModel):
    topic_ids: List[str]


@router.get("/subscriptions", response_model=SubscriptionsResponse)
def get_subscriptions(db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserTopicSubscription
    user_id = _get_user_id(user)
    rows = db.query(UserTopicSubscription).filter(UserTopicSubscription.user_id == user_id).all()
    return SubscriptionsResponse(topic_ids=[str(r.topic_id) for r in rows])


@router.post("/subscriptions", status_code=201)
def add_subscription(body: SubscriptionIn, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserTopicSubscription
    from sqlalchemy.dialects.postgresql import insert
    user_id = _get_user_id(user)
    stmt = (
        insert(UserTopicSubscription)
        .values(user_id=user_id, topic_id=body.topic_id)
        .on_conflict_do_nothing()
    )
    db.execute(stmt)
    db.commit()
    return {}


@router.delete("/subscriptions/{topic_id}", status_code=204)
def remove_subscription(topic_id: UUID, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserTopicSubscription
    user_id = _get_user_id(user)
    db.query(UserTopicSubscription).filter(
        UserTopicSubscription.user_id == user_id,
        UserTopicSubscription.topic_id == topic_id,
    ).delete()
    db.commit()
    return None


# ─── Notification Settings ────────────────────────────────────────────────────

class NotificationSettingsOut(BaseModel):
    email_enabled: bool
    telegram_chat_id: str | None
    telegram_enabled: bool
    locale: str


class NotificationSettingsIn(BaseModel):
    email_enabled: bool | None = None
    telegram_chat_id: str | None = None
    telegram_enabled: bool | None = None
    locale: str | None = None


@router.get("/notification-settings", response_model=NotificationSettingsOut)
def get_notification_settings(db: Session = Depends(get_db), user: dict = Depends(require_user)):
    from models.user_subscription import UserNotificationSettings
    user_id = _get_user_id(user)
    settings = db.query(UserNotificationSettings).filter(UserNotificationSettings.user_id == user_id).first()
    if not settings:
        return NotificationSettingsOut(email_enabled=True, telegram_chat_id=None, telegram_enabled=False, locale="en")
    return NotificationSettingsOut(
        email_enabled=settings.email_enabled,
        telegram_chat_id=settings.telegram_chat_id,
        telegram_enabled=settings.telegram_enabled,
        locale=settings.locale,
    )


@router.put("/notification-settings", response_model=NotificationSettingsOut)
def update_notification_settings(
    body: NotificationSettingsIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_user),
):
    from models.user_subscription import UserNotificationSettings
    from sqlalchemy.dialects.postgresql import insert
    user_id = _get_user_id(user)
    existing = db.query(UserNotificationSettings).filter(UserNotificationSettings.user_id == user_id).first()
    if existing:
        if body.email_enabled is not None:
            existing.email_enabled = body.email_enabled
        if body.telegram_chat_id is not None:
            existing.telegram_chat_id = body.telegram_chat_id
        if body.telegram_enabled is not None:
            existing.telegram_enabled = body.telegram_enabled
        if body.locale is not None:
            existing.locale = body.locale
        db.commit()
        db.refresh(existing)
        return NotificationSettingsOut(
            email_enabled=existing.email_enabled,
            telegram_chat_id=existing.telegram_chat_id,
            telegram_enabled=existing.telegram_enabled,
            locale=existing.locale,
        )
    else:
        new_settings = UserNotificationSettings(
            user_id=user_id,
            email_enabled=body.email_enabled if body.email_enabled is not None else True,
            telegram_chat_id=body.telegram_chat_id,
            telegram_enabled=body.telegram_enabled if body.telegram_enabled is not None else False,
            locale=body.locale or "en",
        )
        db.add(new_settings)
        db.commit()
        return NotificationSettingsOut(
            email_enabled=new_settings.email_enabled,
            telegram_chat_id=new_settings.telegram_chat_id,
            telegram_enabled=new_settings.telegram_enabled,
            locale=new_settings.locale,
        )
