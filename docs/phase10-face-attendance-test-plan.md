# Phase 10 Face Attendance Manual Test Plan

Status: **NOT YET EXECUTED**. Do not interpret the automated fake-repository tests as real biometric or production validation.

## 2026-08-23 checkpoint

- Local MongoDB connected: **YES** (`attendai_python_dev` only)
- Real development Admin created and API login/refresh/`auth/me` verified: **YES**
- Academic hierarchy, two test Students, Faculty assignment, and timetable verified: **YES**
- Real MongoDB manual attendance E2E and Student history: **PASS**
- Real human Flet workflow: **NOT PERFORMED**
- YuNet/SFace models in the new project: **NOT AVAILABLE**
- Real face enrollment / encrypted template: **NOT PERFORMED**
- Real Student recognition / cooldown: **NOT PERFORMED**
- Real camera and unknown-person rejection: **NOT PERFORMED**
- **DIFFERENT-PERSON REAL IMAGE TEST NOT VERIFIED.**

## Preconditions

- Use only the new `attendai_python*` database and a non-production test Institution.
- Configure YuNet/SFace models, `FACE_AI_ENABLED`, and the encryption key without printing secrets.
- Record device, OS, browser/app version, model hashes, lighting, threshold, and margin.
- Obtain the Institution's required biometric notice/consent before enrollment.

## End-to-end flow

1. Admin creates or verifies two active Students in the same Class and Academic Year.
2. Admin enrolls both faces with three distinct, clear frames and verifies enrollment status.
3. Admin creates/verifies an active Faculty member, Faculty Assignment, and matching Timetable entry.
4. Faculty logs in and starts the scheduled lecture's Manual Attendance Session.
5. Faculty opens the integrated **Face Attendance** tab and verifies roster, face-enrolled, recognized, remaining, and manual-only counts.
6. Present Student 1 alone in good lighting. Verify identification, one `present` suggestion, and no automatic submission.
7. Present Student 1 again immediately. Verify `already_recognized`, cooldown behavior, and one AttendanceRecord only.
8. Present Student 2 and verify the second reviewable suggestion.
9. Present a genuinely unknown consenting test person. Verify `unknown`, no Student identity disclosure, and no record update.
10. Test no face, multiple faces, blur, poor lighting, and small face; verify safe feedback and no mark.
11. Switch to Manual Attendance without losing suggestions, change at least one suggested status, and complete all remaining Students manually.
12. Review totals, explicitly confirm submission, and verify Faculty editing is then restricted.
13. Log in as the Student and verify only that Student's submitted attendance history.
14. Verify raw captures, probe embeddings, decrypted candidates, keys, and candidate scores are absent from database responses and logs.

## Required security checks

- Faculty A cannot access Faculty B's session; Student/Admin roles cannot use Faculty identification routes.
- Cross-Institution session IDs fail without revealing whether biometric candidates exist.
- Submitted and locked sessions reject face identification.
- With AI/models/encryption disabled, Manual Attendance remains usable through submission.

## Explicit unverified items

- Real MongoDB production-style flow: not verified.
- Real enrolled Student identification: not verified.
- Real Web/Android camera capture: not verified.
- Real unknown-person rejection: not verified.
- **DIFFERENT-PERSON REAL IMAGE TEST NOT VERIFIED.**
- Full Faculty-to-Student real attendance E2E: not verified.
