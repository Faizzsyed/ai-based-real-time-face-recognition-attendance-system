# Desktop head-turn liveness fix

18 October 2026 — **LIVENESS FIX: READY FOR PHYSICAL RETEST**

Continued the existing desktop implementation. The user physically verified that the webcam and YuNet tracking work, but a left-turn challenge repeatedly failed. This report supersedes the earlier report's “physical test not started” status for that observation. The revised challenge has automated coverage; a successful physical retest is still pending.

1. **Physical bug root cause and evidence.** The old pose detector could reject a small natural turn: its dimensionless threshold was 0.16, it consumed unfiltered samples, neutral calibration had no stillness check, and the action expired after five seconds. A controlled projection of MediaPipe's canonical landmarks reproduces rejection of a 12-degree turn (proxy 0.102844). The revised detector accepts that sustained turn. The old horizontal-only ratio also mixed head roll into yaw. These are confirmed implementation weaknesses. The original webcam attempt did not record yaw values and no diagnostic log file was present, so its exact gesture amplitude, driver reflection and individual contribution to failure cannot be established from that observation alone. No physical success is claimed here.

2. **Mirroring audit.** `CameraService` publishes OpenCV frames directly; preview/capture encoding only resizes/encodes, the green box is drawn on a copy, MediaPipe only converts BGR to RGB, and Flet's preview has no horizontal reflection transform. Thus there is no application-created preview or analysis mirroring. For unmirrored input, positive nose displacement is the person's left, so the existing sign must not simply be reversed. New `CAMERA_INPUT_MIRRORED=false` explicitly describes the analysis input. Set it true only if the camera/driver actually supplies reflected frames; it corrects the pose sign without modifying captured images. Display-only reflection would leave this flag false. Hardware/driver orientation was not physically checked by this agent.

3. **Previous pose logic.** Landmark 1 was the nose, 33 and 263 the outer eye corners. `yaw = (nose.x - mean(eye.x)) / abs(eye263.x - eye33.x)`. Neutral was the median of the first eight valid samples alongside eye calibration, without a yaw-stability gate. Left required `yaw - neutral_yaw >= 0.16`; right required `<= -0.16`. Two consecutive raw samples passed. The pose timeout was five seconds. Multiple faces failed immediately; missing landmarks had a 600 ms grace. YuNet loss over 600 ms also restarted the surrounding camera challenge. Quality rejection of one detected face did not itself restart it.

4. **New pose logic.** Measure the nose's displacement along the eye line in pixel coordinates and normalize by squared eye separation. This removes aspect-ratio bias and the head-roll component. Normalize the sign for reflected analysis input. Keep the person's neutral baseline fixed for the attempt, median-filter three samples, then compare the relative pose to +0.10 for human-left or -0.10 for human-right. No automatic pass, static-photo bypass, identity-threshold change or backend enrollment change was introduced.

5. **Neutral calibration.** After the existing one-second face stability stage, ask the user to hold still and look naturally toward the camera. Collect eight valid samples, approximately half a second at 15 Hz. The rolling pose range must be at most 0.05, half the turn threshold; otherwise keep waiting for a stable window. Use its median as neutral and its eye measurements for open-eye calibration. Settling time does not consume the action timeout. The neutral baseline may be offset from zero, accommodating a person's comfortable sitting position. A dropped calibration observation requires a fresh stable window, without generating a new challenge attempt.

6. **Threshold and actual scale.** This is a normalized pose proxy, not yaw in degrees. The representation and threshold choice were checked against Google's [canonical face mesh](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model.obj), specifically vertices 1, 33 and 263. In a frontal weak-perspective projection, nose-to-eye depth divided by eye span is 0.483841, so proxy approximately equals `0.483841 * tan(turn)`. This gives the following synthetic values; they are a geometric sanity check, not measured webcam results or universal angle calibration.

   | Turn/threshold | Canonical projection |
   | --- | --- |
   | 5-degree turn | 0.042331; insufficient |
   | 12-degree turn | 0.102844; accepted when sustained |
   | 20-degree turn | 0.176104 |
   | Previous 0.16 threshold | Approximately 18.30 degrees |
   | New 0.10 threshold | Approximately 11.68 degrees |

   A subject-specific physical trace may justify later tuning. Recognition **0.363**, second-best margin **0.08**, enrollment consistency **0.40**, and backend cooldown **8 seconds** are unchanged.

7. **Consecutive-frame confirmation and noise.** Require three consecutive median-filtered valid observations. From a neutral filter window, this normally needs four sustained raw turn samples, approximately 0.2–0.3 seconds at 15 Hz. A single outlier cannot complete the default challenge; one noisy intermediate pose sample does not erase an otherwise sustained turn. A missing/invalid landmark sample clears confirmation evidence but preserves the attempt and calibrated neutral during the 600 ms continuity grace. Multiple faces or longer loss still fail safely. Nonfinite measurements never pass.

8. **Timeout/retry.** Pose and normal app blink action timeouts are now nine seconds, beginning after stable calibration. Retry creates a clean attempt, baseline and filter history without restarting the camera. One randomized existing supported challenge remains configured for enrollment: left, right or blink. Longer supported sequences remain available through the existing configuration, but the demo still uses one step. This remains development-grade challenge-response liveness, not certified PAD.

9. **Automatic capture transition.** A successful challenge enters `RETURN_TO_NEUTRAL` with “Great — challenge passed. Look straight and hold still for automatic capture.” Fresh open-eye observations and the existing frontal/quality/stability checks then drive Capture 1/3, 2/3 and 3/3 automatically. Fresh-frame spacing, duplicate rejection, server same-person verification, template encryption, encrypted reference storage, and explicit replacement remain intact. No extra manual Capture button or additional challenge was added.

10. **Files changed in this fix.** Earlier changes in these files were preserved:

   - `app/services/biometric_pipeline.py`: roll-resistant pose measurement, explicit input reflection handling.
   - `app/services/liveness_challenge.py`: stable calibration, median filtering, confirmation, nine-second pose default and optional diagnostics.
   - `app/core/config.py`: current desktop defaults and mirror-input flag.
   - `app/main.py`: mirror setting, developer-only logging gate and calibration/pass guidance.
   - `.env.example`: documented defaults; the real `.env` was not changed, and its inspected liveness fields did not override these defaults.
   - `app/test_phase11_liveness_challenge.py`: existing sequence tests allow the new filter to warm up.
   - `app/test_head_pose_liveness.py`: new regression tests.
   - `docs/head-pose-liveness-fix.md`: this report and retest steps.

11. **Focused validation.** **77 passed** across the new pose tests, existing liveness sequence tests, realtime biometric tests and desktop face acceptance tests. New cases cover human-left/right, reflected/unreflected inputs, head roll and aspect ratio, adapter configuration, unchanged camera orientation, stable/off-center neutral calibration, old small-turn rejection, insufficient/wrong turns, consecutive confirmation, intermediate noise, invalid samples, timeout/retry, diagnostic visibility and the actual controller transition into three automatic captures. Installed MediaPipe also loaded, processed a blank frame with zero faces, and closed successfully; no physical camera was opened.

   ```powershell
   $env:PYTHONPATH = '.'
   .\.venv\Scripts\python.exe -m pytest app/test_head_pose_liveness.py app/test_phase11_liveness_challenge.py app/test_realtime_biometric_pipeline.py app/test_desktop_face_acceptance.py -q
   ```

12. **Backend full suite.** **242 passed**, unchanged from baseline. Two existing dependency deprecation warnings; no failures. Backend tests forbid live MongoDB clients. No backend source or backend threshold was changed by this fix.

13. **Frontend full suite.** **289 passed**, versus the previous 269. The 20 additional test cases pass; no failures.

   ```powershell
   $env:PYTHONPATH = 'backend'
   .\.venv\Scripts\python.exe -m pytest backend/tests -q
   $env:PYTHONPATH = '.'
   .\.venv\Scripts\python.exe -m pytest app/ -q
   ```

14. **Whitespace and effective configuration.** `git diff --check`: PASS. A fresh process verified pose threshold 0.10, three confirmation frames, nine-second pose/blink action windows, eight calibration samples, one enrollment step, `camera_input_mirrored=false`, and diagnostics disabled.

15. **Exact physical webcam retest.**

   1. Close the running desktop app to discard its cached settings. From the project root, launch a fresh PowerShell process, set `$env:PYTHONPATH='.'`, then run `.\.venv\Scripts\python.exe -m app.main`. Keep the existing backend running; this fix changed desktop code only.
   2. Log in as Admin → Student Face Enrollment → select an approved Student → confirm consent → Start Camera. If already enrolled, choose Re-enroll Face explicitly before replacing anything.
   3. Face the camera naturally with eyes open and one person visible. Expect “Hold still … Calibrating” for about half a second after initial face stability. Do not begin turning during calibration.
   4. Read the prompt. For LEFT, turn toward **your own left shoulder**; for RIGHT, toward your own right shoulder. Make a small comfortable turn and hold it briefly, roughly a quarter second; do not rotate into a profile. If the randomized prompt is BLINK, blink once and reopen your eyes. To specifically retest the head-turn regression, stop/restart until a turn prompt appears.
   5. Expect “Great — challenge passed” within a few seconds. You have nine seconds after calibration before retry is required. A single brief tracking/noise disturbance should not create a new attempt. A stationary face or opposite-direction turn must not pass a requested turn.
   6. Return to a comfortable frontal pose with eyes open and hold still. Expect automatic Capture 1/3, 2/3 and 3/3, without pressing Capture or performing another challenge.
   7. Expect Enrollment Complete after server consistency checks and encrypted storage. Reopen the Student and verify enrolled status and the authorized reference image. Exercise the other turn direction on another approved enrollment/re-enrollment, then check that attendance scanning still marks draft only and preserves Faculty overrides.
   8. If the physical gesture still fails, enable `FACE_LIVENESS_DEBUG=true` in the **development process only**, relaunch, and reproduce once. The console records neutral/current yaw, raw/filtered delta, expected direction, input-mirrored flag, threshold and confirmation count. These diagnostics are never displayed in normal UI and are suppressed for production even when the flag is true. A reflected camera source needs `CAMERA_INPUT_MIRRORED=true`; determine that from the actual source/trace, rather than reversing prompts blindly. Disable diagnostics after the retest. Do not record or share embeddings, keys or face images as diagnostics.

No live database reset, unrelated management/Easy Setup changes, Android camera work, cloud deployment, commit, push or tag was performed. Existing continuous attendance, roster scoping, manual override protection, encrypted templates/reference images, explicit re-enrollment and Faculty-only finalization were preserved.
