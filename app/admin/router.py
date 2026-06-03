import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth import require_admin
from app.database import AsyncSessionLocal
from app.models.alert_log import AlertLog
from app.models.business import Business
from app.models.review import Review
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _redirect(path: str, msg: str = "", error: str = "") -> RedirectResponse:
    sep = "?" if "?" not in path else "&"
    if msg:
        path = f"{path}{sep}msg={msg.replace(' ', '+')}"
    elif error:
        path = f"{path}{sep}error={error.replace(' ', '+')}"
    return RedirectResponse(path, status_code=303)


async def _get_stats(session: AsyncSession) -> dict:
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    users_by_plan = dict(
        (await session.execute(select(User.plan, func.count()).group_by(User.plan))).all()
    )
    total_businesses = (await session.execute(select(func.count()).select_from(Business))).scalar_one()
    active_businesses = (await session.execute(
        select(func.count()).select_from(Business).where(Business.is_paused == False)  # noqa: E712
    )).scalar_one()
    total_reviews = (await session.execute(select(func.count()).select_from(Review))).scalar_one()
    negative_reviews = (await session.execute(
        select(func.count()).select_from(Review).where(Review.review_type == "negative")
    )).scalar_one()
    alerts_today = (await session.execute(
        select(func.count()).select_from(AlertLog).where(AlertLog.created_at >= today_start)
    )).scalar_one()
    tokens_today = (await session.execute(
        select(func.coalesce(func.sum(AlertLog.ai_draft_tokens), 0))
        .where(AlertLog.created_at >= today_start)
    )).scalar_one()
    blocked_users = (await session.execute(
        select(func.count()).select_from(User).where(User.is_active == False)  # noqa: E712
    )).scalar_one()

    return {
        "users_by_plan": users_by_plan,
        "total_users": sum(users_by_plan.values()),
        "total_businesses": total_businesses,
        "active_businesses": active_businesses,
        "total_reviews": total_reviews,
        "negative_reviews": negative_reviews,
        "positive_reviews": total_reviews - negative_reviews,
        "alerts_today": alerts_today,
        "tokens_today": tokens_today,
        "blocked_users": blocked_users,
    }


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/")
async def dashboard(request: Request, msg: str = "", error: str = ""):
    async with AsyncSessionLocal() as session:
        stats = await _get_stats(session)
    return templates.TemplateResponse(
        "admin/dashboard.html", {"request": request, "stats": stats, "msg": msg, "error": error}
    )


# ── Businesses ─────────────────────────────────────────────────────────────────

@router.get("/businesses")
async def businesses(request: Request, msg: str = "", error: str = ""):
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Business, User.email, User.plan, User.is_active, func.count(Review.id).label("review_count"))
            .join(User, Business.user_id == User.id)
            .outerjoin(Review, Review.business_id == Business.id)
            .group_by(Business.id, User.email, User.plan, User.is_active)
            .order_by(Business.created_at.desc())
        )).all()

    items = [
        {
            "id": b.id, "name": b.name, "place_id": b.google_place_id,
            "email": email, "plan": plan, "owner_active": is_active,
            "is_paused": b.is_paused, "review_count": review_count,
            "verified": b.self_declared_owner, "created_at": b.created_at,
        }
        for b, email, plan, is_active, review_count in rows
    ]
    return templates.TemplateResponse(
        "admin/businesses.html",
        {"request": request, "businesses": items, "msg": msg, "error": error},
    )


@router.post("/businesses/{bid}/pause")
async def business_pause(bid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(Business).where(Business.id == bid).values(is_paused=True))
        await session.commit()
    return _redirect("/admin/businesses", msg="Negocio pausado")


@router.post("/businesses/{bid}/resume")
async def business_resume(bid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(Business).where(Business.id == bid).values(is_paused=False))
        await session.commit()
    return _redirect("/admin/businesses", msg="Negocio reactivado")


@router.post("/businesses/{bid}/delete")
async def business_delete(bid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Business).where(Business.id == bid))
        await session.commit()
    return _redirect("/admin/businesses", msg="Negocio eliminado")


@router.post("/poll/all")
async def poll_all(background_tasks: BackgroundTasks):
    from app.services.review_service import poll_all_businesses
    background_tasks.add_task(poll_all_businesses)
    return _redirect("/admin/businesses", msg="Polling lanzado en background")


@router.post("/poll/{bid}")
async def poll_one(bid: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(_poll_single, bid)
    return _redirect("/admin/businesses", msg=f"Polling lanzado para negocio {bid}")


# ── Reviews ────────────────────────────────────────────────────────────────────

@router.get("/reviews")
async def reviews(request: Request, business_id: int = 0, review_type: str = "", msg: str = ""):
    async with AsyncSessionLocal() as session:
        q = (
            select(Review, Business.name.label("biz_name"), User.email)
            .join(Business, Review.business_id == Business.id)
            .join(User, Business.user_id == User.id)
            .order_by(Review.created_at.desc())
            .limit(300)
        )
        if business_id:
            q = q.where(Review.business_id == business_id)
        if review_type in ("negative", "positive"):
            q = q.where(Review.review_type == review_type)
        rows = (await session.execute(q)).all()
        biz_list = (await session.execute(select(Business.id, Business.name).order_by(Business.name))).all()

    items = [
        {
            "id": r.id, "biz_name": biz_name, "email": email,
            "rating": r.rating, "review_type": r.review_type,
            "author": r.author_name, "text": (r.text or "")[:150],
            "platform": r.platform, "created_at": r.created_at,
        }
        for r, biz_name, email in rows
    ]
    return templates.TemplateResponse(
        "admin/reviews.html",
        {
            "request": request, "reviews": items, "msg": msg,
            "businesses": [{"id": i, "name": n} for i, n in biz_list],
            "selected_business": business_id, "selected_type": review_type,
        },
    )


@router.post("/reviews/{rid}/delete")
async def review_delete(rid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Review).where(Review.id == rid))
        await session.commit()
    return _redirect("/admin/reviews", msg="Reseña eliminada")


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users")
async def users(request: Request, msg: str = "", error: str = ""):
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(User, func.count(Business.id).label("biz_count"))
            .outerjoin(Business, Business.user_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at.desc())
        )).all()

    items = [
        {
            "id": u.id, "email": u.email or "—", "telegram_id": u.telegram_user_id,
            "plan": u.plan, "sub_status": u.sub_status, "is_active": u.is_active,
            "activated": u.telegram_user_id is not None,
            "biz_count": biz_count, "created_at": u.created_at,
        }
        for u, biz_count in rows
    ]
    return templates.TemplateResponse(
        "admin/users.html", {"request": request, "users": items, "msg": msg, "error": error}
    )


@router.post("/users/{uid}/block")
async def user_block(uid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.id == uid).values(is_active=False))
        await session.commit()
    return _redirect("/admin/users", msg="Usuario bloqueado")


@router.post("/users/{uid}/unblock")
async def user_unblock(uid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.id == uid).values(is_active=True))
        await session.commit()
    return _redirect("/admin/users", msg="Usuario desbloqueado")


@router.post("/users/{uid}/delete")
async def user_delete(uid: int):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.id == uid))
        await session.commit()
    return _redirect("/admin/users", msg="Usuario eliminado")


# ── Poll single business (internal) ───────────────────────────────────────────

async def _poll_single(business_id: int) -> None:
    from app.integrations.anthropic_client import get_anthropic_client
    from app.integrations.google_places import GooglePlacesClient
    from app.repositories import review_repo
    from app.repositories.alert_log_repo import create as create_alert_log
    from app.services.review_service import (
        _build_negative_alert_free,
        _build_negative_alert_pro,
        _classify_review,
    )

    places = GooglePlacesClient()
    anthropic = get_anthropic_client()

    async with AsyncSessionLocal() as session:
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Business).where(Business.id == business_id).options(selectinload(Business.user))
        )
        business = result.scalar_one_or_none()
        if not business:
            return

        user = business.user
        raw_reviews = await places.get_reviews(business.google_place_id)

        for raw in raw_reviews:
            review_id = raw.get("name", "")
            if not review_id:
                continue
            if await review_repo.exists(session, "google", review_id):
                continue

            rating = raw.get("rating", 0)
            review_type = _classify_review(rating)
            text_src = raw.get("originalText") or raw.get("text")
            text = text_src.get("text") if isinstance(text_src, dict) else text_src
            author = raw.get("authorAttribution", {}).get("displayName", "Anónimo")

            from datetime import datetime
            published_at = None
            published_raw = raw.get("publishTime")
            if published_raw:
                try:
                    published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except ValueError:
                    pass

            review = await review_repo.create(
                session, business_id=business.id, platform="google",
                review_id=review_id, rating=rating, text=text,
                author=author, reviewed_at=published_at, review_type=review_type,
            )

            if review_type == "negative" and user.telegram_user_id and user.is_active:
                draft, tokens = "", 0
                if user.plan in ("pro", "multi") and user.sub_status == "active":
                    draft, tokens = await anthropic.generate_negative_draft(review, business)
                    msg = _build_negative_alert_pro(business.name, review, draft)
                else:
                    msg = _build_negative_alert_free(business.name, review)
                try:
                    from app.bot import get_application
                    bot_app = get_application()
                    sent = await bot_app.bot.send_message(chat_id=user.telegram_user_id, text=msg)
                    await create_alert_log(
                        session, review_id=review.id,
                        telegram_message_id=sent.message_id,
                        alert_type="negative_immediate",
                        draft_type="negative" if draft else None,
                        ai_draft_tokens=tokens if tokens else None,
                    )
                except Exception:
                    logger.exception("Admin poll: error sending alert for review %d", review.id)

    logger.info("Admin poll completed for business %d", business_id)
