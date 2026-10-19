"""Resumable guided setup through the existing authenticated API client only."""
from dataclasses import dataclass, field

from app.services.api_client import ApiResult
from app.services.setup_defaults import semester_payloads

STEPS = (
    ("institution", "Institution", "Add your institution’s identity. You only need to do this once."),
    ("academic-years", "Academic Year", "June to May dates are suggested for you. Use the calendar to change them."),
    ("departments", "Department", "Your academic department. Its short code helps suggest names later."),
    ("programs", "Program", "The degree offered by your department, such as B.Tech ECS."),
    ("semesters", "Semester", "Create Semester 1 for a demo, or generate all semesters for this program and academic year."),
    ("classes", "Class / Division", "A group of students studying in the same semester."),
    ("subjects", "Subject", "Start with one subject. You can add more at any time."),
    ("faculty", "Faculty", "Create a faculty login or reuse a member of the selected department."),
    ("students", "Student", "Create a student login and academic placement together, or reuse an enrolled student."),
    ("teaching", "Teaching Setup", "Assign a faculty member to the subject and class, then set their lecture time."),
)
LINKS = {
    "programs": {"department_id": "departments"},
    "semesters": {"academic_year_id": "academic-years", "program_id": "programs"},
    "classes": {"academic_year_id": "academic-years", "department_id": "departments", "program_id": "programs", "semester_id": "semesters"},
    "subjects": {"department_id": "departments", "program_id": "programs", "semester_id": "semesters"},
    "faculty": {"department_id": "departments"},
    "students": {"academic_year_id": "academic-years", "department_id": "departments", "program_id": "programs", "semester_id": "semesters", "class_division_id": "classes"},
}


def record_id(row):
    return str(row.get("_id") or row.get("id") or "")


def record_label(row):
    return row.get("display_name") or row.get("name") or row.get("label") or f"Semester {row.get('semester_number', '')}"


@dataclass
class EasySetup:
    api: object
    authorized: object
    step: int = 0
    records: dict = field(default_factory=dict)
    selected: dict = field(default_factory=dict)
    drafts: dict = field(default_factory=dict)
    error: str | None = None
    field_errors: dict = field(default_factory=dict)
    loading: bool = False
    loaded: bool = False
    busy: bool = False
    editing: bool = False
    creating: bool = False
    assignment: dict | None = None
    timetable: dict | None = None
    complete: bool = False

    @property
    def resource(self):
        return STEPS[min(self.step, 9)][0]

    def require_admin(self):
        if not self.authorized():
            self.error = "Sign in as an Admin to use Easy Setup."
            return False
        return True

    def _list(self, resource):
        """Read all pages, so unique suggestions and reuse never use a truncated list."""
        rows, page = [], 1
        while True:
            if resource == "timetable":result = self.api.list_timetable(page=page, pageSize=100)
            elif resource == "faculty":result = self.api.list_faculty(page=page, pageSize=100)
            elif resource == "students":result = self.api.list_students(page=page, pageSize=100)
            else:result = self.api.list_academic(resource, page=page, pageSize=100)
            if not result.connected:return result
            data = result.data or {}
            rows.extend(data.get("items", []))
            pages = data.get("totalPages") or (data.get("pagination") or {}).get("pages") or 1
            if page >= pages:break
            page += 1
        return ApiResult(True, {"items": rows})

    def load(self):
        if not self.require_admin():return False
        self.loading = True
        self.loaded = False
        self.error = None
        try:
            institution = self.api.academic_institution()
            if not institution.connected:
                self.error = institution.error or "Institution unavailable. Retry when the API is connected."
                return False
            self.records["institution"] = [institution.data]
            self.selected["institution"] = record_id(institution.data)
            for resource, _, _ in STEPS[1:9]:
                result = self._list(resource)
                if not result.connected:
                    self.error = result.error or f"Could not load {resource}. Retry before saving."
                    return False
                self.records[resource] = result.data["items"]
            result = self._list("timetable")
            if not result.connected:
                self.error = result.error or "Could not load timetable. Retry before saving."
                return False
            self.records["timetable"] = result.data["items"]
            self.reconcile()
            self.loaded = True
            return True
        finally:self.loading = False

    def candidates(self, resource):
        rows = [row for row in self.records.get(resource, []) if row.get("status", "active") == "active"]
        links = LINKS.get(resource, {})
        if any(not self.selected.get(parent) for parent in links.values()):return []
        if resource == "students":
            return [row for row in rows if all(str((row.get("current_enrollment") or {}).get(key)) == self.selected.get(parent) for key, parent in links.items())]
        return [row for row in rows if all(str(row.get(key)) == self.selected.get(parent) for key, parent in links.items())]

    def reconcile(self):
        for resource, _, _ in STEPS[:9]:
            rows = self.candidates(resource)
            ids = [record_id(row) for row in rows]
            if self.selected.get(resource) not in ids:
                self.selected.pop(resource, None)
                if resource == "academic-years":
                    current = [row for row in rows if row.get("is_current")]
                    if len(current) == 1:self.selected[resource] = record_id(current[0])
                if resource not in self.selected and len(rows) == 1:self.selected[resource] = ids[0]

    def choose(self, resource, value):
        if not self.require_admin():return
        self.selected[resource] = value
        # Revalidate the entire dependency chain after every parent change.
        self.reconcile()
        self.drafts.clear()
        self.assignment = self.timetable = None
        self.editing = False
        self.creating = False
        self.complete = False
        self.error = None
        self.field_errors = {}

    def chosen(self, resource):
        return next((row for row in self.records.get(resource, []) if record_id(row) == self.selected.get(resource)), {})

    def placement(self, resource):
        return {key: self.selected.get(parent) for key, parent in LINKS.get(resource, {}).items()}

    def missing(self, resource):
        parents = list(dict.fromkeys(LINKS.get(resource, {}).values()))
        if resource == "teaching":parents = [key for key, _, _ in STEPS[:9]]
        missing = [parent for parent in parents if not self.chosen(parent) or self.chosen(parent).get("status", "active") != "active"]
        if resource == "teaching" and "academic-years" not in missing and not self.chosen("academic-years").get("is_current"):
            missing.append("academic-years")
        return missing

    def _accept(self, resource, result):
        if not result.connected:
            self.error = result.error or "Could not save. Your entries are still here."
            self.field_errors = result.field_errors or {}
            return False
        row = result.data or {}
        self.records.setdefault(resource, [])
        self.records[resource] = [x for x in self.records[resource] if record_id(x) != record_id(row)] + [row]
        self.selected[resource] = record_id(row)
        self.reconcile()
        if row.get("status", "active") != "active":self.selected[resource] = record_id(row)
        self.assignment = self.timetable = None
        self.complete = False
        self.drafts.pop(resource, None)  # Discard temporary passwords immediately after success.
        self.error = None
        self.field_errors = {}
        self.editing = row.get("status", "active") != "active"
        self.creating = False
        return True

    def use_current_year(self):
        if not self.require_admin() or not self.loaded or self.busy or not self.chosen("academic-years"):return False
        self.busy=True
        try:
            identifier=self.selected["academic-years"]
            result=self.api.update_academic("academic-years",identifier,{"is_current":True})
            if not result.connected:
                self.error=result.error or "Could not set the current academic year."
                return False
            for row in self.records["academic-years"]:row["is_current"]=record_id(row)==identifier
            return self._accept("academic-years",result)
        finally:self.busy=False

    def save(self, payload):
        if not self.require_admin() or self.busy or self.loading or not self.loaded:return False
        resource = self.resource
        if self.missing(resource):
            self.error = "Complete the required earlier steps first."
            return False
        self.busy = True
        try:
            if resource == "institution":return self._accept(resource, self.api.update_academic_institution(payload))
            if self.editing and self.chosen(resource):
                return self._accept(resource, self.api.update_academic(resource, self.selected[resource], payload))
            # Refresh before matching scoped unique identifiers. The backend remains the final arbiter.
            listed = self._list(resource)
            if not listed.connected:
                self.error = listed.error or "Could not check existing records. Retry."
                return False
            self.records[resource] = listed.data["items"]
            keys = {"academic-years": ("name",), "departments": ("code",), "programs": ("department_id", "code"),
                    "classes": ("academic_year_id", "program_id", "semester_id", "division"),
                    "subjects": ("program_id", "semester_id", "code"), "faculty": ("employee_id",), "students": ("admission_number",)}
            identity = keys[resource]
            existing = next((row for row in self.records[resource] if all(str(row.get(key, "")).casefold() == str(payload.get(key, "")).casefold() for key in identity)), None)
            if existing:
                self.error = "This identifier already exists. Select the existing record above, or choose a different identifier."
                return False
            if resource == "faculty":result = self.api.create_faculty(payload)
            elif resource == "students":result = self.api.create_student(payload)
            else:result = self.api.create_academic(resource, payload)
            return self._accept(resource, result)
        finally:self.busy = False

    def generate_semesters(self, demo=True):
        if not self.require_admin() or self.busy or not self.loaded or self.missing("semesters"):return False
        self.busy = True
        try:
            listed = self._list("semesters")
            if not listed.connected:
                self.error = listed.error or "Could not check existing semesters."
                return False
            self.records["semesters"] = listed.data["items"]
            program = self.chosen("programs")
            plans = semester_payloads(self.selected["programs"], self.selected["academic-years"], program["total_semesters"], self.records["semesters"], demo=demo)
            for payload in plans:
                if not self._accept("semesters", self.api.create_academic("semesters", payload)):return False
            self.reconcile()
            rows = self.candidates("semesters")
            if rows:self.selected["semesters"] = record_id(min(rows, key=lambda row: int(row["semester_number"])))
            self.reconcile()
            self.error = None
            if not rows:self.error = "Matching semesters already exist but are inactive. Activate them in the Semesters management screen before continuing."
            return bool(rows)
        finally:self.busy = False

    def save_teaching(self, payload):
        if not self.require_admin() or self.busy or not self.loaded or self.missing("teaching"):return False
        self.busy = True
        try:
            # Always reuse an active matching assignment, including after a partial failure/restart.
            result = self.api.get_faculty(self.selected["faculty"])
            if not result.connected:
                self.error = result.error or "Faculty assignments unavailable."
                return False
            links = {"academic_year_id": self.selected["academic-years"], "class_division_id": self.selected["classes"], "subject_id": self.selected["subjects"]}
            self.assignment = next((row for row in (result.data or {}).get("assignments", []) if row.get("status") == "active" and all(str(row.get(key)) == value for key, value in links.items())), None)
            if not self.assignment:
                result = self.api.create_faculty_assignment(self.selected["faculty"], links)
                if not result.connected:
                    self.error = result.error or "Could not create assignment."
                    return False
                self.assignment = result.data
            timetable_payload = {**payload, "faculty_assignment_id": record_id(self.assignment)}
            listed = self._list("timetable")
            if not listed.connected:
                self.error = listed.error or "Assignment saved. Could not check the timetable; retry to continue."
                return False
            existing = next((row for row in listed.data["items"] if row.get("status") == "active" and
                             str(row.get("faculty_assignment_id")) == timetable_payload["faculty_assignment_id"] and
                             all(str(row.get(key, ""))[:5] == str(payload.get(key, ""))[:5] for key in ("start_time", "end_time")) and
                             all(str(row.get(key, "")).split("T")[0] == str(payload.get(key, "")) for key in ("day_of_week", "effective_from", "effective_until"))), None)
            if existing:self.timetable = existing
            else:
                result = self.api.create_timetable(timetable_payload)
                if not result.connected:
                    self.error = result.error or "Assignment saved. Correct the lecture details and retry."
                    return False
                self.timetable = result.data
            self.error = None
            self.complete = True
            self.drafts.clear()
            return True
        finally:self.busy = False

    def advance(self):
        if not self.require_admin() or not self.loaded:return False
        if self.resource == "teaching":return False
        if self.missing(self.resource):return False
        if not self.chosen(self.resource):return False
        if self.chosen(self.resource).get("status", "active") != "active":
            self.error = "This record is inactive. Activate it before continuing setup."
            return False
        if self.resource == "academic-years" and not self.chosen("academic-years").get("is_current"):
            self.error = "Use this as the current academic year before continuing."
            return False
        self.step = min(9, self.step + 1)
        self.editing = False
        self.creating = False
        self.error = None
        return True
