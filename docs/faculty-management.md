# Faculty management and teaching assignments

Phase 6 separates authentication, Faculty identity, and teaching ownership:

`User(role=faculty) → Faculty → FacultyAssignment`

The `faculty` document owns professional identity and Department membership. Password hashes and login state remain exclusively on `users`. `faculty_assignments` connects a Faculty member to one Academic Year, ClassDivision, Subject, and explicit assignment type; it does not contain timetable or attendance data.

## Creation and account state

Admin creation validates the Department, creates the User with `must_change_password=true`, creates the Faculty profile, and may create bounded optional assignments. Compensating cleanup removes newly created records if a later step fails. Temporary passwords are never logged or stored on Faculty. Phase 3 exposes the password-change requirement but does not yet provide a secure first-login change endpoint; that enforcement remains an authentication follow-up.

Inactive, resigned, and archived Faculty map to an inactive User. Suspended Faculty map to a suspended User. These transitions increment the token version and deactivate active teaching assignments while preserving their history. Reactivation does not silently reactivate old assignments.

## Teaching ownership

Assignment validation requires Faculty, Academic Year, ClassDivision, and Subject to belong to the authenticated Admin's Institution. The Subject must match the Class Program and Semester, and the Faculty Department must own the Subject. Equivalent active assignments are rejected; multiple Faculty can still be assigned to the same Subject/Class through explicit assignment types such as primary, co-faculty, practical, or project guide.

Only active Faculty can receive new assignments. A Department change is rejected while active assignments remain, preventing existing ownership from becoming inconsistent. Assignment responses resolve scoped Academic Year, Subject, and Class details for safe display; tenant checks are also applied inside lookup pipelines.

Assignment deletion is a status change, never a destructive delete. Faculty self-service exposes only `/api/v1/faculty/profile` and `/api/v1/faculty/assignments`, derived from the authenticated User.

## CSV import

The optional CSV import accepts identity and Department data only. It resolves `department_code`, previews validation with no writes, rejects formula-prefixed cells and field-specific duplicate rows, and requires explicit confirmation. Files are limited to UTF-8 CSV, 1 MB, and 500 rows; confirmed writes run in bounded batches of 100. Subject assignments are deliberately excluded because ambiguous assignment inference is unsafe.

Real Faculty dashboards show persisted identity and assignments. They state that schedule becomes available after timetable setup and never present development-preview lectures as production data.
