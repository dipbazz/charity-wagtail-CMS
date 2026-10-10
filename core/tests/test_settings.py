import pytest
from django.urls import reverse
from wagtail.models import Locale, Site
from wagtail.test.utils.form_data import inline_formset, nested_form_data

from core.brand import DEFAULT_ACCENT, DEFAULT_MAIN
from core.models import AnnouncementBanner, AnnouncementBannerText, SiteSettings, SiteSettingsText
from home.models import StandardPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_settings(site):
    settings = SiteSettings.for_site(site)
    settings.charity_number = "1234567"
    settings.contact_email = "hello@brightwell.example"
    settings.instagram_url = "https://instagram.example/brightwell"
    settings.save()
    return settings


def test_footer_shows_charity_details_from_site_settings(client, home_page, site_settings):
    html = client.get("/").content.decode()

    assert "Registered charity number 1234567" in html
    assert 'href="mailto:hello@brightwell.example"' in html
    assert 'href="https://instagram.example/brightwell"' in html


def test_header_donate_button_links_to_the_chosen_donate_page(client, home_page, site_settings):
    donate = StandardPage(title="Donate", slug="donate")
    home_page.add_child(instance=donate)
    site_settings.donate_page = donate
    site_settings.save()

    html = client.get("/").content.decode()

    assert f'class="button" href="{donate.url}"' in html


def test_header_donate_button_on_a_nepali_page_links_to_the_nepali_donate_page(
    client, home_page, nepali_home_page, nepali_locale, site_settings
):
    donate = add_page(home_page, title="Donate", slug="donate")
    nepali_donate = donate.copy_for_translation(nepali_locale)
    nepali_donate.save_revision().publish()
    site_settings.donate_page = donate
    site_settings.save()

    html = client.get("/ne/").content.decode()

    assert f'class="button" href="{nepali_donate.url}"' in html


def test_header_donate_button_links_to_the_main_donate_page_until_it_is_translated(
    client, home_page, nepali_home_page, site_settings
):
    donate = add_page(home_page, title="Donate", slug="donate")
    site_settings.donate_page = donate
    site_settings.save()

    html = client.get("/ne/").content.decode()

    assert f'class="button" href="{donate.url}"' in html


class TestFooterAddress:
    def test_footer_shows_the_address(self, client, home_page, site_settings):
        add_texts(site_settings, english="1 Example Street\nBirmingham")

        assert "1 Example Street<br>Birmingham" in client.get("/").content.decode()

    def test_nepali_page_shows_the_nepali_address(self, client, nepali_home_page, site_settings):
        add_texts(site_settings, english="1 Example Street", nepali="1 एक्जाम्पल स्ट्रिट")

        assert "1 एक्जाम्पल स्ट्रिट" in client.get("/ne/").content.decode()
        assert "1 Example Street" in client.get("/").content.decode()

    def test_nepali_page_shows_the_main_address_until_it_is_translated(
        self, client, nepali_home_page, site_settings
    ):
        add_texts(site_settings, english="1 Example Street", nepali="")

        assert "1 Example Street" in client.get("/ne/").content.decode()


def test_no_donate_button_without_a_donate_page(client, home_page, site_settings):
    assert 'class="button" href=' not in client.get("/").content.decode()


class TestPrivacyNoticeLink:
    def test_footer_links_to_the_chosen_privacy_notice(self, client, privacy_notice):
        html = client.get("/").content.decode()

        assert f'<a href="{privacy_notice.url}">Privacy notice</a>' in html

    def test_no_link_without_a_privacy_notice(self, client, home_page):
        assert "Privacy notice" not in client.get("/").content.decode()

    def test_no_link_to_an_unpublished_privacy_notice(self, client, privacy_notice):
        privacy_notice.unpublish()

        assert "Privacy notice" not in client.get("/").content.decode()

    def test_nepali_page_links_to_the_nepali_privacy_notice(
        self, client, privacy_notice, nepali_home_page, nepali_locale
    ):
        translation = privacy_notice.copy_for_translation(nepali_locale)
        translation.save_revision().publish()

        html = client.get("/ne/").content.decode()

        assert f'<a href="{translation.url}">गोपनीयता सूचना</a>' in html

    def test_nepali_page_links_to_the_main_notice_until_it_is_translated(
        self, client, privacy_notice, nepali_home_page
    ):
        html = client.get("/ne/").content.decode()

        assert f'<a href="{privacy_notice.url}">गोपनीयता सूचना</a>' in html


class TestAnnouncementBanner:
    def test_hidden_by_default(self, client, home_page):
        assert "announcement" not in client.get("/").content.decode()

    def test_shown_on_every_page_when_enabled(self, client, home_page):
        show_banner(home_page.get_site(), "Emergency appeal: flood relief")

        html = client.get("/").content.decode()

        assert 'class="announcement"' in html
        assert "Emergency appeal: flood relief" in html

    def test_nepali_page_shows_the_nepali_message(self, client, nepali_home_page):
        show_banner(
            nepali_home_page.get_site(),
            "Emergency appeal: flood relief",
            nepali="आपतकालीन अपिल: बाढी राहत",
        )

        assert "आपतकालीन अपिल: बाढी राहत" in client.get("/ne/").content.decode()
        assert "Emergency appeal: flood relief" in client.get("/").content.decode()

    def test_nepali_page_shows_the_main_message_until_it_is_translated(
        self, client, nepali_home_page
    ):
        show_banner(nepali_home_page.get_site(), "Emergency appeal: flood relief")

        assert "Emergency appeal: flood relief" in client.get("/ne/").content.decode()

    def test_links_to_the_nepali_translation_of_its_page_on_a_nepali_page(
        self, client, home_page, nepali_home_page, nepali_locale
    ):
        appeal = add_page(home_page, title="Flood relief", slug="flood-relief")
        nepali_appeal = appeal.copy_for_translation(nepali_locale)
        nepali_appeal.save_revision().publish()
        show_banner(home_page.get_site(), "Flood relief", link_page=appeal)

        assert f'href="{nepali_appeal.url}"' in client.get("/ne/").content.decode()
        assert f'href="{appeal.url}"' in client.get("/").content.decode()

    def test_links_to_the_main_page_until_it_is_translated(
        self, client, home_page, nepali_home_page
    ):
        appeal = add_page(home_page, title="Flood relief", slug="flood-relief")
        show_banner(home_page.get_site(), "Flood relief", link_page=appeal)

        assert f'href="{appeal.url}"' in client.get("/ne/").content.decode()

    def test_each_site_has_its_own_banner(self, site, home_page):
        other = Site.objects.create(hostname="other.example", root_page=home_page)
        show_banner(site, "Flood relief")

        assert not AnnouncementBanner.for_site(other).enabled


class TestTextInEachLanguageInTheAdmin:
    def banner_form(self, *texts):
        return nested_form_data(
            {
                "enabled": "on",
                "link_page": "",
                "texts": inline_formset(
                    [{"locale": locale.pk, "message": message} for locale, message in texts]
                ),
            }
        )

    def test_editor_writes_the_banner_in_both_languages(self, client, editor, site, nepali_locale):
        client.force_login(editor)
        url = reverse("wagtailsettings:edit", args=["core", "announcementbanner", site.pk])

        response = client.post(
            url,
            self.banner_form(
                (Locale.get_default(), "Flood appeal: give now"),
                (nepali_locale, "बाढी अपिल: अहिले सहयोग गर्नुहोस्"),
            ),
        )

        assert response.status_code == 302
        banner = AnnouncementBanner.for_site(site)
        assert banner.enabled
        assert sorted(banner.texts.values_list("message", flat=True)) == [
            "Flood appeal: give now",
            "बाढी अपिल: अहिले सहयोग गर्नुहोस्",
        ]

    def test_one_message_per_language(self, client, editor, site):
        client.force_login(editor)
        url = reverse("wagtailsettings:edit", args=["core", "announcementbanner", site.pk])
        english = Locale.get_default()

        response = client.post(
            url, self.banner_form((english, "Flood appeal"), (english, "Second message"))
        )

        assert response.status_code == 200
        assert not AnnouncementBanner.for_site(site).texts.exists()

    def test_moderator_writes_the_address_in_each_language(
        self, client, moderator, site, nepali_locale
    ):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
        form = nested_form_data(
            {
                "currency": "NPR",
                "phone_country": "NP",
                "main_colour": DEFAULT_MAIN,
                "accent_colour": DEFAULT_ACCENT,
                "name_bar_style": "dark",
                "footer_style": "dark",
                "texts": inline_formset(
                    [
                        {"locale": Locale.get_default().pk, "address": "1 Example Street"},
                        {"locale": nepali_locale.pk, "address": "1 एक्जाम्पल स्ट्रिट"},
                    ]
                ),
            }
        )

        response = client.post(url, form)

        assert response.status_code == 302
        assert SiteSettings.for_site(site).texts.count() == 2


class TestBrandColours:
    """Site settings → Brand (#133). How shades and contrast are worked out: test_brand.py."""

    def save(self, client, moderator, site, main, accent):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
        form = {
            "currency": "NPR",
            "phone_country": "NP",
            "main_colour": main,
            "accent_colour": accent,
            "name_bar_style": "dark",
            "footer_style": "dark",
            "texts": inline_formset([]),
        }
        return client.post(url, nested_form_data(form))

    def test_moderator_chooses_the_brand_colours(self, client, moderator, site):
        response = self.save(client, moderator, site, "#8e1b3b", "#1f6feb")

        assert response.status_code == 302
        site_settings = SiteSettings.for_site(site)
        assert (site_settings.main_colour, site_settings.accent_colour) == ("#8e1b3b", "#1f6feb")

    def test_a_main_colour_too_light_to_read_cant_be_saved(self, client, moderator, site):
        response = self.save(client, moderator, site, "#f2b134", DEFAULT_ACCENT)

        assert response.status_code == 200
        assert "Too light to read easily" in response.content.decode()
        assert SiteSettings.for_site(site).main_colour == DEFAULT_MAIN

    def test_an_accent_colour_no_text_is_readable_on_cant_be_saved(self, client, moderator, site):
        response = self.save(client, moderator, site, DEFAULT_MAIN, "#0077dd")

        assert response.status_code == 200
        assert "Neither dark nor white text is easy to read" in response.content.decode()
        assert SiteSettings.for_site(site).accent_colour == DEFAULT_ACCENT

    def test_the_colours_are_chosen_with_colour_pickers(self, client, moderator, site):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

        assert client.get(url).content.decode().count('type="color"') == 2

    def test_a_site_that_hasnt_chosen_keeps_the_stylesheets_colours(self, client, home_page):
        assert "--colour-primary" not in client.get("/").content.decode()

    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/about/",
            "/appeals/",
            "/appeals/flood-relief/",
            "/stories/",
            "/donate/",
            "/volunteer/",
            "/search/?query=water",
            "/ne/",
            "/ne/donate/",
            "/no-such-page/",
        ],
    )
    def test_every_page_uses_the_chosen_colours(self, client, demo_site, path):
        site_settings = SiteSettings.for_site(demo_site)
        site_settings.main_colour = "#8e1b3b"
        site_settings.accent_colour = "#1f6feb"
        site_settings.save()

        html = client.get(path).content.decode()

        assert "<style>:root { --colour-primary:#8e1b3b;" in html
        assert "--colour-accent:#1f6feb;" in html


class TestHeaderAndFooter:
    """Site settings → Brand → Header and footer (#134): a light or dark name bar and footer.

    That every combination keeps its text readable: test_brand.py and test_demo_layout_browser.py.
    """

    def save(self, client, moderator, site, name_bar, footer):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
        form = {
            "currency": "NPR",
            "phone_country": "NP",
            "main_colour": DEFAULT_MAIN,
            "accent_colour": DEFAULT_ACCENT,
            "name_bar_style": name_bar,
            "footer_style": footer,
            "texts": inline_formset([]),
        }
        return client.post(url, nested_form_data(form))

    def test_moderator_chooses_a_light_name_bar_and_a_dark_footer(self, client, moderator, site):
        response = self.save(client, moderator, site, "light", "dark")

        assert response.status_code == 302
        site_settings = SiteSettings.for_site(site)
        assert (site_settings.name_bar_style, site_settings.footer_style) == ("light", "dark")

    def test_each_is_a_choice_of_light_or_dark(self, client, moderator, site):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

        html = client.get(url).content.decode()

        for field in ("name_bar_style", "footer_style"):
            assert html.count(f'type="radio" name="{field}"') == 2

    @pytest.mark.parametrize("field", ["name_bar_style", "footer_style"])
    def test_each_choice_says_where_the_main_colour_goes(self, field):
        """So choosing light doesn't look like losing the colour chosen above it."""
        labels = [label for _, label in SiteSettings._meta.get_field(field).choices]

        assert len(labels) == 2
        assert all("main colour" in label for label in labels)

    def test_a_site_that_hasnt_chosen_keeps_its_dark_name_bar_and_footer(self, client, home_page):
        html = client.get("/").content.decode()

        assert '<div class="brand-bar">' in html
        assert '<footer class="site-footer">' in html

    def test_the_name_bar_and_footer_are_chosen_separately(self, client, site, home_page):
        site_settings = SiteSettings.for_site(site)
        site_settings.footer_style = "light"
        site_settings.save()

        html = client.get("/").content.decode()

        assert '<div class="brand-bar">' in html
        assert '<footer class="site-footer is-light">' in html

    @pytest.mark.parametrize("path", ["/", "/donate/", "/ne/", "/ne/donate/", "/no-such-page/"])
    def test_every_page_has_the_chosen_name_bar_and_footer(self, client, demo_site, path):
        site_settings = SiteSettings.for_site(demo_site)
        site_settings.name_bar_style = "light"
        site_settings.footer_style = "light"
        site_settings.save()

        html = client.get(path).content.decode()

        assert '<div class="brand-bar is-light">' in html
        assert '<footer class="site-footer is-light">' in html


class TestTabsAfterARefusedSave:
    """A refused save opens the tab with the mistake in it, not always the first tab.

    In a real browser: test_settings_browser.py.
    """

    def save(self, client, moderator, site, **changes):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
        form = {
            "currency": "NPR",
            "phone_country": "NP",
            "main_colour": DEFAULT_MAIN,
            "accent_colour": DEFAULT_ACCENT,
            "name_bar_style": "dark",
            "footer_style": "dark",
            "texts": inline_formset([]),
            **changes,
        }
        return client.post(url, nested_form_data(form))

    def test_a_refused_brand_colour_opens_the_brand_tab(self, client, moderator, site):
        response = self.save(client, moderator, site, main_colour="#f2b134")

        assert response.status_code == 200
        assert 'data-w-tabs-active-panel-id-value="tab-brand"' in response.content.decode()

    def test_a_mistake_on_the_organisation_tab_opens_that_tab(self, client, moderator, site):
        response = self.save(client, moderator, site, contact_email="not an email address")

        assert response.status_code == 200
        assert 'data-w-tabs-active-panel-id-value="tab-organisation"' in response.content.decode()

    def test_opening_site_settings_starts_on_the_first_tab(self, client, moderator, site):
        client.force_login(moderator)
        url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

        assert "data-w-tabs-active-panel-id-value" not in client.get(url).content.decode()


class TestPreview:
    """Seeing unsaved Site settings on real pages before saving them (#136).

    Wagtail's preview panel sends the form to the preview address, then shows what that address
    renders with it. In a real browser: test_settings_browser.py. Who can preview:
    test_permissions.py.
    """

    def preview(self, client, user, site, mode="", **changes):
        """What the preview panel shows for Site settings changed by `changes`, unsaved."""
        client.force_login(user)
        url = reverse("wagtailsettings:preview_on_edit", args=["core", "sitesettings", site.pk])
        site_settings = SiteSettings.for_site(site)
        form = {
            "currency": site_settings.currency,
            "phone_country": site_settings.phone_country,
            "donate_page": site_settings.donate_page_id or "",
            "privacy_page": site_settings.privacy_page_id or "",
            "main_colour": site_settings.main_colour,
            "accent_colour": site_settings.accent_colour,
            "name_bar_style": site_settings.name_bar_style,
            "footer_style": site_settings.footer_style,
            "texts": inline_formset([]),
            **changes,
        }
        sent = client.post(url, nested_form_data(form))
        assert sent.json() == {"is_valid": True, "is_available": True}
        return client.get(url, {"mode": mode, "in_preview_panel": "true"})

    def test_site_settings_have_a_preview_panel(self, client, moderator, site):
        client.force_login(moderator)
        edit = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
        preview = reverse("wagtailsettings:preview_on_edit", args=["core", "sitesettings", site.pk])

        assert preview in client.get(edit).content.decode()

    def test_the_home_page_shows_the_unsaved_brand(self, client, moderator, site, home_page):
        response = self.preview(
            client,
            moderator,
            site,
            main_colour="#8e1b3b",
            accent_colour="#1f6feb",
            name_bar_style="light",
            footer_style="light",
        )

        html = response.content.decode()
        assert response.status_code == 200
        assert f"<title>\n            {home_page.title}" in html
        assert "<style>:root { --colour-primary:#8e1b3b;" in html
        assert "--colour-accent:#1f6feb;" in html
        assert '<div class="brand-bar is-light">' in html
        assert '<footer class="site-footer is-light">' in html

    def test_visitors_dont_see_the_preview(self, client, moderator, site, home_page):
        self.preview(client, moderator, site, main_colour="#8e1b3b", name_bar_style="light")

        assert SiteSettings.for_site(site).main_colour == DEFAULT_MAIN
        client.logout()
        html = client.get("/").content.decode()
        assert "--colour-primary" not in html
        assert '<div class="brand-bar">' in html

    def test_the_unsaved_address_shows_in_the_footer(self, client, moderator, site, home_page):
        texts = inline_formset([{"locale": Locale.get_default().pk, "address": "2 New Street"}])

        response = self.preview(client, moderator, site, texts=texts)

        assert "2 New Street" in response.content.decode()

    def test_a_colour_that_cant_be_saved_cant_be_previewed(self, client, moderator, site):
        client.force_login(moderator)
        url = reverse("wagtailsettings:preview_on_edit", args=["core", "sitesettings", site.pk])
        form = {
            "currency": "NPR",
            "phone_country": "NP",
            "main_colour": "#f2b134",
            "accent_colour": DEFAULT_ACCENT,
            "name_bar_style": "dark",
            "footer_style": "dark",
            "texts": inline_formset([]),
        }

        assert client.post(url, nested_form_data(form)).json()["is_valid"] is False

    def test_the_pages_to_preview(self, demo_site):
        """A long page (the home page), the Donate form and a page in the other language."""
        modes = SiteSettings.for_site(demo_site).preview_modes

        assert modes == [("", "Home page"), ("donate", "Donate page"), ("ne", "Nepali home page")]

    def test_only_pages_the_site_has(self, demo_site):
        site_settings = SiteSettings.for_site(demo_site)
        site_settings.donate_page = None
        demo_site.root_page.get_translations().unpublish()

        assert site_settings.preview_modes == [("", "Home page")]

    def test_the_donate_page_shows_its_form_in_the_unsaved_brand(
        self, client, moderator, demo_site
    ):
        response = self.preview(client, moderator, demo_site, "donate", accent_colour="#1f6feb")

        html = response.content.decode()
        assert '<form class="pledge-form"' in html
        assert "--colour-accent:#1f6feb;" in html

    def test_the_nepali_home_page_is_in_nepali(self, client, moderator, demo_site):
        response = self.preview(client, moderator, demo_site, "ne", main_colour="#8e1b3b")

        html = response.content.decode()
        assert '<html lang="ne">' in html
        assert "मुख्य सामग्रीमा जानुहोस्" in html
        assert "--colour-primary:#8e1b3b;" in html


def test_site_settings_open_in_the_admin(admin_client, site):
    url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

    assert admin_client.get(url).status_code == 200


def add_page(parent, **fields):
    page = StandardPage(**fields)
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


def show_banner(site, message, nepali=None, link_page=None):
    banner = AnnouncementBanner.for_site(site)
    banner.enabled = True
    banner.link_page = link_page
    banner.texts = [AnnouncementBannerText(locale=Locale.get_default(), message=message)]
    if nepali:
        banner.texts.add(
            AnnouncementBannerText(locale=Locale.objects.get(language_code="ne"), message=nepali)
        )
    banner.save()


def add_texts(site_settings, english, nepali=None):
    site_settings.texts = [SiteSettingsText(locale=Locale.get_default(), address=english)]
    if nepali is not None:
        site_settings.texts.add(
            SiteSettingsText(locale=Locale.objects.get(language_code="ne"), address=nepali)
        )
    site_settings.save()
