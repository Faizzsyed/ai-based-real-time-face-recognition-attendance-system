# Real-time biometric performance and manual test

The capture thread stores only the newest raw frame in a size-one buffer. Preview encoding, Flet image updates, throttled YuNet analysis, MediaPipe blink landmarks, and event-driven SFace recognition do not execute in the capture loop. Stale frames are dropped.

Preview targets 24 FPS and updates only the camera Image. Analysis targets 6 FPS on a copy downscaled to 640 pixels wide. SFace is skipped during preview and runs only after liveness passes. Logs report FPS, queued/dropped frames, JPEG time, analysis time, YuNet time, and SFace time without image or embedding content.

## Manual hardware record

| Check | Observation | Result |
| --- | --- | --- |
| Preview smoothness / approximate FPS | Not physically tested | Pending |
| CPU pattern / sustained backlog | Not physically tested | Pending |
| Stable face for about one second | Not physically tested | Pending |
| Calibrated blink within five seconds | Not physically tested | Pending |
| Automatic enrollment capture 1/3 to 3/3 | Not physically tested | Pending |
| Student One recognition | Not physically tested | Pending |
| Student Two recognition | Not physically tested | Pending |
| Wrong Student rejection | Not physically tested | Pending |
| Unknown-person rejection | Not physically tested | Pending |
| Camera lifecycle | Automated coverage; physical check pending | Pending |

## Procedure

1. Start the backend and Flet desktop client, open Face Enrollment, grant consent, and start the in-layout camera.
2. Observe `[PERF]` logs for 30 seconds and record capture/preview FPS, YuNet/SFace milliseconds, CPU behavior, and any persistent backlog.
3. Hold exactly one clear face stable with eyes open during calibration, then perform one open-closed-open cycle within five seconds. Confirm held-closed eyes do not increment repeatedly and timeout marks nobody.

### Blink blocker retest

1. Admin real login → Face Enrollment → Test Student One → Start Camera.
2. Wait through `Hold still` and `Calibrating eyes 1/8 … 8/8` without blinking.
3. At `BLINK ONCE`, blink normally once. Expect `Blink detected... open your eyes`, then `✓ Blink verified`.
4. Look straight with eyes open for neutral stabilization; verify Capture 1/3, 2/3, and 3/3, consistency verification, encryption, and final Enrolled status.
5. To test Retry, deliberately do not blink for five seconds. Select `Retry Liveness`; the webcam must remain open while calibration restarts.

If detection still fails, set `FACE_LIVENESS_DEBUG=true`, reproduce once, and send only the `[LIVENESS]` lines containing left/right eye metrics, baseline, adaptive thresholds, state, blink count, timeout remaining, and analysis FPS. Never send images, tokens, embeddings, or secrets.
4. Confirm enrollment automatically collects three distinct quality-approved frames after liveness.
5. Test roster-wide and Specific Student modes with both enrolled Students, a wrong Student, and an unknown person.
6. Confirm identified attendance remains an editable AI suggestion requiring Faculty review.

## Limitation

The MediaPipe blink challenge is development-grade challenge-response. It does not provide production-grade presentation-attack detection.

## Enrollment stability correction

The original server check compared consecutive normalized SFace embeddings against `0.80` and reported a misleading positional-stability error. Final enrollment now waits for liveness to finish, requires an open-eyed frontal neutral face to remain stable for 700 ms, and only then collects three quality-approved frames.

Each accepted enrollment capture must have a new monotonic camera frame sequence and is spaced by 500 ms. Reused candidates are discarded and the same slot is recaptured without resetting liveness or stopping the camera. The server retains exact-byte protection plus a conservative decoded-image safeguard (`0.02` mean grayscale delta) for effectively re-encoded frame reuse; normal stationary webcam frames are accepted. It separately normalizes all three ephemeral embeddings and checks all pairwise similarities with `FACE_ENROLLMENT_CONSISTENCY_THRESHOLD=0.40` before averaging and encrypting the template. Safe logs contain only frame sequence, slot, retry count, similarity, threshold, and duplicate delta.

Real-webcam retest of this corrected flow is pending and must cover Student One through final `ENROLLED` status.
