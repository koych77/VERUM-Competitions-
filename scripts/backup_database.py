"""Create a portable, compressed JSON backup without logging database secrets or row data."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, inspect, text


def encode_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
        return {"$type": "datetime", "value": normalized.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"$type": "time", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"$type": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"$type": "uuid", "value": str(value)}
    if isinstance(value, bytes):
        return {"$type": "bytes", "value": base64.b64encode(value).decode("ascii")}
    return {"$type": "string", "value": str(value)}


def create_backup(database_url: str, output: Path) -> tuple[dict[str, int], str]:
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(database_url, pool_pre_ping=True)
    inspector = inspect(engine)
    schema = "public" if engine.dialect.name == "postgresql" else None
    preparer = engine.dialect.identifier_preparer
    table_names = sorted(inspector.get_table_names(schema=schema))
    tables: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    with engine.connect() as connection:
        for table_name in table_names:
            qualified = preparer.quote(table_name)
            if schema:
                qualified = f"{preparer.quote_schema(schema)}.{qualified}"
            rows = connection.execute(text(f"SELECT * FROM {qualified}")).mappings().all()
            counts[table_name] = len(rows)
            tables.append(
                {
                    "name": table_name,
                    "columns": [column["name"] for column in inspector.get_columns(table_name, schema=schema)],
                    "primary_key": inspector.get_pk_constraint(table_name, schema=schema).get("constrained_columns", []),
                    "foreign_keys": inspector.get_foreign_keys(table_name, schema=schema),
                    "rows": [{key: encode_value(value) for key, value in row.items()} for row in rows],
                }
            )

    payload = {
        "format": "verum-portable-backup",
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "database_dialect": engine.dialect.name,
        "table_counts": counts,
        "tables": tables,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    temporary.replace(output)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(f"{output.suffix}.sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")

    with gzip.open(output, "rt", encoding="utf-8") as stream:
        verified = json.load(stream)
    verified_counts = {table["name"]: len(table["rows"]) for table in verified["tables"]}
    if verified_counts != counts:
        raise RuntimeError("Backup verification failed: table counts do not match")
    return counts, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    counts, digest = create_backup(database_url, args.output.resolve())
    print(f"Backup verified: {len(counts)} tables, {sum(counts.values())} rows, SHA-256 {digest}")


if __name__ == "__main__":
    main()
