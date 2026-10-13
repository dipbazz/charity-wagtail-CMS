"""onboarding/form-script.gs runs inside Google Sheets, so these tests run it in Node against the
fake Apps Script services in form_script_fakes.js, one scenario each.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

FAKES = Path(__file__).with_name("form_script_fakes.js")
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js runs the form script tests")


@pytest.mark.parametrize(
    "scenario",
    [
        "updates an existing tracker in place",
        "never edits the form of the tracker it was copied from",
        "creates the guide on a first run",
    ],
)
def test_form_script(scenario):
    result = subprocess.run(
        [NODE, str(FAKES), scenario], capture_output=True, text=True, encoding="utf-8"
    )

    assert result.returncode == 0, result.stderr
