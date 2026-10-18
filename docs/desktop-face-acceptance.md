# Desktop face workflow recovery and acceptance report

Verified on 18 October 2026. Continued the existing working tree on `main` at `9ecab63`; no Git finalization or live database operations were performed.

1. **FACE DESKTOP: READY FOR PHYSICAL WEBCAM TEST.** Automated checks pass. Physical camera behavior and recognition accuracy remain unverified.

2. **Recovered previous work.** Inspected the working tree, branch, last ten commits, diff summary and whitespace check. Preserved unrelated management, Easy Setup, deployment and Android changes. The following classification concerns the desktop implementation; it does not imply physical acceptance.

   | Area | Recovered state | Final state |
   | --- | --- | --- |
   | Automatic three-frame enrollment and same-person checks | COMPLETE | COMPLETE; preserved |
   | Local YuNet preview guidance | COMPLETE | COMPLETE; added serialization across camera restarts |
   | Continuous attendance scanning and roster restriction | COMPLETE | COMPLETE; preserved |
   | Delayed responses and camera lifecycle | PARTIAL | COMPLETE in automated coverage; stale worker failures and session-switch responses covered |
   | Manual override safety | PARTIAL | COMPLETE in automated coverage; saved overrides survive older refreshes; conditional database updates protect manual marks |
   | Explicit re-enrollment | PARTIAL | COMPLETE; preserved explicit action and authorization, added append-only audit events |
   | New encrypted reference storage and authorized viewing | COMPLETE | COMPLETE; authenticated endpoint decryption and legacy read-only behavior verified |
   | Model reuse | PARTIAL | COMPLETE; equivalent path/default arguments now share one protected backend model pair |
   | Camera errors, unknown faces, ambiguity and cooldown | COMPLETE | COMPLETE; added uninterrupted leave-frame regression coverage |
   | Development-grade client liveness | COMPLETE | COMPLETE; unchanged |
   | Physical webcam acceptance | NOT STARTED | NOT STARTED; exact procedure below |

3. **Delayed-response handling.** Live recognition, camera/model startup, preview encoding and local analysis run outside the UI event loop. Backend face inference and enrollment now run in the API thread pool. Recognition shows a pending message before waiting. Each response is checked against the camera generation and attendance session, including after draft/status refreshes. An old task's error cannot stop a newly started camera. In-flight duplicates are suppressed. Leaving the attendance screen releases the camera. An HTTP request already sent may still finish against its original draft after camera closure; closure cannot cancel a committed server write. Reopening that draft reconciles its authoritative state. It cannot redirect the request into the newly selected session.

4. **Manual overrides.** Present to Absent, Late or Excused remains authoritative. Unsaved and saved overrides survive an older recognition refresh during the current session. Recognition's MongoDB update only matches an unmarked record, so a manual decision made between the service check and database write wins. The next recognition returns `manual_override` without restoring Present. Unchanged AI suggestions retain `source=face_recognition`; manual changes use `source=manual` and clear `review_state`. New AI writes retain a separate `face_suggestion` timestamp/actor/status that survives a manual correction. Faculty finalization and its existing session history remain required.

5. **Re-enrollment.** The dialog says “Face already enrolled” and provides “Re-enroll Face.” Camera enrollment requires that explicit action plus consent. The replacement flag defaults to false; duplicate enrollment returns a conflict. Admin role checks and institution/student scope are enforced before enrollment. Replacement updates the existing uniquely scoped template, invalidates prepared templates, and emits `face.enrollment.replaced` in the existing audit collection. Creation/removal emit corresponding audit events. Audit metadata contains method, capture count and model version, never biometric payloads. No records were actually replaced during this audit.

6. **Encrypted reference images.** New approved camera frames are encoded and encrypted in memory with AES-256-GCM before `.enc` files are written. They have an explicit format prefix and use the existing configured biometric encryption key, fresh nonces and institution/student/frame-bound authenticated data. Staging contains encrypted bytes only and is cleaned after failure. Authorized routes decrypt in memory and return JPEG with `Cache-Control: private, no-store`; keys never enter frontend responses. Legacy JPG references remain readable without rewriting them. No historical-image migration was run.

7. **Enrollment UX.** Select Student, confirm consent, Start Camera, present exactly one face, follow local quality/stability guidance and the device challenge, return to a neutral pose, then receive three automatic captures. The server rejects reused frames and inconsistent identities before averaging SFace vectors and storing the encrypted template. A duplicate frame pair can recapture the offending slot without requiring three manual capture presses. Enrollment completes with a confirmation and refreshed status. Optional reference-storage failure is surfaced without discarding the valid encrypted template.

8. **Attendance UX.** Faculty opens an editable class draft, chooses Face, then Start Camera. A successful roster match writes a Present suggestion to that draft, updates recognition counts and keeps the camera open. Scanning rearms after the person leaves; the next Student completes their own device challenge. Faculty can use Manual mode for corrections and final review. UI omits raw match similarity from the normal result display.

9. **Duplicate suppression.** Camera request gating, an in-flight request key, a stable empty-frame interval of at least 0.25 seconds, backend identity cooldown, authoritative already-Present checks, conditional database updates and the existing unique session/student record prevent repeated marks. Multiple faces or a blurry detected face interrupt the empty-frame interval. Holding one face in view does not resubmit it. Already-Present remains authoritative even after the eight-second cooldown expires. A failed draft write does not start cooldown and can be retried.

10. **Unknown/ambiguous faces.** A below-threshold probe returns Unknown; insufficient second-best separation returns Ambiguous. Neither writes attendance. Multiple faces require one Student at a time. Matching stays within the active session roster, and selected-Student verification cannot fall back to another Student. Invalid/nonfinite probe vectors are rejected safely.

11. **Liveness.** Existing temporal challenge-response protection was retained, including calibration, blink/pose sequencing, continuity checks, timeouts and retry. The installed configuration uses one randomized device challenge step for enrollment and attendance. This is **development-grade challenge-response liveness**, not certified PAD or guaranteed anti-spoofing. Backend `FACE_LIVENESS_MODE` is currently `optional`. The separate server `required` mode expects its pose sequence; the current desktop frontal-capture/device-challenge flow does not supply that server evidence and fails closed in that mode. No liveness setting was weakened or changed in this continuation.

12. **Performance.** Preview uses local YuNet and makes no preview API requests. Capture uses a latest-frame buffer and separate preview/analysis/liveness work. Local detection is protected against overlapping workers after restart; MediaPipe access and close are serialized. Equivalent backend configurations share a cached YuNet/SFace pair, whose mutable inference buffers are locked. Prepared roster vectors are held in a bounded memory cache scoped to institution, session, user, encryption configuration and template signature; changes/finalization invalidate them. No roster API fetch occurs on every preview frame. Database writes occur only for accepted recognition of an unmarked roster member.

13. **Actual configured thresholds, unchanged.** Recognition cosine threshold **0.363**; second-best margin **0.08**; enrollment same-person consistency **0.40**; identity cooldown **8 seconds**; detection confidence **0.90**.

14. **Files changed in this continuation.** Existing changes in these files were preserved and extended:

   - `app/main.py`
   - `app/services/face_preview.py` (already untracked at recovery)
   - `app/test_desktop_face_acceptance.py` (already untracked at recovery)
   - `backend/app/api/attendance.py`
   - `backend/app/api/face_enrollment.py`
   - `backend/app/modules/attendance/repositories.py`
   - `backend/app/modules/face_ai/engine.py`
   - `backend/app/modules/face_ai/identification.py`
   - `backend/app/modules/face_ai/service.py`
   - `backend/tests/test_desktop_face_acceptance.py` (already untracked at recovery)
   - `backend/tests/test_phase9_face_enrollment.py` (injects an isolated audit double)
   - `docs/desktop-face-acceptance.md` (new report)

   Recovered camera service, biometric pipeline, encrypted storage, enrollment repository, enrollment/attendance screens and API client work was reviewed and retained. Other entries in `git status` predate this continuation.

15. **Focused tests.** Frontend **76 passed** across desktop acceptance, enrollment/attendance screens, realtime biometric pipeline, integrated camera, biometric authentication refresh and liveness challenge tests. Backend **51 passed** across desktop acceptance, enrollment, identification and integrated face workflow tests. Coverage includes slow inference, stale responses at each refresh stage, camera restart/closure, concurrent manual decisions, saved-override refresh, explicit/unauthorized/cross-tenant re-enrollment, audit metadata, encrypted reference authentication/decryption, legacy nonmigration, cleanup, unknown/ambiguous matches, duplicates, cooldown and leave-frame flicker.

16. **Backend full suite.** **242 passed**, two dependency deprecation warnings (Starlette/httpx test client and AnyIO BlockingPortal alias). No failures. The backend test fixture forbids real MongoDB clients.

   ```powershell
   $env:PYTHONPATH = 'backend'
   .\.venv\Scripts\python.exe -m pytest backend/tests -q
   ```

17. **Frontend full suite.** **269 passed**, no failures.

   ```powershell
   $env:PYTHONPATH = '.'
   .\.venv\Scripts\python.exe -m pytest app/ -q
   ```

18. **Whitespace validation.** `git diff --check`: PASS. Existing CRLF conversion notices from the initial check were informational, not whitespace failures.

19. **Actual model-load verification.** Installed backend YuNet and SFace loaded successfully; blank-frame preview returned `FACE_NOT_FOUND`. Installed desktop YuNet loaded and returned `FACE_NOT_FOUND`; MediaPipe loaded, processed a blank frame with zero landmark faces, and closed successfully. No physical `cv2.VideoCapture` was opened. These checks prove model loading/invocation, not real identity accuracy, device throughput or webcam permissions.

20. **Exact physical webcam acceptance procedure.** Use authenticated accounts and approved demo Students enrolled in the Faculty's active class. Do not use development role previews as evidence of access control. If the backend is already running, restart it to load the current Python changes. The existing launcher is `./scripts/run_backend.ps1 -NoReload`; launch the desktop app in another terminal with `PYTHONPATH='.'` and `./.venv/Scripts/python.exe -m app.main`.

   **A — Enrollment:** Admin login → Student Face Enrollment → select the first approved Student → confirm consent → Start Camera. Keep only that face visible, follow the displayed blink/turn prompt, then look straight with eyes open and hold still. Expect Capture 1/3, 2/3, 3/3 automatically and Enrollment Complete. Close/reopen the Student: expect Face already enrolled. Attempt ordinary enrollment without selecting Re-enroll Face: expect refusal with the existing template retained. For an approved replacement test, select Re-enroll Face, confirm consent and repeat; verify one active institution/student template remains and a replacement audit event appears. Confirm newly retained frames under `data/face_enrollments/<institution>/<student>/` are `.enc`, not new JPGs, and the authorized reference thumbnail displays. Inspect counts and file types only; do not print embeddings or keys. Enroll a second approved roster Student in the same way.

   **B — Continuous attendance:** Faculty login → Take Attendance → start/continue the correct lecture draft → Face → identify anyone in roster → Start Camera. First Student follows the displayed challenge and neutral guidance. Expect their name, Present in draft, and the camera still running. Keep the same face visible for more than eight seconds: expect no repeated mark. Remove the face completely for at least half a second; second Student presents and completes the challenge. Expect a second Present suggestion without closing/restarting the camera, with recognized/remaining counts updated. Present two faces together, an unenrolled person and poor-quality lighting/blur: expect guidance or Unknown and no new marks. Ambiguity is deterministically covered in automated tests; do not presume two particular people will produce an ambiguous score.

   **C — Manual override and delayed responses:** Change the first recognized Student from Present to Absent in Manual mode. Save Draft. Return to Face, Start Camera and present that Student again. Expect the Faculty mark to remain Absent. Confirm it still remains Absent after another successful recognition refresh. Repeat without saving first to check pending local edits survive refresh, then Save Draft. During a slow recognition, Stop Camera or open a different session through the normal navigation; expect no late result to repaint the new session or restart its camera. Reopen the original session to reconcile any draft write already accepted by the server. Retry a simulated API/write failure after restoring connectivity; expect one authoritative roster record and no duplicate.

   **D — Finalize and inspect:** Mark every remaining roster Student manually as appropriate → Save Draft → Review & Submit → Confirm Submit. This is Faculty finalization. Verify the draft becomes submitted/read-only and the manual Absent decision is retained. Student login → Attendance → verify the finalized result appears for that Student. Before submission, AI draft marks must not appear as official Student attendance. Stop/close the camera and confirm another camera application can acquire the device. Also test a busy/unavailable webcam and closing enrollment early; expect friendly messages and released resources.

21. **Known limitations.** Physical recognition accuracy, lighting/camera behavior, UI rendering and sustained real-device performance await the procedure above. Server-required pose liveness is a separate, currently incompatible evidence flow as described in item 11; the verified configuration uses optional server liveness plus the desktop challenge. Uploaded/profile-photo fallbacks do not prove live camera use. Encryption does not turn development liveness into certified PAD. In-flight HTTP work can complete against its original draft; inspect that draft after interruption. Re-enrollment's Python lock is per process, and reference files/audit/template updates do not form a distributed transaction; this audit does not certify concurrent multiworker deployment behavior. No threshold tuning or physical acceptance result is claimed.

22. **Security and scope confirmation.** Raw embeddings are not exposed by face APIs; biometric templates remain encrypted; new retained reference images are encrypted at rest; existing plaintext historical images were not migrated automatically. Reference access remains authenticated and scoped. Face recognition marks draft only; official attendance requires Faculty finalization. No live or unrelated database changes, resets or data migrations were performed. No Easy Setup, unrelated academic management, Android, cloud deployment or hosting changes were made in this continuation. No reset, clean, restore, checkout-over-changes, stash, revert, commit, push or tag was run.
