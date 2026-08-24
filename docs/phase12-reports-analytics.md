# Phase 12 — Reports and Analytics

## Architecture

The backend reporting module is split into repository, service, router, and schema/policy layers under `backend/app/modules/reports`. The repository performs institution-scoped bulk reads of finalized sessions, their attendance records, and referenced academic labels. It does not perform per-student API or database request loops. The service owns role authorization, hierarchy filtering, calculations, drill-downs, pagination, and export shaping. Flet consumes summarized API responses and does not calculate official percentages.

An index on `(institution_id, status, lecture_date)` supports official date-range reports. Existing class/date, faculty/date, subject/status, session/student, and student-history indexes support drill-downs.

## Official calculation policy

Only sessions in `submitted` or `locked` state are official. `draft` and `reopened` sessions, unmarked records, abandoned work, and unsubmitted AI suggestions are excluded.

The centralized rule is:

`(present + late) / (present + late + absent) × 100`

`late` is present-equivalent because that is the current AttendAI attendance domain rule. `excused` and unmarked records are excluded from the denominator. When the denominator is zero, the percentage is `null`; the UI displays `—` rather than a misleading 0%. Cancelled sessions are not a current persisted state, so no cancelled rule was invented.

The low-attendance threshold is configured once with `ATTENDANCE_LOW_THRESHOLD_PERCENT` (default `75`).

## Role scope and privacy

- Admin APIs derive the institution exclusively from the authenticated user and provide institution overview, trend, departments, subjects, class/student/session drill-down, low-attendance, and CSV exports.
- Faculty queries are constrained by the authenticated Faculty profile and finalized sessions owned by that Faculty. Unassigned class, unrelated Student, and unrelated session lookups fail.
- Student reporting derives the Student profile from the authenticated user. There is no client-supplied Student ID on the self-report endpoint.

Responses and CSV shaping contain academic attendance fields only. Face images, embeddings, biometric metadata, credentials, hashes, access/refresh tokens, and authentication sessions are never queried or exported. Source reporting normalizes `face_recognition` to the safe label `face_assisted`; it does not expose biometric confidence or templates.

## Endpoints

Admin routes are under `/api/v1/admin/reports`: `overview`, `trend`, `departments`, `subjects`, `classes/{id}`, `students/low-attendance`, `students/{id}`, `sessions/{id}`, and scoped CSV routes under `exports`.

Faculty routes are under `/api/v1/faculty/reports`: `overview`, `subjects`, authorized class/student/session drill-downs, and authorized class CSV export.

Student self-service is `GET /api/v1/student/reports/attendance`.

Date filters use local-calendar attendance dates. Attendance sessions persist `lecture_date` as UTC-midnight BSON while explicitly retaining Institution local-calendar semantics, consistent with the timetable architecture; the Institution IANA timezone is not hardcoded to India.

## Implemented UI behavior

Admin and Faculty navigation expose Reports. Student Attendance uses the same official analytics API. The responsive page provides:

- real summary cards with explicit no-data values;
- authorized, dependent academic/class/subject filters, date fields, 7/30-day shortcuts, and reset;
- subject analytics and safe source distribution;
- server-paginated and searchable low-attendance rows;
- class, Student, and finalized-session drill-down dialogs without manual ID entry;
- recent finalized sessions and personal attendance history;
- simple Flet-compatible trend progress visuals;
- context-aware CSV actions using the central authenticated API client and `FilePicker.save_file` with explicit success, cancellation, and error feedback;
- loading, empty, error/retry, and success states using the shared light/dark design tokens.

Faculty filter options and drill-downs originate only from Faculty-owned finalized sessions. Student reporting remains self-only.

## CSV and PDF

CSV is supported for low-attendance, class, and session reports according to role authorization. Filenames are sanitized and date-stamped. Student bulk export is intentionally unavailable.

PDF is deferred. No PDF dependency exists in the current runtime, and adding a new rendering stack without a full A4 render-and-verify workflow would create unnecessary deployment risk. CSV and printable UI remain the stable outputs for this phase.

## Automated verified

Deterministic backend tests verify the centralized formula, zero denominator, draft exclusion, threshold behavior, source distribution, date/class/subject isolation, Faculty scope, Student self scope, horizontal role enforcement, CSV privacy, scoped options, search, and pagination. Flet tests verify metric mapping, both themes, loading/empty/error states, Student status/history, low-attendance pagination rendering, central authenticated export transport, and absence of biometric report content. The full project regression suite also covers authentication refresh, Phase 10 face attendance, and Phase 11 liveness.

## Manual verification pending

The automated suite does not physically operate a desktop window, real accounts, the local MongoDB dataset, or the native save dialog. Follow the checklist below before release sign-off. A no-data screen is a valid result when the selected real scope has no finalized sessions.

## Known limitations

- Department/program/semester filtering is based on current academic reference documents associated with each finalized session's class snapshot.
- AI review analytics are not described as accuracy. The current records store suggestion state but do not persist a complete, immutable suggested-versus-final ground-truth history sufficient for a reliable override-rate report.
- No live database performance benchmark or manual UI session was performed by automated tests.

## Deferred

PDF remains a non-blocking future enhancement. The current runtime has no established PDF rendering dependency or A4 render-and-verify workflow. CSV is the supported Phase 12 export.

## Manual verification checklist

1. Admin login → Reports; verify real overview values, empty states, theme switch, class drill-down API, low-attendance API, finalized session report, and each CSV download.
2. Compare one known 8/10 Student record to 80%; confirm a draft edit does not change it until submission.
3. Change academic/date scope and verify department, subject, and class totals against finalized sessions.
4. Faculty login → Reports; verify only owned submitted sessions/classes and confirm an unassigned class URL returns an authorization-safe error.
5. Student login → Attendance; verify only the logged-in Student's overall, subject percentages, status, and recent history.
6. Test dates around local midnight using the Institution's configured IANA timezone.
7. Inspect exported CSV headers and confirm no biometric, token, password, or authentication-session data exists.
