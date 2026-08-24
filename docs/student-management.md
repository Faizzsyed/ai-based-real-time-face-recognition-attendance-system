# Student management and enrollment

Phase 5 introduces separate `students` and `student_academic_enrollments` records. A Student profile links one authentication `users` record through `user_id`; credentials and password hashes are never stored on the profile. Enrollment changes close the previous current record and append a new record, preserving history.

All `/api/v1/admin/students` operations derive `institution_id` from the authenticated Admin. Academic references are verified as active, same-Institution, and as one valid year → department → program → semester → class hierarchy. Admission numbers, account identifiers, current enrollment, and current class roll numbers are protected by validation plus database indexes.

New accounts set `must_change_password=true`. Phase 3 exposes this flag but does not yet provide a safe password-change endpoint, so enforcement of the first-login change remains a documented authentication follow-up; Phase 5 does not pretend that workflow exists. Temporary passwords are never logged or stored on Student records.

Status changes synchronize access: active and graduated profiles retain active portal access, inactive/archived profiles disable it, and suspended profiles suspend it. Disabling access increments the token version so existing access tokens cease to authorize requests. Student self-service is read-only at `/api/v1/student/profile`.

CSV import is a two-step preview/confirm flow. It accepts UTF-8 `.csv` files up to 1 MB and 500 rows, rejects missing headers and spreadsheet-formula values, performs no preview writes, and refuses confirmation when validation errors exist. Temporary credentials are returned only by a successful confirmed import; operators must transfer them securely and must not retain import files or exported credentials.

No attendance values are invented for authenticated Students. Until the attendance phase exists, the production dashboard shows identity/enrollment data and an explicit unavailable state. Development preview dashboards remain isolated and may continue to show labeled preview data.

## Failure safety

Student creation compensates completed user/profile/enrollment writes if a later write fails. Enrollment changes restore the former current enrollment if creating its replacement fails. MongoDB unique indexes remain the final concurrency guard. A future deployment using replica-set transactions may replace this compensation boundary without changing the API.
