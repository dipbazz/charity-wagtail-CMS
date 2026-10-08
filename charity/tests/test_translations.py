"""Guards for the site's Nepali text (#116): nothing visible is left unmarked, nothing is
untranslated, and the compiled catalog is the one the .po file describes.

The two catalog checks need GNU gettext (`msgattrib`, `msgfmt`); they skip where it isn't installed
and always run in CI.
"""

import gettext
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest
from django.conf import settings

LOCALE = settings.BASE_DIR / "locale" / "ne" / "LC_MESSAGES"

# Folders whose templates aren't part of the public site, or aren't ours.
NOT_PUBLIC = {".venv", "node_modules", "docs", "static", "media", "previews", "admin"}
# The attributes a visitor, or their screen reader, reads.
READ_ATTRIBUTES = {"aria-label", "placeholder", "title", "alt"}

NOTHING = "\x00"  # stands in for something the template fills in or marks for translation


def templates():
    root = settings.BASE_DIR
    return sorted(
        path
        for path in root.glob("**/templates/**/*.html")
        if not NOT_PUBLIC & set(path.relative_to(root).parts)
    )


def hide_what_is_marked(source):
    """The template with notes, marked text and everything it fills in replaced by NOTHING."""
    source = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "", source, flags=re.DOTALL)
    source = re.sub(r"\{#.*?#\}", "", source)
    # Class names, not words; and a tag whose name is filled in (<{{ value.size }}>) is still a tag.
    source = re.sub(r"\{% block body_class %\}.*?\{% endblock %\}", "", source)
    source = re.sub(r"(</?)\{\{.*?\}\}", r"\1x", source)
    source = re.sub(
        r"\{% blocktrans(?:late)?\b.*?\{% endblocktrans(?:late)? %\}",
        NOTHING,
        source,
        flags=re.DOTALL,
    )
    source = re.sub(r"\{% trans(?:late)?\b.*?%\}", NOTHING, source)
    source = re.sub(r"\{%.*?%\}", "", source)
    return re.sub(r"\{\{.*?\}\}", NOTHING, source)


class UnmarkedText(HTMLParser):
    """Collects the words a visitor would read that no one marked for translation."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []
        self.skipping = 0

    @staticmethod
    def has_words(text):
        return re.search(r"[^\W\d_]", text.replace(NOTHING, "")) is not None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skipping += 1
        for name, value in attrs:
            if name in READ_ATTRIBUTES and value and self.has_words(value):
                self.found.append(f'{name}="{value}"')

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping and self.has_words(data):
            self.found.append(" ".join(data.replace(NOTHING, "").split()))


def unmarked_text(source):
    parser = UnmarkedText()
    parser.feed(hide_what_is_marked(source))
    return parser.found


class TestNoVisibleTextIsLeftUnmarked:
    @pytest.mark.parametrize(
        "path", templates(), ids=lambda path: path.relative_to(settings.BASE_DIR).as_posix()
    )
    def test_template(self, path):
        found = unmarked_text(path.read_text(encoding="utf-8"))

        assert not found, (
            "Visible text that isn't marked for translation. Wrap it in {% translate %} or "
            "{% blocktranslate %}, then run `python manage.py makemessages -l ne` and add the "
            f"Nepali (docs/site/languages.md): {found}"
        )

    def test_the_guard_finds_unmarked_text(self):
        source = """
            {% load i18n %}
            <h1>Welcome</h1>
            <a href="/x/" aria-label="Go home">{% translate "Home" %}</a>
            <input placeholder="Your name">
            <p>{% blocktranslate %}Marked{% endblocktranslate %} but this is not.</p>
        """

        assert unmarked_text(source) == [
            "Welcome",
            'aria-label="Go home"',
            'placeholder="Your name"',
            "but this is not.",
        ]

    def test_the_guard_ignores_what_a_visitor_doesnt_read(self):
        source = """
            {# A note about the page #}
            {% comment %}Another note{% endcomment %}
            <script>document.title = "title"</script>
            <p class="lead" id="intro">{{ page.introduction }} &copy; {% now "Y" %}</p>
            <a href="{% url 'search' %}" aria-label="{% translate "Search" %}">1,500</a>
            <img src="x.jpg" alt="{{ image.title }}">
        """

        assert unmarked_text(source) == []


class TestTheNepaliCatalog:
    def test_every_message_is_translated(self):
        if not shutil.which("msgattrib"):
            pytest.skip("GNU gettext isn't installed")
        po = LOCALE / "django.po"

        untranslated = subprocess.run(
            ["msgattrib", "--untranslated", "--no-obsolete", str(po)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        fuzzy = subprocess.run(
            ["msgattrib", "--only-fuzzy", "--no-obsolete", str(po)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert re.findall(r'^msgid "(.+)"$', untranslated, flags=re.MULTILINE) == []
        assert re.findall(r'^msgid "(.+)"$', fuzzy, flags=re.MULTILINE) == []

    def test_the_compiled_file_matches_the_po_file(self, tmp_path):
        if not shutil.which("msgfmt"):
            pytest.skip("GNU gettext isn't installed")
        compiled_now = tmp_path / "django.mo"
        subprocess.run(
            ["msgfmt", "--check", "-o", str(compiled_now), str(LOCALE / "django.po")],
            check=True,
        )

        def messages(mo):
            with mo.open("rb") as file:
                return gettext.GNUTranslations(file)._catalog

        assert messages(LOCALE / "django.mo") == messages(compiled_now), (
            "locale/ne/LC_MESSAGES/django.mo is out of date: run `python manage.py compilemessages`"
            " and commit it."
        )
