from django.core.management.commands import compilemessages

from .makemessages import IGNORED


class Command(compilemessages.Command):
    """Django's compilemessages, skipping the folders makemessages skips, so it needs no flags."""

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.set_defaults(ignore_patterns=[*IGNORED])
