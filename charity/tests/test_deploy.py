"""The single-server deployment in deploy/aws/."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "aws"


def test_server_secrets_stay_out_of_the_image():
    """The server's .env holds the secret key; `COPY . .` in the Dockerfile must never see it."""
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "**/.env" in ignored
    assert "deploy/" in ignored


def test_server_secrets_stay_out_of_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in ignored


def test_images_from_docker_hub_are_pinned_to_a_digest():
    """A tag can be pushed again with other contents; a digest names exactly one image."""
    compose = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    images = re.findall(r"^\s*image:\s*(\S+)", compose, flags=re.MULTILINE)
    pulled = [image for image in images if image != "charity-web"]

    assert pulled, "expected the compose file to pull at least the Caddy image"
    pinned = re.compile(r":[\w.-]+@sha256:[0-9a-f]{64}$")
    assert [image for image in pulled if not pinned.search(image)] == []


def test_logs_cant_fill_the_disk():
    """Docker keeps container logs forever by default; the server has a 20 GB disk."""
    compose = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")

    assert "max-size" in compose
    assert "max-file" in compose
