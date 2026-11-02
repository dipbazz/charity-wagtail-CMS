from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.models import Locale, PageLogEntry, Site
from wagtail.permissions import page_permission_policy

from core.models import SiteSettings
from core.publishing import has_placeholders
from home.standard_site import NEW_SITE_BUILT, STANDARD_PAGES

DONE_LINE_DAYS = 7


@dataclass
class Row:
    title: str
    status: str
    why: str = ""
    edit_url: str | None = None
    settings_url: str | None = None
    translate_url: str | None = None


@dataclass
class Group:
    language: str
    rows: list[Row]


@dataclass
class StillToWrite:
    groups: list[Group] = field(default_factory=list)
    left: int = 0
    total: int = 0
    all_done: bool = False
    add_registration_url: str | None = None


def settings_link(user, site):
    if user.has_perm("core.change_sitesettings"):
        return reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
    return None


def find_page(standard, site, site_settings):
    """The standard page in the site's main language, or None if the site doesn't have it."""
    if standard.setting:
        page = getattr(site_settings, standard.setting)
        return page and page.get_translation_or_none(site.root_page.locale)
    return site.root_page.get_children().filter(slug=standard.slug).first()


def what_is_left(page):
    """Why an existing page still counts as to write: a status, or None if it's done."""
    page = page.specific
    latest = page if page.live else page.get_latest_revision_as_object()
    if has_placeholders(latest):
        return _("Has [Write: …] text")
    return None if page.live else _("Draft")


def row_for_main_page(standard, page, user, site):
    if page is None:
        return Row(
            standard.name,
            _("Not set"),
            standard.why,
            settings_url=settings_link(user, site) if standard.setting else None,
        )
    status = what_is_left(page)
    return status and row_for(standard, page, status, user)


def row_for(standard, page, status, user):
    can_edit = page.permissions_for_user(user).can_edit()
    edit_url = reverse("wagtailadmin_pages:edit", args=[page.pk]) if can_edit else None
    return Row(page.title, status, standard.why, edit_url=edit_url)


def row_in_second_language(standard, main_page, translation, user):
    if translation is not None:
        status = what_is_left(translation)
        return status and row_for(standard, translation, status, user)
    if not main_page.live:
        return Row(main_page.title, _("Translate after publishing"), standard.why)
    translate_url = None
    if user.has_perm("simple_translation.submit_translation"):
        translate_url = reverse("simple_translation:submit_page_translation", args=[main_page.pk])
    return Row(main_page.title, _("Not translated yet"), standard.why, translate_url=translate_url)


def still_to_write(user, site):
    """What's left of the standard on `site`. Nothing's stored: an upgrade adding a standard page,
    or a page being unpublished, brings its row back."""
    site_settings = SiteSettings.for_site(site)
    main = site.root_page.locale
    codes = [code for code, _name in settings.WAGTAIL_CONTENT_LANGUAGES]
    others = [locale for locale in Locale.objects.filter(language_code__in=codes) if locale != main]

    pages = [(standard, find_page(standard, site, site_settings)) for standard in STANDARD_PAGES]
    main_rows = [row_for_main_page(standard, page, user, site) for standard, page in pages]
    groups = [Group(main.get_display_name(), [row for row in main_rows if row])]
    translations = []
    for locale in others:
        found = [
            (standard, page, page.get_translation_or_none(locale))
            for standard, page in pages
            if page is not None
        ]
        translations += [translation for _standard, _page, translation in found]
        rows = [row_in_second_language(*each, user) for each in found]
        groups.append(Group(locale.get_display_name(), [row for row in rows if row]))

    add_registration_url = None
    if not site_settings.charity_number.strip():
        add_registration_url = settings_link(user, site) or ""
    groups = [group for group in groups if group.rows]
    return StillToWrite(
        groups=groups,
        left=sum(len(group.rows) for group in groups),
        total=len(STANDARD_PAGES) * (1 + len(others)),
        all_done=not groups
        and add_registration_url is None
        and recently_finished(site, [page for _standard, page in pages] + translations),
        add_registration_url=add_registration_url,
    )


def recently_finished(site, every_version):
    """On a site `new_site` built, for a week after its last standard page first went live, in
    any language. A hand-built site isn't told it's done: the standard may ask for more than these
    pages show."""
    if any(page is None for page in every_version):
        return False
    if not PageLogEntry.objects.filter(page=site.root_page, action=NEW_SITE_BUILT).exists():
        return False
    published = [page.first_published_at for page in every_version if page.first_published_at]
    return bool(published) and timezone.now() - max(published) < timedelta(days=DONE_LINE_DAYS)


class StillToWritePanel(Component):
    name = "still_to_write"
    template_name = "home/admin/still_to_write_panel.html"
    order = 10

    def __init__(self, result):
        self.result = result

    def get_context_data(self, parent_context):
        context = super().get_context_data(parent_context)
        context["result"] = self.result
        return context


def can_act_on_it(user):
    """Someone who can change no page and no settings, such as a pledges-only user, can do
    nothing the panel asks."""
    return user.has_perm(
        "core.change_sitesettings"
    ) or page_permission_policy.user_has_any_permission(user, {"add", "change", "publish"})


@hooks.register("construct_homepage_panels")
def add_still_to_write_panel(request, panels):
    site = Site.find_for_request(request)
    if site is None or not can_act_on_it(request.user):
        return
    result = still_to_write(request.user, site)
    if result.groups or result.all_done or result.add_registration_url is not None:
        panels.append(StillToWritePanel(result))


@hooks.register("register_log_actions")
def register_new_site(actions):
    actions.register_action(NEW_SITE_BUILT, "Site set up", "Site set up with new_site")
