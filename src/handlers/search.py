# search.py — bot-side search/filter/saves handlers removed.
# All search, filter and saves functionality is handled by the WebApp.
from aiogram import Router

router = Router()


def normalize_uid(uid: str) -> str:
	"""Normalize legacy vacancy UID values to current osonish-prefixed format."""
	value = str(uid or "").strip()
	if value.startswith("osonish_"):
		return value
	if value.startswith("ishapi_"):
		value = value[len("ishapi_") :]
	if value.isdigit():
		return f"osonish_{value}"
	return value
