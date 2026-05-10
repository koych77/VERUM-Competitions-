from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Event, EventStatus, Nomination
from app.routers.deps import require_admin
from app.schemas import EventCreate, EventOut, EventUpdate, NominationCreate, NominationOut, NominationUpdate

router = APIRouter(prefix="/api/events", tags=["events"])


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


@router.post("/admin/{event_id}/nominations", response_model=NominationOut, dependencies=[Depends(require_admin)])
def create_nomination(event_id: int, payload: NominationCreate, db: Session = Depends(get_db)) -> Nomination:
    if db.get(Event, event_id) is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    nomination = Nomination(event_id=event_id, **payload.model_dump())
    db.add(nomination)
    db.commit()
    db.refresh(nomination)
    return nomination


@router.put("/admin/nominations/{nomination_id}", response_model=NominationOut, dependencies=[Depends(require_admin)])
def update_nomination(nomination_id: int, payload: NominationUpdate, db: Session = Depends(get_db)) -> Nomination:
    nomination = db.get(Nomination, nomination_id)
    if nomination is None:
        raise HTTPException(status_code=404, detail="Номинация не найдена")
    for key, value in payload.model_dump().items():
        setattr(nomination, key, value)
    db.commit()
    db.refresh(nomination)
    return nomination


@router.post("/admin/nominations/{nomination_id}/toggle", response_model=NominationOut, dependencies=[Depends(require_admin)])
def toggle_nomination(nomination_id: int, db: Session = Depends(get_db)) -> Nomination:
    nomination = db.get(Nomination, nomination_id)
    if nomination is None:
        raise HTTPException(status_code=404, detail="Номинация не найдена")
    nomination.is_active = not nomination.is_active
    db.commit()
    db.refresh(nomination)
    return nomination
