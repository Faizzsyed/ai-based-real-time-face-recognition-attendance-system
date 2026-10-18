"""Management list responses must never expose raw joined User documents."""

from unittest.mock import Mock

from bson import ObjectId
import pytest

from app.modules.faculty.service import FacultyService
from app.modules.students.service import StudentService


@pytest.mark.parametrize("kind", ["student", "faculty"])
def test_management_list_whitelists_joined_account_and_preserves_tenant_scope(kind):
    institution_id = str(ObjectId())
    user_id = ObjectId()
    account = {"_id": user_id, "username": "demo-account", "status": "active", "password_hash": "must-not-leak", "token_version": 4, "refresh_token_hash": "must-not-leak"}
    profile = {"_id": ObjectId(), "display_name": "Demo Person", "account": account, "accounts": [account]}
    repository = Mock()
    repository.list.return_value = ([profile], 1)
    service = StudentService(students=repository, passwords=Mock()) if kind == "student" else FacultyService(faculty=repository, passwords=Mock())
    result = service.list(institution_id, {"status": "active"}, "", 1, 20)
    repository.list.assert_called_once_with(institution_id, {"status": "active"}, "", 1, 20)
    item = result["items"][0]
    assert item["account"]["username"] == "demo-account"
    assert item["account"]["_id"] == str(user_id)
    assert "accounts" not in item and "must-not-leak" not in str(item)
    assert "password_hash" not in item["account"] and "token_version" not in item["account"]
    assert profile["account"]["password_hash"] == "must-not-leak"  # Do not mutate persistence data.
