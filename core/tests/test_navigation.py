import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import translation
from wagtail.models import PageViewRestriction
from wagtail.test.utils.form_data import nested_form_data

from campaigns.models import CampaignIndexPage
from campaigns.tests.factories import DonatePageFactory
from core.brand import DEFAULT_LOGO_SIZE
from core.menu import SECTIONS
from core.models import SiteSettings
from core.tests.test_settings import registered_texts
from home.models import StandardPage
from news.models import NewsIndexPage

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "charity" / "static"


def add_page(parent, title, show_in_menus=True, live=True, page_class=StandardPage):
    page = page_class(title=title, show_in_menus=show_in_menus, live=live)
    parent.add_child(instance=page)
    return page


def choose(site, **pages):
    """Chooses `pages` in Site settings, by field name, as a moderator would."""
    settings = SiteSettings.for_site(site)
    for name, page in pages.items():
        setattr(settings, name, page)
    settings.save()


def menu_html(client, path="/"):
    html = client.get(path).content.decode()
    start = html.index('<nav class="main-nav"')
    return html[start : html.index("</nav>", start)]


def menu_links(client, path="/"):
    """Each link in the menu as (its text, its address, its aria-current)."""
    nav = BeautifulSoup(menu_html(client, path), "html.parser")
    return [(a.get_text(), a["href"], a.get("aria-current")) for a in nav.find_all("a")]


@pytest.fixture
def every_section(site, home_page):
    """A published page chosen for each of the five sections, titled unlike the section."""
    pages = {
        "about_page": add_page(home_page, "Who we are"),
        "appeals_page": add_page(home_page, "Give to a cause", page_class=CampaignIndexPage),
        "stories_page": add_page(home_page, "Latest news", page_class=NewsIndexPage),
        "get_involved_page": add_page(home_page, "Help out"),
        "contact_page": add_page(home_page, "Reach us"),
    }
    choose(site, **pages)
    return pages


class TestMenuSections:
    """The menu is the standard's five sections, in its order and with its names (#171)."""

    def test_shows_the_five_sections_in_order_named_by_the_standard(self, client, every_section):
        links = menu_links(client)

        assert [(text, href) for text, href, _current in links] == [
            ("About us", every_section["about_page"].url),
            ("Appeals", every_section["appeals_page"].url),
            ("Stories", every_section["stories_page"].url),
            ("Get involved", every_section["get_involved_page"].url),
            ("Contact", every_section["contact_page"].url),
        ]

    def test_pages_ticked_show_in_menus_arent_added(self, client, home_page, every_section):
        add_page(home_page, "Our own page")

        assert "Our own page" not in menu_html(client)

    def test_a_section_not_set_is_left_out_and_the_others_keep_their_order(
        self, client, site, home_page
    ):
        stories = add_page(home_page, "Latest news", page_class=NewsIndexPage)
        about = add_page(home_page, "Who we are")
        choose(site, stories_page=stories, about_page=about)

        assert [text for text, _href, _current in menu_links(client)] == ["About us", "Stories"]

    def test_a_section_whose_page_isnt_published_is_left_out(self, client, site, home_page):
        choose(site, about_page=add_page(home_page, "Who we are"))
        choose(site, contact_page=add_page(home_page, "Reach us", live=False))

        assert [text for text, _href, _current in menu_links(client)] == ["About us"]

    def test_a_section_whose_page_is_behind_a_password_is_left_out(self, client, site, home_page):
        about = add_page(home_page, "Who we are")
        contact = add_page(home_page, "Reach us")
        PageViewRestriction.objects.create(
            page=contact, restriction_type=PageViewRestriction.PASSWORD, password="secret"
        )
        choose(site, about_page=about, contact_page=contact)

        assert [text for text, _href, _current in menu_links(client)] == ["About us"]

    def test_a_section_under_a_page_behind_a_login_is_left_out(self, client, site, home_page):
        about = add_page(home_page, "Who we are")
        private = add_page(home_page, "Members")
        PageViewRestriction.objects.create(page=private, restriction_type=PageViewRestriction.LOGIN)
        choose(site, about_page=about, contact_page=add_page(private, "Reach us"))

        assert [text for text, _href, _current in menu_links(client)] == ["About us"]

    def test_no_menu_at_all_while_no_section_is_set(self, client, home_page):
        assert '<nav class="main-nav"' not in client.get("/").content.decode()

    def test_marks_the_current_page(self, client, every_section):
        about = every_section["about_page"]

        assert ("About us", about.url, "page") in menu_links(client, about.url)

    def test_marks_the_section_containing_the_current_page(self, client, every_section):
        about = every_section["about_page"]
        team = add_page(about, "Our team", show_in_menus=False)

        links = menu_links(client, team.url)

        assert ("About us", about.url, "true") in links
        assert ("Appeals", every_section["appeals_page"].url, None) in links

    def test_nepali_readers_get_the_nepali_names_and_pages(
        self, client, every_section, nepali_home_page
    ):
        about = every_section["about_page"]
        hamro_barema = about.copy_for_translation(nepali_home_page.locale)
        hamro_barema.save_revision().publish()

        links = menu_links(client, "/ne/")

        assert links[0] == ("हाम्रो बारेमा", hamro_barema.url, None)
        assert [text for text, _href, _current in links] == [
            "हाम्रो बारेमा",
            "सहयोग अपिल",
            "कथाहरू",
            "सहभागी हुनुहोस्",
            "सम्पर्क",
        ]

    def test_without_a_published_translation_links_to_the_chosen_page(
        self, client, every_section, nepali_home_page
    ):
        about = every_section["about_page"]
        draft = about.copy_for_translation(nepali_home_page.locale)
        draft.save_revision()

        assert ("हाम्रो बारेमा", about.url, None) in menu_links(client, "/ne/")

    def test_with_a_translation_behind_a_login_links_to_the_chosen_page(
        self, client, every_section, nepali_home_page
    ):
        about = every_section["about_page"]
        hamro_barema = about.copy_for_translation(nepali_home_page.locale)
        hamro_barema.save_revision().publish()
        PageViewRestriction.objects.create(
            page=hamro_barema, restriction_type=PageViewRestriction.LOGIN
        )

        assert ("हाम्रो बारेमा", about.url, None) in menu_links(client, "/ne/")

    def test_a_section_is_left_out_in_every_language_while_its_chosen_page_isnt_published(
        self, client, site, home_page, nepali_home_page
    ):
        """As the Menu tab says, which reads only the chosen page."""
        about = add_page(home_page, "Who we are")
        hamro_barema = about.copy_for_translation(nepali_home_page.locale)
        hamro_barema.save_revision().publish()
        about.unpublish()
        choose(site, about_page=about, contact_page=add_page(home_page, "Reach us"))

        assert [text for text, _href, _current in menu_links(client, "/ne/")] == ["सम्पर्क"]


def test_the_sections_are_the_standards_in_its_order_and_names():
    """The menu drifts from `docs/site/standard.md`'s table of sections only if this fails."""
    standard = (ROOT / "docs" / "site" / "standard.md").read_text(encoding="utf-8")
    table = standard.split("## The menu")[1].split("\n\n")[2]
    rows = [re.split(r"\s*\|\s*", line.strip("| ")) for line in table.splitlines()[2:]]
    in_the_standard = [(name, nepali) for name, nepali, _holds in rows if "Donate" not in name]

    with translation.override("ne"):
        nepali_names = [str(section.name) for section in SECTIONS]
    with translation.override("en"):
        names = [str(section.name) for section in SECTIONS]

    assert list(zip(names, nepali_names, strict=True)) == in_the_standard


class TestMenuInTheAdmin:
    """Site settings → Menu: a page for each section, and what the menu leaves out."""

    def url(self, site):
        return reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

    def save(self, client, moderator, site, **pages):
        client.force_login(moderator)
        form = {
            "currency": "NPR",
            "phone_country": "NP",
            "main_colour": SiteSettings.for_site(site).main_colour,
            "accent_colour": SiteSettings.for_site(site).accent_colour,
            "name_bar_style": "dark",
            "logo_size": DEFAULT_LOGO_SIZE,
            "footer_style": "dark",
            "font_style": "modern",
            "texts": registered_texts(site),
            **{name: page.pk for name, page in pages.items()},
        }
        return client.post(self.url(site), nested_form_data(form))

    def errors(self, response):
        return response.context["form"].errors

    def test_moderator_chooses_a_page_for_each_section(self, client, moderator, site, home_page):
        pages = {
            "about_page": add_page(home_page, "Who we are"),
            "appeals_page": add_page(home_page, "Appeals", page_class=CampaignIndexPage),
            "stories_page": add_page(home_page, "Stories", page_class=NewsIndexPage),
            "get_involved_page": add_page(home_page, "Help out"),
            "contact_page": add_page(home_page, "Reach us"),
        }

        response = self.save(client, moderator, site, **pages)

        assert response.status_code == 302
        settings = SiteSettings.for_site(site)
        assert {name: getattr(settings, f"{name}_id") for name in pages} == {
            name: page.pk for name, page in pages.items()
        }

    def test_the_same_page_cant_be_two_sections(self, client, moderator, site, home_page):
        page = add_page(home_page, "Who we are")

        response = self.save(client, moderator, site, about_page=page, contact_page=page)

        assert response.status_code == 200
        # On both sections, so the editor sees which two clash and chooses which keeps it.
        wanted = [
            "About us and Contact link to the same page. Keep it on one and choose another page "
            "for the other."
        ]
        assert self.errors(response)["about_page"] == wanted
        assert self.errors(response)["contact_page"] == wanted

    def test_a_page_in_three_sections_names_all_three(self, client, moderator, site, home_page):
        page = add_page(home_page, "Who we are")

        response = self.save(
            client, moderator, site, about_page=page, get_involved_page=page, contact_page=page
        )

        wanted = [
            "About us, Get involved and Contact link to the same page. Keep it on one and choose "
            "other pages for the others."
        ]
        errors = self.errors(response)
        assert errors["about_page"] == errors["get_involved_page"] == errors["contact_page"]
        assert errors["contact_page"] == wanted

    def test_the_admin_names_sections_in_english_on_a_site_that_opens_in_nepali(
        self, client, moderator, site, home_page, settings
    ):
        """Production opens in Nepali, but the admin stays in English (`languages.md`)."""
        settings.LANGUAGE_CODE = "ne"
        page = add_page(home_page, "Who we are")

        response = self.save(client, moderator, site, about_page=page, contact_page=page)

        assert self.errors(response)["contact_page"] == [
            "About us and Contact link to the same page. Keep it on one and choose another page "
            "for the other."
        ]
        choose(site, about_page=page)
        assert "Not set: Appeals, Stories, Get involved and Contact." in self.menu_tab(
            client, moderator, site
        )

    def test_a_page_and_its_translation_cant_be_two_sections(
        self, client, moderator, site, home_page, nepali_home_page
    ):
        page = add_page(home_page, "Who we are")
        hamro_barema = page.copy_for_translation(nepali_home_page.locale)

        response = self.save(
            client, moderator, site, about_page=page, get_involved_page=hamro_barema
        )

        assert response.status_code == 200
        wanted = [
            "About us and Get involved link to the same page. Keep it on one and choose another "
            "page for the other."
        ]
        assert self.errors(response)["about_page"] == wanted
        assert self.errors(response)["get_involved_page"] == wanted

    def test_the_home_page_cant_be_a_section(self, client, moderator, site, home_page):
        response = self.save(client, moderator, site, about_page=home_page)

        assert response.status_code == 200
        assert self.errors(response)["about_page"] == [
            "Choose a page under the home page: the site's name links to it already."
        ]

    @pytest.mark.parametrize(
        "field, wanted",
        [
            ("appeals_page", "Choose the appeals page: Appeals lists its appeals."),
            ("stories_page", "Choose the stories page: Stories lists its stories."),
            ("donate_page", "Choose the Donate page: it holds the pledge form."),
        ],
    )
    def test_appeals_stories_and_donate_take_only_their_own_kind_of_page(
        self, client, moderator, site, home_page, field, wanted
    ):
        response = self.save(client, moderator, site, **{field: add_page(home_page, "Other")})

        assert response.status_code == 200
        assert wanted in str(self.errors(response).get(field))

    def test_donate_takes_the_donate_page(self, client, moderator, site, home_page):
        donate = DonatePageFactory(parent=home_page)

        assert self.save(client, moderator, site, donate_page=donate).status_code == 302

    def test_each_chooser_offers_only_the_kind_of_page_it_takes(self):
        fields = SiteSettings.edit_handler.bind_to_model(SiteSettings).get_form_class().base_fields

        def offered(name):
            return [model._meta.label_lower for model in fields[name].widget.target_models]

        assert offered("appeals_page") == ["campaigns.campaignindexpage"]
        assert offered("stories_page") == ["news.newsindexpage"]
        assert offered("donate_page") == ["campaigns.donatepage"]
        assert offered("about_page") == ["wagtailcore.page"]

    def menu_tab(self, client, moderator, site):
        client.force_login(moderator)
        soup = BeautifulSoup(client.get(self.url(site)).content, "html.parser")
        return soup.select_one("#tab-menu").get_text(" ", strip=True)

    def test_the_menu_tab_names_the_sections_not_set(self, client, moderator, site, home_page):
        choose(site, about_page=add_page(home_page, "Who we are"))

        tab = self.menu_tab(client, moderator, site)

        assert (
            "Not set: Appeals, Stories, Get involved and Contact. The menu leaves them out until "
            "you choose a published page for each."
        ) in tab

    def test_the_menu_tab_names_the_sections_not_published(
        self, client, moderator, site, every_section
    ):
        contact = every_section["contact_page"]
        contact.unpublish()
        PageViewRestriction.objects.create(
            page=every_section["about_page"], restriction_type=PageViewRestriction.LOGIN
        )

        tab = self.menu_tab(client, moderator, site)

        assert "Not set" not in tab
        assert "Not published: Contact. The menu leaves it out until it's published." in tab
        assert (
            "Not public: About us. The menu leaves it out while it's behind a password or a login."
        ) in tab

    def test_the_menu_tab_names_the_saved_menu_after_a_refused_save(
        self, client, moderator, site, home_page
    ):
        choose(site, about_page=add_page(home_page, "Who we are"))

        response = self.save(client, moderator, site, contact_page=home_page)

        assert self.errors(response)["contact_page"]
        tab = BeautifulSoup(response.content, "html.parser").select_one("#tab-menu")
        assert "Not set: Appeals, Stories, Get involved and Contact." in tab.get_text(
            " ", strip=True
        )

    def test_the_menu_tab_says_nothing_when_every_section_is_shown(
        self, client, moderator, site, every_section
    ):
        tab = self.menu_tab(client, moderator, site)

        assert "Not set" not in tab and "Not published" not in tab and "Not public" not in tab


def header_html(client, path="/"):
    html = client.get(path).content.decode()
    start = html.index('<header class="site-header"')
    return html[start : html.index("</header>", start)]


def test_header_has_a_menu_button_that_controls_the_menu(client, home_page):
    header = header_html(client)

    assert (
        '<button class="menu-toggle" type="button" aria-expanded="false" '
        'aria-controls="site-menu">Menu</button>'
    ) in header


def test_menu_is_collapsed_before_the_page_is_first_drawn(client, home_page):
    """Collapsing the menu after the page appears would move everything below the header up.

    charity.js runs at the end of the body, often after the browser has drawn the page once. So a
    script in <head> marks the page as having JavaScript before anything is drawn, and the CSS
    collapses the menu and shows its button from that mark. Without JavaScript there's no mark, so
    the menu stays open and there's no button that does nothing.
    """
    html = client.get("/").content.decode()
    head = html[: html.index("</head>")]
    stylesheet = (STATIC / "css" / "charity.css").read_text(encoding="utf-8")

    # Before the stylesheet, so the script doesn't have to wait for it to download.
    assert head.index('document.documentElement.classList.add("js")') < head.index(
        'rel="stylesheet"'
    )
    assert '.js .menu-toggle[aria-expanded="false"] + .site-menu' in stylesheet


def test_menu_reopens_if_its_script_fails_to_download(client, home_page):
    """Otherwise phones would get a collapsed menu and a Menu button that does nothing."""
    html = client.get("/").content.decode()

    script = html[html.index('<script src="/static/js/charity') :]
    assert "onerror=\"document.documentElement.classList.remove('js')\"" in script.split(">")[0]


def test_menu_button_opens_both_the_menu_and_the_search(client, every_section):
    header = header_html(client)
    site_menu = header[header.index('id="site-menu"') :]

    assert '<nav class="main-nav"' in site_menu
    assert 'role="search"' in site_menu


def test_donate_button_stays_outside_the_collapsible_menu(client, home_page, site):
    donate = add_page(home_page, "Donate", show_in_menus=False)
    settings = SiteSettings.for_site(site)
    settings.donate_page = donate
    settings.save()

    header = header_html(client)

    # The search form is the last thing in the collapsible menu.
    assert header.index('class="button"') > header.index("</form>")


def test_site_name_links_to_the_home_page_in_the_language_being_read(
    client, home_page, nepali_home_page
):
    # The name is written in the main language (English in tests), so it keeps lang="en".
    assert '<a class="brand" href="/" lang="en">' in header_html(client, "/")
    assert '<a class="brand" href="/ne/" lang="en">' in header_html(client, "/ne/")
