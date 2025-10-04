from pytest_bdd import scenarios

from tests.e2e.steps import common  # noqa: F401
from tests.e2e.steps import projects  # noqa: F401

scenarios("projects.feature")
