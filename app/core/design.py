"""Shared, mobile-first dimensions and presentation helpers for the live app."""
from dataclasses import dataclass
import flet as ft


@dataclass(frozen=True)
class Layout:
    phone: int = 600
    desktop: int = 900
    page_padding: int = 16
    section_gap: int = 16
    card_radius: int = 16
    field_radius: int = 12
    touch_height: int = 48
    dialog_max_width: int = 760


DESIGN = Layout()


def walk_controls(control):
    if not isinstance(control, ft.Control):
        return
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from walk_controls(content)
    for attribute in ("controls", "actions"):
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
        fields = [x for x in (control.title, control.subtitle) if isinstance(x, ft.Control)]
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
    if isinstance(control, (ft.TextField, ft.Dropdown)):
        control.border_radius = DESIGN.field_radius
        control.border_color = tokens["border"]
        control.focused_border_color = tokens["primary"]
        if isinstance(control, ft.TextField):
            control.scroll_padding = 80
            control.error_max_lines = 3
        if isinstance(control, ft.Dropdown):
            control.enable_search = True
    if compact and isinstance(control, ft.Text) and control.size and control.size > 24:
        control.size = 24
    if compact and isinstance(control, ft.Row) and all(not child.expand for child in control.controls):
        control.wrap = True
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
    ], spacing=12), padding=16, bgcolor=tokens["surface"], border_radius=DESIGN.card_radius,
                        border=ft.Border.all(1, tokens["border"]))
