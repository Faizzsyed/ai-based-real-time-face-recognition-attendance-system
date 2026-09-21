# Final QA & Testing Guide

## Automated Baseline
The project maintains a rigorous automated test suite covering both the FastAPI backend and the Flet frontend.
**Final Status:**
- Backend Tests: 176+ passed
- Flet Tests: 109+ passed
- Total: 285+ passed (0 failures)

## Scope of Testing
1. **RBAC & Tenant Isolation**: Unit tests ensure that requests across `institution_id` boundaries strictly yield `HTTP 404 / 403`.
2. **Attendance Integrity**: Duplicate sessions, unauthorized student additions, and attendance formula math `(Present + Late) / Total * 100` are validated.
3. **Authentication Lifecycles**: Tests cover lockout thresholds, JWT expiration, refresh rotation, and `token_version` incrementation (effectively invalidating previously issued sessions).

## Manual QA Checklist

### Desktop Application
- [ ] Application starts successfully.
- [ ] Admin login and dashboard loads.
- [ ] Live webcam enrollment captures frames, enforces neutral face, and encrypts embeddings.
- [ ] Challenge-response liveness sequence completes.
- [ ] Real-time attendance accurately identifies enrolled student faces.

### Android Application
- [ ] APK installs successfully on the target device.
- [ ] Login screen scales properly without clipping headers.
- [ ] Authentication successfully retrieves JWTs from the backend.
- [ ] Manual attendance fallback works flawlessly (no crashing due to missing OpenCV).
- [ ] Face enrollment/attendance via native device photo-picker completes and uploads properly to the backend.

### Known Limitations
- The Android build requires `API_BASE_URL` to be explicitly defined during compilation; dynamic switching in the APK is not available.
- Liveness detection is completely disabled on the Android platform.
- YuNet/SFace models must be independently present in the backend's `/models` directory (they are not tracked in Git).
