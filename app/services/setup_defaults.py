"""Pure suggestions shared by guided and manual academic forms."""
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo


def local_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def academic_year_suggestion(today=None):
    today = today or local_today()
    start = today.year if today.month >= 6 else today.year - 1
    return {"name": f"{start}-{str(start + 1)[-2:]}", "start_date": f"{start}-06-01",
            "end_date": f"{start + 1}-05-31", "status": "active", "is_current": True}


def single_value(options, current=None):
    keys = [str(key) for key, _ in options]
    return str(current) if current is not None and str(current) in keys else keys[0] if len(keys) == 1 else None


def username_suggestion(name):
    return re.sub(r"[^a-z0-9_.-]", "", str(name).strip().casefold().split(" ")[0])[:80]


def employee_id_suggestion(records):
    used = {str(row.get("employee_id", "")).upper() for row in records}
    number = 1
    while f"FAC{number:03d}" in used:
        number += 1
    return f"FAC{number:03d}"


def program_suggestion(code, degree="B.Tech", years=4):
    degree_code = re.sub(r"[^A-Z0-9]", "", degree.upper())
    return {"name": f"{degree} {code}".strip(), "code": f"{degree_code}-{code}"[:20],
            "degree_type": degree, "duration_years": years, "total_semesters": int(years * 2)}


def class_name_suggestion(code, semester_number=1, division="A"):
    year = (int(semester_number) + 1) // 2
    prefix = {1: "FY", 2: "SY", 3: "TY"}.get(year, f"Year {year}")
    return f"{prefix} {code} - {division.strip().upper()}"


def semester_payloads(program_id, year_id, count, existing, *, demo=True):
    """Plan only missing semesters; each keeps the real Program and Year links."""
    used = {int(row["semester_number"]) for row in existing
            if str(row.get("program_id")) == str(program_id) and str(row.get("academic_year_id")) == str(year_id)}
    return [{"program_id": program_id, "academic_year_id": year_id, "semester_number": n,
             "label": f"Semester {n}", "status": "active"}
            for n in range(1, (1 if demo else int(count)) + 1) if n not in used]
