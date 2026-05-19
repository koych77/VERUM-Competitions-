from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import DirectoryKind, EventStatus, Gender, GenderRule, NominationBattleType, RegistrationType


class TelegramUserIn(BaseModel):
    telegram_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class UserOut(TelegramUserIn):
    id: int
    is_admin: bool = False

    class Config:
        from_attributes = True


class EventBase(BaseModel):
    title: str
    event_date: date
    place: str
    description: str = ""
    image_url: str | None = None
    registration_opens_at: date
    registration_closes_at: date
    status: EventStatus = EventStatus.draft
    is_republic_championship: bool = False
    allow_full_registration: bool = True
    allow_short_registration: bool = True
    allow_coach_registration: bool = True


class EventCreate(EventBase):
    nominations: list["NominationCreate"] = Field(default_factory=list)


class EventUpdate(EventBase):
    pass


class EventOut(EventBase):
    id: int
    nominations: list["NominationOut"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class NominationBase(BaseModel):
    title: str
    min_age: int
    max_age: int
    gender_rule: GenderRule = GenderRule.any
    battle_type: NominationBattleType = NominationBattleType.solo
    experience: str = ""
    description: str = ""
    is_active: bool = True
    sort_order: int = 100


class NominationCreate(NominationBase):
    pass


class NominationUpdate(NominationBase):
    pass


class NominationOut(NominationBase):
    id: int
    event_id: int

    class Config:
        from_attributes = True


EventCreate.model_rebuild()
EventOut.model_rebuild()


class ParticipantProfileIn(BaseModel):
    full_name: str
    nickname: str
    birth_date: date
    gender: Gender
    phone: str | None = None
    city: str
    club: str
    trainer: str


class ParticipantProfileOut(ParticipantProfileIn):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class CoachProfileIn(BaseModel):
    full_name: str
    phone: str | None = None
    city: str
    club: str


class CoachProfileOut(CoachProfileIn):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class StudentIn(BaseModel):
    full_name: str
    nickname: str
    birth_date: date
    gender: Gender
    city: str
    club: str
    trainer: str


class StudentOut(StudentIn):
    id: int
    coach_id: int
    is_archived: bool

    class Config:
        from_attributes = True


class ShortRegistrationIn(BaseModel):
    user: TelegramUserIn
    full_name: str
    nickname: str
    birth_date: date
    gender: Gender
    phone: str | None = None
    nomination_ids: list[int]


class FullRegistrationIn(BaseModel):
    user: TelegramUserIn
    profile: ParticipantProfileIn
    nomination_ids: list[int]


class CoachRegistrationItemIn(BaseModel):
    student_id: int
    nomination_ids: list[int]


class CoachRegistrationIn(BaseModel):
    user: TelegramUserIn
    coach: CoachProfileIn
    registrations: list[CoachRegistrationItemIn]


class RegistrationNominationOut(BaseModel):
    id: int
    nomination_id: int
    title: str


class RegistrationOut(BaseModel):
    id: int
    event_id: int
    registration_type: RegistrationType
    full_name: str
    nickname: str
    birth_date: date
    age_on_event: int
    gender: Gender
    phone: str | None = None
    city: str | None = None
    club: str | None = None
    trainer: str | None = None
    created_at: datetime
    nominations: list[RegistrationNominationOut]


class RegistrationEditIn(BaseModel):
    full_name: str
    nickname: str
    birth_date: date
    gender: Gender
    phone: str | None = None
    city: str | None = None
    club: str | None = None
    trainer: str | None = None
    nomination_ids: list[int]


class DirectoryAliasOut(BaseModel):
    id: int
    alias: str
    normalized_key: str

    class Config:
        from_attributes = True


class DirectoryEntryOut(BaseModel):
    id: int
    kind: DirectoryKind
    display_name: str
    normalized_key: str
    aliases: list[DirectoryAliasOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DirectoryEntryIn(BaseModel):
    display_name: str
    aliases: list[str] = Field(default_factory=list)


class DirectoryAliasIn(BaseModel):
    alias: str


class DirectorySuggestionOut(BaseModel):
    value: str
    normalized_key: str
    count: int
    in_directory: bool = False
    directory_display_name: str | None = None
