"""Reusable live-data dashboard, feedback and workflow components."""
import flet as ft
from app.core.design import DESIGN, RADIUS, TYPOGRAPHY, STATUS_TONES, attendance_tone, ATTENDANCE_THRESHOLD
from app.components.ui import surface_card, section_header, status_badge, empty_state


def action_button(label, handler, *, icon=None, kind="primary", loading=False, disabled=False, tokens=None):
    cls = {"primary": ft.FilledButton, "secondary": ft.OutlinedButton, "text": ft.TextButton,
           "danger": ft.FilledButton}[kind]
    return cls("Working…" if loading else label, icon=icon, on_click=handler,
               disabled=disabled or loading or handler is None, height=DESIGN.touch_height,
               style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS["medium"]),
                                    bgcolor=tokens["danger"] if kind == "danger" and tokens else None))


def dashboard_section(title, content, tokens, subtitle=None, *, col=12, key=None, action=None):
    return surface_card(ft.Column([
        ft.Row([ft.Column([section_header(title, tokens, subtitle)], expand=True),
                *([action] if action else [])], spacing=8), content,
    ], spacing=20), tokens, padding=24, col=col, key=key)


def quick_action(label, icon, handler, tokens, *, tone="primary", col=6):
    return ft.Container(ft.Column([
        ft.Container(ft.Icon(icon, color=tokens[tone], size=22), bgcolor=tokens[f"{tone}_soft"],
                     padding=12, border_radius=RADIUS["medium"]),
        ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
    ], spacing=12), padding=16, bgcolor=tokens["surface_secondary"], border_radius=RADIUS["large"],
        border=ft.Border.all(1, tokens["border"]), col=col, on_click=handler,
        disabled=handler is None, ink=True, tooltip=label)


def identity_avatar(name, tokens, radius=22):
    initials = "".join(word[0] for word in str(name or "?").split()[:2]).upper()
    return ft.CircleAvatar(content=ft.Text(initials, size=14, weight=ft.FontWeight.W_600),
                           radius=radius, bgcolor=tokens["primary_soft"], color=tokens["primary"])


def workflow_status(status, tokens):
    return status_badge(str(status).replace("_", " ").title(), tokens,
                        STATUS_TONES.get(str(status).casefold(), "info"))


def attendance_hero(summary, tokens, threshold=ATTENDANCE_THRESHOLD, *, key="student-overall-attendance"):
    eligible = sum(summary.get(k, 0) for k in ("present", "late", "absent"))
    if not eligible:
        return surface_card(empty_state("No attendance yet", "Your attendance appears after eligible classes are finalized.",
                                        ft.Icons.FACT_CHECK_OUTLINED, tokens), tokens, key=key)
    percentage = float(summary.get("attendancePercentage", 0))
    tone = attendance_tone(percentage, threshold)
    ring = ft.Stack([
        ft.ProgressRing(value=max(0, min(1, percentage / 100)), width=112, height=112, stroke_width=9,
                        color=tokens["on_accent"], bgcolor=tokens["secondary"],
                        semantics_label="Overall attendance", semantics_value=percentage),
        ft.Container(ft.Text(f"{percentage:g}%", size=26, weight=ft.FontWeight.BOLD, color=tokens["on_accent"]),
                     width=112, height=112, alignment=ft.Alignment.CENTER),
    ], width=112, height=112)
    return ft.Container(ft.Column([
        ft.Row([ft.Column([
            ft.Text("OVERALL ATTENDANCE", size=11, weight=ft.FontWeight.W_600, color=tokens["on_accent"]),
            ft.Text("Every class counts.", size=22, weight=ft.FontWeight.BOLD, color=tokens["on_accent"]),
            status_badge("On track" if tone == "success" else "Needs attention", tokens, tone),
        ], expand=True, spacing=12), ring], spacing=12),
        ft.Divider(color=tokens["secondary"], height=1),
        ft.Row([ft.Column([ft.Text(str(summary.get("present", 0) + summary.get("late", 0)), size=22,
                                   color=tokens["on_accent"], weight=ft.FontWeight.BOLD),
                          ft.Text("Classes attended", size=12, color=tokens["on_accent"])], expand=True),
                ft.Column([ft.Text(str(eligible), size=22, weight=ft.FontWeight.BOLD, color=tokens["on_accent"]),
                           ft.Text("Eligible classes", size=12, color=tokens["on_accent"])], expand=True)], spacing=16),
        ft.Text(f"Minimum {threshold:g}% · Excused classes excluded", size=11, color=tokens["on_accent"]),
    ], spacing=20), padding=24, border_radius=RADIUS["xlarge"],
        gradient=ft.LinearGradient(colors=[tokens["primary"], tokens["secondary"]] if tokens["mode"] == "light" else [tokens["surface_accent"], tokens["secondary_soft"]]), key=key)


def notification_item(item, tokens, on_read=None):
    unread = not item.get("read_at")
    return ft.Container(ft.Row([
        ft.Container(ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=tokens["primary"], size=20),
                     padding=12, bgcolor=tokens["primary_soft"], border_radius=12),
        ft.Column([
            ft.Text(item.get("title") or "Notification", weight=ft.FontWeight.W_600,
                    color=tokens["text_primary"]),
            ft.Text(item.get("message") or "", size=13, color=tokens["text_secondary"]),
            ft.Text(str(item.get("created_at") or "")[:19].replace("T", " · "), size=11, color=tokens["text_secondary"]),
        ], expand=True, spacing=6),
        *([ft.IconButton(ft.Icons.DONE, tooltip="Mark notification read",
                        on_click=lambda _: on_read(item.get("_id")))] if unread and on_read else []),
        *([ft.Icon(ft.Icons.CIRCLE, size=8, color=tokens["primary"])] if unread else []),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START), padding=16,
        bgcolor=tokens["surface_accent"] if unread else tokens["surface_secondary"],
        border_radius=RADIUS["large"], key=f"notification-{item.get('_id', '')}")


def schedule_timeline(entries, tokens):
    if not entries:
        return empty_state("No classes today", "Your published timetable will appear here.", ft.Icons.EVENT_AVAILABLE, tokens)
    return ft.Column([ft.Container(ft.Row([
        ft.Column([ft.Text(str(x.get("startTime") or x.get("start_time") or "")[:5],
                           weight=ft.FontWeight.W_600, color=tokens["primary"]),
                   ft.Text(str(x.get("endTime") or x.get("end_time") or "")[:5], size=11,
                           color=tokens["text_secondary"])], width=48, spacing=4),
        ft.Container(width=3, height=60, bgcolor=tokens["secondary_soft"], border_radius=4),
        ft.Column([
            ft.Text((x.get("subject") or {}).get("name", "Scheduled subject"), weight=ft.FontWeight.W_600,
                    color=tokens["text_primary"]),
            ft.Text(" · ".join(str(v) for v in [(x.get("class") or x.get("class_division") or {}).get("name"),
                                               x.get("room"), (x.get("faculty") or {}).get("display_name") or
                                               (x.get("faculty") or {}).get("displayName")] if v),
                    size=12, color=tokens["text_secondary"]),
        ], expand=True, spacing=6),
    ], spacing=12), padding=ft.Padding.symmetric(vertical=8)) for x in entries], spacing=4)


def loading_card(message, tokens):
    return surface_card(ft.Row([ft.ProgressRing(width=24, height=24, stroke_width=3),
                                ft.Text(message, expand=True)], spacing=16), tokens, key="loading-state")


def error_card(message, tokens, retry=None):
    return surface_card(ft.Column([ft.Icon(ft.Icons.CLOUD_OFF_OUTLINED, color=tokens["danger"]),
                                  ft.Text(message, color=tokens["text_secondary"]),
                                  *([action_button("Try again", retry, kind="secondary")] if retry else [])],
                                 spacing=12), tokens, key="error-state")
