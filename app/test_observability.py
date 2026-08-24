"""Flet async callback execution, exception visibility, and UI redaction."""
import asyncio,logging
import flet as ft
from app.core.events import event_handler,invoke_callback
from app.core.logging import sanitize
from app.core.logging import log_ui_event
from app.core.config import get_settings
from app.core.theme import tokens_for_mode
from app.screens.admin.face_enrollment import build_face_enrollment_dialog

def walk(control):
    yield control
    for child in getattr(control,"controls",[]) or []:yield from walk(child)
    content=getattr(control,"content",None)
    if content:yield from walk(content)
def test_sync_and_async_callbacks_execute():
    called=[]
    def sync(event):called.append(("sync",event))
    async def async_callback(event):await asyncio.sleep(0);called.append(("async",event))
    asyncio.run(invoke_callback(sync,"a"));asyncio.run(invoke_callback(async_callback,"b"));assert called==[("sync","a"),("async","b")]
def test_async_callback_exception_is_logged(caplog):
    caplog.set_level(logging.ERROR)
    async def broken(_):raise RuntimeError("safe failure")
    try:asyncio.run(event_handler(broken,action="test async")("event"))
    except RuntimeError:pass
    assert "event=test async callback failed" in caplog.text
def test_face_enrollment_select_frames_callback_is_awaited():
    called=[]
    async def choose(event):await asyncio.sleep(0);called.append(event)
    dialog=build_face_enrollment_dialog({"display_name":"Test","face":{}},tokens_for_mode(ft.ThemeMode.LIGHT),choose,lambda _:None,lambda _:None,lambda _:None)
    controls=list(walk(dialog));checkbox=next(x for x in controls if isinstance(x,ft.Checkbox));checkbox.value=True;button=next(x for x in controls if isinstance(x,ft.OutlinedButton) and x.content=="Select 3 camera frames")
    result=button.on_click("clicked");assert hasattr(result,"__await__");asyncio.run(result);assert called==["clicked"]
def test_ui_redaction_and_bytes_are_safe():
    text=str(sanitize({"password":"bad-value","access_token":"token-value","image_bytes":b"raw-value"}));assert "bad-value" not in text and "token-value" not in text and "raw-value" not in text
def test_ui_logging_flag_disables_event_logs(caplog):
    caplog.set_level(logging.INFO);settings=get_settings();previous=settings.enable_ui_event_logging;settings.enable_ui_event_logging=False
    try:log_ui_event("must not appear")
    finally:settings.enable_ui_event_logging=previous
    assert "must not appear" not in caplog.text
