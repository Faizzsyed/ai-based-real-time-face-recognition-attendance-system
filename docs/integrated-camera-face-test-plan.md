# Integrated camera face workflow

## Implemented flow

Admin Face Enrollment opens a responsive OpenCV webcam panel, requires consent, validates one stable clear face, calibrates an open-eye baseline, runs a one-blink challenge, and automatically collects three distinct quality frames. Confirmation creates an averaged encrypted server-side embedding and retains only approved JPEGs in private ignored development storage. Preview and rejected frames are memory-only.

Faculty Face Attendance is available only for an owned editable attendance session. Faculty chooses either `Identify anyone in roster` or `Verify selected student`, completes two open-closed-open blink cycles, and receives a Present suggestion. Unknown, ambiguous, wrong-selected-student, quality, and liveness failures do not change attendance. Manual edits and Faculty submission remain authoritative.

The in-app liveness implementation uses MediaPipe Face Landmarker eye-blink blendshapes and temporal open-closed-open transitions. It does not provide production-grade presentation-attack detection. `optional` remains the default server mode.

This challenge-response liveness implementation provides development-level spoof resistance and requires dedicated production biometric evaluation before institutional deployment.

## Automated verification

```powershell
$env:PYTHONPATH="$PWD\backend;$PWD"
.\.venv\Scripts\python.exe -m pytest -q backend\tests
$env:PYTHONPATH="$PWD"
.\.venv\Scripts\python.exe -m pytest -q app
```

Coverage includes camera open/duplicate-start/stop/release, ordered distinct challenge frames, scoped image replacement/removal, selected-Student no-fallback behavior, required-liveness rejection, encryption safety, tenant/roster ownership, cooldown, manual override, and responsive Flet construction.

## Physical Windows checkpoint

1. Start backend and app using `scripts/run_backend.ps1` and `scripts/run_app.ps1`.
2. Admin: open Face Enrollment, confirm consent, start the camera, and complete the displayed center/left/right sequence in even light.
3. Confirm only three JPEGs exist below the matching institution/student storage path and UI reports enrolled/liveness metadata.
4. Faculty: start or open today's draft, select Face Attendance, first verify a specific enrolled Student, then use roster-wide mode.
5. Test the enrolled person, another enrolled roster person, an unknown person, two faces, poor light, a blurred frame, camera denial, repeated recognition within cooldown, navigation away, logout, and app close.
6. Confirm failure cases never mark a Student, manual override works, camera releases promptly, and submission still requires Faculty review.

Physical device behavior and recognition accuracy are not established by the automated suite; record the camera model, lighting, observed results, and logs during this checkpoint.
