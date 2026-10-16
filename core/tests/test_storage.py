import os
import sys

import pytest
from django.core.files.base import ContentFile

from core.storage import PrivateStorage


def test_a_private_file_has_no_address(tmp_path):
    with pytest.raises(ValueError):
        PrivateStorage(location=tmp_path).url("receipt.png")


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no file modes to check")
def test_only_the_sites_own_user_can_read_it(tmp_path):
    storage = PrivateStorage(location=tmp_path / "receipts")

    name = storage.save("in/receipt.png", ContentFile(b"x"))

    assert os.stat(storage.path(name)).st_mode & 0o777 == 0o600
    assert os.stat(tmp_path / "receipts" / "in").st_mode & 0o777 == 0o700
