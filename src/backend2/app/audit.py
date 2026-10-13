import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import AuditLog, User

GENESIS = "0" * 64


def _digest(prev: str, row: AuditLog) -> str:
    payload = json.dumps(
        [
            row.ts.isoformat(),
            row.actor_id,
            row.actor_role,
            row.action,
            row.entity,
            row.entity_id,
            row.before,
            row.after,
            row.ip,
        ],
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256((prev + payload).encode()).hexdigest()


def log(
    db: Session,
    user: User | None,
    action: str,
    entity: str | None = None,
    entity_id=None,
    before=None,
    after=None,
    ip: str | None = None,
) -> None:
    """Adds to the caller's transaction, so the audit row commits atomically with the change."""
    last = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    prev = last.row_hash if last else GENESIS
    row = AuditLog(
        ts=utcnow(),
        actor_id=user.id if user else None,
        actor_role=user.role.value if user else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
        ip=ip,
        prev_hash=prev,
        row_hash="",
    )
    row.row_hash = _digest(prev, row)
    db.add(row)
    return row


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    for row in db.scalars(select(AuditLog).order_by(AuditLog.id)):
        if row.prev_hash != prev or row.row_hash != _digest(prev, row):
            return {"ok": False, "first_bad_id": row.id}
        prev = row.row_hash
    return {"ok": True, "first_bad_id": None}
