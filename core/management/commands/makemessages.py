from django.core.management.commands import makemessages

# Folders that hold no text of the site's own. compilemessages walks the whole tree, so without
# these it would also compile the .po files of every installed package in .venv.
IGNORED = [".venv", "docs", "node_modules", "static", "media"]


class Command(makemessages.Command):
    """Django's makemessages, with this repo's folders and .po style as the defaults.

    `makemessages -l ne` then needs no flags (docs/site/languages.md). Any --ignore given on the
    command line is added to the list.
    """

    def add_arguments(self, parser):
        super().add_arguments(parser)
        # A new list per parser: makemessages adds its own patterns to the one it's given.
        parser.set_defaults(ignore_patterns=[*IGNORED], no_location=True, no_wrap=True)
