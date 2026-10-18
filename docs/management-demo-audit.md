# AttendAI management audit for the October 20, 2026 demo

Audit date: October 17, 2026. Scope: the existing LAN Flet -> FastAPI -> MongoDB management system. Cloud work was stopped. No APK build, deployment, database connection, data migration, reseed, credential change, commit or push was performed in this audit. Face enrollment/recognition algorithms and endpoints were not changed.

## Evidence and interpretation

- Branch `main`, HEAD `9ecab63`. At entry: 24 modified tracked files and 9 untracked entries, including a directory entry. The tracked diff was 584 additions / 233 deletions. All pre-existing work was retained.
- Before this audit's edits: backend 199 passed (two dependency deprecation warnings); frontend 171 passed; `git diff --check` passed.
- Status below describes source wiring and automated checks, **not a completed live three-device/database rehearsal**. No Android screen was visually inspected on a physical device in this task.
- WORKING means the core management operation has frontend/API/service wiring and existing automated coverage. PARTIAL means useful functionality exists but a visible action, state, scope or completeness issue remains. BROKEN means an advertised operation cannot complete as wired. MISSING means no implementation for that advertised screen was found.
- Exact baseline caveat: three tests in `backend/tests/test_phase16_attendance_integrity.py` and `test_faculty_cross_tenant_attendance_session_rejected` in `test_phase16_rbac_isolation.py` contain only `pass`. Other Phase 8/12 tests provide real attendance/scope coverage, but those four passing tests add none.
- Source configuration inspected without exposing secrets: `APP_ENV=development`, `ENABLE_DEV_ACADEMIC_API=false`, `ENABLE_DEV_ROLE_PREVIEW=true`. Use real role logins for the demo; development previews explicitly contain static example schedules/figures.

## Screen -> API -> database map

Every path below has the common `/api/v1` prefix. Read operations are GET unless stated otherwise. Core dispatch is in `app/main.py:476` and `render_authenticated_shell`; navigation definitions are in `app/components/navigation.py`.

The common Splash screen opens Login without reading a collection. Login uses `POST /auth/login`; expired access tokens use `POST /auth/refresh`; logout uses `POST /auth/logout`; `/auth/me` exposes the authenticated safe user. These flows use `users` and `auth_sessions`, with JWTs held in the client's memory-only token storage. API status/server settings use `/health` through the configured HTTP client, not a frontend MongoDB connection.

### Admin

| Screen/module | Status after fixes | API wiring | Collections and remaining limits |
|---|---|---|---|
| Dashboard statistics | WORKING | `/admin/dashboard`, `/admin/academic/setup-status`; login also fetches `/admin/attendance/sessions` | `students`, `faculty`, `attendance_sessions`, `attendance_requests`, academic collections. Fixed wrong request collection and date type. Counts reflect active people and today's sessions, not an invented attendance percentage. Local server date is still used rather than institution timezone. |
| Institution | WORKING for existing institution | `/admin/academic/institution` GET/PATCH | `institutions`. Edits the logged-in Admin's institution; does not bootstrap an institution/Admin from scratch. |
| Academic Years | WORKING core CRUD/status | `/admin/academic/academic-years` GET/POST; `/{id}` GET/PATCH | `academic_years`; current-year uniqueness/date validation; active dependent semester/class checks. Deactivation through edit form. |
| Departments | WORKING core CRUD/status | `/admin/academic/departments` GET/POST; `/{id}` GET/PATCH | `departments`; scoped code uniqueness; active Program dependency checks. |
| Programs / courses | WORKING core CRUD/status | `/admin/academic/programs` GET/POST; `/{id}` GET/PATCH | `programs`; institution/department hierarchy and dependent semester/class/subject checks. |
| Semesters | WORKING core CRUD/status | `/admin/academic/semesters` GET/POST; `/{id}` GET/PATCH | `semesters`; year/program references and semester-number bounds. Search text is offered but semester search is not implemented by `AcademicService.list`. |
| Classes / divisions | WORKING core CRUD/status | `/admin/academic/classes` GET/POST; `/{id}` GET/PATCH | `class_divisions`; year/department/program/semester hierarchy, unique division. Deactivation does not check student enrollments, assignments or timetable dependencies. |
| Subjects | WORKING core CRUD/status | `/admin/academic/subjects` GET/POST; `/{id}` GET/PATCH | `subjects`; hierarchy/code validation. Deactivation does not check active teaching assignments/timetable. |
| Faculty management | PARTIAL | `/admin/faculty` GET/POST; `/{id}` GET/PATCH; `/{id}/status` PATCH; `/import/template`, `/import/preview` POST, `/import/confirm` POST | `faculty`, `users`, `departments`, `faculty_assignments`. List/profile/create/edit/account synchronization exist. UI fixes page=1/pageSize=20 without a pager. Status callback ignores failure response. Raw joined User exposure fixed in this audit. |
| Student management | PARTIAL | `/admin/students` GET/POST; `/{id}` GET/PATCH; `/{id}/status` PATCH; `/{id}/enrollments` POST; import template/preview/confirm | `students`, `users`, `student_academic_enrollments`, academic collections. Identity+login+enrollment creation and history exist. UI first 20 only; enrollment changes and advanced filters require raw IDs. Status errors ignored. Raw joined User exposure fixed. |
| Faculty assignments | PARTIAL | `GET/POST /admin/faculty/{id}/assignments`; `PATCH/DELETE /admin/faculty/{id}/assignments/{assignmentId}` | `faculty_assignments` plus year/class/subject references. UI supports view/create only; PATCH/soft-deactivate have no client methods or UI actions. Year -> class -> subject selection exists. |
| Timetable | PARTIAL | `/admin/timetable` GET/POST; `/{id}` PATCH; `/{id}/status` PATCH | `timetable_entries`, joined academic/faculty records. Conflict checks, edit/status and paging exist. Weekly grid renders only the current 20-entry page. Reference lists capped at 100. Status failures ignored by UI. |
| Attendance oversight | PARTIAL | `/admin/attendance/sessions`, `/{id}`; `/{id}/reopen` POST; `/{id}/lock` POST; `/{id}/records` PUT | `attendance_sessions`, `attendance_records`. UI inspects/reopens/locks; direct record edit is backend-only. UI supplies a fixed reason rather than collecting one; no action confirmation or explicit return-to-list button. List capped at 100. |
| Correction requests | PARTIAL | `/requests/attendance`, `/{id}`; `/{id}/approve` POST; `/{id}/reject` POST | `attendance_requests`, attendance records/sessions, `notifications`, `audit_events`. Approval/rejection UI exists; errors no longer erased by refresh. First 50 only, no queue filters/pager, no explicit success notice. Multi-document approval is not transactional. |
| Notifications | PARTIAL | `/notifications`, `/unread-count`; `/{id}/read` POST; `/read-all` POST | `notifications`; scoped by institution and recipient. Read/unread implemented. First 50 only; mark-read failures ignored; badge refreshes on login/inbox load rather than live updates. |
| Reports | PARTIAL | `/admin/reports/{overview,options,subjects,trend,departments}`, `/classes/{id}`, `/students/low-attendance`, `/students/{id}`, `/sessions/{id}`, `/exports/...` | Finalized attendance records/sessions plus academic/person reference collections. Overview/drill-down/formula exist. Export async wiring fixed. Filter/export scope inconsistencies and fixed export limits remain; see below. Department endpoint has no dedicated panel. |
| Audit logs | PARTIAL | `/audit`, `/audit/{id}` | `audit_events`; Admin/institution scoped, append-only through service. UI shows first 50, no detail/filter/pager. Persistence currently covers correction request actions/record correction, not academic/person CRUD or session submit/lock/reopen. Ordinary application logs are not audit entries. |
| Settings | MISSING | No dispatch/screen/API for this navigation item | Menu item is enabled but selecting it returns without changing the screen. |
| Face AI / Face Enrollment | OUT OF SCOPE | Existing face routes retained | Face AI menu dispatch is absent; no recognition/enrollment changes made. Dashboard now says face status was not checked rather than asserting it is unconfigured. |

Academic DELETE endpoints are intentionally absent; edit/status changes preserve history. Missing hard-delete actions are not defects for this audit.

### Faculty

| Screen/module | Status | API wiring | Persistence / exact gap |
|---|---|---|---|
| Dashboard | PARTIAL | `/faculty/profile`, `/faculty/timetable`, `/faculty/attendance/sessions` at login | `faculty`, `users`, assignments, timetable and sessions. Authenticated branch uses real data. Profile/schedule/session snapshot is not refreshed when returning to Dashboard. Schedule failures become an empty schedule without an explanatory error. |
| Assigned classes and subjects | PARTIAL | Assignments embedded in `/faculty/profile`; `/faculty/assignments` also exists | Active assignments are shown on dashboard. **My Classes navigation is a no-op** despite the available endpoint. No dedicated subject screen in faculty navigation. |
| Today's Lectures / Timetable | PARTIAL | `/faculty/timetable` | Both labels render the same full dashboard, using the login-time schedule. No dedicated schedule view/refresh. |
| Start attendance | WORKING core flow | POST `/faculty/attendance/sessions` | Validates owned active timetable entry, active assignment, weekday/effective dates; creates session and roster snapshot from active enrollments. Start is idempotent for the scheduled occurrence. UI offers today's lectures only, not arbitrary dates. |
| Manual marking | WORKING after fix | Local status edits, then draft PUT below | Present/absent/late/excused controls. Fixed zero-unmarked count that left Submit disabled after finishing roster. Full roster view rebuilds after each mark/search. |
| Save draft | WORKING | PUT `/faculty/attendance/sessions/{id}/draft` | Owned draft/reopened session only; membership validation and status/remark persistence. No session topic/notes editors; marks save only when explicitly saved/submitted. |
| Finalize attendance | WORKING after fix | POST `/faculty/attendance/sessions/{id}/submit` after draft PUT | Complete nonempty roster required; submitted/locked blocks ordinary Faculty edits. Fixed continuing to submit after a failed draft save. Confirmation and completion notice exist. |
| Attendance History | PARTIAL | `/faculty/attendance/sessions` and `/{id}` | Shares Take Attendance view; only first 50 sessions returned, recent submitted/locked section displays eight without open action. Continue exists for drafts. Existing selected session is not cleared by navigation, so no explicit return-to-list path. |
| Correction review | PARTIAL | `/requests/attendance`, `/{id}/approve`, `/{id}/reject` | Owning active Faculty/assignment checks exist; review errors retained after fix. Pagination, success feedback, concurrent approval/cancel consistency and service-level regression coverage remain. |
| Notifications | PARTIAL | Shared notification endpoints | Recipient/institution scope exists; same paging/feedback limits as Admin. |
| Reports | PARTIAL | `/faculty/reports/{overview,options,subjects}`, `/classes/{id}`, `/students/{id}`, `/sessions/{id}`, `/exports/classes/{id}.csv` | Historical session ownership scopes data. **Session detail offers CSV but `/faculty/reports/exports/sessions/{id}.csv` does not exist**, so that export still returns 404. Class export exists. |
| Profile / Settings | MISSING as dedicated screens | Profile data exists at `/faculty/profile`; Settings has no screen/API | Both navigation clicks are no-ops. Profile information is visible on the dashboard. |

### Student

| Screen/module | Status | API wiring | Persistence / exact gap |
|---|---|---|---|
| Dashboard | WORKING core read, partial schedule freshness | `/student/profile`, `/student/timetable`, `/student/attendance/summary`, `/student/attendance/history` | Own user/profile/current enrollment and finalized attendance. Returning to Dashboard now reloads attendance. Timetable remains a login snapshot; schedule errors are hidden as empty results. |
| Overall attendance / percentage | WORKING | `/student/attendance/summary` | `(present + late) / (present + late + absent) * 100`; excused excluded; submitted/locked sessions only. UI now refreshes correctly instead of fetching unused report data. Backend failure is no longer rendered as a fabricated zero attendance result. |
| Subject-wise attendance | PARTIAL | Same summary endpoint; richer `/student/reports/attendance` exists | Correct grouping/formula but the rendered attendance screen shows raw subject IDs, not names. Only subjects with attendance appear. Threshold is hardcoded to 75 in this surface rather than reading configurable report threshold. |
| Attendance history | PARTIAL | `/student/attendance/history`; own `/student/attendance/sessions/{id}` endpoint exists | Self records only. UI renders at most 20 with date/subject ID; no pager or session drill-down. Server history sorts by mark time, not necessarily lecture date. |
| Submit correction | WORKING core flow | POST `/requests/attendance` | Student ID is derived server-side; only own finalized session record, valid different requested status and reason accepted. Form is reached via Attendance -> Request Correction, not the Requests page. Eligible options come from loaded history. |
| Duplicate protection | WORKING in source; real index/service workflow not live-verified | Same POST; partial unique index for pending student/session | Duplicate insert becomes 409 `REQUEST_ALREADY_PENDING`. Existing Phase 13 tests exercise schemas/route stubs, not a real duplicate database insert. |
| Request status / cancel | PARTIAL | `/requests/mine`, `/{id}`, `/{id}/cancel` POST | Self/institution checked; pending-only cancellation with guarded update. Failure feedback fixed. First 50 only; resolution note not displayed; updates require reopening Requests/inbox. |
| Notifications | PARTIAL | Shared notification endpoints | Recipient-only; first 50/read-feedback limitations. |
| Timetable / Upcoming Classes | PARTIAL | `/student/timetable` | Both render the full dashboard using the current enrollment's class schedule. No distinct timetable page/refresh. |
| Subjects | MISSING as advertised screen | No navigation dispatch or dedicated curriculum endpoint | Subject-wise attendance exists on Attendance; Subjects menu is a no-op. Timetable data is not a full curriculum list. |
| Profile / Settings | MISSING as dedicated screens | Own profile endpoint exists; no settings screen/API | Both menu clicks are no-ops; profile data is visible on dashboard. |

## CRUD, validation, feedback and responsive-state audit

| Area | List/create/edit/status | Validation and authorization | Loading / empty / error / success | Mobile/layout finding |
|---|---|---|---|---|
| Academic structure | List, create, edit, deactivate via form; institution edit only | Role/institution derived from token, reference hierarchy/code/date rules; some dependency checks incomplete | Loading/empty/error and paging exist. Successful save reloads; no success banner. Failed save closes form and loses input. Invalid numbers now show field errors instead of crashing. | ResponsiveRow fields; scroll set but academic dialog has no explicit height constraint; actual keyboard fit needs device check. |
| Students / Faculty | List, create, profile edit, status, CSV preview/confirm | Scoped services, duplicate identifiers, linked User password hashing and account status/token invalidation | Loading/empty/error exist. Profile mutation/import usually reloads without success banner; status errors discarded. Form closes on backend validation failure. | Unwrapped person rows contain name/email plus roll/designation/status/menu; long data may squeeze/clip. Dialog widths 600-760 and heights 600-650 need device/keyboard validation. |
| Assignment | View/create frontend; update/deactivate backend-only | Scoped active hierarchy/faculty department and duplicate assignment checks | Save errors appear on faculty list after dialog closes. No explicit success banner. | Cascading year/class/subject dropdown exists; no lifecycle edit UI. |
| Timetable | List/create/edit/status and pager | Faculty/class/room conflict rules; timezone/effective dates | Loading/empty/error exist; success reloads; status failure ignored | Grid only current page; list rows and control grouping may crowd 360px displays. |
| Faculty attendance | Start/open draft/mark/save/submit; history incomplete | Owner, tenant, roster and state checks in service | Save/submit notices exist; no explicit loading flag for session requests; complete roster Submit fixed | Status buttons wrap, scroll container exists; long lecture Row and mode selector need device check. Search rebuilds field each keystroke. |
| Student attendance | Read/self summary/history; correction action | Self identity + finalized state | Failed summary now explicit error; partial history errors shown. No visible loading spinner; empty/no-eligible summary still displays 0%/Watch. | Scroll exists; summary ring/formula horizontal Row needs narrow-device verification. |
| Requests | List/create/review/cancel; no arbitrary edit/delete | Self/owner/institution, schema and pending unique index | Loading/empty/error and Retry exist; failed cancel/review now visible. Success only reflected in list. | Request/review dialogs lack scroll setting; long reasons and keyboard may overflow. ListTile trailing Column has status+action. |
| Notifications / Audit | Inbox read/read-all; audit read-only | Recipient/tenant or Admin/tenant scope | Loading/empty/error; mark-read failures not surfaced; no success feedback | Scroll set; long titles/trailing actions need physical-device check. |
| Reports | Overview/filters/drill-down/CSV | Role/session/self scope and finalized-only repository query | Loading/empty/error/retry exist; sub-request failures become empty sections, metrics may default to zero on error | Horizontal table scrolling is implemented; subject action Rows, fixed-width dialogs and export file picker need device verification. |

The common app shell already uses SafeArea on all sides, bottom view padding, responsive sidebar (>=900px), mobile drawer, compact headers and width-band resize preservation. Those foundation/mobile tests pass; they do not prove absence of clipping on a real device. Drawer heading still says `<role> preview` for real sessions. Outdated Phase 5/6 copy remains in Student/Faculty detail panels. Palette/theme/layout direction was retained.

## Exact end-to-end workflow and remaining breaks

1. **Existing Admin and institution login are prerequisites.** Institution management only edits the current institution; there is no first-run Admin creation wizard. No bootstrap or password changes were performed.
2. Academic year -> department -> program -> semester -> class -> subject is wired. Required dates and IDs must form a consistent hierarchy. Independent academic/student-create dropdowns are not cascaded, so mismatches are rejected only after submit and the form closes. Numeric conversion crash fixed.
3. Admin creates Faculty: user/profile linkage, password hashing, department and account access are wired. The first-page limit can conceal older records. Feedback after create is only a refreshed list.
4. Admin creates Student: user/profile/enrollment creation is wired. Enrollment start_date must cover the lecture date, and the student must be active. Enrollment change UI still requires raw IDs.
5. Admin assigns Faculty/Class/Subject: create is wired; edit/deactivate/recover an inactive assignment is not available in the UI. Reactivating a Faculty account does not restore deactivated assignments; existing timetable entries can still reference them.
6. **A matching active recurring timetable entry is also required.** Assignment alone does not create a scheduled lecture. For the October 20 demo, the lecture must include Tuesday, October 20, with valid effective dates. To rehearse earlier, use a valid occurrence for that day's weekday; this UI only offers today's lectures. No test data was inserted during the audit.
7. Faculty login fetches profile, active assignments, timetable and session list. Faculty already logged in before Admin changes must log out/in to refresh schedule/profile; clicking Timetable does not reload it. API failures can masquerade as no lectures.
8. Start -> active enrollment roster -> manual marks -> Save Draft -> Review & Submit is wired. Fixed complete-roster submit disablement and failed-save-then-submit. Return from a selected session to the list and viewing finalized sessions through Attendance History remain incomplete.
9. Student login sees finalized attendance. If already signed in, reopening Attendance/Dashboard now reloads it. Subject names/threshold/no-data display still need polish.
10. Student submits correction from Attendance. Duplicate-pending protection and scoped review are present. Cancel/review failure feedback fixed; requests-page create action, filters/paging and resolution-note display remain absent.
11. Faculty owner with active assignment or institution Admin can review. Approval changes the record, sends Student notification and appends audit entries; rejection leaves record unchanged in source. Approval record update, request status, notification and audit insert are separate writes, so races/failures can leave partial results. No new real database workflow was executed to prove these transitions.
12. Reopen Student Attendance/Requests to fetch changes, then reopen Reports. Finalized-only report queries read corrected records. However, report panels/CSV do not consistently apply the same selected scope, as detailed below.

## Backend/API and RBAC findings

- **Fixed:** Admin dashboard queried `requests` instead of `attendance_requests`, and ISO strings instead of the BSON datetime used by attendance services. Tests now use the actual stored date representation and test other-tenant/prior-day/resolved exclusion.
- **Fixed:** Admin Student/Faculty list aggregations returned raw `accounts` and `account` User documents, including authentication internals. Services now strip the raw join array and whitelist public account fields without mutating stored data. Two regression tests cover both lists.
- Production management routes enforce `require_role`/`require_roles`; institution IDs come from authenticated users. Student attendance derives profile from authenticated user; Faculty session details require owning Faculty; request reviewers also need an active assignment. Existing tests cover several cross-tenant and wrong-role cases. No new role-bypass route was found in these production flows; this is not an exhaustive penetration-test claim.
- **Conditional development bypass:** `/dev/*` academic tooling is gated by `ENABLE_DEV_ACADEMIC_API` alone, without JWT or an APP_ENV production check. It is currently disabled. Keep it disabled for the LAN demo; enabling it exposes academic reads/writes without role authorization.
- **Validation/data consistency:** `StudentUpdate`/`FacultyUpdate` allow explicit nulls in identity fields. Student profile form converts blank display name/email into null, and service synchronizes nulls to User. Validate required identity before saving; no existing records were edited here.
- **Partial writes:** draft record save updates rows sequentially before validating the whole submitted roster; an invalid later row can leave earlier rows changed. Session creation persists session before initializing all roster rows. Correction resolution is multi-document/nontransactional. These need deliberate service changes, not an audit-time rewrite.
- **Reporting scope mismatch:** Admin overview accepts year/department/program/semester/class/subject/date filters; Admin subject endpoint accepts class/subject/date only; low-attendance endpoint ignores year/date; trend endpoint accepts only date. UI sends a shared filter set, but different panels can display different scopes. Class/student/session drill-down and CSV don't carry the selected filter scope. CSV class/low-attendance is capped at 100 without exhaust/paging. Faculty session export route is missing.
- `ReportFilters` has date-order validation but router handlers do not instantiate it. Reversed date ranges can silently return empty results. Some class report page parameters also lack the expected >=1 bound.
- CSV import validators stringify exceptions, including Pydantic validation details that can echo submitted temporary-password input. Return sanitized row/field messages rather than raw exception text. Imported credentials are returned to Admin by design but should not be logged. This was identified, not modified.
- Authentication refresh/timeouts and LAN/public URL support were preserved. `must_change_password` is set on new accounts but there is no UI password-change workflow; do not promise this in the demo. Raw password/hash/token values were not printed or changed.

## Narrow fixes completed

1. Complete manual roster retains explicit zero status counts, enabling Review & Submit.
2. Failed draft save aborts final submission, preserving its error.
3. Student Attendance/Dashboard fetch current summary/history; failure is shown as unavailable, not a fabricated zero.
4. Failed request cancel/review is no longer overwritten by an automatic list refresh.
5. Academic invalid/nonfinite numeric values show inline field errors instead of an uncaught conversion exception.
6. Admin dashboard reads actual attendance request collection/BSON date; unavailable statistics show dashes; API badge uses connection state. Face status label is explicitly unchecked, without any face logic change.
7. Report CSV actions now register async event handlers, so Flet awaits the existing export/file-picker operation. Missing Faculty session CSV endpoint and filter/export semantics remain open.
8. Student/Faculty list account fields are whitelisted and raw joined User arrays removed.

Files changed only for this audit: `app/main.py`; `app/screens/admin/academic.py`; `app/screens/admin/dashboard.py`; `app/screens/reports.py`; `app/screens/student/attendance.py`; `app/test_management_audit.py`; `backend/app/api/dashboard.py`; `backend/app/modules/auth/schemas.py`; `backend/app/modules/faculty/service.py`; `backend/app/modules/students/service.py`; `backend/tests/test_dashboard.py`; `backend/tests/test_management_audit.py`; this document. Several were already modified/untracked at entry; this list does not attribute earlier work to this task.

## Top 10 remaining fixes / validation actions by demo priority

| Rank | Priority and concrete acceptance criterion |
|---|---|
| 1 | **Prove the complete three-role manual flow with real authorized demo accounts on LAN.** Replace four empty tests with real service assertions; add correction create/duplicate/approve/reject/cancel, notification and report checks. Then rehearse from a second device without touching unrelated records. Current unit success is insufficient for demo sign-off. |
| 2 | **Make attendance history navigable.** Add explicit Back to sessions, open finalized session read-only, and protect unsaved drafts when leaving. Verify consecutive lectures without logging out. |
| 3 | **Refresh Faculty/Student schedules and surface fetch failures.** Admin edits must appear through a Refresh action; backend error must not be presented as a real empty schedule. |
| 4 | **Finish or disable dead navigation.** Faculty My Classes, Student Subjects, all Profile/Settings items should open meaningful screens or clearly indicate unavailability. Correct real-session drawer heading. |
| 5 | **Keep forms usable after errors.** Preserve input, validate required names/email/dates, prevent null identity writes, cascade academic selections, and replace enrollment raw-ID inputs with reference dropdowns. |
| 6 | **Expose teaching assignment edit/deactivate and explain lifecycle effects.** Prevent a reactivated Faculty from seeing unstartable lectures that reference inactive assignments. Validate dependent academic deactivation. |
| 7 | **Add paging and honest completeness.** Reach beyond Student/Faculty first 20; requests/notifications/audit first 50; show all relevant weekly lectures and reference choices; paginate report detail/export. |
| 8 | **Complete mutation feedback.** Handle failed person/timetable status changes and notification reads; show success notices; expose request resolution note and add new-request action to Requests. Sanitize CSV validation feedback. |
| 9 | **Align reports and exports.** Apply identical scope across cards/subjects/trend/low list/export, validate date ranges, and implement or disable Faculty session CSV. Use subject names and configured threshold on Student attendance. |
| 10 | **Perform physical-phone layout/keyboard QA at 360/390px plus desktop.** Fix long names/IDs, trailing actions, full-height dialogs, request reason scrolling, keyboard focus and dropdown search usability while retaining current theme. |

The multi-write/race consistency findings and complete audit coverage also require follow-up before claiming robust concurrent use. They were not changed blindly in this deadline-focused audit.

## Verification

Run from the project root with its existing virtual environment:

```powershell
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe -m pytest backend/tests
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest app/
git diff --check
```

Final post-change results: **201 backend tests passed** (two existing dependency deprecation warnings), **184 frontend tests passed**, and **`git diff --check` passed**. The counts increased by two backend and thirteen frontend regression cases. The four pre-existing empty tests remain explicitly identified above; they were not counted as meaningful new coverage.

New focused tests cover UI workflow failures, async export dispatch, invalid form numbers, stale Student refresh, truthful failed metrics and safe account-list serialization. Tests retain the existing real-MongoDB guard and use in-memory doubles; they do not migrate, delete or reseed local data. A real multi-account LAN rehearsal and physical-phone visual QA are still required before demo sign-off.
