# Architecture

AttendAI Pro is a modular FastAPI monolith with Flet clients. Clients use HTTPS REST and never connect directly to MongoDB, storage, or future biometric services.

```text
Flet Android / Web
        -> FastAPI routers
        -> service layer (ownership and business rules)
        -> repository layer (MongoDB operations)
        -> MongoDB Atlas
```

## Phase 2 academic boundary

Phase 2 introduces Institution, AcademicYear, Department, Program, Semester, ClassDivision, and Subject. Phase 3 adds Users and authentication sessions, but does not create Student or Faculty domain records, timetable, attendance, or face recognition.

All tenant-owned records carry `institution_id`. API/service code must never query a tenant-owned resource solely by document ID without validating institution ownership. Phase 3 derives the trusted scope from the authenticated principal.

The synchronous PyMongo client matches the current synchronous FastAPI routes. A connection is optional: missing configuration reports `not_configured`; an unavailable server reports `disconnected`; connected startup initializes academic and authentication indexes once.

Temporary `/api/v1/dev/*` academic routes are disabled by default through `ENABLE_DEV_ACADEMIC_API=false`. Authentication does not enable them. Phase 4 production Admin pages use the separate `/api/v1/admin/academic/*` surface and continue working when development APIs are disabled.

## Phase 8–10 attendance and biometric boundary

Face Enrollment, Face Identification, and Attendance Submission are separate operations. Phase 9 enrollment quality-checks a Student image, creates an SFace template, and stores only its AES-256-GCM encrypted representation. Phase 10 receives a bounded temporary frame and creates an ephemeral probe embedding on the server.

Identification candidates are the immutable roster snapshot already attached to the editable Phase 8 Attendance Session, intersected with active, same-Institution face enrollments. It never performs an Institution-wide biometric search. Stored vectors are decrypted only during matching and are never returned to Flet. A match must pass both `FACE_MATCH_THRESHOLD` and `FACE_IDENTIFICATION_MIN_MARGIN`; unknown and ambiguous results do not update attendance.

An identified Student updates the existing unique AttendanceRecord as `present`, `source: face_recognition`, and `review_state: ai_suggested`. The Attendance Session remains draft/reopened. Faculty can manually override any suggestion and must explicitly review and submit using the Phase 8 lifecycle. AI unavailability cannot disable manual attendance. Phase 10 does not implement liveness or anti-spoof challenge-response.

## Client targets

- Admin: primarily web
- Faculty: Android and web
- Student: Android and web

Face embeddings and biometric processing will remain server-side in later phases.
# Phase 3 authentication boundary

Flet authentication now flows through FastAPI's Auth Service, User Repository, and the NEW Python MongoDB `users` and `auth_sessions` collections. JWT claims provide a signed transport context but every protected request revalidates the current account, tenant, role, and token version. See [authentication-architecture.md](authentication-architecture.md) for lifecycle and storage details.

## Phase 4 Admin academic boundary

The authenticated Admin principal supplies the only trusted Institution scope. The production router injects that scope into the existing academic service layer, which enforces hierarchy, references, uniqueness, status, and deactivation rules before repositories write to MongoDB. Database indexes remain authoritative for concurrent duplicates.

The Admin Flet shell uses the production API client for management pages and the setup wizard. Development Preview renders UI-only states without tokens or production calls. See [admin-academic-management.md](admin-academic-management.md).
