from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import CoachProfile, DirectoryAlias, DirectoryEntry, DirectoryKind, ParticipantProfile, Registration, Student
from app.routers.deps import require_admin
from app.schemas import DirectoryAliasIn, DirectoryEntryIn, DirectoryEntryOut, DirectorySuggestionOut
from app.services.text import normalize_directory_key

router = APIRouter(prefix="/api/admin/directories", tags=["directories"])


def _kind(value: str) -> DirectoryKind:
    try:
        return DirectoryKind(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неизвестный тип справочника") from exc


def _entry_out(entry: DirectoryEntry) -> DirectoryEntryOut:
    entry.aliases.sort(key=lambda item: item.alias.lower())
    return DirectoryEntryOut.model_validate(entry)


def _add_alias(db: Session, entry: DirectoryEntry, alias: str) -> None:
    normalized_key = normalize_directory_key(alias)
    if not normalized_key:
        return
    existing = (
        db.query(DirectoryAlias)
        .filter(DirectoryAlias.kind == entry.kind, DirectoryAlias.normalized_key == normalized_key)
        .one_or_none()
    )
    if existing is not None:
        if existing.entry_id != entry.id:
            raise HTTPException(status_code=400, detail=f'Вариант "{alias}" уже привязан к другой записи')
        existing.alias = alias.strip()
        return
    db.add(
        DirectoryAlias(
            entry_id=entry.id,
            kind=entry.kind,
            alias=alias.strip(),
            normalized_key=normalized_key,
        ),
    )


def _suggestion_sources(db: Session, directory_kind: DirectoryKind):
    if directory_kind == DirectoryKind.trainer:
        return [
            db.query(ParticipantProfile.trainer.label("value")),
            db.query(Student.trainer.label("value")),
            db.query(Registration.trainer.label("value")),
        ]
    return [
        db.query(ParticipantProfile.club.label("value")),
        db.query(CoachProfile.club.label("value")),
        db.query(Student.club.label("value")),
        db.query(Registration.club.label("value")),
    ]


@router.get("/{kind}/suggestions", response_model=list[DirectorySuggestionOut], dependencies=[Depends(require_admin)])
def list_directory_suggestions(kind: str, db: Session = Depends(get_db)) -> list[DirectorySuggestionOut]:
    directory_kind = _kind(kind)
    suggestions: dict[str, dict] = {}

    for source in _suggestion_sources(db, directory_kind):
        for (value,) in source.all():
            display = str(value or "").strip()
            normalized_key = normalize_directory_key(display)
            if not normalized_key:
                continue
            current = suggestions.setdefault(
                normalized_key,
                {"value": display, "normalized_key": normalized_key, "count": 0},
            )
            current["count"] += 1
            if len(display) > len(current["value"]):
                current["value"] = display

    aliases = (
        db.query(DirectoryAlias)
        .options(joinedload(DirectoryAlias.entry))
        .join(DirectoryEntry, DirectoryEntry.id == DirectoryAlias.entry_id)
        .filter(DirectoryAlias.kind == directory_kind)
        .all()
    )
    alias_map = {alias.normalized_key: alias.entry.display_name for alias in aliases}
    for entry in db.query(DirectoryEntry).filter(DirectoryEntry.kind == directory_kind).all():
        alias_map[entry.normalized_key] = entry.display_name

    rows = []
    for item in suggestions.values():
        directory_display_name = alias_map.get(item["normalized_key"])
        rows.append(
            DirectorySuggestionOut(
                **item,
                in_directory=directory_display_name is not None,
                directory_display_name=directory_display_name,
            )
        )
    return sorted(rows, key=lambda item: (item.in_directory, -item.count, item.value.lower()))


@router.get("/{kind}", response_model=list[DirectoryEntryOut], dependencies=[Depends(require_admin)])
def list_directory(kind: str, db: Session = Depends(get_db)) -> list[DirectoryEntryOut]:
    directory_kind = _kind(kind)
    rows = (
        db.query(DirectoryEntry)
        .options(joinedload(DirectoryEntry.aliases))
        .filter(DirectoryEntry.kind == directory_kind)
        .order_by(DirectoryEntry.display_name)
        .all()
    )
    return [_entry_out(row) for row in rows]


@router.post("/{kind}", response_model=DirectoryEntryOut, dependencies=[Depends(require_admin)])
def create_directory_entry(kind: str, payload: DirectoryEntryIn, db: Session = Depends(get_db)) -> DirectoryEntryOut:
    directory_kind = _kind(kind)
    display_name = payload.display_name.strip()
    normalized_key = normalize_directory_key(display_name)
    if not normalized_key:
        raise HTTPException(status_code=400, detail="Введите название")

    entry = (
        db.query(DirectoryEntry)
        .options(joinedload(DirectoryEntry.aliases))
        .filter(DirectoryEntry.kind == directory_kind, DirectoryEntry.normalized_key == normalized_key)
        .one_or_none()
    )
    if entry is None:
        entry = DirectoryEntry(kind=directory_kind, display_name=display_name, normalized_key=normalized_key)
        db.add(entry)
        db.flush()
    else:
        entry.display_name = display_name

    for alias in [display_name, *payload.aliases]:
        _add_alias(db, entry, alias)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Такой вариант уже есть в справочнике") from exc
    return _entry_out(
        db.query(DirectoryEntry)
        .options(joinedload(DirectoryEntry.aliases))
        .filter(DirectoryEntry.id == entry.id)
        .one()
    )


@router.post("/{kind}/{entry_id}/aliases", response_model=DirectoryEntryOut, dependencies=[Depends(require_admin)])
def add_directory_alias(
    kind: str,
    entry_id: int,
    payload: DirectoryAliasIn,
    db: Session = Depends(get_db),
) -> DirectoryEntryOut:
    directory_kind = _kind(kind)
    entry = (
        db.query(DirectoryEntry)
        .options(joinedload(DirectoryEntry.aliases))
        .filter(DirectoryEntry.id == entry_id, DirectoryEntry.kind == directory_kind)
        .one_or_none()
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Запись справочника не найдена")
    _add_alias(db, entry, payload.alias)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Такой вариант уже есть в справочнике") from exc
    db.refresh(entry)
    return _entry_out(entry)


@router.delete("/{kind}/{entry_id}", dependencies=[Depends(require_admin)])
def delete_directory_entry(kind: str, entry_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    directory_kind = _kind(kind)
    entry = db.query(DirectoryEntry).filter(DirectoryEntry.id == entry_id, DirectoryEntry.kind == directory_kind).one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Запись справочника не найдена")
    db.delete(entry)
    db.commit()
    return {"ok": True}


@router.delete("/{kind}/aliases/{alias_id}", dependencies=[Depends(require_admin)])
def delete_directory_alias(kind: str, alias_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    directory_kind = _kind(kind)
    alias = db.query(DirectoryAlias).filter(DirectoryAlias.id == alias_id, DirectoryAlias.kind == directory_kind).one_or_none()
    if alias is None:
        raise HTTPException(status_code=404, detail="Вариант написания не найден")
    db.delete(alias)
    db.commit()
    return {"ok": True}
