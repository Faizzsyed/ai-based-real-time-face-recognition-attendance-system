# Biometric access-token refresh manual test

## Admin Face Enrollment

1. Sign in as Admin and open Face Enrollment.
2. Start the in-layout camera and verify analysis begins.
3. In a safe development session, use a deliberately expired access token while retaining the current valid refresh session, or wait for normal access expiry.
4. Confirm the first `POST /api/v1/admin/students/{student_id}/face/analyze` returns `401 AUTH_TOKEN_EXPIRED`.
5. Confirm safe logs show one refresh request, refresh success, one original-request retry, and retry success. Token values must not appear.
6. Confirm the camera stays usable and enrollment continues without resetting the liveness/capture flow.
7. Repeat with an invalid/revoked refresh session. Confirm the camera releases and the UI returns to Login with “Your session has expired. Please sign in again.”

## Faculty Face Attendance

Repeat the expiry test for:

- `POST /api/v1/faculty/attendance/sessions/{session_id}/face/analyze`
- `POST /api/v1/faculty/attendance/sessions/{session_id}/face/identify`

Confirm refresh rotation updates both access and refresh tokens, identification retries once with the new access token, and the editable attendance suggestion is created normally.

These real-camera checks remain pending until performed on the target Windows hardware.
