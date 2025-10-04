from pytest_bdd import scenarios

from tests.e2e.steps import common  # noqa: F401
from tests.e2e.steps import updates_support  # noqa: F401

scenarios("updates_support.feature")
