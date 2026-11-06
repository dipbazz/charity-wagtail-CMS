"""Every kind of demo page at the six widths the QA pass checks, in a real browser.

This is the mechanical half of QA: a page that scrolls sideways, or a control too small to tap,
fails here on every pull request. What needs eyes (wording, whether a page looks right) is listed
under "Check before merging" in the pull request. Run `uv run playwright install --with-deps
chromium` once; `uv run pytest -m "not browser"` leaves these out.
"""

import re

import pytest
from django.urls import reverse

from campaigns.models import DonatePage, Pledge, QRCode, StepKind
from conftest import SITE
from core.brand import FONT_STACKS, contrast
from core.models import SiteSettings

pytestmark = [pytest.mark.browser, pytest.mark.django_db]

WIDTHS = [320, 375, 412, 768, 1024, 1440]

# One page of each kind, in both languages where the demo has both.
PATHS = [
    "/",
    "/about/",
    "/appeals/",
    "/appeals/flood-relief/",
    "/stories/",
    "/donate/",
    "/volunteer/",
    "/search/?query=water",
    "/ne/",
    "/ne/appeals/flood-relief/",
    "/ne/donate/",
]

# What a thumb taps. Text links inside a paragraph are exempt: they're as tall as the line.
TAP_TARGETS = (
    ".site-footer a, .tag-list a, .day-one-contact a, .pagination a, .pay-way, .pay-steps a,"
    " .share-links a, .button, button, summary, select,"
    " input:not([type=checkbox]):not([type=radio]):not([type=hidden])"
)

# The measurements the checks need, taken in the page in one go.
MEASURE = """
([selector, smallest]) => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    small: [...document.querySelectorAll(selector)]
        .filter((el) => el.offsetParent !== null)
        .map((el) => [el, el.getBoundingClientRect()])
        .filter(([, box]) => box.width > 0 && box.height < smallest - 0.5)
        .map(([el, box]) => `${el.tagName.toLowerCase()}.${el.className}`.trim()
            + ` "${el.textContent.trim().slice(0, 30)}" is ${Math.round(box.height)}px tall`),
})
"""


def layout_problems(site_page, path, tap_targets=TAP_TARGETS, smallest=44):
    """Where `path` scrolls sideways or has a control (`tap_targets`) under `smallest` pixels
    tall, at each width."""
    problems = []
    for width in WIDTHS:
        site_page.set_viewport_size({"width": width, "height": 800})
        site_page.goto(SITE + path)
        found = site_page.evaluate(MEASURE, [tap_targets, smallest])
        if found["scrollWidth"] > found["innerWidth"]:
            problems.append(f"{width}px: scrolls sideways ({found['scrollWidth']}px wide)")
        problems += [f"{width}px: {item}" for item in found["small"]]
    return problems


@pytest.mark.parametrize("path", PATHS)
def test_page_fits_and_can_be_tapped_at_every_width(site_page, demo_site, path):
    problems = layout_problems(site_page, path)

    assert not problems, f"{path}\n" + "\n".join(problems)


@pytest.fixture
def pay_pages(demo_site, settings):
    """Every address of a pledge's pay page (the choices and each way's), for a pledge on the
    demo Donate page in each language. eSewa is set up with made-up keys: its pay button shows
    without asking eSewa anything. The demo's sample QR code can't be scanned."""
    settings.PAYMENT_KEYS = {"ESEWA_PRODUCT_CODE": "EPAYTEST", "ESEWA_SECRET_KEY": "made-up"}
    paths = []
    for donate_page in DonatePage.objects.live():
        pledge = Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )
        pay = f"{donate_page.url}pay/{pledge.reference}/"
        paths += [pay + way for way in ("", "online/", "qr/", "qr/paid/", "in-person/", "later/")]
        # The page while the team checks a QR payment, which every pay address then goes to.
        claimed = Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )
        claimed.claim_paid(QRCode.objects.first(), "TXN-8841")
        paths.append(f"{donate_page.url}pay/{claimed.reference}/checking/")
        # The QR page once the team couldn't find it, with the QR code and its steps folded away.
        not_found = Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )
        not_found.claim_paid(QRCode.objects.first(), "TXN-8842").mark_not_found(by=None)
        paths.append(f"{donate_page.url}pay/{not_found.reference}/qr/")
        # The page saying to wait, after one try too many coming back from a provider again
        # (#226): the first time back is always asked.
        waiting = Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )
        payment = waiting.start_payment("esewa", live=False)
        payment.add_step(StepKind.CAME_BACK)
        paths.append(f"{donate_page.url}payment/{payment.reference}/")
    settings.LIMITS = {**settings.LIMITS, "payment_return": 0}
    return paths


def test_each_pay_page_fits_and_can_be_tapped_at_every_width(site_page, pay_pages):
    assert len(pay_pages) == 18  # in both languages
    problems = []
    for path in pay_pages:
        problems += [f"{path} {item}" for item in layout_problems(site_page, path)]

    assert not problems, "\n".join(problems)


def test_a_gift_and_its_thanks_fit_and_can_be_tapped_at_every_width(site_page, demo_site):
    """The demo's shared gift (#100): its thank-you page, with the share section, and its page
    for friends."""
    gift = Pledge.objects.get(show_on_website=True)
    problems = []
    for path in (
        f"{gift.page.url}pay/{gift.reference}/",
        f"{gift.page.url}gifts/{gift.gift_code}/",
    ):
        problems += [f"{path} {item}" for item in layout_problems(site_page, path)]

    assert not problems, "\n".join(problems)


def test_a_pledges_page_in_the_admin_fits_and_can_be_tapped_at_every_width(
    site_page, client, demo_site, moderator
):
    """The team reads pledges on their phones too: one with a payment of each kind, opened by a
    moderator, who sees every action (#96). Wagtail's own controls keep their size, so the page
    looks like the rest of the admin; the page's own are at least WCAG 2.2 AA's 24px."""
    pledge = Pledge.objects.create(
        page=DonatePage.objects.live().first(),
        amount=2500,
        currency="NPR",
        name="Asha Gurung",
        email="asha.gurung.with.a.long.address@example.org",
        phone="+9779841234567",
        address="Ward 4, Biratnagar",
        message="Please use it for the school tap.",
    )
    pledge.start_payment("esewa", live=False).record("failed")
    claimed = pledge.claim_paid(QRCode.objects.first(), "TXN-8841-0000000000000000000000")
    claimed.mark_not_found(by=moderator)
    pledge.claim_paid(QRCode.objects.first(), "TXN-8842")
    client.force_login(moderator)

    problems = layout_problems(
        site_page,
        reverse("pledges:inspect", args=[pledge.pk]),
        tap_targets=".pledge-record :is(a, summary, button, input)",
        smallest=24,
    )

    assert not problems, "\n".join(problems)


# The fill the eye sees where `layers` (topmost first) overlap: each one's background laid over
# those below it and the white page, so a see-through fill counts as the colour it shows.
SEEN_FILL = r"""
const seenFill = (layers) => {
    let [r, g, b] = [255, 255, 255];
    for (const el of [...layers].reverse()) {
        const [lr, lg, lb, a = 1] = getComputedStyle(el).backgroundColor.match(/[\d.]+/g)
            .map(Number);
        [r, g, b] = [r + (lr - r) * a, g + (lg - g) * a, b + (lb - b) * a];
    }
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
};
const withAncestors = (el) => {
    const all = [];
    for (; el; el = el.parentElement) all.push(el);
    return all;
};
const named = (el) => `${el.tagName.toLowerCase()}.${el.className}`.trim()
    + ` "${el.textContent.trim().slice(0, 30)}"`;
"""

# Each text in the name bar and the footer, its colour, and the fill behind it: its own laid over
# its ancestors'.
TEXT_AND_FILL = f"""
(selector) => {{
    {SEEN_FILL}
    return [...document.querySelectorAll(selector)].map((el) => [
        named(el), getComputedStyle(el).color, seenFill(withAncestors(el)),
    ]);
}}
"""
NAME_BAR_AND_FOOTER_TEXT = ".brand, .site-footer :is(p, address, li, a)"


def hex_colour(computed):
    """A computed colour, such as "rgb(11, 85, 99)", as "#0b5563"."""
    return "#{:02x}{:02x}{:02x}".format(*(int(n) for n in re.findall(r"\d+", computed)[:3]))


# A light or dark name bar and footer (#134): every combination fits and can be tapped at every
# width, in both languages, and the text on each stays readable.
@pytest.mark.parametrize("footer", ["dark", "light"])
@pytest.mark.parametrize("name_bar", ["dark", "light"])
def test_a_light_or_dark_name_bar_and_footer_fit_and_stay_readable(
    site_page, demo_site, name_bar, footer
):
    site_settings = SiteSettings.for_site(demo_site)
    site_settings.name_bar_style = name_bar
    site_settings.footer_style = footer
    site_settings.save()
    problems = []
    for path in ("/", "/ne/"):
        problems += [f"{path} {item}" for item in layout_problems(site_page, path)]
        assert site_page.locator(".brand-bar.is-light").count() == (name_bar == "light")
        assert site_page.locator(".site-footer.is-light").count() == (footer == "light")
        for text, colour, fill in site_page.evaluate(TEXT_AND_FILL, NAME_BAR_AND_FOOTER_TEXT):
            ratio = contrast(hex_colour(colour), hex_colour(fill))
            if ratio < 4.5:
                problems.append(f"{path} {text}: contrast {ratio:.1f}:1")

    assert not problems, "\n".join(problems)


# A font style (#135) can be wider than the stylesheet's own, so each fits and can be tapped at
# every width, in both languages, and is the font the page is drawn in.
@pytest.mark.parametrize("font_style", [style for style in FONT_STACKS if style != "modern"])
def test_each_font_style_fits_and_can_be_tapped_at_every_width(site_page, demo_site, font_style):
    site_settings = SiteSettings.for_site(demo_site)
    site_settings.font_style = font_style
    site_settings.save()
    problems = []
    for path in ("/", "/appeals/flood-relief/", "/donate/", "/ne/", "/ne/donate/"):
        problems += [f"{path} {item}" for item in layout_problems(site_page, path)]
        font = site_page.evaluate("getComputedStyle(document.body).fontFamily")
        first = FONT_STACKS[font_style].split(",")[0]
        if not font.startswith(first) or "Devanagari" not in font:
            problems.append(f"{path} is drawn in {font}, not the {font_style} style")

    assert not problems, "\n".join(problems)


# The ring round what has the keyboard's focus, and the fills it's drawn on: what's on screen
# under the middle of each side of the ring, so a control placed over another area, such as the
# skip link over the name bar, is checked on that area. An amount card draws the ring for its
# hidden radio button. Nothing once Tab has gone past the last control, back to the page or to a
# control it has already reached (two can share a name, such as two Donate buttons).
FOCUS_RING = f"""
() => {{
    {SEEN_FILL}
    const focused = document.activeElement;
    window.ringed ??= new WeakSet();
    if (focused === document.body || window.ringed.has(focused)) return null;
    window.ringed.add(focused);
    const ringed = focused.closest(".amount-option") || focused;
    const ring = getComputedStyle(ringed);
    const box = ringed.getBoundingClientRect();
    const out = parseFloat(ring.outlineOffset) + parseFloat(ring.outlineWidth) / 2;
    const [x, y] = [box.left + box.width / 2, box.top + box.height / 2];
    const fills = [[box.left - out, y], [box.right + out, y], [x, box.top - out],
                   [x, box.bottom + out]]
        .filter(([px, py]) => px >= 0 && py >= 0 && px < innerWidth && py < innerHeight)
        .map(([px, py]) => seenFill(document.elementsFromPoint(px, py)));
    return [named(ringed), ring.outlineStyle, ring.outlineColor, fills];
}}
"""


def focus_ring_problems(site_page, path):
    """Each link, button and field on `path` that Tab reaches with no ring, or a ring under 3:1
    on a fill it's drawn on."""
    site_page.goto(SITE + path)
    problems = []
    for _ in range(300):
        site_page.keyboard.press("Tab")
        found = site_page.evaluate(FOCUS_RING)
        if found is None:
            break
        name, style, colour, fills = found
        ratio, fill = min((contrast(hex_colour(colour), hex_colour(fill)), fill) for fill in fills)
        if style == "none" or ratio < 3:
            problems.append(f"{path} {name}: ring {style} {colour} on {fill}, {ratio:.1f}:1")
    return problems


# The ring that shows where the keyboard is (#211) can be seen on every page, on whatever it
# sits on, with the name bar and footer dark and again light. A dark area added later that
# doesn't set --colour-focus fails here.
@pytest.mark.parametrize("style", ["dark", "light"])
def test_the_focus_ring_can_be_seen_on_everything_tab_reaches(site_page, demo_site, style):
    site_settings = SiteSettings.for_site(demo_site)
    site_settings.name_bar_style = style
    site_settings.footer_style = style
    site_settings.save()
    site_page.set_viewport_size({"width": 1440, "height": 800})
    problems = []
    for path in PATHS:
        problems += focus_ring_problems(site_page, path)

    assert not problems, "\n".join(problems)
