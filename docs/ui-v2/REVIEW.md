# AttendAI UI V2 review

## Final demo-cloud checkpoint verification - 19 October 2026

The source was reviewed on `demo-cloud` from checkpoint `019c253` for the final
Git checkpoint and push. Backend verification: **259 passed** (two upstream
deprecation warnings). Frontend verification: **335 passed**. `git diff --check`
passed. The source audit reported no secrets or forbidden checkpoint artifacts.

Current branding uses a shared Flet `FACE_OUTLINED` icon inside `CROP_FREE` scan
corners with the existing blue/teal palette. Sidebar text remains
**AttendAI / Smart Attendance**. Login and splash show **AI Based Real-Time Face
Recognition Attendance System**. UI fingerprint icons have been removed.

Easy Setup, management fixes, face enrollment/recognition, liveness, cloud
preparation, and encrypted production GridFS storage remain present and covered
by the full suites. `render.yaml`, `Dockerfile`, `.dockerignore`, and backend
sources are unchanged from `019c253`; Render auto-deployment remains off.
No deployment, database reset, or live biometric acceptance was performed.

The original review below records the earlier UI V2 work before this final
checkpoint and branding correction. Its screenshots are historical offline QA
captures and may show the previous fingerprint branding; they contain no real
biometric records. Its statements about uncommitted changes and no Git push
describe that earlier review, not the final checkpoint operation.

## Original UI V2 review

**UI V2: READY FOR VISUAL REVIEW**

Review date: 19 October 2026. Branch: `demo-cloud`. Starting HEAD: `019c253`.
The initial working tree was clean. All changes remain uncommitted.

This is a frontend review build. The local API refused connections during desktop QA. Screenshots therefore show explicitly empty or unavailable states, without fabricated records. Populated live workflows and biometric hardware performance still require a connected backend and camera.

1. **UI V2 status:** Ready for visual review; not a deployment or hardware acceptance sign-off.

2. **Design system:** `app/core/design.py` now owns light/dark palettes, blue/teal accents, semantic status colors, spacing, radius, typography and shadow tokens, layout breakpoints, attendance thresholds and camera colors. `theme.py` configures Material controls, buttons, dialogs and navigation consistently. Backend attendance thresholds take precedence over the centralized frontend fallback.

3. **Desktop shell:** A 248-pixel branded sidebar with grouped destinations, selected highlights, scrolling navigation and an institution/role footer. The toolbar sits beside the sidebar, with subtle connection state, alerts, account avatar and a real action menu. The authenticated Admin search explicitly searches students through the existing list endpoint; it does not imply unsupported global search.

4. **Mobile shell:** No desktop sidebar below 600 pixels. Student and Faculty receive five bottom destinations: Home, Attendance, Requests, Notifications and Profile. A drawer retains secondary routes. Tablets use an 80-pixel rail. Existing SafeArea protection and keyboard-aware dialog sizing remain in place.

5. **Login redesign:** Bounded split desktop panel, focused single mobile card, AttendAI branding, unified fields, password reveal, autofill hints, disabled/loading states, friendly error messages and a small API indicator. Development previews are collapsed into a disclosure. The splash no longer displays a fabricated progress percentage.

6. **Admin Dashboard:** Four real-value metrics: students, faculty, active classes and finalized attendance rate. Missing values stay unavailable rather than turning into zero. Institution name, current academic year and institution-local date are read from existing data. Setup progress includes timetable readiness when its endpoint succeeds. Existing report endpoints supply daily and subject percentage bars; audit events and published timetable supply activity and lectures. Quick actions open real management/create screens. Unsupported or unavailable data receives an explicit empty/unavailable state.

7. **Academic Management:** One sidebar entry opens a workspace containing Institution, Academic Years, Departments, Programs, Semesters, Classes & Divisions and Subjects. All original CRUD handlers remain reachable. Tabs and guided setup steps scroll horizontally on phones so they do not consume the form area. Easy Setup remains available as the guided path.

8. **Faculty/Student management:** Shared initial avatars, identity cards, consistent spacing, status badges, real action menus, search, filters, import and pagination. Loading feedback and retry cards replace isolated spinners/error blocks. Forms retain hierarchy-aware dropdowns, validation, date controls and single-option defaults.

9. **Faculty Dashboard:** Next lecture, today's timetable, assigned teaching work, draft counts, pending request entries and a working Take Attendance action. Previous illustrative lecture fixtures were removed from the runtime dashboard builder. Preview actions requiring authentication are disabled.

10. **Attendance:** Class/session context, clearer mode selection, draft totals including Remaining, initial-based roster cards and status badges. Manual Present/Absent/Late/Excused actions retain their existing callbacks and override protection. Rosters larger than 12 entries use a bounded native lazy ListView. Review Draft leads to explicit Faculty finalization; unmarked records still prevent review.

11. **Face Attendance:** Existing OpenCV image control, gapless preview, camera lifecycle, quality/liveness indicators and guide overlay retained. Camera sizing adapts to a narrow desktop window without incorrectly switching to Android image-picker behavior. Reused recognition-progress controls show actual counts. The roster remains available beneath the face panel for manual adjustments. Recognition still writes drafts; finalization remains mandatory. No detection, recognition, liveness or encryption algorithms were changed.

12. **Student Dashboard:** Real finalized percentage in a gradient attendance hero with a native progress ring, attended/eligible totals and backend threshold. Subject percentage cards use shared good/warning/critical colors. Today's timetable uses compact timeline rows; recent notifications use the shared notification component. No-data and failed-data states stay distinct. Program/semester labels render when supplied by the profile; the current profile API generally returns enrollment IDs, which are not substituted as public-facing labels.

13. **Requests/Notifications:** Consistent workflow cards with actual subject, student, date, reason and state where supplied. Counts describe the loaded request page. Existing review/cancel/create actions remain role-scoped. Notification cards include timestamps and read/unread styling with working mark-read actions. Audit lists retain their read-only API-backed behavior.

14. **Reports:** Existing scope filters, ranges, exports, detail dialogs and pagination preserved. Shared cards, fields, semantic colors and spacing apply throughout. Attendance sources use flexible native percentage bars. Existing mobile table-to-card conversion remains available. No additional or fabricated analytics were introduced.

15. **Responsive behavior:** Structural shell coverage at 360, 390, 430, 600, 768, 1024, 1366 and 1600 pixels. Phone fields stack and lose fixed widths; actions wrap. Horizontal setup/tab scrollers remain scrollers. Native desktop window resize QA included requested sizes of 1366×768, 1920×1080, 360×800, 390×844 and 430×932. Window frames, host display scaling and the QA toolbar reduce the content area relative to the requested outer dimensions.

16. **Components added/extended:** DashboardSection, QuickAction, initial avatar, workflow status, attendance hero, notification item, loading/error cards and common action button in `app/components/v2.py`; updated MetricCard, surface, section, empty-state and subject-attendance helpers. Profile screens for all three roles use actual account/profile data and expose secondary routes without fake editable fields. Shared button styling inherits normal, hover and disabled Material states; loading actions disable submission.

17. **Files changed:**

    - Foundation: `app/core/design.py`, `app/core/theme.py`, `app/main.py`.
    - Components: `app/components/ui.py`, `navigation.py`, `camera.py`; new `v2.py`.
    - Admin: `app/screens/admin/academic.py`, `dashboard.py`, `easy_setup.py`, `faculty.py`, `students.py`.
    - Auth: `app/screens/auth/login.py`, `splash.py`.
    - Faculty: `app/screens/faculty/dashboard.py`, `attendance.py`.
    - Student: `app/screens/student/dashboard.py`, `attendance.py`.
    - Other screens: `app/screens/phase13.py`, `reports.py`, `workspace.py`.
    - Frontend setup helper: `app/services/easy_setup.py` (institution guidance text only).
    - Regression coverage: new `app/test_ui_v2.py`; updated `test_flet_foundation.py`, `test_management_audit.py`, `test_phase14_mobile.py`, `test_phase4_academic.py` for intentional navigation/branding changes and new read-only API calls.
    - Review artifacts: new `scripts/preview_ui_v2.py`, this report and the screenshots below.

18. **Backend tests:** Baseline **259 passed**; post-change **259 passed**, with the same two upstream Starlette/httpx deprecation warnings. Command: `$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/tests -q`.

19. **Frontend tests:** Baseline **289 passed**; final **335 passed**. Added 46 V2 cases covering shell breakpoints, bottom navigation routes, academic CRUD reachability, scoped search and dirty-state protection, real/absent dashboard data, API enrichment, setup/timetable progress, status thresholds, attendance counts, manual marks, draft review gating, camera-control reuse, large-roster lazy rendering, responsive forms/dialogs, step scrolling, loading, notification states and read actions. Existing camera, biometric, authentication, Easy Setup and single-option default coverage remains green. Command: `$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest app/ -q`.

20. **Whitespace:** `git diff --check` passed. Backend, API-client, face-pipeline, camera-service, liveness, preview-processing and deployment paths have no diff.

21. **Desktop visual QA:** Launched the actual desktop application and inspected its public splash/login. Used the offline native Flet gallery for Admin and academic layouts at requested desktop sizes. Sidebar scrolling, content columns and resizing were inspected. Populated database screens and a live authenticated desktop session were not visually exercised because the API was offline.

22. **Mobile simulation QA:** Inspected Student/Faculty homes, face camera layout, Easy Setup, academic management, login and a scrolling student form dialog. Verified that the dialog's Cancel/Create actions can be reached by scrolling, and that phone navigation stays visible. Fixed wrapping setup steps found during visual QA. A populated roster/hero is covered by fixture-based regression tests, not claimed as a live hardware screenshot. Physical Android and an actual soft keyboard remain deferred as requested.

23. **Known Flet limitations:** Installed Flet 0.86.5 does not expose the older built-in LineChart/BarChart classes, and the separate charts extension is not installed. Analytics therefore use real-data native percentage bars, not chart screenshots. Font rendering and window chrome vary by platform. Native dialog fields scroll internally; a desktop resize is a simulation of a phone layout, not an Android runtime test.

24. **Deferred polish/validation:** Review with institution data and roles against a running API; measure camera preview/recognition FPS on the target hardware; test Android keyboard/system bars on a physical device. A dedicated charts extension can be evaluated separately if richer native chart interactions are wanted. Optional program/semester display-name hydration would require a suitable Student-authorized source. No deployment work was undertaken to address these items.

25. **Confirmation:** Backend architecture preserved. No database reset, seed, migration, or direct data writes performed. Face algorithms, thresholds and biometric encryption unchanged. Existing LAN/cloud-ready configuration preserved; cloud deployment untouched. No fake runtime data introduced. No commit, push or tag created.

## Screenshot gallery

These are native Flet screenshots of offline QA views. The toolbar identifies the requested outer window dimensions. Disabled camera controls are deliberate in the offline gallery; no camera or biometric record is loaded there.

| View | Screenshot |
| --- | --- |
| Admin desktop, 1366×768 | [Open](screenshots/admin-desktop-1366.png) |
| Admin desktop, 1920×1080 | [Open](screenshots/admin-desktop-1920.png) |
| Faculty mobile, 390×844 | [Open](screenshots/faculty-mobile-390.png) |
| Face Attendance, 430×932 | [Open](screenshots/face-attendance-mobile-430.png) |
| Student mobile, 390×844 | [Open](screenshots/student-mobile-390.png) |
| Academic Management desktop | [Open](screenshots/academic-management-desktop-1366.png) |
| Academic Management mobile | [Open](screenshots/academic-management-mobile-360.png) |
| Easy Setup, 360×800 | [Open](screenshots/easy-setup-mobile-360.png) |
| Login, 430×932 | [Open](screenshots/login-mobile-430.png) |

Run the database-free gallery from the project root:

```powershell
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe scripts/preview_ui_v2.py
```

Optional starting view:

```powershell
.\.venv\Scripts\python.exe scripts/preview_ui_v2.py --screen Student --width 390 --height 844
```

Use the existing `scripts/run_app.ps1` for normal authenticated operation against your configured API.
