from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import CoachProfile, ParticipantProfile, Student, User
from app.routers.auth import upsert_user
from app.routers.deps import require_admin
from app.schemas import (
    CoachProfileIn,
    CoachProfileOut,
    CoachWithStudentsOut,
    ParticipantProfileIn,
    ParticipantProfileOut,
    StudentIn,
    StudentOut,
    TelegramUserIn,
)
from app.services.text import normalize_nickname

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _normalized_payload(payload):
    data = payload.model_dump()
    if "nickname" in data:
        data["nickname"] = normalize_nickname(data["nickname"])
        if not data["nickname"]:
            raise HTTPException(status_code=400, detail="Введите никнейм без Bboy/Bgirl")
    return data


@router.post("/participant", response_model=ParticipantProfileOut)
def upsert_participant_profile(
    user_in: TelegramUserIn,
    profile: ParticipantProfileIn,
    db: Session = Depends(get_db),
) -> ParticipantProfile:
    user = upsert_user(db, user_in)
    profile_data = _normalized_payload(profile)
    saved = db.query(ParticipantProfile).filter(ParticipantProfile.user_id == user.id).one_or_none()
    if saved is None:
        saved = ParticipantProfile(user_id=user.id, **profile_data)
        db.add(saved)
    else:
        for key, value in profile_data.items():
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


@router.get("/admin/participants", response_model=list[ParticipantProfileOut], dependencies=[Depends(require_admin)])
def list_participant_profiles(db: Session = Depends(get_db)) -> list[ParticipantProfile]:
    return db.query(ParticipantProfile).order_by(ParticipantProfile.full_name).all()


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


@router.get("/admin/coaches", response_model=list[CoachWithStudentsOut], dependencies=[Depends(require_admin)])
def list_coach_profiles(db: Session = Depends(get_db)) -> list[CoachProfile]:
    rows = (
        db.query(CoachProfile)
        .options(joinedload(CoachProfile.students))
        .order_by(CoachProfile.full_name)
        .all()
    )
    for row in rows:
        row.students.sort(key=lambda student: (student.is_archived, student.full_name.lower()))
    return rows


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
    student = Student(coach_id=coach_id, **_normalized_payload(payload))
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentIn, db: Session = Depends(get_db)) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    for key, value in _normalized_payload(payload).items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return student


@router.post("/students/{student_id}/archive", response_model=StudentOut)
def archive_student(student_id: int, db: Session = Depends(get_db)) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    student.is_archived = True
    db.commit()
    db.refresh(student)
    return student
