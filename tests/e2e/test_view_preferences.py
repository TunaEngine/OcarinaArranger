from pytest_bdd import scenarios

from tests.e2e.steps import common  # noqa: F401
from tests.e2e.steps import view_preferences  # noqa: F401

scenarios("view_preferences.feature")
