from __future__ import annotations

import pytest
from pytest_bdd import scenarios


pytest_plugins = ["tests.e2e.linux_fixtures", "tests.e2e.linux_steps"]

pytestmark = [pytest.mark.e2e, pytest.mark.linux]

scenarios("main_window_linux.feature")

