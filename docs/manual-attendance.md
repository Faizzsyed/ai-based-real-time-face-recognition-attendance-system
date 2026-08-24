# Manual Attendance Architecture

Phase 8 adds reliable, manual attendance without enabling face recognition. Faculty start a session from an owned, active timetable occurrence. The backend derives the Institution, Academic Year, teaching assignment, Faculty, Class, Subject, and scheduled times; clients cannot override that ownership.

## Persistence and concurrency

- `attendance_sessions` stores one session per Institution, timetable entry, and lecture date. The unique index makes retrying Start Attendance safe; the service returns the Faculty member's existing session.
- `attendance_records` stores one roster snapshot row per session and Student. Its unique `(session_id, student_id)` index and upsert-based roster initialization avoid duplicate records.
- Roster initialization includes active Student profiles with an active enrollment in the lecture's Class and Academic Year whose enrollment dates cover the lecture date. Transferred, inactive, ended, and cross-Institution records are excluded. Existing records keep their enrollment ID, so later transfers do not rewrite attendance history.

## Lifecycle and permissions

`draft` and `reopened` sessions are Faculty-editable. Every roster record must be `present`, `absent`, `late`, or `excused` before submission. `submitted` and `locked` sessions cannot be edited by Faculty. Admin may reopen submitted/locked sessions, lock submitted/reopened sessions, and perform an explicit correction only while the session is not locked. Administrative reasons and status transitions are stored with actor and timestamp for future audit-log publication.

All Faculty mutations resolve the authenticated Faculty profile and verify session ownership. Admin access is scoped to the authenticated Institution. Student endpoints resolve the authenticated Student profile and never accept a Student ID.

## Percentage formula

Late counts as attended. Excused is reported as a raw count but excluded from the denominator:

`attendance percentage = (present + late) / (present + late + absent) × 100`

When the denominator is zero, the percentage is `0.0`.

## APIs

- Faculty: create/list/read sessions, save a draft, and submit under `/api/v1/faculty/attendance/sessions`.
- Admin: list/read sessions, explicitly edit, reopen, and lock under `/api/v1/admin/attendance/sessions`.
- Student: `GET /api/v1/student/attendance/summary`, `GET /api/v1/student/attendance/history`, and `GET /api/v1/student/attendance/sessions/{id}`.

Face recognition remains outside this phase. Manual records use `source: manual`; `future_face_recognition` is reserved for a later verified workflow.
