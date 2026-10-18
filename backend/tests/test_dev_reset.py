from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from backend.scripts.reset_dev_data import verify_target, reset_database


@pytest.mark.parametrize("environment,name,uri", [
    ("production", "attendai_python_dev", "mongodb://127.0.0.1:27017"),
    ("development", "other_database", "mongodb://127.0.0.1:27017"),
    ("development", "attendai_python_dev", "mongodb://example.test:27017"),
])
def test_reset_rejects_ambiguous_or_non_dev_target(environment, name, uri):
    with pytest.raises(ValueError):
        verify_target(SimpleNamespace(app_env=environment, mongodb_database=name, mongodb_uri=uri))


def test_reset_checks_confirmation_before_any_mutation():
    database = Mock(name="database")
    database.name = "attendai_python_dev"
    with pytest.raises(ValueError):
        reset_database(database, {}, {}, "NO")
    assert database.mock_calls == []


def test_reset_accepts_exact_local_development_configuration():
    verify_target(SimpleNamespace(app_env="development", mongodb_database="attendai_python_dev", mongodb_uri="mongodb://127.0.0.1:27017"))
