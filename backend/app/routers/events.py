from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.models import Event, EventStatus, Nomination
from app.routers.deps import require_admin
from app.schemas import EventCreate, EventOut, EventUpdate, NominationCreate, NominationOut, NominationUpdate

router = APIRouter(prefix="/api/events", tags=["events"])

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@router.get("", response_model=list[EventOut])
def list_public_events(db: Session = Depends(get_db)) -> list[Event]:
    today = date.today()
    return (
        db.query(Event)
        .options(selectinload(Event.nominations))
        .filter(
            Event.status == EventStatus.open,
            Event.registration_opens_at <= today,
            Event.registration_closes_at >= today,
        )
        .order_by(Event.event_date)
        .all()
    )


@router.get("/admin", response_model=list[EventOut], dependencies=[Depends(require_admin)])
def list_admin_events(db: Session = Depends(get_db)) -> list[Event]:
    return db.query(Event).options(selectinload(Event.nominations)).order_by(Event.event_date.desc()).all()


def get_event_with_nominations(db: Session, event_id: int) -> Event:
    event = (
        db.query(Event)
        .options(selectinload(Event.nominations))
        .filter(Event.id == event_id)
        .one_or_none()
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    return event


@router.post("/admin", response_model=EventOut, dependencies=[Depends(require_admin)])
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> Event:
    event = Event(**payload.model_dump(exclude={"nominations"}))
    db.add(event)
    db.flush()
    for nomination_data in payload.nominations:
        db.add(Nomination(event_id=event.id, **nomination_data.model_dump()))
    db.commit()
    db.refresh(event)
    return event


@router.put("/admin/{event_id}", response_model=EventOut, dependencies=[Depends(require_admin)])
def update_event(event_id: int, payload: EventUpdate, db: Session = Depends(get_db)) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    for key, value in payload.model_dump().items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


@router.post("/admin/{event_id}/archive", response_model=EventOut, dependencies=[Depends(require_admin)])
def archive_event(event_id: int, db: Session = Depends(get_db)) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    event.status = EventStatus.archived
    db.commit()
    db.refresh(event)
    return event


@router.post("/admin/{event_id}/image", response_model=EventOut, dependencies=[Depends(require_admin)])
async def upload_event_image(
    event_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Загрузите JPG, PNG или WEBP")

    content = await image.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Картинка должна быть до 5 МБ")

    settings = get_settings()
    target_dir = settings.upload_dir / "events"
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = ALLOWED_IMAGE_TYPES[image.content_type]
    filename = f"event_{event_id}_{uuid4().hex}{suffix}"
    target_path = target_dir / filename
    target_path.write_bytes(content)

    event.image_url = f"/uploads/events/{filename}"
    db.commit()
    db.refresh(event)
    return event


@router.post("/admin/{event_id}/nominations", response_model=EventOut, dependencies=[Depends(require_admin)])
def create_nomination(event_id: int, payload: NominationCreate, db: Session = Depends(get_db)) -> Event:
    if db.get(Event, event_id) is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    if payload.min_age > payload.max_age:
        raise HTTPException(status_code=400, detail="Возраст от не может быть больше возраста до")
    nomination = Nomination(event_id=event_id, **payload.model_dump())
    db.add(nomination)
    db.commit()
    return get_event_with_nominations(db, event_id)


@router.put("/admin/nominations/{nomination_id}", response_model=EventOut, dependencies=[Depends(require_admin)])
def update_nomination(nomination_id: int, payload: NominationUpdate, db: Session = Depends(get_db)) -> Event:
    nomination = db.get(Nomination, nomination_id)
    if nomination is None:
        raise HTTPException(status_code=404, detail="Номинация не найдена")
    if payload.min_age > payload.max_age:
        raise HTTPException(status_code=400, detail="Возраст от не может быть больше возраста до")
    event_id = nomination.event_id
    for key, value in payload.model_dump().items():
        setattr(nomination, key, value)
    db.commit()
    return get_event_with_nominations(db, event_id)


@router.post("/admin/nominations/{nomination_id}/toggle", response_model=EventOut, dependencies=[Depends(require_admin)])
def toggle_nomination(nomination_id: int, db: Session = Depends(get_db)) -> Event:
    nomination = db.get(Nomination, nomination_id)
    if nomination is None:
        raise HTTPException(status_code=404, detail="Номинация не найдена")
    event_id = nomination.event_id
    nomination.is_active = not nomination.is_active
    db.commit()
    return get_event_with_nominations(db, event_id)
