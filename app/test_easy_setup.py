"""Isolated setup workflow tests. Never connect to the development database."""
from copy import deepcopy
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import Mock

import flet as ft
import msgpack
import pytest
from flet.controls.base_control import BaseControl
from flet.messaging.protocol import configure_encode_object_for_msgpack

from app.components.forms import connect_hierarchy, date_field, time_field
from app.core.design import adapt_view, walk_controls
from app.core.theme import LIGHT
from app.screens.admin.easy_setup import build_easy_setup
from app.screens.admin.faculty import build_faculty_form, build_assignment_form
from app.screens.admin.students import build_student_create_form
from app.screens.admin.timetable import build_timetable_page, TimetablePageState, build_timetable_form
from app.screens.faculty.attendance import build_take_attendance
from app.services.easy_setup import EasySetup, STEPS
from app.services.setup_defaults import academic_year_suggestion, employee_id_suggestion, class_name_suggestion, program_suggestion, single_value
from app.services.api_client import ApiResult
from app.test_management_audit import controller_for, session


class MemoryApi:
    """API-shaped fixture with no HTTP, filesystem persistence, or MongoDB."""
    def __init__(self):
        self.rows={key:[] for key,_,_ in STEPS}
        self.rows["institution"]=[{"_id":"institution","name":"Existing College","code":"COL","status":"active"}]
        self.rows["timetable"]=[]
        self.writes=[]
        self.assignments=[]
        self.fail_timetable=False

    def academic_institution(self):return ApiResult(True,deepcopy(self.rows["institution"][0]))
    def list_academic(self,key,**kwargs):return ApiResult(True,{"items":deepcopy(self.rows[key]),"totalPages":1})
    def list_faculty(self,**kwargs):return self.list_academic("faculty")
    def list_students(self,**kwargs):return self.list_academic("students")
    def list_timetable(self,**kwargs):return self.list_academic("timetable")
    def update_academic_institution(self,payload):
        self.rows["institution"][0].update(payload);return self.academic_institution()
    def create_academic(self,key,payload):
        self.writes.append((key,deepcopy(payload)))
        row={"_id":f"{key}-{len(self.rows[key])+1}","status":"active",**payload}
        self.rows[key].append(row)
        return ApiResult(True,deepcopy(row))
    def update_academic(self,key,identifier,payload):
        row=next(x for x in self.rows[key] if x["_id"]==identifier)
        row.update(payload);return ApiResult(True,deepcopy(row))
    def create_faculty(self,payload):return self.create_academic("faculty",{key:value for key,value in payload.items() if key!="temporary_password"})
    def create_student(self,payload):
        placement={key:value for key,value in payload.items() if key.endswith("_id") or key=="roll_number"}
        return self.create_academic("students",{key:value for key,value in payload.items() if key!="temporary_password"}|{"current_enrollment":placement})
    def get_faculty(self,identifier):return ApiResult(True,{"_id":identifier,"assignments":deepcopy(self.assignments)})
    def create_faculty_assignment(self,identifier,payload):
        row={"_id":f"assignment-{len(self.assignments)+1}","faculty_id":identifier,"status":"active",**payload}
        self.assignments.append(row);return ApiResult(True,deepcopy(row))
    def create_timetable(self,payload):
        if self.fail_timetable:return ApiResult(False,error="Time conflicts with another lecture.")
        return self.create_academic("timetable",payload)


def setup_through_subject():
    api=MemoryApi();state=EasySetup(api,lambda:True);assert state.load();assert state.advance()
    payloads=[academic_year_suggestion(date(2026,10,18)),{"name":"Electronics and Computer Science","code":"ECS"},program_suggestion("ECS")]
    for payload in payloads:
        assert state.save({**payload,**state.placement(state.resource)})
        assert state.advance()
    assert state.resource=="semesters" and state.generate_semesters()
    assert state.advance()
    assert state.save({"name":"FY ECS - A","division":"A","capacity":60,**state.placement("classes")})
    assert state.advance()
    assert state.save({"name":"Programming Fundamentals","code":"ECS101","subject_type":"theory",**state.placement("subjects")})
    return api,state


def setup_people():
    api,state=setup_through_subject();assert state.advance()
    assert state.save({"display_name":"Rashmi Faculty","employee_id":"FAC001","email":"rashmi@example.test","username":"rashmi","temporary_password":"Secret123!",**state.placement("faculty")})
    assert state.advance()
    assert state.save({"display_name":"Student One","admission_number":"ADM001","roll_number":"1","email":"one@example.test","username":"one","temporary_password":"Secret123!","start_date":"2026-10-18",**state.placement("students")})
    assert state.advance()
    return api,state


def view(state,**kwargs):
    def run(operation,advance=False):
        result=operation()
        if result and advance:state.advance()
    return build_easy_setup(state,LIGHT,redraw=Mock(),run=run,go_step=Mock(),dashboard=Mock(),faculty_login=Mock(),**kwargs)


def controls(root):return {x.key:x for x in walk_controls(root) if x.key}


def serialized(root):return msgpack.packb(root,default=configure_encode_object_for_msgpack(BaseControl))


@pytest.mark.parametrize("month",range(1,13))
def test_june_to_may_academic_year(month):
    actual=academic_year_suggestion(date(2027,month,15));start=2026 if month<6 else 2027
    assert actual=={"name":f"{start}-{str(start+1)[-2:]}","start_date":f"{start}-06-01","end_date":f"{start+1}-05-31","status":"active","is_current":True}


def test_resume_reuses_every_existing_record_without_writes():
    api,state=setup_people();writes=len(api.writes)
    resumed=EasySetup(api,lambda:True);assert resumed.load()
    assert len(resumed.selected)==9
    for _ in range(9):assert resumed.advance()
    assert resumed.resource=="teaching" and len(api.writes)==writes
    assert resumed.chosen("students")["display_name"]=="Student One"


def test_duplicate_identifier_is_reported_and_no_duplicate_created():
    api,state=setup_through_subject();state.step=2;state.creating=True
    before=len(api.writes)
    assert not state.save({"name":"Renamed department","code":"ecs"})
    assert "already exists" in state.error and len(api.writes)==before


def test_one_semester_demo_and_all_semesters_are_repeatable():
    api,state=setup_through_subject();state.step=4
    assert len(api.rows["semesters"])==1
    assert state.generate_semesters(True) and len(api.rows["semesters"])==1
    assert state.generate_semesters(False) and len(api.rows["semesters"])==8
    assert state.generate_semesters(False) and len(api.rows["semesters"])==8
    assert all(x["program_id"]==state.selected["programs"] and x["academic_year_id"]==state.selected["academic-years"] for x in api.rows["semesters"])


def test_semester_partial_failure_can_resume_without_repeating_saved_rows():
    api,state=setup_through_subject();state.step=4;original=api.create_academic
    def create(key,payload):
        if key=="semesters" and payload["semester_number"]==4:return ApiResult(False,error="Temporary failure")
        return original(key,payload)
    api.create_academic=create
    assert not state.generate_semesters(False)
    assert len(api.rows["semesters"])==3
    api.create_academic=original
    assert state.generate_semesters(False) and len(api.rows["semesters"])==8


def test_single_option_and_invalid_existing_selection():
    assert single_value([("only","Only")])=="only"
    assert single_value([("one","One"),("two","Two")]) is None
    assert single_value([("one","One")],"stale")=="one"


def test_parent_change_clears_stale_values_and_selects_only_valid_descendants():
    fields={key:ft.Dropdown() for key in ("academic_year_id","department_id","program_id","semester_id","class_division_id")}
    fields["academic_year_id"].options=[ft.DropdownOption(key="year")]
    fields["department_id"].options=[ft.DropdownOption(key="a"),ft.DropdownOption(key="b")]
    fields["department_id"].value="a"
    records={"program_id":[{"_id":"p-a","department_id":"a"},{"_id":"p-b","department_id":"b"}],
             "semester_id":[{"_id":"s-b","program_id":"p-b","academic_year_id":"year"}],
             "class_division_id":[{"_id":"c-b","department_id":"b","program_id":"p-b","semester_id":"s-b","academic_year_id":"year"}]}
    connect_hierarchy(fields,records)
    assert fields["program_id"].value=="p-a" and fields["semester_id"].value is None
    fields["department_id"].value="b";fields["department_id"].on_select(None)
    assert [fields[x].value for x in ("program_id","semester_id","class_division_id")]==["p-b","s-b","c-b"]


def test_creating_new_parent_invalidates_existing_downstream_wizard_choices():
    _,state=setup_people();state.step=2;state.creating=True
    assert state.save({"name":"Computer Engineering","code":"CE"})
    assert state.chosen("departments")["code"]=="CE"
    assert all(not state.selected.get(key) for key in ("programs","semesters","classes","subjects","faculty","students"))
    assert state.advance() and state.resource=="programs"
    assert not state.chosen("programs")


def test_program_class_and_employee_suggestions():
    assert program_suggestion("ECS")=={"name":"B.Tech ECS","code":"BTECH-ECS","degree_type":"B.Tech","duration_years":4,"total_semesters":8}
    assert class_name_suggestion("ECS",1,"b")=="FY ECS - B"
    assert class_name_suggestion("ECS",8,"A")=="Year 4 ECS - A"
    assert employee_id_suggestion([{"employee_id":"FAC001"},{"employee_id":"FAC002"}])=="FAC003"


def test_manual_faculty_and_student_smart_defaults():
    faculty=controls(build_faculty_form(LIGHT,Mock(),Mock(),departments=[{"_id":"dept","name":"ECS"}],existing=[{"employee_id":"FAC001"}]))
    assert faculty["field-department_id"].value=="dept" and faculty["field-employee_id"].value=="FAC002"
    faculty["field-display_name"].value="Rashmi Faculty";faculty["field-display_name"].on_blur(None)
    assert faculty["field-username"].value=="rashmi"
    api,state=setup_people()
    mapping={"academic_year_id":"academic-years","department_id":"departments","program_id":"programs","semester_id":"semesters","class_division_id":"classes"}
    records={key:api.rows[value] for key,value in mapping.items()}
    references={key:[(x["_id"],x.get("name") or x.get("label")) for x in rows] for key,rows in records.items()}
    student=controls(build_student_create_form(LIGHT,Mock(),Mock(),references,records))
    assert all(student[f"field-{key}"].value for key in mapping)
    assert date.fromisoformat(student["field-start_date"].value)


def test_combined_teaching_retries_assignment_and_prefills_timetable():
    api,state=setup_people()
    payload={"day_of_week":"monday","start_time":"10:00","end_time":"11:00","effective_from":"2026-06-01","effective_until":"2027-05-31"}
    api.fail_timetable=True
    assert not state.save_teaching(payload) and not state.complete
    assert len(api.assignments)==1 and "conflicts" in state.error
    api.fail_timetable=False
    assert state.save_teaching(payload) and state.complete and len(api.assignments)==1
    assert api.rows["timetable"][0]["faculty_assignment_id"]==api.assignments[0]["_id"]
    resumed=EasySetup(api,lambda:True);assert resumed.load();resumed.step=9
    assert resumed.save_teaching(payload) and len(api.rows["timetable"])==1 and len(api.assignments)==1


def test_missing_prerequisites_provide_action_instead_of_empty_form():
    state=EasySetup(MemoryApi(),lambda:True);assert state.load();state.step=8
    labels=[x.value for x in walk_controls(view(state)) if isinstance(x,ft.Text)]
    assert any("No Academic Year selected" in x for x in labels)
    assert not any(x.key=="easy-temporary_password" for x in walk_controls(view(state)))


def test_teaching_cannot_complete_while_student_step_is_missing():
    _,state=setup_people();state.selected.pop("students")
    assert "students" in state.missing("teaching")
    assert not state.save_teaching({}) and not state.complete


def test_failed_save_keeps_draft_and_displays_backend_field_error():
    api,state=setup_through_subject();state.step=7
    api.create_faculty=Mock(return_value=ApiResult(False,error="Email already exists.",field_errors={"email":"Choose another email."}))
    root=view(state)
    fields=controls(root)
    for key,value in {"display_name":"Faculty One","email":"used@example.test","username":"one","temporary_password":"Secret123!"}.items():
        fields[f"easy-{key}"].value=value;fields[f"easy-{key}"].on_change(None)
    click(root,"Save & Continue")
    fields=controls(view(state))
    assert state.step==7 and fields["easy-email"].value=="used@example.test"
    assert fields["easy-email"].error=="Choose another email."


@pytest.mark.parametrize("role",["Faculty","Student"])
def test_non_admin_cannot_open_setup_or_make_setup_requests(role):
    controller,_,_=controller_for(role);controller.api_client=Mock()
    controller.open_easy_setup();assert controller.easy_setup is None
    controller.api_client.academic_institution.assert_not_called()
    state=EasySetup(controller.api_client,lambda:False)
    assert not state.load() and not state.save({}) and not state.generate_semesters() and not state.save_teaching({})
    assert not controller.api_client.mock_calls


def test_failed_load_prevents_creation():
    api=MemoryApi();api.list_students=Mock(return_value=ApiResult(False,error="Offline"))
    state=EasySetup(api,lambda:True);assert not state.load()
    state.step=2
    assert not state.save({"name":"ECS","code":"ECS"}) and not api.writes
    assert any(isinstance(x,ft.Text) and x.value=="Offline" for x in walk_controls(view(state)))


def test_active_noncurrent_year_can_be_reused_and_promoted_without_duplicate():
    api=MemoryApi();api.rows["academic-years"]=[{"_id":"year","name":"2026-27","start_date":"2026-06-01","end_date":"2027-05-31","status":"active","is_current":False}]
    state=EasySetup(api,lambda:True);assert state.load();state.step=1
    assert state.selected["academic-years"]=="year" and not state.advance()
    assert state.use_current_year() and state.advance() and state.step==2
    assert len(api.rows["academic-years"])==1 and not api.writes


def test_current_year_preferred_and_multiple_departments_require_choice():
    api=MemoryApi();api.rows["academic-years"]=[{"_id":"old","name":"Old"},{"_id":"current","name":"Current","is_current":True}]
    api.rows["departments"]=[{"_id":"a","name":"A"},{"_id":"b","name":"B"}]
    state=EasySetup(api,lambda:True);assert state.load()
    assert state.selected["academic-years"]=="current" and not state.selected.get("departments")
    state.choose("departments","b");assert state.selected["departments"]=="b"


def test_inactive_saved_record_stays_editable_and_cannot_advance():
    api,state=setup_through_subject();state.step=2;state.editing=True
    assert state.save({"status":"inactive"}) and not state.advance() and state.editing
    assert state.chosen("departments")["status"]=="inactive"
    assert not state.chosen("programs")
    assert state.save({"status":"active"}) and state.advance()


def test_date_and_time_pickers_emit_api_values_and_readable_hints():
    date_input=date_field("Start date","2026-06-01")
    time_input=time_field("Start time","10:00")
    assert date_input.read_only and date_input.helper_text=="01 Jun 2026"
    page=SimpleNamespace(show_dialog=Mock())
    event=SimpleNamespace(control=SimpleNamespace(page=page))
    date_input.suffix.on_click(event)
    picker=page.show_dialog.call_args.args[0];assert isinstance(picker,ft.DatePicker)
    picker.on_change(SimpleNamespace(control=SimpleNamespace(value=datetime(2026,7,2))))
    assert date_input.value=="2026-07-02" and date_input.helper_text=="02 Jul 2026"
    time_input.suffix.on_click(event)
    picker=page.show_dialog.call_args.args[0];assert isinstance(picker,ft.TimePicker)
    picker.on_change(SimpleNamespace(control=SimpleNamespace(value=time(13,30))))
    assert time_input.value=="13:30" and time_input.helper_text=="01:30 PM"


@pytest.mark.parametrize("width",[360,390,430,768,1024,1366])
def test_every_wizard_step_and_completion_serialize_at_target_widths(width):
    _,state=setup_people()
    for step in range(10):
        state.step=step;state.creating=step!=4;state.editing=False
        root=adapt_view(view(state),width,LIGHT)
        assert serialized(root)
        assert isinstance(root,ft.SafeArea)
        assert any(isinstance(x,ft.Column) and x.scroll==ft.ScrollMode.AUTO for x in walk_controls(root))
    state.complete=True
    assert serialized(adapt_view(view(state),width,LIGHT))


def test_segmented_controls_use_lists_and_real_flet_transport_serializes():
    timetable=build_timetable_page(TimetablePageState(),LIGHT,*([Mock()]*5))
    attendance=build_take_attendance(LIGHT,{},[],session(),*([Mock()]*5),on_mode=Mock())
    for root in (timetable,attendance):
        segmented=next(x for x in walk_controls(root) if isinstance(x,ft.SegmentedButton))
        assert isinstance(segmented.selected,list)
        assert serialized(root)


def test_success_discards_temporary_password_draft_and_never_displays_existing_password():
    api,state=setup_people();state.step=7
    state.drafts["faculty"]={"temporary_password":"DoNotPersist!"}
    state.creating=True
    assert state.save({"display_name":"New Faculty","employee_id":"FAC002","email":"new@example.test","username":"new","temporary_password":"DoNotPersist!",**state.placement("faculty")})
    assert "faculty" not in state.drafts
    assert not any(x.key=="easy-temporary_password" for x in walk_controls(view(state)))


def test_manual_assignment_and_timetable_single_option_prefill():
    options={"years":[{"_id":"year","name":"2026-27"}],"classes":[{"_id":"class","academic_year_id":"year","program_id":"program","semester_id":"semester","name":"FY ECS A"}],"subjects":[{"_id":"subject","program_id":"program","semester_id":"semester","name":"Programming"}]}
    fields=controls(build_assignment_form(LIGHT,Mock(),Mock(),options))
    assert [fields[f"field-{key}"].value for key in ("academic_year_id","class_division_id","subject_id")]==["year","class","subject"]
    fields=controls(build_timetable_form(LIGHT,Mock(),Mock(),[{"_id":"faculty","display_name":"Faculty"}],lambda _:[{"_id":"assignment","status":"active"}]))
    assert fields["field-faculty_id"].value=="faculty" and fields["field-faculty_assignment_id"].value=="assignment"


def click(root, label):
    button=next(x for x in walk_controls(root) if isinstance(x,(ft.FilledButton,ft.OutlinedButton,ft.TextButton)) and x.content==label)
    assert not button.disabled
    button.on_click(None)


def test_admin_controller_ui_callbacks_create_entire_demo_and_resume():
    controller,_,host=controller_for("Admin");api=MemoryApi();controller.api_client=api
    controller.open_easy_setup()
    assert controller.active_navigation=="Easy Setup" and controller.easy_setup.loaded
    click(host.content,"Next · Use selected record")
    assert controller.easy_setup.step==1
    # Suggested year needs no typing.
    click(host.content,"Save & Continue")
    for key,value in {"name":"Electronics and Computer Science","code":"ECS"}.items():controls(host.content)[f"easy-{key}"].value=value
    click(host.content,"Save & Continue")
    # Program defaults include a valid name, code, four years, and eight semesters.
    click(host.content,"Save & Continue")
    click(host.content,"Create only Semester 1 for now")
    click(host.content,"Next · Use selected record")
    click(host.content,"Save & Continue")  # Class suggestion.
    controls(host.content)["easy-name"].value="Programming Fundamentals"
    click(host.content,"Save & Continue")
    for key,value in {"display_name":"Rashmi Faculty","email":"rashmi@example.test","username":"rashmi","temporary_password":"Secret123!"}.items():controls(host.content)[f"easy-{key}"].value=value
    click(host.content,"Save & Continue")
    for key,value in {"display_name":"Student One","admission_number":"ADM001","roll_number":"1","email":"student@example.test","username":"student","temporary_password":"Secret123!"}.items():controls(host.content)[f"easy-{key}"].value=value
    click(host.content,"Save & Continue")
    assert controller.easy_setup.step==9
    click(host.content,"Save Teaching Setup")
    assert controller.easy_setup.complete and len(api.assignments)==1 and len(api.rows["timetable"])==1
    assert serialized(host.content)
    assert "Setup Complete" in [x.value for x in walk_controls(host.content) if isinstance(x,ft.Text)]
    # Returning to a new wizard session reuses all nine entities.
    controller.easy_setup=None;controller.open_easy_setup()
    assert len(controller.easy_setup.selected)==9 and len(api.rows["students"])==1
