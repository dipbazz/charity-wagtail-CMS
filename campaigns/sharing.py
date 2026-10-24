"""Sharing a gift (#100): what a gift's public page shows, and what a supporter shares.

One rule decides what's shown of a gift, here and in the recent supporters list (#99): only what
the supporter agreed to (Pledge.show_on_website, in the words of forms.SHOW_GIFT_HELP), only once
they've told us they've paid (once it's reached us, if they agreed in the words used before gift
pages), the amount only once it's reached us, and nothing while the team has taken it down. A
share never carries the pay page's reference, which pays the pledge: friends get the gift's own
page, or else the appeal or the Donate page.
"""

from urllib.parse import urlencode

from django.utils.translation import gettext

# What a gift's public page may show.
SHOWN = "shown"  # the name, appeal, date and amount
CHECKING = "checking"  # a QR payment the team is still checking: the name, appeal and date
HIDDEN = "hidden"  # nothing: the page isn't found

# The pay page states (Pledge.pay_page_state()) whose page offers sharing: thanks, or the page
# saying the team is checking a QR payment.
SHARING_STATES = ("paid", "received", "to-confirm")


def gift_view(pledge):
    """SHOWN, CHECKING or HIDDEN. Reads payments as fetched, so a list can prefetch them."""
    if not pledge.show_on_website or pledge.hidden_by_team:
        return HIDDEN
    state = pledge.pay_page_state()
    if state in ("paid", "received"):
        return SHOWN
    # Agreed before gift pages (no time recorded), the box said "Once your gift reaches us".
    if state == "to-confirm" and pledge.show_on_website_changed_at is not None:
        return CHECKING
    return HIDDEN


def offers_sharing(pledge):
    """Whether its pay page invites the supporter to share, with or without their name: once
    they've told us they've paid. A pledge that isn't paid isn't a gift yet."""
    return pledge.pay_page_state() in SHARING_STATES


def appeal_shown(pledge):
    """The pledge's appeal if visitors can see it (live, and not behind a password or login),
    else None: a private or unpublished appeal is shown as wherever it's needed most. One query,
    so it's worked out once per page and passed to the functions below."""
    appeal = pledge.appeal
    if appeal and appeal.live and not appeal.get_view_restrictions().exists():
        return appeal
    return None


def gift_amount(pledge):
    """What the gift is for, as (amount, currency): what was received, which can differ from the
    pledge's (the team received another amount, or the pledge was changed after the payment
    started)."""
    paid = pledge.paid_payment() or pledge
    return paid.amount, paid.currency


def is_test(pledge):
    """Whether only a provider's test system took it: no money moved."""
    paid = pledge.paid_payment()
    return bool(paid and not paid.live)


def as_phrase(text):
    """An editor's "A hygiene kit for a family" as it reads within a sentence. A first word in
    capitals ("UV filters") is left as it is."""
    first_word = text.split(" ", 1)[0]
    if len(first_word) > 1 and first_word.isupper():
        return text
    return text[:1].lower() + text[1:]


def impact_line(pledge, appeal, site_currency):
    """What the gift does, in a sentence, from what editors already wrote: the suggested amount
    it matches (on the appeal, or the Donate page for wherever it's needed most), else the
    appeal's summary, else a sentence about the need. `appeal` is appeal_shown(). Suggested
    amounts are in the site's currency, so money received in another matches none."""
    page = appeal or pledge.page
    amount, currency = gift_amount(pledge)
    options = page.donation_amounts.all() if page and currency == site_currency else []
    impact = next((option.impact for option in options if option.amount == amount), "")
    if impact:
        return gettext("It pays for %(impact)s.") % {"impact": as_phrase(impact)}
    if appeal:
        return appeal.summary
    return gettext("It helps wherever the need is greatest.")


def gift_url(pledge, request=None):
    """The gift's public page, under the Donate page it was pledged on."""
    page = pledge.page
    return page.get_full_url(request) + page.reverse_subpage("gift", args=[pledge.gift_code])


def share_url(pledge, appeal, request=None):
    """Where a share sends friends: the gift's page while it's shown, else the appeal, else the
    Donate page. Never the pay page. `appeal` is appeal_shown()."""
    if gift_view(pledge) != HIDDEN:
        return gift_url(pledge, request)
    return (appeal or pledge.page).get_full_url(request)


def needs_help(appeal):
    """Whether an appeal can still say it needs help: open, and short of its target."""
    return appeal.is_active and not appeal.target_reached


def share_text(pledge, appeal, charity):
    """The supporter's message before the link, in the language they're reading: an invitation
    to help the cause, never the amount. `appeal` is appeal_shown(); `charity` its name."""
    if appeal is None:
        return gettext(
            "I've just given to %(charity)s. They still need help. If you can, you could give too:"
        ) % {"charity": charity}
    names = {"appeal": appeal.title, "charity": charity}
    if needs_help(appeal):
        return (
            gettext(
                "I've just given to %(appeal)s with %(charity)s. They still need help. If you can, "
                "you could give too:"
            )
            % names
        )
    return (
        gettext("I've just given to %(appeal)s with %(charity)s. If you can, you could give too:")
        % names
    )


def gift_title(pledge, appeal, charity):
    """The gift page's heading, and its title in a link's preview: "Asha is supporting Clean
    water for Sindhupalchok"."""
    if appeal is None:
        return gettext("%(name)s is supporting %(charity)s") % {
            "name": pledge.name,
            "charity": charity,
        }
    return gettext("%(name)s is supporting %(appeal)s") % {
        "name": pledge.name,
        "appeal": appeal.title,
    }


def whatsapp_link(text, url):
    """A link that opens WhatsApp with the message and the link written in."""
    return "https://wa.me/?" + urlencode({"text": f"{text} {url}"})


def facebook_link(url):
    """A link that opens Facebook's share box for the link (Facebook takes no message)."""
    return "https://www.facebook.com/sharer/sharer.php?" + urlencode({"u": url})
