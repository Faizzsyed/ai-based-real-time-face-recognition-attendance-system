# Development roadmap

Every phase requires verification before the next begins.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Existing project audit | Complete |
| 1 | Python/Flet/FastAPI foundation | Complete |
| 1.5 | Premium Flet UI foundation | Complete |
| 2 | Academic data and institution architecture | Complete |
| 3 | Authentication, JWT, and RBAC | Complete |
| 4 | Admin academic management | Complete |
| 5 | Student management | Complete |
| 6 | Faculty management and assignments | Complete |
| 7 | Timetable | Complete |
| 8 | Manual attendance | Complete |
| 9 | Face enrollment | Implementation Complete; real camera verification pending |
| 10 | AI-assisted roster-scoped face attendance | Current |
| 11 | Liveness / anti-spoof improvements | Planned |
| 12 | Reports and analytics | Planned |
| 13 | Requests, notifications, and audit | Planned |
| 14 | Android packaging | Planned |
| 15 | Web deployment | Planned |
| 16 | Scale testing and multi-institution readiness | Planned |

Phase 2 APIs remain independently guarded development tooling. Production routes do not rely on that flag. Phase 10 identifies only against an editable Phase 8 session roster, writes a reviewable `face_recognition` suggestion, and never submits attendance. Phase 11 liveness/anti-spoof work is not part of Phase 10.

## Real-world verification checkpoint

On 2026-08-23, local MongoDB connectivity, a real development Admin/API login, minimum academic data, two test Students, Faculty assignment, timetable derivation, and database-backed manual attendance through submitted Student history were verified in `attendai_python_dev`. Phase 10 real biometric verification did not run because the new project had no YuNet/SFace model assets or user-supplied biometric captures. Phase 11 should wait for real Phase 10 face verification.
