"""AttendAI Design System V2: tokens, breakpoints and responsive behavior."""
from dataclasses import dataclass
import flet as ft


@dataclass(frozen=True)
class Layout:
    phone: int = 600
    tablet: int = 768
    desktop: int = 1024
    wide: int = 1440
    sidebar_width: int = 248
    rail_width: int = 80
    page_padding: int = 24
    section_gap: int = 24
    card_radius: int = 20
    field_radius: int = 12
    touch_height: int = 48
    dialog_max_width: int = 760
    roster_view_height: int = 480


LIGHT = {
    "mode": "light",
    "background": "#F3F7FC",
    "surface": "#FFFFFF",
    "surface_secondary": "#F8FAFC",
    "surface_accent": "#EEF4FF",
    "border": "#E2E8F0",
    "text_primary": "#14213D",
    "text_secondary": "#64748B",
    "primary": "#2563EB",
    "primary_soft": "#DBEAFE",
    "secondary": "#0891A1",
    "secondary_soft": "#DFF7F6",
    "success": "#059669",
    "success_soft": "#D1FAE5",
    "warning": "#D97706",
    "warning_soft": "#FEF3C7",
    "danger": "#DC2626",
    "danger_soft": "#FEE2E2",
    "shadow": "#0C203208",
    "on_accent": "#FFFFFF",
}

DARK = {
    "mode": "dark",
    "background": "#0F172A",
    "surface": "#172033",
    "surface_secondary": "#1E293B",
    "surface_accent": "#172554",
    "border": "#334155",
    "text_primary": "#F8FAFC",
    "text_secondary": "#A8B3C7",
    "primary": "#60A5FA",
    "primary_soft": "#1E3A5F",
    "secondary": "#55D6D2",
    "secondary_soft": "#173F47",
    "success": "#34D399",
    "success_soft": "#123D35",
    "warning": "#FBBF24",
    "warning_soft": "#493614",
    "danger": "#F87171",
    "danger_soft": "#4A2025",
    "shadow": "#00000033",
    "on_accent": "#FFFFFF",
}

# Compatibility aliases for the existing API-status boundary.
LIGHT["text"] = LIGHT["text_primary"]
LIGHT["muted"] = LIGHT["text_secondary"]
DARK["text"] = DARK["text_primary"]
DARK["muted"] = DARK["text_secondary"]


for palette in (LIGHT, DARK):
    palette["info"] = palette["primary"]
    palette["info_soft"] = palette["primary_soft"]


DESIGN = Layout()
SPACING = (4, 8, 12, 16, 20, 24, 32, 40)
RADIUS = {"small": 8, "medium": 12, "large": 20, "xlarge": 28}
TYPOGRAPHY = {"display": 40, "page_title": 28, "section_title": 18,
              "body": 14, "caption": 12, "metric": 32}
SHADOWS = {"card": (16, 2), "dialog": (32, 12), "floating": (24, 6)}
ATTENDANCE_THRESHOLD = 75
ATTENDANCE_CRITICAL = 60
STATUS_TONES = {"present": "success", "approved": "success", "active": "success",
                "absent": "danger", "rejected": "danger", "late": "warning",
                "pending": "warning", "draft": "warning", "unmarked": "info",
                "excused": "secondary", "cancelled": "info", "inactive": "info"}
CAMERA = {"background": "#091827", "surface": "#132638", "border": "#304B5E",
          "text": "#DDEBF4", "muted": "#9DB4C6", "guide": "#64D6DA",
          "success": "#47D7AE", "danger": "#FB9090", "active": "#75B9FF"}


def layout_band(width):
    return "phone" if width < DESIGN.phone else "tablet" if width < DESIGN.desktop else "desktop"


def attendance_tone(percentage, threshold=ATTENDANCE_THRESHOLD):
    return "success" if percentage >= threshold else "danger" if percentage < min(ATTENDANCE_CRITICAL, threshold) else "warning"


def walk_controls(control):
    if not isinstance(control, ft.Control):
        return
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from walk_controls(content)
    for attribute in ("controls", "actions", "items"):
        for child in getattr(control, attribute, []) or []:
            yield from walk_controls(child)


def table_cards(table, tokens):
    """Render real table cells/actions as labeled cards on narrow screens."""
    cards = []
    for row in table.rows:
        fields = []
        for column, cell in zip(table.columns, row.cells):
            label = column.label.value if isinstance(column.label, ft.Text) else "Details"
            fields.append(ft.Column([ft.Text(str(label), size=11, color=tokens["text_secondary"]), cell.content], spacing=4))
        cards.append(ft.Container(ft.Column(fields, spacing=12), padding=16, border_radius=16,
                                  bgcolor=tokens["surface_secondary"], border=ft.Border.all(1, tokens["border"])))
    return ft.Column(cards, spacing=12, key="mobile-report-cards")


def adapt_view(control, width, tokens):
    """Apply shared sizing; preserve event handlers and actual data controls."""
    compact = width < DESIGN.phone
    if compact and isinstance(control, ft.ListTile):
        fields = [x for x in (control.leading, control.title, control.subtitle) if isinstance(x, ft.Control)]
        if control.trailing:
            fields.append(ft.Row([control.trailing], wrap=True))
        return ft.Container(adapt_view(ft.Column(fields, spacing=10), width, tokens), padding=12,
                            on_click=control.on_click, border_radius=DESIGN.field_radius,
                            bgcolor=tokens["surface_secondary"])
    if compact and isinstance(control, ft.Row) and any(isinstance(x, ft.DataTable) for x in control.controls):
        return ft.Column([table_cards(x, tokens) if isinstance(x, ft.DataTable) else x for x in control.controls], spacing=12)
    if isinstance(control, ft.Container) and control.expand and control.padding == 24:
        control.padding = 16 if compact else 24
    if isinstance(control, (ft.FilledButton, ft.OutlinedButton, ft.TextButton)):
        control.style = control.style or ft.ButtonStyle()
        control.style.padding = ft.Padding.symmetric(horizontal=16, vertical=12)
        control.style.shape = ft.RoundedRectangleBorder(radius=12)
        control.height=control.height or DESIGN.touch_height
        if compact and isinstance(control, (ft.FilledButton, ft.OutlinedButton)):
            control.width = None
    if isinstance(control, (ft.TextField, ft.Dropdown)):
        control.border_radius = DESIGN.field_radius
        control.border_color = tokens["border"]
        control.focused_border_color = tokens["primary"]
        control.filled = True
        control.fill_color = tokens["surface_secondary"]
        control.content_padding = ft.Padding.symmetric(horizontal=16, vertical=16)
        if compact:
            control.width = None
        if isinstance(control, ft.TextField):
            control.scroll_padding = 80
            control.error_max_lines = 3
        if isinstance(control, ft.Dropdown):
            control.enable_search = True
    if compact and isinstance(control, ft.Text) and control.size and 24 < control.size < TYPOGRAPHY["metric"]:
        control.size = 24
    if compact and isinstance(control, ft.Row) and control.scroll is None and all(not child.expand for child in control.controls):
        control.wrap = True
    if compact and isinstance(control, ft.Row):
        # Constrained fields/actions must stack, rather than overflow inside a Row.
        if any(isinstance(child, (ft.TextField, ft.Dropdown)) for child in control.controls):
            return adapt_view(ft.Column(control.controls, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), width, tokens)
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        control.content = adapt_view(content, width, tokens)
    if hasattr(control, "controls"):
        control.controls = [adapt_view(child, width, tokens) for child in control.controls]
    return control


def prepare_dialog(dialog, page, tokens):
    width = max(240, min(DESIGN.dialog_max_width, (page.width or 390) - 64))
    media = getattr(page, "media", None)
    keyboard = getattr(getattr(media, "view_insets", None), "bottom", 0) or 0
    height = max(120, min(680, (getattr(page, "height", None) or 800) - keyboard - 180))
    dialog.inset_padding = 12
    dialog.content_padding = 16
    dialog.actions_padding = 12
    dialog.shape = ft.RoundedRectangleBorder(radius=20)
    dialog.scrollable = True
    content = dialog.content
    if content:
        if isinstance(content, ft.Container):
            content.width = width
            content.height = None
        progress = ft.ProgressBar(visible=False, key="form-progress")
        feedback = ft.Text("", visible=False, color=tokens["danger"], key="form-feedback")
        # A bounded scrolling body keeps fields reachable above the keyboard.
        adapted = adapt_view(content, page.width or 390, tokens)
        # A single scrolling body lets focus scroll every field and embedded action.
        for child in walk_controls(adapted):
            if isinstance(child, ft.Column):child.scroll = None;child.expand = None
        dialog.content = ft.Container(ft.Column([progress, feedback, adapted],
                                                scroll=ft.ScrollMode.AUTO, spacing=12, tight=True), width=width,
                                      height=height if isinstance(content, ft.Container) else None)
    return dialog


def person_card(name, identity, relation, badge, actions, tokens):
    return ft.Container(ft.Column([
        ft.Row([ft.CircleAvatar(content=ft.Text((name or "?")[:1].upper()), radius=21,
                               bgcolor=tokens["primary_soft"], color=tokens["primary"]),
                ft.Column([ft.Text(name, weight=ft.FontWeight.W_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                           ft.Text(identity, size=12, color=tokens["text_secondary"], max_lines=2,
                                   overflow=ft.TextOverflow.ELLIPSIS)], expand=True, spacing=4), actions], spacing=12),
        ft.Row([badge, ft.Text(relation, size=12, color=tokens["text_secondary"], expand=True)], spacing=10),
    ], spacing=12), padding=20, bgcolor=tokens["surface"], border_radius=DESIGN.card_radius,
                        border=ft.Border.all(1, tokens["border"]))
