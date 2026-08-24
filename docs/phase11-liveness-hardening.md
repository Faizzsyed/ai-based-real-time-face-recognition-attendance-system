# Phase 11 — Liveness and anti-spoof hardening

## Status and scope

AttendAI now uses a randomized, ordered challenge-response flow before face enrollment and face attendance capture. The implementation is development-grade liveness hardening; it is not a certified presentation-attack-detection system and must not be represented as production-grade anti-spoofing.

## Challenge engine

Enrollment randomly selects one of these three-step sequences using `secrets.choice`:

- blink → turn left → return center
- blink → turn right → return center
- turn left → return center → blink
- turn right → return center → blink

Attendance uses one randomly selected step from the same pattern pool to keep the flow lighter. Challenge actions must pass in order. Each retry creates a new attempt ID, discards prior calibration and progress, and chooses a fresh sequence.

The UI displays `Step X of N` and the current instruction. It does not reveal later steps. A single continuous face is required; multiple faces fail immediately, and face loss beyond the configured grace period fails the attempt.

## Landmark signals

The existing MediaPipe Face Landmarker supplies eye-blink blendshapes and facial landmarks. Blink detection retains per-session eye-open calibration, bilateral eye checks, consecutive open/closed frames, and reopening confirmation.

Head pose is estimated from the horizontal relation of the nose to the eye midpoint, normalized by eye distance. The engine first measures a neutral-yaw baseline, then evaluates pose relative to that baseline with thresholds and consecutive-frame confirmation. `RETURN_CENTER` requires the relative yaw to return inside the center tolerance.

The OpenCV preview is currently unmirrored. In this coordinate convention, a positive relative value maps to the subject turning left and a negative value maps to turning right. This mapping and camera-driver mirroring must be confirmed on each deployment camera.

## Configuration

- `FACE_LIVENESS_CHALLENGE_MODE=challenge` enables randomized challenges. Set it to `blink` for the documented blink-only fallback.
- `FACE_LIVENESS_ENROLLMENT_STEPS=3`
- `FACE_LIVENESS_ATTENDANCE_STEPS=1`
- `FACE_LIVENESS_POSE_TIMEOUT_SECONDS=5`
- `FACE_LIVENESS_POSE_DELTA=0.16`
- `FACE_LIVENESS_POSE_CENTER_TOLERANCE=0.07`
- `FACE_LIVENESS_POSE_FRAMES=2`
- `FACE_LIVENESS_FACE_LOSS_GRACE_MS=600`

`FACE_LIVENESS_MODE` remains the separate backend enforcement setting (`required`, `optional`, or `disabled`).

## Performance architecture

The preview remains on its independent high-rate loop, while YuNet detection and MediaPipe liveness analysis remain throttled separately. SFace embedding extraction is still event-driven after successful liveness and stable capture; it does not run on every preview frame.

## Privacy and security boundaries

Logs contain attempt IDs, challenge types, state transitions, and optional numeric debug metrics. They do not contain raw frames, embeddings, access tokens, or biometric payloads.

Current challenge generation and evaluation occur in the trusted application session, and the enrollment API receives captured images rather than a client-supplied `liveness_passed` boolean. However, the backend does not issue a signed challenge or independently verify temporal landmark evidence. A modified client could bypass the local gate when backend liveness enforcement is optional. Server-issued challenges and server-verifiable evidence are required before production deployment.

This technique can raise the cost of simple static-photo and naive replay attacks, but it does not provide depth, IR, texture-based PAD, mask detection, deepfake detection, or ISO/IEC 30107 certification. Sophisticated replay, injection, generative-video, and 3D-mask attacks may still succeed.

## Manual validation checklist

Run these with a real webcam after automated tests pass:

1. Complete enrollment with two different randomized sequences and confirm capture starts only after the final step.
2. Perform a correct blink but the wrong turn; confirm no early pass.
3. Hold a printed photo and replay a static face on another screen; confirm the ordered motion challenge does not pass.
4. Let a step time out, retry, and confirm the new attempt has no stale progress.
5. Repeat attendance several times and confirm its one-step profile remains fast.
6. With consent, test a second person and a second camera/lighting setup; record threshold observations without saving raw biometric material.

If head-pose direction is reversed or unstable on a specific camera, stop the trial, use `FACE_LIVENESS_CHALLENGE_MODE=blink`, and calibrate the pose convention/thresholds before re-enabling challenge mode.
