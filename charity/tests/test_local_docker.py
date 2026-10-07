"""compose.yaml at the root: the live site's Docker image on a developer's computer."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = (ROOT / "compose.yaml").read_text(encoding="utf-8")


def test_it_doesnt_clash_with_runserver():
    ports = re.findall(r'^\s*-\s*"(\d+):\d+"', LOCAL, flags=re.MULTILINE)

    assert ports
    assert "8000" not in ports


def test_it_doesnt_share_containers_or_data_with_the_live_server_config():
    """Both compose files could be run from one machine; their projects must stay apart."""
    deploy = (ROOT / "deploy" / "aws" / "compose.yaml").read_text(encoding="utf-8")

    assert re.search(r"^name: charity-local$", LOCAL, flags=re.MULTILINE)
    assert re.search(r"^name: charity$", deploy, flags=re.MULTILINE)


def test_its_throwaway_secrets_never_reach_the_live_server():
    key = re.search(r"DJANGO_SECRET_KEY: (\S+)", LOCAL)
    deploy = (ROOT / "deploy" / "aws" / "compose.yaml").read_text(encoding="utf-8")

    assert key
    assert key.group(1) not in deploy


def test_it_keeps_the_demo_data_on_a_volume_not_in_the_project_folder():
    """A bind mount of this folder would let it overwrite the developer's runserver database."""
    assert "data:/data" in LOCAL
    assert "./" not in LOCAL.split("volumes:")[1].split("healthcheck:")[0]


def test_the_proxy_image_is_pinned_to_a_digest():
    images = re.findall(r"^\s*image:\s*(\S+)", LOCAL, flags=re.MULTILINE)
    pulled = [image for image in images if image != "charity-web-local"]

    assert pulled
    assert [i for i in pulled if not re.search(r":[\w.-]+@sha256:[0-9a-f]{64}$", i)] == []


def test_the_image_build_ignores_it():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "compose.yaml" in ignored
