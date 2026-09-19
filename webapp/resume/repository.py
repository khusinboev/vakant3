"""All SQL used by the resume feature."""

import json
import time
from typing import Any

from webapp.resume.normalize import default_profile, normalize_color, normalize_profile_from_payload
from webapp.resume.schemas import ResumeProfileData, ResumeProfileResponse


async def load_resume_row(db, user_id: int):
    cursor = await db.execute(
        "SELECT profile_json, selected_template, updated_at FROM resume_profiles WHERE user_id = ?",
        (int(user_id),),
    )
    return await cursor.fetchone()


def load_profile_for_generation(row, first_name_fallback: str, template_id: str) -> tuple[ResumeProfileData, str]:
    """Return ``(profile, accent_hex)`` from a DB row; defaults when the row is missing."""
    if not row:
        return default_profile(first_name_fallback), normalize_color(None, template_id)
    try:
        raw_payload = json.loads(str(row["profile_json"] or "{}"))
    except Exception:
        raw_payload = {}
    profile = normalize_profile_from_payload(raw_payload, first_name_fallback)
    accent_hex = normalize_color(
        raw_payload.get("accent_color") if isinstance(raw_payload, dict) else None,
        template_id,
    )
    return profile, accent_hex


async def save_profile(db, user_id: int, profile_json: str, template_id: str, now: int) -> None:
    await db.execute(
        """
        INSERT INTO resume_profiles (user_id, profile_json, selected_template, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            profile_json = excluded.profile_json,
            selected_template = excluded.selected_template,
            updated_at = excluded.updated_at
        """,
        (int(user_id), profile_json, template_id, now),
    )


async def get_idempotent_response(db, user_id: int, action: str, key: str) -> ResumeProfileResponse | None:
    cursor = await db.execute(
        """
        SELECT response_json FROM resume_idempotency
        WHERE idempotency_key = ? AND user_id = ? AND action = ?
        """,
        (key, int(user_id), action),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    try:
        payload = json.loads(str(row["response_json"] or "{}"))
        return ResumeProfileResponse(**payload)
    except Exception:
        return None


async def save_idempotent_response(
    db, user_id: int, action: str, key: str, response_obj: ResumeProfileResponse
) -> None:
    response_dict: dict[str, Any] = response_obj.model_dump()
    # Strip the base64 photo: it is already stored in resume_profiles and would
    # otherwise add 100 KB+ to every idempotency row.
    profile_dict = response_dict.get("profile") or {}
    if isinstance(profile_dict.get("photo_url"), str) and profile_dict["photo_url"].startswith("data:"):
        profile_dict["photo_url"] = ""
    await db.execute(
        """
        INSERT OR REPLACE INTO resume_idempotency (idempotency_key, user_id, action, response_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (key, int(user_id), action, json.dumps(response_dict, ensure_ascii=False), int(time.time())),
    )


async def create_export_row(db, user_id: int, fmt: str, template_id: str, status: str = "pending") -> int:
    now = int(time.time())
    cursor = await db.execute(
        """
        INSERT INTO resume_exports (user_id, fmt, template_id, status, error_text, created_at, completed_at)
        VALUES (?, ?, ?, ?, NULL, ?, NULL)
        """,
        (int(user_id), fmt, template_id, status, now),
    )
    return int(cursor.lastrowid)


async def complete_export_row(db, export_id: int, status: str, error_text: str | None = None) -> None:
    await db.execute(
        """
        UPDATE resume_exports
        SET status = ?, error_text = ?, completed_at = ?
        WHERE id = ?
        """,
        (status, error_text, int(time.time()), int(export_id)),
    )


async def insert_event(db, user_id: int, event_name: str, step: str | None, meta_json: str | None) -> None:
    await db.execute(
        """
        INSERT INTO resume_events (user_id, event_name, step, meta_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (int(user_id), event_name, step, meta_json, int(time.time())),
    )
