from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.orm import Session

from app.models import Event, Nomination, Registration, RegistrationNomination


HEADERS = [
    "#",
    "ФИО",
    "Никнейм",
    "Дата рождения",
    "Возраст",
    "Пол",
    "Город",
    "Клуб/команда",
    "Тренер",
    "Телефон",
    "Тип регистрации",
    "Дата регистрации",
]


REGISTRATION_TYPE_LABELS = {
    "full": "Полная",
    "short": "Короткая",
    "coach": "Ученики",
}


def _safe_sheet_name(title: str) -> str:
    cleaned = "".join(ch for ch in title if ch not in "[]:*?/\\")
    return (cleaned or "Номинация")[:31]


def build_event_export(db: Session, event: Event) -> BytesIO:
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    nominations = (
        db.query(Nomination)
        .filter(Nomination.event_id == event.id)
        .order_by(Nomination.sort_order, Nomination.title)
        .all()
    )

    if not nominations:
        workbook.create_sheet("Без номинаций")

    for nomination in nominations:
        sheet = workbook.create_sheet(_safe_sheet_name(nomination.title))
        sheet.append(HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="111111")

        rows = (
            db.query(Registration)
            .join(RegistrationNomination)
            .filter(
                Registration.event_id == event.id,
                RegistrationNomination.nomination_id == nomination.id,
            )
            .order_by(Registration.full_name)
            .all()
        )
        for index, registration in enumerate(rows, start=1):
            sheet.append(
                [
                    index,
                    registration.full_name,
                    registration.nickname,
                    registration.birth_date.strftime("%d.%m.%Y"),
                    registration.age_on_event,
                    "Мужской" if registration.gender.value == "male" else "Женский",
                    registration.city or "",
                    registration.club or "",
                    registration.trainer or "",
                    registration.phone or "",
                    REGISTRATION_TYPE_LABELS.get(registration.registration_type.value, registration.registration_type.value),
                    registration.created_at.strftime("%d.%m.%Y %H:%M"),
                ]
            )

        for column in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column)
            sheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 40)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
