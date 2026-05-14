from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    CoachProfile,
    Event,
    ParticipantProfile,
    Registration,
    RegistrationNomination,
    RegistrationType,
    Student,
    User,
)
from app.routers.auth import upsert_user
from app.routers.deps import require_admin, require_admin_download
from app.schemas import (
    CoachRegistrationIn,
    FullRegistrationIn,
    NominationOut,
    RegistrationEditIn,
    RegistrationNominationOut,
    RegistrationOut,
    ShortRegistrationIn,
)
from app.services.age import calculate_event_age
from app.services.export import build_event_export
from app.services.registrations import ensure_event_open, replace_registration_nominations, validate_nomination_ids

router = APIRouter(prefix="/api", tags=["registrations"])


def _registration_out(registration: Registration) -> RegistrationOut:
    return RegistrationOut(
        id=registration.id,
        event_id=registration.event_id,
        registration_type=registration.registration_type,
        full_name=registration.full_name,
        nickname=registration.nickname,
        birth_date=registration.birth_date,
        age_on_event=registration.age_on_event,
        gender=registration.gender,
        phone=registration.phone,
        city=registration.city,
        club=registration.club,
        trainer=registration.trainer,
        created_at=registration.created_at,
        nominations=[
            RegistrationNominationOut(
                id=item.id,
                nomination_id=item.nomination_id,
                title=item.nomination.title,
            )
            for item in registration.nominations
        ],
    )


def _load_registration(db: Session, registration_id: int) -> Registration:
    registration = (
        db.query(Registration)
        .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
        .filter(Registration.id == registration_id)
        .one_or_none()
    )
    if registration is None:
        raise HTTPException(status_code=404, detail="Регистрация не найдена")
    return registration


def _normalize_identity(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _same_short_participant(registration: Registration, payload: ShortRegistrationIn) -> bool:
    return (
        _normalize_identity(registration.full_name) == _normalize_identity(payload.full_name)
        and _normalize_identity(registration.nickname) == _normalize_identity(payload.nickname)
        and registration.birth_date == payload.birth_date
    )


@router.get("/events/{event_id}/available-nominations", response_model=list[NominationOut])
def available_nominations(
    event_id: int,
    birth_date: str,
    gender: str,
    db: Session = Depends(get_db),
):
    from datetime import date

    from app.models import Gender
    from app.services.registrations import get_available_nominations

    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    parsed_birth_date = date.fromisoformat(birth_date)
    nominations = get_available_nominations(db, event, parsed_birth_date, Gender(gender))
    return nominations


@router.post("/events/{event_id}/register/full", response_model=RegistrationOut)
def register_full(event_id: int, payload: FullRegistrationIn, db: Session = Depends(get_db)) -> RegistrationOut:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    ensure_event_open(event)

    user = upsert_user(db, payload.user)
    profile = db.query(ParticipantProfile).filter(ParticipantProfile.user_id == user.id).one_or_none()
    if profile is None:
        profile = ParticipantProfile(user_id=user.id, **payload.profile.model_dump())
        db.add(profile)
        db.flush()
    else:
        for key, value in payload.profile.model_dump().items():
            setattr(profile, key, value)

    nominations = validate_nomination_ids(db, event, profile.birth_date, profile.gender, payload.nomination_ids)
    age = calculate_event_age(profile.birth_date, event.event_date, event.is_republic_championship)
    registration = (
        db.query(Registration)
        .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
        .filter(Registration.event_id == event.id, Registration.participant_profile_id == profile.id)
        .one_or_none()
    )
    if registration is None:
        registration = Registration(
            event_id=event.id,
            registration_type=RegistrationType.full,
            user_id=user.id,
            participant_profile_id=profile.id,
            full_name=profile.full_name,
            nickname=profile.nickname,
            birth_date=profile.birth_date,
            age_on_event=age,
            gender=profile.gender,
            phone=profile.phone,
            city=profile.city,
            club=profile.club,
            trainer=profile.trainer,
        )
        db.add(registration)
        db.flush()
    else:
        registration.full_name = profile.full_name
        registration.nickname = profile.nickname
        registration.birth_date = profile.birth_date
        registration.age_on_event = age
        registration.gender = profile.gender
        registration.phone = profile.phone
        registration.city = profile.city
        registration.club = profile.club
        registration.trainer = profile.trainer
        current_by_id = {item.nomination_id: item.nomination for item in registration.nominations}
        nominations = list({item.id: item for item in [*current_by_id.values(), *nominations]}.values())

    replace_registration_nominations(registration, nominations)
    db.commit()
    db.refresh(registration)
    return _registration_out(_load_registration(db, registration.id))


@router.post("/events/{event_id}/register/short", response_model=RegistrationOut)
def register_short(event_id: int, payload: ShortRegistrationIn, db: Session = Depends(get_db)) -> RegistrationOut:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    ensure_event_open(event)

    user = upsert_user(db, payload.user)
    nominations = validate_nomination_ids(db, event, payload.birth_date, payload.gender, payload.nomination_ids)
    existing_short_registrations = (
        db.query(Registration)
        .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
        .filter(
            Registration.event_id == event.id,
            Registration.user_id == user.id,
            Registration.registration_type == RegistrationType.short,
        )
        .all()
    )
    registration = next((row for row in existing_short_registrations if _same_short_participant(row, payload)), None)
    if registration is None:
        registration = Registration(
            event_id=event.id,
            registration_type=RegistrationType.short,
            user_id=user.id,
            full_name=payload.full_name,
            nickname=payload.nickname,
            birth_date=payload.birth_date,
            age_on_event=calculate_event_age(payload.birth_date, event.event_date, event.is_republic_championship),
            gender=payload.gender,
            phone=payload.phone,
        )
        db.add(registration)
        db.flush()
    else:
        registration.full_name = payload.full_name
        registration.nickname = payload.nickname
        registration.birth_date = payload.birth_date
        registration.age_on_event = calculate_event_age(payload.birth_date, event.event_date, event.is_republic_championship)
        registration.gender = payload.gender
        registration.phone = payload.phone
        current_by_id = {item.nomination_id: item.nomination for item in registration.nominations}
        nominations = list({item.id: item for item in [*current_by_id.values(), *nominations]}.values())
    replace_registration_nominations(registration, nominations)
    db.commit()
    db.refresh(registration)
    return _registration_out(_load_registration(db, registration.id))


@router.post("/events/{event_id}/register/coach", response_model=list[RegistrationOut])
def register_coach(event_id: int, payload: CoachRegistrationIn, db: Session = Depends(get_db)) -> list[RegistrationOut]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    ensure_event_open(event)

    user = upsert_user(db, payload.user)
    coach = db.query(CoachProfile).filter(CoachProfile.user_id == user.id).one_or_none()
    if coach is None:
        coach = CoachProfile(user_id=user.id, **payload.coach.model_dump())
        db.add(coach)
        db.flush()
    else:
        for key, value in payload.coach.model_dump().items():
            setattr(coach, key, value)

    created_ids: list[int] = []
    for item in payload.registrations:
        student = db.get(Student, item.student_id)
        if student is None or student.coach_id != coach.id or student.is_archived:
            raise HTTPException(status_code=400, detail="Один из учеников недоступен")
        nominations = validate_nomination_ids(db, event, student.birth_date, student.gender, item.nomination_ids)
        registration = (
            db.query(Registration)
            .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
            .filter(Registration.event_id == event.id, Registration.student_id == student.id)
            .one_or_none()
        )
        if registration is None:
            registration = Registration(
                event_id=event.id,
                registration_type=RegistrationType.coach,
                user_id=user.id,
                coach_id=coach.id,
                student_id=student.id,
                full_name=student.full_name,
                nickname=student.nickname,
                birth_date=student.birth_date,
                age_on_event=calculate_event_age(student.birth_date, event.event_date, event.is_republic_championship),
                gender=student.gender,
                city=student.city,
                club=student.club,
                trainer=student.trainer,
            )
            db.add(registration)
            db.flush()
        else:
            registration.full_name = student.full_name
            registration.nickname = student.nickname
            registration.birth_date = student.birth_date
            registration.age_on_event = calculate_event_age(student.birth_date, event.event_date, event.is_republic_championship)
            registration.gender = student.gender
            registration.city = student.city
            registration.club = student.club
            registration.trainer = student.trainer
            current_by_id = {item.nomination_id: item.nomination for item in registration.nominations}
            nominations = list({item.id: item for item in [*current_by_id.values(), *nominations]}.values())
        replace_registration_nominations(registration, nominations)
        created_ids.append(registration.id)

    db.commit()
    return [_registration_out(_load_registration(db, registration_id)) for registration_id in created_ids]


@router.get("/events/{event_id}/registrations", response_model=list[RegistrationOut], dependencies=[Depends(require_admin)])
def list_event_registrations(event_id: int, db: Session = Depends(get_db)) -> list[RegistrationOut]:
    rows = (
        db.query(Registration)
        .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
        .filter(Registration.event_id == event_id)
        .order_by(Registration.full_name)
        .all()
    )
    return [_registration_out(row) for row in rows]


@router.put("/admin/registrations/{registration_id}", response_model=RegistrationOut, dependencies=[Depends(require_admin)])
def edit_registration(
    registration_id: int,
    payload: RegistrationEditIn,
    db: Session = Depends(get_db),
) -> RegistrationOut:
    registration = _load_registration(db, registration_id)
    event = db.get(Event, registration.event_id)
    nominations = validate_nomination_ids(db, event, payload.birth_date, payload.gender, payload.nomination_ids)
    for key, value in payload.model_dump(exclude={"nomination_ids"}).items():
        setattr(registration, key, value)
    registration.age_on_event = calculate_event_age(payload.birth_date, event.event_date, event.is_republic_championship)
    replace_registration_nominations(registration, nominations)
    db.commit()
    return _registration_out(_load_registration(db, registration.id))


@router.delete("/admin/registrations/{registration_id}", dependencies=[Depends(require_admin)])
def delete_registration(registration_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    registration = _load_registration(db, registration_id)
    db.delete(registration)
    db.commit()
    return {"ok": True}


@router.get("/events/{event_id}/export", dependencies=[Depends(require_admin_download)])
def export_event(event_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    output = build_event_export(db, event)
    filename = f"verum_event_{event.id}_participants.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/users/{telegram_id}/events/{event_id}/registration", response_model=RegistrationOut | None)
def get_user_registration(telegram_id: int, event_id: int, db: Session = Depends(get_db)) -> RegistrationOut | None:
    user = db.query(User).filter(User.telegram_id == telegram_id).one_or_none()
    if user is None:
        return None
    registration = (
        db.query(Registration)
        .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
        .filter(
            Registration.event_id == event_id,
            Registration.user_id == user.id,
            Registration.registration_type == RegistrationType.full,
        )
        .order_by(Registration.created_at.desc())
        .first()
    )
    return _registration_out(registration) if registration else None


@router.get("/users/{telegram_id}/events/{event_id}/registrations", response_model=list[RegistrationOut])
def get_user_registrations(telegram_id: int, event_id: int, db: Session = Depends(get_db)) -> list[RegistrationOut]:
    user = db.query(User).filter(User.telegram_id == telegram_id).one_or_none()
    if user is None:
        return []
    rows = (
        db.query(Registration)
        .options(joinedload(Registration.nominations).joinedload(RegistrationNomination.nomination))
        .filter(
            Registration.event_id == event_id,
            Registration.user_id == user.id,
            Registration.registration_type == RegistrationType.short,
        )
        .order_by(Registration.created_at.desc())
        .all()
    )
    return [_registration_out(row) for row in rows]
