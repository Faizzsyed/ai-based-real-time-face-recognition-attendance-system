# AttendAI Easy Setup

EASY SETUP: READY FOR MANUAL TEST

Implemented on the existing `main` working tree. All pre-existing uncommitted changes were preserved. No database reset, reseed, direct database writes from Flet, commit, push, cloud deployment, or biometric pipeline change was performed.

## What changed

The Admin dashboard has a permanent **Start Easy Setup** card. The sidebar also contains **Easy Setup**. The optional Academic Setup checklist still shows seven academic completion checks and manual Configure links; hiding that checklist leaves the main entry available.

The ten-step wizard uses the existing authenticated API client and backend services. Its saved records are the source of progress. A sole valid option is selected automatically; multiple options require a choice. Changing a parent revalidates the full dependency chain. Reopening setup loads saved records rather than duplicating them. Unsaved drafts stay in memory only, and successful account creation discards the temporary password draft.

| Step | Guided behavior |
| --- | --- |
| Institution | Reuses the authenticated Admin's institution; name, short name, city, and address can be edited. Code and institution status follow the existing backend's immutable-field policy. |
| Academic Year | Suggests June 1 to May 31. October 2026 and March 2027 both produce `2026-27`. Prefers an existing active current year. An active noncurrent year can be explicitly made current. |
| Department | Name and prominent short code; optional description; active by default. |
| Program | Editable B.Tech/code suggestions from the department, 3/4/5-year choices or custom duration, and editable semester count. Four years suggests eight semesters. The existing API requires a code, so one is generated. |
| Semester | Default action creates only Semester 1. The alternative creates every missing semester for the selected program and year. Existing numbers are reused, and partial failures can be retried. |
| Class / Division | Suggests `FY ECS - A` from department code, semester number, and division. Capacity defaults to 60 and remains optional. |
| Subject | One subject is sufficient; type defaults to Theory. Existing subjects can be selected, and Add another subject is available when a saved subject is selected. |
| Faculty | Full name, employee ID, email, username, temporary password. Suggests the first unused FAC number and a username from the name. Department is inherited. |
| Student | Full name, admission number, roll number, email, username, temporary password, and enrollment date. The selected academic placement is shown clearly. |
| Teaching Setup | Reuses or creates a matching faculty assignment, then carries that assignment into a timetable entry with day, time, and effective dates. An assignment saved before a timetable failure is reused on retry. |

The final summary shows the selected records and lecture, with **Go to Dashboard** and **Login as Faculty**. The latter signs out the Admin and opens login; it never signs into another account automatically.

## Serialization repair

The Admin timetable view switch and Faculty attendance mode switch passed Python sets to `SegmentedButton.selected`. Flet 0.86.5 expects `list[str]`; its MessagePack transport could not serialize those sets. Both properties now receive lists. Regression tests serialize the actual control trees with Flet's transport encoder, covering both affected screens and every wizard step.

## Date/time and manual forms

Shared date fields use Flet DatePicker calendars with readable date hints and ISO API values. Time fields use Flet TimePicker, readable AM/PM hints, and `HH:MM` API values. These are used in the wizard and the manual Academic Year, Semester, Student enrollment, Faculty joining/assignment, and Timetable forms where applicable.

The manual Faculty, Student, Assignment, Timetable, and academic forms also select a sole valid reference. Student dependent choices clear and refill after parent changes. Missing references are disabled with guidance, and the Student/Faculty create forms offer a Return to Easy Setup action when prerequisites are absent.

All existing advanced screens remain available: Institution, Academic Years, Departments, Programs, Semesters, Classes & Divisions, Subjects, Faculty, Students, and Timetable. Password hashing, RBAC, institution isolation, uniqueness, scheduling conflict checks, and existing audit behavior remain in the backend.

## Files changed for this task

New:

- `app/services/setup_defaults.py`
- `app/services/easy_setup.py`
- `app/screens/admin/easy_setup.py`
- `app/test_easy_setup.py`
- `backend/tests/test_easy_setup_contracts.py`
- `docs/easy-setup.md`

Updated while preserving existing edits:

- `app/components/forms.py` (already untracked when this task began)
- `app/components/navigation.py`
- `app/main.py`
- `app/screens/admin/academic.py`
- `app/screens/admin/dashboard.py`
- `app/screens/admin/faculty.py`
- `app/screens/admin/students.py`
- `app/screens/admin/timetable.py`
- `app/screens/faculty/attendance.py` (only the selected-list compatibility fix)

## Validation

- Backend: **216 passed**, up from the recovered 213 baseline. Two existing dependency deprecation warnings remain.
- Frontend: **236 passed**, up from the recovered 194 baseline.
- `git diff --check`: passed.
- The full Admin UI callback flow completes using an isolated in-memory API fixture; reopening setup reuses its saved records.
- Backend contract tests send the generated academic payloads through real FastAPI routes and services backed by in-memory repositories. Faculty/Student writes are denied.
- Every wizard step and its completion view serialize at widths 360, 390, 430, 768, 1024, and 1366. These are construction/transport checks, not physical phone screenshots.
- The backend started on `0.0.0.0:8000`, connected to the existing development database, and returned HTTP 200 for health.
- The desktop Flet app launched. Its live Admin wizard was visually inspected with existing records loaded. No smoke-test records were saved to the development database by the agent. Full live-data completion and physical-phone layout remain manual checks.

## Exact manual test

1. Restart the desktop app to load all final source changes. Keep one backend running. If needed, start it with `powershell -ExecutionPolicy Bypass -File scripts/run_backend.ps1 -NoReload`; start the app with `.\.venv\Scripts\python.exe -m app.main`.
2. Sign in as Admin. Open Dashboard → Start Easy Setup, or the sidebar Easy Setup entry.
3. Institution: confirm the existing institution is selected and marked Done. Try Edit without creating a duplicate, then use Next.
4. Academic Year: reuse your current year. If creating a missing year in October 2026, verify `2026-27`, June 1 2026, and May 31 2027. Open a calendar, cancel or select an intended date, and try Use Suggested Academic Year. Use Save & Continue. For an existing active noncurrent year, use the explicit current-year action.
5. Department: reuse an existing department, or save the intended name and code (for example ECS). Program: verify editable B.Tech/code suggestions; choose four years and verify eight semesters.
6. Semester: choose Create only Semester 1 for now for a demo. Repeating this action must not create another Semester 1. Create all semesters only if you intend to add them to your real data.
7. Class: check the inherited year/program/semester and the suggested division A/name/capacity. Save only your intended class. Subject: create or reuse one subject.
8. Faculty: reuse your existing member where possible. For a new account, check the suggested ID and username and set a temporary password. Existing passwords must never appear.
9. Student: create or reuse an intended student. Verify all five academic placement values without selecting five sole-option dropdowns. Check the default enrollment date and calendar.
10. Teaching Setup: verify faculty, subject, and class once; choose Monday and the intended 10:00–11:00 slot with time pickers. Verify effective dates and save. A backend conflict must leave the wizard usable and preserve the already saved assignment for retry.
11. Verify Setup Complete and all summary values. Go to Dashboard and confirm academic checks. Reopen Easy Setup and confirm existing records are reused.
12. Use Login as Faculty only when ready to sign out of Admin; enter the faculty credentials yourself. Also verify Faculty and Student sessions cannot open Admin setup.
13. Test a narrow window and then a phone/LAN session: check scrolling, touch targets, calendar/time dialogs, and fields above the keyboard. Use the progress steps to change a parent and verify downstream selections are cleared or replaced by sole compatible options.

## Remaining complexity

Admins still supply real identity details and temporary passwords, choose among multiple legitimate structures, and resolve backend validation or timetable conflicts. Institution code/status remain governed by the existing Admin API. Subject types beyond the guided Theory default, detailed profile fields, imports, and more specialized scheduling remain available in advanced management. Wizard drafts are not persisted across process restarts; saved backend records are reused.
