from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CoachProfile, ParticipantProfile, Student, User
from app.routers.auth import upsert_user
from app.schemas import (
    CoachProfileIn,
    CoachProfileOut,
    ParticipantProfileIn,
    ParticipantProfileOut,
    StudentIn,
    StudentOut,
    TelegramUserIn,
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.post("/participant", response_model=ParticipantProfileOut)
def upsert_participant_profile(
    user_in: TelegramUserIn,
    profile: ParticipantProfileIn,
    db: Session = Depends(get_db),
) -> ParticipantProfile:
    user = upsert_user(db, user_in)
    saved = db.query(ParticipantProfile).filter(ParticipantProfile.user_id == user.id).one_or_none()
    if saved is None:
        saved = ParticipantProfile(user_id=user.id, **profile.model_dump())
        db.add(saved)
    else:
        for key, value in profile.model_dump().items():
            setattr(saved, key, value)
    db.commit()
    db.refresh(saved)
    return saved


@router.get("/participant/{telegram_id}", response_model=ParticipantProfileOut | None)
def get_participant_profile(telegram_id: int, db: Session = Depends(get_db)) -> ParticipantProfile | None:
    user = db.query(User).filter(User.telegram_id == telegram_id).one_or_none()
    if user is None:
        return None
    return db.query(ParticipantProfile).filter(ParticipantProfile.user_id == user.id).one_or_none()


@router.post("/coach", response_model=CoachProfileOut)
def upsert_coach_profile(
    user_in: TelegramUserIn,
    coach: CoachProfileIn,
    db: Session = Depends(get_db),
) -> CoachProfile:
    user = upsert_user(db, user_in)
    saved = db.query(CoachProfile).filter(CoachProfile.user_id == user.id).one_or_none()
    if saved is None:
        saved = CoachProfile(user_id=user.id, **coach.model_dump())
        db.add(saved)
    else:
        for key, value in coach.model_dump().items():
            setattr(saved, key, value)
    db.commit()
    db.refresh(saved)
    return saved


@router.get("/coach/{telegram_id}", response_model=CoachProfileOut | None)
def get_coach_profile(telegram_id: int, db: Session = Depends(get_db)) -> CoachProfile | None:
    user = db.query(User).filter(User.telegram_id == telegram_id).one_or_none()
    if user is None:
        return None
    return db.query(CoachProfile).filter(CoachProfile.user_id == user.id).one_or_none()


@router.get("/coach/{coach_id}/students", response_model=list[StudentOut])
def list_students(coach_id: int, db: Session = Depends(get_db)) -> list[Student]:
    return (
        db.query(Student)
        .filter(Student.coach_id == coach_id, Student.is_archived.is_(False))
        .order_by(Student.full_name)
        .all()
    )


@router.post("/coach/{coach_id}/students", response_model=StudentOut)
def create_student(coach_id: int, payload: StudentIn, db: Session = Depends(get_db)) -> Student:
    if db.get(CoachProfile, coach_id) is None:
        raise HTTPException(status_code=404, detail="Профиль тренера не найден")
    student = Student(coach_id=coach_id, **payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentIn, db: Session = Depends(get_db)) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    for key, value in payload.model_dump().items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return student
