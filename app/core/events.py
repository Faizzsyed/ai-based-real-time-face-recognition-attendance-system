"""Async-safe reusable Flet callback adapters."""
from __future__ import annotations
import inspect,logging
from collections.abc import Callable
from app.core.logging import log_ui_event
async def invoke_callback(callback:Callable,event,*,action="event"):
    try:
        result=callback(event)
        if inspect.isawaitable(result):return await result
        return result
    except Exception:
        logging.getLogger("UI").exception("event=%s callback failed",action);raise
def event_handler(callback:Callable,*,action="event",before:Callable|None=None):
    async def wrapped(event):
        if before and not before():return None
        log_ui_event(action);return await invoke_callback(callback,event,action=action)
    return wrapped
