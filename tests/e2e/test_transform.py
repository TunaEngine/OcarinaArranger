from pytest_bdd import scenarios

from tests.e2e.steps import common  # noqa: F401
from tests.e2e.steps import preview_controls  # noqa: F401
from tests.e2e.steps import transform  # noqa: F401

scenarios("transform.feature")
