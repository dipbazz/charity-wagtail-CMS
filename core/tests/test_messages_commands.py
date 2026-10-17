import pytest
from django.core.management import get_commands, load_command_class


def options(name, *args):
    command = load_command_class(get_commands()[name], name)
    return vars(command.create_parser("manage.py", name).parse_args(list(args)))


@pytest.mark.parametrize("name", ["makemessages", "compilemessages"])
def test_skips_the_folders_that_arent_the_sites_own(name):
    ignored = options(name, "-l", "ne")["ignore_patterns"]

    assert {".venv", "docs", "node_modules", "static", "media"} <= set(ignored)


@pytest.mark.parametrize("name", ["makemessages", "compilemessages"])
def test_an_ignore_given_on_the_command_line_is_added(name):
    ignored = options(name, "-l", "ne", "--ignore", "drafts")["ignore_patterns"]

    assert {".venv", "drafts"} <= set(ignored)


def test_makemessages_writes_the_po_file_as_it_is_committed():
    given = options("makemessages", "-l", "ne")

    assert given["no_location"] is True
    assert given["no_wrap"] is True
