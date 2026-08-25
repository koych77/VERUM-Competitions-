from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.models import CoachProfile, ParticipantProfile, Student, User
from app.routers.deps import get_current_user, require_admin, require_self_or_admin
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


def _require_profile_owner(current_user: User, telegram_id: int) -> None:
    if current_user.telegram_id != telegram_id:
        raise HTTPException(status_code=403, detail="Нельзя изменять профиль другого пользователя")


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParticipantProfile:
    _require_profile_owner(current_user, user_in.telegram_id)
    profile_data = _normalized_payload(profile)
    saved = db.query(ParticipantProfile).filter(ParticipantProfile.user_id == current_user.id).one_or_none()
    if saved is None:
        saved = ParticipantProfile(user_id=current_user.id, **profile_data)
        db.add(saved)
    else:
        for key, value in profile_data.items():
            setattr(saved, key, value)
    db.commit()
    db.refresh(saved)
    return saved


@router.get("/participant/{telegram_id}", response_model=ParticipantProfileOut | None)
def get_participant_profile(
    telegram_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParticipantProfile | None:
    require_self_or_admin(current_user, telegram_id)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoachProfile:
    _require_profile_owner(current_user, user_in.telegram_id)
    saved = db.query(CoachProfile).filter(CoachProfile.user_id == current_user.id).one_or_none()
    if saved is None:
        saved = CoachProfile(user_id=current_user.id, **coach.model_dump())
        db.add(saved)
    else:
        for key, value in coach.model_dump().items():
            setattr(saved, key, value)
    db.commit()
    db.refresh(saved)
    return saved


@router.get("/coach/{telegram_id}", response_model=CoachProfileOut | None)
def get_coach_profile(
    telegram_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoachProfile | None:
    require_self_or_admin(current_user, telegram_id)
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


def _require_coach_owner(db: Session, current_user: User, coach_id: int) -> CoachProfile:
    coach = db.get(CoachProfile, coach_id)
    if coach is None:
        raise HTTPException(status_code=404, detail="Профиль тренера не найден")
    if coach.user_id != current_user.id and current_user.telegram_id not in get_settings().admin_id_set:
        raise HTTPException(status_code=403, detail="Нет доступа к ученикам другого тренера")
    return coach


@router.get("/coach/{coach_id}/students", response_model=list[StudentOut])
def list_students(
    coach_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Student]:
    _require_coach_owner(db, current_user, coach_id)
    return (
        db.query(Student)
        .filter(Student.coach_id == coach_id, Student.is_archived.is_(False))
        .order_by(Student.full_name)
        .all()
    )


@router.post("/coach/{coach_id}/students", response_model=StudentOut)
def create_student(
    coach_id: int,
    payload: StudentIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Student:
    _require_coach_owner(db, current_user, coach_id)
    student = Student(coach_id=coach_id, **_normalized_payload(payload))
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    payload: StudentIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    _require_coach_owner(db, current_user, student.coach_id)
    for key, value in _normalized_payload(payload).items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return student


@router.post("/students/{student_id}/archive", response_model=StudentOut)
def archive_student(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    _require_coach_owner(db, current_user, student.coach_id)
    student.is_archived = True
    db.commit()
    db.refresh(student)
    return student
