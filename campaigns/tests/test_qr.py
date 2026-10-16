"""Paying a pledge by scanning the charity's own QR code (#197): the QR codes in the admin, the QR
page and its states, "I've paid", and the team marking it paid or not found."""

import datetime
import io

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation
from PIL import Image
from wagtail.models import Locale

from campaigns.forms import MarkPaidForm
from campaigns.models import Payment, PaymentStatus, Pledge, QRCode, QRCodeName, StepKind
from campaigns.payments import TEAM_CONFIRMED
from core.models import SiteSettings

pytestmark = pytest.mark.django_db


def card(image_format="PNG", name="qr.png", size=(1800, 1800)):
    saved = io.BytesIO()
    Image.new("RGB", size, "white").save(saved, format=image_format)
    return SimpleUploadedFile(name, saved.getvalue())


def make_code(name="eSewa", account_name="BRIGHTWELL WATER", account_number="", **fields):
    code = QRCode.objects.create(
        image=card(), account_name=account_name, account_number=account_number, **fields
    )
    QRCodeName.objects.create(code=code, locale=Locale.get_default(), name=name)
    return code


@pytest.fixture
def esewa_qr():
    return make_code("eSewa", account_number="9801234567")


@pytest.fixture
def fonepay_qr():
    return make_code("Fonepay (bank)", account_name="BRIGHTWELL WATER TRUST")


@pytest.fixture
def pledge(donate_page):
    return Pledge.objects.create(
        page=donate_page, amount=2500, currency="NPR", name="Sita Sharma", email="sita@example.com"
    )


def qr_url(donate_page, pledge, tail=""):
    return f"{donate_page.url}pay/{pledge.reference}/qr/{tail}"


def checking_url(donate_page, pledge):
    return f"{donate_page.url}pay/{pledge.reference}/checking/"


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def text(response):
    return text_of(soup(response))


def text_of(element):
    return " ".join(element.get_text().split())


def say_paid(client, donate_page, pledge, code, transaction_id="TXN-8841"):
    return client.post(
        qr_url(donate_page, pledge, "paid/"), {"code": code.pk, "transaction_id": transaction_id}
    )


class TestQRCodeImages:
    def test_is_saved_at_two_sizes_in_its_own_format(self, esewa_qr):
        code = QRCode.objects.get(pk=esewa_qr.pk)

        assert code.image.name.endswith(".png")
        assert Image.open(code.image).size == (1600, 1600)
        assert Image.open(code.image_small).size == (800, 800)
        assert (code.image_width, code.image_height, code.small_width) == (1600, 1600, 800)

    def test_keeps_none_of_the_uploads_name(self):
        code = QRCode.objects.create(image=card(name="my-secret-name.png"), account_name="X")

        assert "my-secret-name" not in code.image.name

    def test_replacing_the_image_removes_the_old_files(
        self, esewa_qr, django_capture_on_commit_callbacks
    ):
        old = {esewa_qr.image.name, esewa_qr.image_small.name}

        with django_capture_on_commit_callbacks(execute=True):
            esewa_qr.image = card("JPEG", "new.jpg")
            esewa_qr.save()

        storage = esewa_qr.image.storage
        assert not any(storage.exists(name) for name in old)
        assert storage.exists(esewa_qr.image.name)

    def test_removing_the_code_removes_both_files(
        self, esewa_qr, django_capture_on_commit_callbacks
    ):
        names = {esewa_qr.image.name, esewa_qr.image_small.name}

        with django_capture_on_commit_callbacks(execute=True):
            esewa_qr.delete()

        assert not any(esewa_qr.image.storage.exists(name) for name in names)

    @pytest.mark.parametrize("change", ["replace", "delete"])
    def test_a_change_undone_keeps_the_files_the_code_points_at(
        self, esewa_qr, django_capture_on_commit_callbacks, change
    ):
        # Say Wagtail's history entry fails after the save: the code still points at these.
        names = {esewa_qr.image.name, esewa_qr.image_small.name}

        with django_capture_on_commit_callbacks(execute=True):
            with pytest.raises(RuntimeError), transaction.atomic():
                if change == "replace":
                    esewa_qr.image = card("JPEG", "new.jpg")
                    esewa_qr.save()
                else:
                    esewa_qr.delete()
                raise RuntimeError

        assert all(esewa_qr.image.storage.exists(name) for name in names)

    def test_saving_again_without_a_new_image_keeps_the_files(self, esewa_qr):
        name = QRCode.objects.get(pk=esewa_qr.pk).image.name

        esewa_qr.account_name = "BRIGHTWELL"
        esewa_qr.save()

        assert QRCode.objects.get(pk=esewa_qr.pk).image.name == name
        assert esewa_qr.image.storage.exists(name)


class TestQRCodeNames:
    def test_is_the_name_in_the_reading_language(self, esewa_qr):
        assert QRCode.objects.get(pk=esewa_qr.pk).name == "eSewa"

    def test_falls_back_to_the_main_languages_when_blank(self, esewa_qr):
        nepali, _ = Locale.objects.get_or_create(language_code="ne")
        QRCodeName.objects.create(code=esewa_qr, locale=nepali, name="")

        with translation.override("ne"):
            assert QRCode.objects.get(pk=esewa_qr.pk).name == "eSewa"


class TestClaimingPaid:
    def test_makes_one_payment_for_the_team_to_confirm(self, pledge, esewa_qr):
        payment = pledge.claim_paid(esewa_qr, "TXN-8841")

        assert (payment.method, payment.status, payment.live) == ("qr", "to-confirm", True)
        assert (payment.qr_name, payment.supporters_reference) == ("eSewa", "TXN-8841")
        assert payment.amount == 2500
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.TO_CONFIRM
        assert [step.kind for step in payment.steps.all()] == [StepKind.CLAIMED]

    def test_a_second_claim_makes_no_second_payment(self, pledge, esewa_qr):
        pledge.claim_paid(esewa_qr, "TXN-8841")

        assert pledge.claim_paid(esewa_qr, "TXN-8841") is None
        assert pledge.payments.count() == 1

    def test_a_paid_pledge_cant_be_claimed(self, pledge, esewa_qr):
        pledge.start_payment("esewa", live=False).record("paid", "000AWEO")

        assert pledge.claim_paid(esewa_qr, "TXN-8841") is None

    def test_keeps_the_name_in_the_sites_main_language(self, pledge, esewa_qr):
        # The team reads it in the admin and exports, whichever language the supporter read in.
        nepali, _ = Locale.objects.get_or_create(language_code="ne")
        QRCodeName.objects.create(code=esewa_qr, locale=nepali, name="इसेवा")

        with translation.override("ne"):
            payment = pledge.claim_paid(QRCode.objects.get(pk=esewa_qr.pk), "TXN-8841")

        assert payment.qr_name == "eSewa"

    def test_keeps_a_name_only_written_in_another_language(self, pledge):
        nepali, _ = Locale.objects.get_or_create(language_code="ne")
        code = QRCode.objects.create(image=card(), account_name="BRIGHTWELL WATER")
        QRCodeName.objects.create(code=code, locale=nepali, name="इसेवा")

        with translation.override("ne"):
            payment = pledge.claim_paid(QRCode.objects.get(pk=code.pk), "TXN-8841")

        assert payment.qr_name == "इसेवा"

    def test_keeps_the_codes_name_once_it_is_removed(self, pledge, esewa_qr):
        payment = pledge.claim_paid(esewa_qr, "TXN-8841")

        esewa_qr.delete()

        payment.refresh_from_db()
        assert (payment.qr_code, payment.qr_name) == (None, "eSewa")


class TestMarkingPaid:
    @pytest.fixture
    def claimed(self, pledge, esewa_qr):
        return pledge.claim_paid(esewa_qr, "TXN-8841")

    @pytest.fixture
    def team(self, django_user_model):
        return django_user_model.objects.create_user(username="ram")

    def test_pays_the_payment_and_the_pledge(self, pledge, claimed, team):
        assert claimed.mark_paid(team, timezone.localdate(), 2500, "RBB-77") is True

        claimed.refresh_from_db()
        pledge.refresh_from_db()
        assert (claimed.status, claimed.provider_reference) == ("paid", "RBB-77")
        assert pledge.payment_status == PaymentStatus.PAID
        assert pledge.paid_at is not None
        assert claimed.steps.last().by == team
        assert claimed.steps.last().kind == StepKind.MARKED_PAID
        assert pledge.pay_page_state() == "paid"

    def test_another_amount_is_received_not_paid(self, pledge, claimed, team):
        claimed.mark_paid(team, timezone.localdate(), 2000, "RBB-77")

        pledge = Pledge.objects.prefetch_related("payments").get(pk=pledge.pk)
        assert pledge.payment_status == PaymentStatus.PAID
        assert pledge.paid_payment().amount == 2000
        assert pledge.pay_page_state() == "received"

    def test_is_set_once(self, pledge, claimed, team):
        claimed.mark_paid(team, timezone.localdate(), 2500, "RBB-77")

        assert claimed.mark_paid(team, timezone.localdate(), 9999, "OTHER") is False
        claimed.refresh_from_db()
        assert (claimed.amount, claimed.provider_reference) == (2500, "RBB-77")

    def test_never_an_online_payment(self, pledge, team):
        online = pledge.start_payment("esewa", live=True)

        assert online.mark_paid(team, timezone.localdate(), 2500, "X") is False
        assert Payment.objects.get(pk=online.pk).status == PaymentStatus.WAITING

    def test_not_found_fails_it_and_the_pledge(self, pledge, claimed, team):
        assert claimed.mark_not_found(team) is True

        claimed.refresh_from_db()
        assert claimed.status == PaymentStatus.FAILED
        pledge = Pledge.objects.prefetch_related("payments").get(pk=pledge.pk)
        assert pledge.payment_status == PaymentStatus.FAILED
        assert pledge.pay_page_state() == "not-found"
        assert claimed.steps.last().kind == StepKind.NOT_FOUND

    def test_not_found_can_still_be_marked_paid_later(self, pledge, claimed, team):
        claimed.mark_not_found(team)

        assert claimed.mark_paid(team, timezone.localdate(), 2500, "RBB-77") is True
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.PAID

    def test_asking_adds_no_step_and_asks_nobody(self, claimed):
        assert claimed.ask() is None
        assert [step.kind for step in claimed.steps.all()] == [StepKind.CLAIMED]

    def test_a_failed_online_attempt_leaves_it_to_confirm(self, pledge, claimed):
        pledge.start_payment("esewa", live=False).record("failed")

        pledge = Pledge.objects.prefetch_related("payments").get(pk=pledge.pk)
        assert pledge.payment_status == PaymentStatus.TO_CONFIRM
        assert pledge.pay_page_state() == "to-confirm"


class TestWhenTheQRPageIsOffered:
    def test_not_without_codes(self, client, donate_page, pledge):
        response = client.get(qr_url(donate_page, pledge))

        assert response.status_code == 303
        assert response.url == f"{donate_page.url}pay/{pledge.reference}/"

    def test_the_only_way_when_a_charity_has_only_a_qr(self, client, donate_page, esewa_qr):
        response = client.post(
            donate_page.url,
            {
                "amount": "2500",
                "other_amount": "",
                "frequency": "one-off",
                "name": "Sita Sharma",
                "email": "sita@example.com",
                "phone_country": "NP",
                "phone": "",
                "appeal": "flood-relief",
                "address": "",
                "postcode": "",
            },
        )

        assert response.status_code == 303
        assert response.url.endswith("/qr/")

    def test_for_rupees_only(self, client, donate_page, esewa_qr):
        pledge = Pledge.objects.create(
            page=donate_page, amount=25, currency="GBP", name="Sita", email="sita@example.com"
        )

        response = client.get(qr_url(donate_page, pledge))

        assert response.status_code == 303
        assert response.url == f"{donate_page.url}pay/{pledge.reference}/"

    def test_is_named_in_the_choices_with_another_way(
        self, client, donate_page, pledge, esewa_qr, site
    ):
        site_settings = SiteSettings.for_site(site)
        site_settings.phone = "+977 1-4567890"
        site_settings.takes_gifts_in_person = True
        site_settings.save()

        page = soup(client.get(f"{donate_page.url}pay/{pledge.reference}/"))

        rows = [a.find("strong").get_text() for a in page.select("a.pay-way")]
        assert rows == ["Scan our QR code", "Pay in person", "Not ready to pay yet?"]


class TestTheQRPage:
    def test_gives_the_amount_and_the_remarks_to_copy_first(
        self, client, donate_page, pledge, esewa_qr
    ):
        response = client.get(qr_url(donate_page, pledge))
        page = soup(response)

        buttons = page.select("button[data-copy-value]")
        values = [button["data-copy-value"] for button in buttons]
        assert values[:2] == ["2500", pledge.number]
        assert values[2:] == ["BRIGHTWELL WATER", "9801234567"]
        assert [button["aria-label"] for button in buttons][:2] == [
            "Copy amount",
            "Copy remarks",
        ]

    def test_shows_each_code_under_its_name_with_a_way_to_save_it(
        self, client, donate_page, pledge, esewa_qr, fonepay_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge)))

        names = [h3.get_text(strip=True) for h3 in page.select(".qr-card h3")]
        assert names == ["eSewa", "Fonepay (bank)"]
        save = page.select_one(".qr-card a[download]")
        assert save["href"].endswith(".png")
        assert "Save QR code" in save.get_text()

    def test_one_code_has_no_chooser(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        assert page.select(".qr-choice") == []
        assert page.select_one("input[name=code]")["value"] == str(esewa_qr.pk)

    def test_two_codes_have_a_chooser_with_the_first_chosen(
        self, client, donate_page, pledge, esewa_qr, fonepay_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge)))

        radios = page.select(".qr-choice input[type=radio]")
        assert [radio["value"] for radio in radios] == [str(esewa_qr.pk), str(fonepay_qr.pk)]
        assert [radio.has_attr("checked") for radio in radios] == [True, False]

    def test_the_image_is_alt_texted_and_sized_for_phones(
        self, client, donate_page, pledge, esewa_qr
    ):
        image = soup(client.get(qr_url(donate_page, pledge))).select_one(".qr-card img")

        assert "eSewa QR code to pay" in image["alt"]
        assert "800w" in image["srcset"]
        assert "1600w" in image["srcset"]
        assert (image["width"], image["height"]) == ("1600", "1600")

    def test_asks_the_supporter_to_check_the_account_name(
        self, client, donate_page, pledge, esewa_qr
    ):
        assert "After you scan, your app should show BRIGHTWELL WATER." in text(
            client.get(qr_url(donate_page, pledge))
        )

    def test_says_it_isnt_checked_automatically(self, client, donate_page, pledge, esewa_qr):
        assert "We check QR payments by hand" in text(client.get(qr_url(donate_page, pledge)))

    def test_the_summary_says_what_each_detail_is_for(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        summary = page.select_one("dl.gift-summary")
        labels = [dt.get_text(strip=True) for dt in summary.select("dt")]
        assert labels == ["Your gift amount", "Appeal", "Pledge number (use this as Remarks)"]
        # One summary: the amount and the remarks aren't given a second time further down.
        assert page.find_all("dt", string="Amount") == []
        assert page.find_all("dt", string="Remarks") == []

    def test_other_pay_pages_keep_the_plain_summary(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(f"{donate_page.url}pay/{pledge.reference}/later/"))

        assert [dt.get_text(strip=True) for dt in page.select("dl.gift-summary dt")] == [
            "Your gift",
            "Appeal",
            "Pledge number",
        ]
        assert page.select("button[data-copy-value]") == []

    def test_the_account_to_pay_instead_is_under_its_own_heading(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge)))

        fallback = page.select_one(".qr-card .qr-fallback")
        assert fallback.h4.get_text(strip=True) == (
            "Can't scan the QR code? Pay to this account instead"
        )
        assert [dt.get_text(strip=True) for dt in fallback.select("dt")] == [
            "Account name",
            "Account number",
        ]
        assert len(fallback.select("button[data-copy-value]")) == 2
        # Paying to the account leaves out the QR's own details, so the pledge number is asked for.
        assert "Don't forget to use the pledge number above as the Remarks" in text_of(fallback)

    def test_says_how_to_scan_on_a_phone_and_on_a_computer(
        self, client, donate_page, pledge, esewa_qr
    ):
        response = client.get(qr_url(donate_page, pledge))
        words = text(response)

        # Folded under a title that says what's inside, so it doesn't push the account down.
        how = soup(response).select_one(".qr-card details.qr-how")
        assert how.summary.get_text(strip=True) == "Need help saving or scanning the QR code?"
        assert not how.has_attr("open")
        assert len(how.select("p.qr-help")) == 3
        assert "On an Android phone? Save the QR code" in words
        assert "On a computer? Scan the code on screen with your phone." in words
        assert "On an iPhone, press and hold the QR code" in words

    def test_has_its_own_title(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        assert "Scan our QR code" in page.title.get_text()


class TestTheTwoSteps:
    """Each step is its own page: scanning at qr/, telling us at qr/paid/."""

    def test_each_page_shows_its_own_step_and_links_to_the_other(
        self, client, donate_page, pledge, esewa_qr
    ):
        step_1 = soup(client.get(qr_url(donate_page, pledge)))
        step_2 = soup(client.get(qr_url(donate_page, pledge, "paid/")))

        for page, current, other, href in [
            (step_1, "Scan the QR code", "Paid? Tell us", qr_url(donate_page, pledge, "paid/")),
            (step_2, "Paid? Tell us", "Scan the QR code", qr_url(donate_page, pledge)),
        ]:
            nav = page.select_one("nav[aria-label=Steps]")
            here = nav.select_one("[aria-current=step]")
            assert here.get_text(strip=True).lstrip("12") == current
            assert here.name == "span"
            links = nav.select("a")
            assert [(a.get_text(strip=True).lstrip("12"), a["href"]) for a in links] == [
                (other, href)
            ]
        assert [h2.get_text(strip=True) for h2 in step_1.select(".qr-step > h2")] == [
            "Step 1: Pay with your app"
        ]
        assert step_1.select("input[name=transaction_id]") == []
        assert [h2.get_text(strip=True) for h2 in step_2.select(".qr-step > h2")] == [
            "Step 2: Paid? Tell us here"
        ]
        assert step_2.select(".qr-card") == []

    def test_step_1_ends_by_going_to_step_2_with_the_chosen_app(
        self, client, donate_page, pledge, esewa_qr, fonepay_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge)))

        form = page.select_one("form.qr-pay")
        assert form["method"] == "get"
        assert form["action"] == qr_url(donate_page, pledge, "paid/")
        assert "Paid in your app? Come back to this page, then go to step 2." in text_of(form)
        assert form.select_one("button[type=submit]").get_text(strip=True) == "Go to step 2"
        assert {radio["name"] for radio in form.select(".qr-choice input")} == {"code"}

    def test_step_2_starts_with_the_app_chosen_at_step_1(
        self, client, donate_page, pledge, esewa_qr, fonepay_qr
    ):
        chosen = soup(client.get(qr_url(donate_page, pledge, f"paid/?code={fonepay_qr.pk}")))
        none = soup(client.get(qr_url(donate_page, pledge, "paid/")))
        unknown = soup(client.get(qr_url(donate_page, pledge, "paid/?code=9999")))

        def checked(page):
            return [radio["value"] for radio in page.select("input[name=code]:checked")]

        assert checked(chosen) == [str(fonepay_qr.pk)]
        # Not a guess: the wrong one would send the team to the wrong statement.
        assert checked(none) == []
        assert checked(unknown) == []

    def test_step_2_asks_which_app_when_none_is_chosen(
        self, client, donate_page, pledge, esewa_qr, fonepay_qr
    ):
        response = client.post(qr_url(donate_page, pledge, "paid/"), {"transaction_id": "TXN"})
        page = soup(response)

        assert response.status_code == 422
        assert "Choose the app you paid with." in page.select_one("#id_code_error").get_text()
        assert page.select_one("fieldset.qr-choice")["aria-describedby"] == "id_code_error"
        alert = page.select_one("[role=alert]")
        assert alert.select_one("a")["href"] == "#id_code_0"
        assert "Check which app you paid with below." in alert.get_text()
        assert page.select_one("input[name=transaction_id]")["value"] == "TXN"

    def test_step_2_says_where_to_find_the_id_before_the_field(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge, "paid/")))

        field = page.select_one("input[name=transaction_id]")
        steps = page.select("#transaction-id-help li")
        assert len(steps) == 2
        # The receipt calls it one or the other.
        assert steps[1].get_text(strip=True) == (
            "Copy the Transaction ID or Transaction code and paste it here."
        )
        assert field.sourceline > steps[1].sourceline
        assert "transaction-id-help" in field["aria-describedby"]
        assert "Paid? Tell us here" in page.title.get_text()

    def test_ive_paid_says_it_is_sending(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge, "paid/")))

        button = page.select_one("form.qr-paid button[type=submit]")
        assert button.get_text(strip=True) == "I've paid"
        assert button["data-busy-text"] == "Sending…"
        assert page.select_one("form.qr-paid [data-busy-status][role=status]")

    def test_step_2_goes_to_the_checking_page_once_they_have_told_us(
        self, client, donate_page, pledge, esewa_qr
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        response = client.get(qr_url(donate_page, pledge, "paid/"))

        assert response.status_code == 303
        assert response.url == checking_url(donate_page, pledge)

    def test_step_2_is_open_when_the_team_couldnt_find_it(
        self, client, donate_page, pledge, esewa_qr, django_user_model
    ):
        pledge.claim_paid(esewa_qr, "TXN-8841").mark_not_found(
            django_user_model.objects.create_user(username="ram")
        )

        page = soup(client.get(qr_url(donate_page, pledge, "paid/")))

        assert page.select_one("form.qr-paid input[name=transaction_id]")

    def test_the_steps_fold_away_with_the_qr_code_when_the_team_couldnt_find_it(
        self, client, donate_page, pledge, esewa_qr, django_user_model
    ):
        pledge.claim_paid(esewa_qr, "TXN-8841").mark_not_found(
            django_user_model.objects.create_user(username="ram")
        )

        page = soup(client.get(qr_url(donate_page, pledge)))

        fold = page.select_one("details.pay-again")
        assert page.select("ol.qr-progress") == fold.select("ol.qr-progress")
        nav = fold.select_one("nav[aria-label=Steps]")
        here = nav.select_one("[aria-current=step]")
        assert here.get_text(strip=True).lstrip("12") == "Scan the QR code"
        assert [a["href"] for a in nav.select("a")] == [qr_url(donate_page, pledge, "paid/")]

    def test_step_2_isnt_offered_without_codes(self, client, donate_page, pledge):
        response = client.get(qr_url(donate_page, pledge, "paid/"))

        assert response.status_code in (302, 303)


class TestCopiedMessages:
    def test_each_copy_button_has_its_message_right_under_its_value(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge)))

        for button in page.select("button[data-copy-value]"):
            row = button.find_parent("dd")
            line = row.find_next_sibling("dd")
            assert line.get("data-copy-status") == button["data-copy"], button["aria-label"]
            assert line.get("role") == "status"

    def test_no_message_is_left_below_the_page(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        assert page.select("p[data-copy-status]") == []
        keys = [button["data-copy"] for button in page.select("button[data-copy-value]")]
        assert len(keys) == len(set(keys))


class TestSayingIvePaid:
    def test_goes_to_the_checking_page(self, client, donate_page, pledge, esewa_qr):
        response = say_paid(client, donate_page, pledge, esewa_qr)

        assert response.status_code == 303
        assert response.url == checking_url(donate_page, pledge)

    def test_sent_again_from_a_stale_tab_goes_to_the_checking_page(
        self, client, donate_page, pledge, esewa_qr
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        response = say_paid(client, donate_page, pledge, esewa_qr, transaction_id="TXN-2")

        assert response.status_code == 303
        assert response.url == checking_url(donate_page, pledge)
        assert list(pledge.payments.values_list("supporters_reference", flat=True)) == ["TXN-8841"]

    def test_sending_it_twice_makes_one_payment(self, client, donate_page, pledge, esewa_qr):
        say_paid(client, donate_page, pledge, esewa_qr)
        say_paid(client, donate_page, pledge, esewa_qr)

        assert pledge.payments.count() == 1

    def test_needs_the_transaction_id_or_a_screenshot(self, client, donate_page, pledge, esewa_qr):
        response = say_paid(client, donate_page, pledge, esewa_qr, transaction_id="  ")

        assert response.status_code == 422
        assert "Enter the transaction ID, or add a screenshot of the receipt." in text(response)
        assert pledge.payments.count() == 0
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.WAITING

    def test_the_error_is_under_the_field_and_the_alert_links_to_it(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(say_paid(client, donate_page, pledge, esewa_qr, transaction_id="  "))

        field = page.select_one("input[name=transaction_id]")
        error = page.select_one("#id_transaction_id_error")
        assert field["aria-invalid"] == "true"
        assert "id_transaction_id_error" in field["aria-describedby"].split()
        assert "Enter the transaction ID, or add a screenshot of the receipt." in error.get_text()
        assert field.find_parent("div").select_one("#id_transaction_id_error")
        alert = page.select_one("[role=alert]")
        assert alert.select_one("a")["href"] == "#id_transaction_id"
        assert "Check the transaction ID below." in alert.get_text()
        assert "Enter the transaction ID" not in alert.get_text()

    def test_the_field_has_no_error_before_anything_is_sent(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge, "paid/")))

        field = page.select_one("input[name=transaction_id]")
        assert not field.has_attr("aria-invalid")
        assert page.select("#id_transaction_id_error") == []

    def test_a_mistake_shows_step_2_again(self, client, donate_page, pledge, esewa_qr):
        page = soup(say_paid(client, donate_page, pledge, esewa_qr, transaction_id=" "))

        assert (
            page.select_one("nav[aria-label=Steps] [aria-current=step]")
            .get_text(strip=True)
            .endswith("Paid? Tell us")
        )
        assert page.select(".qr-card") == []

    def test_only_names_a_code_on_the_page(self, client, donate_page, pledge, esewa_qr):
        response = client.post(
            qr_url(donate_page, pledge, "paid/"), {"code": "9999", "transaction_id": "TXN"}
        )

        assert response.status_code == 422
        assert pledge.payments.count() == 0

    def test_is_only_opened_or_sent(self, client, donate_page, pledge, esewa_qr):
        assert client.put(qr_url(donate_page, pledge, "paid/")).status_code == 405

    def test_not_while_an_online_payment_may_be_paid(self, client, donate_page, pledge, esewa_qr):
        # Step 2 opened before the online attempt started, and sent after it: the stale tab.
        pledge.start_payment("esewa", live=False)

        response = say_paid(client, donate_page, pledge, esewa_qr)

        assert response.status_code == 303
        assert response.url == f"{donate_page.url}pay/{pledge.reference}/online/"
        assert not pledge.payments.filter(method="qr").exists()
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.WAITING

    def test_not_once_paid(self, client, donate_page, pledge, esewa_qr):
        pledge.start_payment("esewa", live=False).record("paid", "000AWEO")

        response = say_paid(client, donate_page, pledge, esewa_qr)

        assert response.status_code == 303
        assert pledge.payments.count() == 1


class TestTheCheckingPage:
    """Where a pledge's every pay address goes while the team checks a payment the supporter
    says they made: nothing else can be paid until it's found or not."""

    def test_says_thank_you_and_what_they_told_us(self, client, donate_page, pledge, esewa_qr):
        say_paid(client, donate_page, pledge, esewa_qr)

        response = client.get(checking_url(donate_page, pledge))
        page = soup(response)

        assert response.status_code == 200
        lead = page.select_one("[data-focus-on-load]")
        assert "Thank you. You've told us you paid Rs 2,500 by eSewa" in text_of(lead)
        assert "You sent us the transaction ID TXN-8841." in text(response)
        assert "There's nothing more to do here." in text(response)
        assert "Checking your payment" in page.title.get_text()
        assert page.h1.get_text(strip=True) == "Checking your payment"

    def test_repeats_nothing_and_offers_nothing_to_pay(
        self, client, donate_page, pledge, esewa_qr, fake_provider
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        page = soup(client.get(checking_url(donate_page, pledge)))

        # The thanks already says the amount: no summary, no steps, no QR, no other way.
        content = page.select_one("main")
        assert content.select("dl.gift-summary, ol.qr-progress, form, .qr-card, .pay-way") == []
        assert "Pay another way" not in text_of(page)

    def test_gives_the_pledge_number_to_call_about_it(
        self, client, donate_page, pledge, esewa_qr, site
    ):
        site_settings = SiteSettings.for_site(site)
        site_settings.phone = "+977 1-4567890"
        site_settings.save()
        say_paid(client, donate_page, pledge, esewa_qr)

        page = soup(client.get(checking_url(donate_page, pledge)))

        assert (
            f"Questions? Call us and give your pledge number, {pledge.display_number()}:"
            in text_of(page)
        )
        assert page.select_one("main a[href='tel:+97714567890']")

    def test_asks_nobody_to_call_without_a_phone(self, client, donate_page, pledge, esewa_qr):
        say_paid(client, donate_page, pledge, esewa_qr)

        page = soup(client.get(checking_url(donate_page, pledge)))

        assert "Call us" not in text_of(page.select_one("main"))

    def test_names_the_code_in_the_readers_language(
        self, client, donate_page, nepali_home_page, esewa_qr
    ):
        nepali_page = donate_page.copy_for_translation(nepali_home_page.locale)
        nepali_page.save_revision().publish()
        QRCodeName.objects.create(code=esewa_qr, locale=nepali_home_page.locale, name="इसेवा")
        pledge = Pledge.objects.create(page=nepali_page, amount=2500, currency="NPR", name="Sita")
        say_paid(client, nepali_page, pledge, esewa_qr)

        assert "इसेवा" in text(client.get(checking_url(nepali_page, pledge)))

    def test_keeps_the_codes_name_once_it_is_removed(self, client, donate_page, pledge, esewa_qr):
        say_paid(client, donate_page, pledge, esewa_qr)
        esewa_qr.delete()

        assert "by eSewa on" in text(client.get(checking_url(donate_page, pledge)))

    @pytest.mark.parametrize("tail", ["", "online/", "qr/", "qr/paid/", "in-person/", "later/"])
    def test_every_pay_address_goes_to_it(
        self, client, donate_page, pledge, esewa_qr, fake_provider, tail
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        response = client.get(f"{donate_page.url}pay/{pledge.reference}/{tail}")

        assert response.status_code == 303
        assert response.url == checking_url(donate_page, pledge)

    def test_no_online_payment_starts_meanwhile(
        self, client, donate_page, pledge, esewa_qr, fake_provider
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        response = client.post(f"{donate_page.url}pay/{pledge.reference}/online/fakepay/")

        assert response.status_code == 303
        assert response.url == checking_url(donate_page, pledge)
        assert list(pledge.payments.values_list("method", flat=True)) == ["qr"]
        assert fake_provider.started == []

    @pytest.mark.parametrize("outcome", ["unpaid", "not-found", "paid"])
    def test_goes_to_the_pay_page_when_nothing_is_being_checked(
        self, client, donate_page, pledge, esewa_qr, django_user_model, outcome
    ):
        if outcome != "unpaid":
            payment = pledge.claim_paid(esewa_qr, "TXN-8841")
            user = django_user_model.objects.create_user(username="ram")
            if outcome == "paid":
                payment.mark_paid(user, timezone.localdate(), 2500, "RBB-77")
            else:
                payment.mark_not_found(user)

        response = client.get(checking_url(donate_page, pledge))

        assert response.status_code == 303
        assert response.url == f"{donate_page.url}pay/{pledge.reference}/"


class TestWhenTheTeamCouldntFindIt:
    def test_says_so_and_asks_not_to_pay_again(
        self, client, donate_page, pledge, esewa_qr, django_user_model
    ):
        payment = pledge.claim_paid(esewa_qr, "TXN-8841")
        payment.mark_not_found(django_user_model.objects.create_user(username="ram"))

        response = client.get(qr_url(donate_page, pledge))

        assert "We haven't found your payment yet." in text(response)
        assert "don't pay again" in text(response)
        assert soup(response).select_one("[role=alert].is-problem")
        assert soup(response).select_one("details.pay-again form.qr-pay")


class TestOnceThePaymentIsConfirmed:
    @pytest.mark.parametrize(
        "amount, says", [(2500, "has reached us"), (2000, "We received Rs 2,000")]
    )
    def test_every_pay_address_says_thank_you(
        self, client, donate_page, pledge, esewa_qr, django_user_model, amount, says
    ):
        payment = pledge.claim_paid(esewa_qr, "TXN-8841")
        user = django_user_model.objects.create_user(username="ram")
        payment.mark_paid(user, timezone.localdate(), amount, "RBB-77")

        for tail in ("", "qr/", "online/", "later/"):
            page = client.get(f"{donate_page.url}pay/{pledge.reference}/{tail}")
            assert says in text(page), tail


class TestTheMarkPaidForm:
    def form(self, pledge, received_on, amount=2500):
        return MarkPaidForm(
            {"received_on": received_on, "amount": amount, "reference": "RBB-77"}, pledge=pledge
        )

    def test_takes_today_and_the_day_of_the_pledge(self, pledge):
        assert self.form(pledge, timezone.localdate()).is_valid()
        assert self.form(pledge, timezone.localdate(pledge.created_at)).is_valid()

    def test_refuses_a_day_after_today(self, pledge):
        # Say the year from a Nepali statement: 2083 in Bikram Sambat.
        form = self.form(pledge, timezone.localdate().replace(year=2083))

        assert form.errors["received_on"] == ["It can't be after today."]

    def test_refuses_a_day_before_the_pledge(self, pledge):
        form = self.form(pledge, timezone.localdate(pledge.created_at) - datetime.timedelta(1))

        assert form.errors["received_on"] == ["It can't be before the pledge was sent."]

    def test_takes_up_to_the_most_a_pledge_can_be(self, pledge):
        assert self.form(pledge, timezone.localdate(), amount=999_999).is_valid()

    def test_refuses_an_amount_no_pledge_could_have(self, pledge):
        form = self.form(pledge, timezone.localdate(), amount=1_000_000)

        assert "amount" in form.errors


class TestConfirmingInTheAdmin:
    @pytest.fixture
    def claimed(self, pledge, esewa_qr):
        return pledge.claim_paid(esewa_qr, "TXN-8841")

    def mark_paid_url(self, claimed):
        return reverse("pledges:mark_paid", args=[claimed.pledge_id, claimed.pk])

    def not_found_url(self, claimed):
        return reverse("pledges:not_found", args=[claimed.pledge_id, claimed.pk])

    def test_a_moderator_marks_it_paid(self, client, moderator, claimed):
        client.force_login(moderator)

        response = client.post(
            self.mark_paid_url(claimed),
            {"received_on": timezone.localdate(), "amount": "2500", "reference": "RBB-77"},
        )

        assert response.status_code == 302
        claimed.refresh_from_db()
        assert (claimed.status, claimed.provider_reference) == ("paid", "RBB-77")
        assert claimed.steps.last().by == moderator

    def test_a_moderator_marks_it_not_found(self, client, moderator, claimed):
        client.force_login(moderator)

        client.post(self.not_found_url(claimed))

        claimed.refresh_from_db()
        assert claimed.status == PaymentStatus.FAILED
        assert claimed.steps.last().by == moderator

    def test_an_editor_cant(self, client, editor, claimed):
        client.force_login(editor)

        paid = client.post(
            self.mark_paid_url(claimed),
            {"received_on": "2026-10-15", "amount": "2500", "reference": "RBB-77"},
        )
        missing = client.post(self.not_found_url(claimed))

        # Wagtail sends a user without permission back to the dashboard.
        assert [(r.status_code, r.url) for r in (paid, missing)] == [
            (302, reverse("wagtailadmin_home"))
        ] * 2
        claimed.refresh_from_db()
        assert claimed.status == PaymentStatus.TO_CONFIRM

    def test_never_an_online_payment(self, client, moderator, pledge):
        online = pledge.start_payment("esewa", live=True)
        client.force_login(moderator)

        client.post(
            self.mark_paid_url(online),
            {"received_on": "2026-10-15", "amount": "2500", "reference": "X"},
        )

        online.refresh_from_db()
        assert online.status == PaymentStatus.WAITING

    def test_a_bad_form_changes_nothing(self, client, moderator, claimed):
        client.force_login(moderator)

        client.post(
            self.mark_paid_url(claimed),
            {"received_on": "not a date", "amount": "0", "reference": ""},
        )

        claimed.refresh_from_db()
        assert claimed.status == PaymentStatus.TO_CONFIRM

    def test_it_is_a_post(self, client, moderator, claimed):
        client.force_login(moderator)

        assert client.get(self.mark_paid_url(claimed)).status_code == 405

    def test_the_pledge_page_offers_the_actions_to_a_moderator_only(
        self, client, moderator, editor, claimed
    ):
        inspect = reverse("pledges:inspect", args=[claimed.pledge_id])

        client.force_login(moderator)
        moderators = client.get(inspect).content.decode()
        client.force_login(editor)
        editors = client.get(inspect).content.decode()

        assert "Mark as paid" in moderators
        assert "Not found" in moderators
        assert "TXN-8841" in editors
        assert "Mark as paid" not in editors

    def test_any_method_the_team_confirms_gets_the_actions(
        self, client, moderator, pledge, monkeypatch
    ):
        # Say a bank transfer, checked by hand like a QR payment.
        monkeypatch.setitem(TEAM_CONFIRMED, "bank", "Bank transfer")
        pledge.payments.create(
            method="bank", amount=2500, currency="NPR", status=PaymentStatus.TO_CONFIRM, live=True
        )
        client.force_login(moderator)

        html = client.get(reverse("pledges:inspect", args=[pledge.pk])).content.decode()

        assert "Mark as paid" in html
        assert "Not found" in html

    def test_to_confirm_is_listed_and_filterable(self, client, moderator, claimed):
        client.force_login(moderator)

        listed = client.get(reverse("pledges:index"), {"payment_status": "to-confirm"})

        assert "To confirm" in listed.content.decode()
        assert "Sita Sharma" in listed.content.decode()


class TestQRCodesInTheAdmin:
    def test_a_moderator_sees_an_add_button_when_there_are_none(self, client, moderator):
        client.force_login(moderator)

        html = client.get(reverse("wagtailsnippets_campaigns_qrcode:list")).content.decode()

        assert "QR code" in html
        assert reverse("wagtailsnippets_campaigns_qrcode:add") in html

    def test_a_listed_code_opens_its_edit_page(self, client, moderator, esewa_qr):
        client.force_login(moderator)

        html = client.get(reverse("wagtailsnippets_campaigns_qrcode:list")).content.decode()

        assert "BRIGHTWELL WATER" in html
        assert reverse("wagtailsnippets_campaigns_qrcode:edit", args=[esewa_qr.pk]) in html

    def test_the_list_costs_the_same_however_many_codes(self, client, moderator, esewa_qr):
        client.force_login(moderator)
        url = reverse("wagtailsnippets_campaigns_qrcode:list")
        client.get(url)  # the first request warms Wagtail's caches

        with CaptureQueriesContext(connection) as one:
            client.get(url)
        make_code("Fonepay (bank)")
        make_code("Khalti")
        with CaptureQueriesContext(connection) as three:
            html = client.get(url).content.decode()

        assert len(three) == len(one)
        assert "Fonepay (bank)" in html and "Khalti" in html

    def test_an_editor_cant_open_them(self, client, editor, esewa_qr):
        client.force_login(editor)

        for name, args in [("list", []), ("add", []), ("edit", [esewa_qr.pk])]:
            response = client.get(reverse(f"wagtailsnippets_campaigns_qrcode:{name}", args=args))
            assert response.status_code in (302, 403), name
            assert "BRIGHTWELL" not in response.content.decode()

    @pytest.mark.parametrize("extension, image_format", [("jpeg", "JPEG"), ("jpg", "JPEG")])
    def test_a_jpeg_is_accepted_whichever_way_its_named(
        self, client, moderator, extension, image_format
    ):
        client.force_login(moderator)
        locale = Locale.get_default()

        response = client.post(
            reverse("wagtailsnippets_campaigns_qrcode:add"),
            {
                "image": card(image_format, f"qr.{extension}"),
                "account_name": "BRIGHTWELL WATER",
                "account_number": "",
                "texts-TOTAL_FORMS": "1",
                "texts-INITIAL_FORMS": "0",
                "texts-MIN_NUM_FORMS": "0",
                "texts-MAX_NUM_FORMS": "1000",
                "texts-0-locale": str(locale.pk),
                "texts-0-name": "eSewa",
                "texts-0-id": "",
                "texts-0-ORDER": "1",
                "texts-0-DELETE": "",
            },
        )

        assert response.status_code == 302, response.content.decode()[:2000]
        assert QRCode.objects.get().image.name.endswith(".jpg")

    def test_something_that_isnt_a_picture_is_refused(self, client, moderator):
        client.force_login(moderator)

        response = client.post(
            reverse("wagtailsnippets_campaigns_qrcode:add"),
            {
                "image": SimpleUploadedFile("qr.png", b"not a picture"),
                "account_name": "BRIGHTWELL WATER",
                "texts-TOTAL_FORMS": "0",
                "texts-INITIAL_FORMS": "0",
                "texts-MIN_NUM_FORMS": "0",
                "texts-MAX_NUM_FORMS": "1000",
            },
        )

        assert response.status_code == 200
        assert QRCode.objects.count() == 0
