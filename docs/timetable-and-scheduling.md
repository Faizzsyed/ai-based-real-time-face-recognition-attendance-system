# Timetable and lecture scheduling

Phase 7 stores recurring weekly teaching schedules in `timetable_entries`. It does not create thousands of future lecture documents:

`FacultyAssignment → TimetableEntry → computed lecture instance → AttendanceSession (Phase 8)`

Each entry derives Institution, Academic Year, Faculty, ClassDivision, and Subject ownership from one active FacultyAssignment. Clients cannot override those ownership fields. The service also verifies that the active Academic Year, Subject Program/Semester, and Class hierarchy still agree.

## Conflicts

Active entries conflict when their weekday, effective date ranges, and half-open time windows overlap and they share a Faculty member, ClassDivision, or non-empty normalized room. Adjacent entries such as 09:00–10:00 and 10:00–11:00 are accepted. Creation, editing, and reactivation all run the same conflict check and return `TIMETABLE_CONFLICT` with bounded structured `details.conflicts` entry/time/type information.

Room conflict checking is enabled whenever a room is supplied. Empty rooms do not reserve a shared room resource. Deactivation changes status without deleting the recurring entry.

## Timezone handling

The Institution's IANA timezone (for example `Asia/Kolkata`) is authoritative. Weekday and `HH:MM` values represent local wall-clock teaching time. Effective dates are stored as UTC-midnight BSON datetimes but retain local-calendar date semantics; they are never interpreted using the server's local timezone.

Today, Week, Next Lecture, and Upcoming Classes are computed by combining the local calendar date with each wall-clock time using `zoneinfo.ZoneInfo`. Returned lecture instances include the Institution timezone and one of `upcoming`, `active`, or `completed-window`. Computed instances are not persisted.

## Access

- Admin routes manage Institution-scoped entries with pagination and academic filters.
- `/api/v1/faculty/timetable` resolves the authenticated Faculty record and returns only that Faculty member's active schedule.
- `/api/v1/student/timetable` resolves the authenticated Student's current enrollment and returns only that ClassDivision's active schedule.

The Flet Admin workspace provides weekly-grid and list views plus accessible add/edit/deactivate actions. Real Faculty and Student dashboards use these APIs and never fall back to preview schedule values. Take Attendance remains disabled until Phase 8.
