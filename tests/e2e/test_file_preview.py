from pytest_bdd import scenarios

from tests.e2e.steps import common  # noqa: F401 - imported for step registration
from tests.e2e.steps import preview  # noqa: F401 - imported for step registration

scenarios("file_preview.feature")
