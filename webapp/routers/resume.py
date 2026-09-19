"""Thin re-export: the resume feature lives in the webapp.resume package."""

from webapp.resume.router import router

__all__ = ["router"]
