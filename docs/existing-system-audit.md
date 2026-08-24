# Existing-system audit (read-only reference)

This is an inspection of `Aiattendance` performed without editing files, configuration, Git state, or MongoDB. Names below are confirmed from source unless marked otherwise.

## Confirmed existing functionality

### Roles and authentication

`User` supports `admin`, `faculty`, and `student`, with name, unique email, bcrypt-hashed password, active flag, and last-login timestamp. Express routes include `/api/auth`, `/api/protected`, and role-aware client routes/layouts. Authentication uses server middleware and generated tokens/cookies; exact deployment policy should be redesigned rather than ported verbatim.

### Identifiable collections and relationships

Mongoose model names identify collections (Mongoose defaults usually pluralize these): `User`, `Student`, `Faculty`, `Department`, `Class`, `Subject`, `FacultyAssignment`, `TimetableEntry`, `AttendanceSession`, `AttendanceRecord`, `ServiceRequest`, `ServiceRequestMessage`, `AuditLog`, `NotificationRead`, `UserPreference`, `AppSettings`, and timetable demo models.

| Area | Confirmed shape |
| --- | --- |
| Student | One `userId`; unique roll/enrollment numbers; department/class references plus denormalized department; semester, division, academic year, contact/admission/status, profile image, and face-enrollment metadata. |
| Faculty | One `userId`; unique employee ID; department reference, designation, qualifications, specialization, dates, status. |
| Department | Unique name/code, description, faculty HOD reference, status. |
| Class | Department, semester, division, academic year, faculty coordinator, status; compound uniqueness. |
| Subject | Unique code, department, semester, type, credits, description, status. |
| Faculty assignment | Faculty, subject, class, academic year, active period/status, creator; compound uniqueness. |
| Timetable | Department/class/subject/faculty references, weekday and validated time range, lecture/batch/room/year/semester/division, review/source metadata. |
| Attendance session | Assignment/faculty/class/subject/date/time, lecture context, counts, method, lifecycle, author and timetable linkage. |
| Attendance record | Per-session student record; legacy source shows present/absent/late/excused statuses and session-derived summaries. |
| Requests | Student/faculty requester references, request category/type, priority and workflow state; optional attendance correction linkage, messages and attachments. |
| Audit | Immutable actor/action/module/entity, before/after/changed fields, request metadata, result/error, timestamp. |

Express registers routes for health, auth, attendance, students, classes, subjects, faculty, assignments, departments, admin, audit logs, notifications, settings, requests, and timetable.

### Attendance and permissions

Sessions use `draft → completed → locked`; attendance methods are `manual` or `face-recognition`. Records use `present`, `absent`, `late`, and `excused`. Route middleware and separate admin/faculty/student pages indicate server-side protected and role-based flows, but this needs formal policy tests in the rewrite.

### Face architecture

The legacy system has a separately located Python `ai-service` with FastAPI routes (`/api/v1/health` and face operations) and a Node service adapter that uses an AI-service key and timeouts. Its planned engine is OpenCV YuNet/SFace. Student embeddings are encrypted in the Node service with AES-256-GCM; enrollment metadata includes method, version, quality, actor and timestamps. Face recognition events, pending attendance suggestions, and TTL liveness challenge/token models are present.

## Partially implemented or experimental/demo functionality

Timetable demo runs/seeding and imported timetable review fields are explicit. Face AI diagnostics, attendance suggestions, liveness endpoints, and several face-related files are untracked in the legacy Git worktree, so their production status is unconfirmed. Notification routes and read/preferences models exist, but delivery channels and reliability are not confirmed by this audit.

## Required redesign for the Python rewrite

- Add `institution_id` to every future owned document and redesign uniqueness/indexes around it.
- Replace duplicated student department fields with a clear migration and consistency policy.
- Formalize RBAC policy matrices and tests rather than inferring permissions from frontend pages.
- Treat biometric enrollment, encryption/key management, retention, consent, liveness, and human confirmation as security-reviewed backend workflows.
- Preserve attendance-session immutability/auditability and define controlled reopen/correction semantics.
- Rework existing data only through an explicit migration plan; do not point the new code at the legacy MongoDB.
