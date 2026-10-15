"""Paying a pledge by scanning the charity's own QR code (#197): the QR codes in the admin, the QR
page and its states, "I've paid", and the team marking it paid or not found."""

import io

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone, translation
from PIL import Image
from wagtail.models import Locale

from campaigns.models import Payment, PaymentStatus, Pledge, QRCode, QRCodeName, StepKind
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


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def text(response):
    return " ".join(soup(response).get_text().split())


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

    def test_replacing_the_image_removes_the_old_files(self, esewa_qr):
        old = {esewa_qr.image.name, esewa_qr.image_small.name}

        esewa_qr.image = card("JPEG", "new.jpg")
        esewa_qr.save()

        storage = esewa_qr.image.storage
        assert not any(storage.exists(name) for name in old)
        assert storage.exists(esewa_qr.image.name)

    def test_removing_the_code_removes_both_files(self, esewa_qr):
        names = {esewa_qr.image.name, esewa_qr.image_small.name}

        esewa_qr.delete()

        assert not any(esewa_qr.image.storage.exists(name) for name in names)

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
        assert "Save image" in save.get_text()

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

    def test_says_how_to_scan_on_a_phone_and_on_a_computer(
        self, client, donate_page, pledge, esewa_qr
    ):
        response = client.get(qr_url(donate_page, pledge))
        words = text(response)

        # Folded under a title that says what's inside, so it doesn't push the account down.
        how = soup(response).select_one(".qr-card details.qr-how")
        assert how.summary.get_text(strip=True) == "Need help saving or scanning the image?"
        assert not how.has_attr("open")
        assert len(how.select("p.qr-help")) == 3
        assert "On an Android phone? Save the image" in words
        assert "On a computer? Scan the code on screen with your phone." in words
        assert "On an iPhone, press and hold the QR code" in words

    def test_has_its_own_title(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        assert "Scan our QR code" in page.title.get_text()


class TestTheTwoSteps:
    def test_are_sections_the_row_of_steps_jumps_to(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        nav = page.select_one("nav[aria-label=Steps]")
        assert [a["href"] for a in nav.select("ol > li > a")] == ["#step-1", "#step-2"]
        assert [a.get_text(strip=True).lstrip("12") for a in nav.select("a")] == [
            "Scan the QR code",
            "Paid? Tell us",
        ]
        headings = [h2.get_text(strip=True) for h2 in page.select("form.qr-pay section > h2")]
        assert headings == ["Step 1: Pay with your app", "Step 2: Paid? Tell us here"]
        for number in ("1", "2"):
            section = page.select_one(f"form.qr-pay section#step-{number}")
            assert section["aria-labelledby"] == f"step-{number}-title"
            assert section.select_one(f"#step-{number}-title")

    def test_step_1_ends_with_a_way_back_to_step_2(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        step_1 = page.select_one("#step-1")
        assert "Paid in your app? Come back to this page and" in step_1.get_text()
        assert step_1.select("a[href='#step-2']")

    def test_step_2_says_where_to_find_the_id_before_the_field(
        self, client, donate_page, pledge, esewa_qr
    ):
        step_2 = soup(client.get(qr_url(donate_page, pledge))).select_one("#step-2")

        field = step_2.select_one("input[name=transaction_id]")
        steps = step_2.select("#transaction-id-help li")
        assert len(steps) == 2
        assert field.sourceline > steps[1].sourceline
        assert "transaction-id-help" in field["aria-describedby"]
        assert field.has_attr("required")

    def test_ive_paid_says_it_is_sending(self, client, donate_page, pledge, esewa_qr):
        page = soup(client.get(qr_url(donate_page, pledge)))

        button = page.select_one("form.qr-pay button[type=submit]")
        assert button["data-busy-text"] == "Sending…"
        assert page.select_one("form.qr-pay [data-busy-status][role=status]")

    def test_the_second_is_ticked_once_they_have_paid_and_nothing_jumps_into_the_fold(
        self, client, donate_page, pledge, esewa_qr
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        page = soup(client.get(qr_url(donate_page, pledge)))

        assert page.select("nav[aria-label=Steps]") == []
        steps = page.select("ol.pay-steps > li")
        assert [li.select("a") for li in steps] == [[], []]
        assert steps[0].select(".is-done") == []
        assert steps[1].select_one(".is-done svg")
        assert "(done)" in steps[1].get_text()

    def test_nothing_is_ticked_when_the_team_couldnt_find_it(
        self, client, donate_page, pledge, esewa_qr, django_user_model
    ):
        payment = pledge.claim_paid(esewa_qr, "TXN-8841")
        payment.mark_not_found(django_user_model.objects.create_user(username="ram"))

        page = soup(client.get(qr_url(donate_page, pledge)))

        assert len(page.select("ol.pay-steps > li")) == 2
        assert page.select("ol.pay-steps .is-done") == []
        assert "(done)" not in page.select_one("ol.pay-steps").get_text()


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
    def test_goes_to_the_page_that_says_thank_you(self, client, donate_page, pledge, esewa_qr):
        response = say_paid(client, donate_page, pledge, esewa_qr)

        assert response.status_code == 303
        assert response.url == qr_url(donate_page, pledge)
        page = client.get(response.url)
        assert "Thank you. You've told us you paid Rs 2,500 by eSewa" in text(page)
        assert "TXN-8841" in text(page)
        assert "There's nothing more to do here." in text(page)
        assert "Checking your payment" in soup(page).title.get_text()

    def test_the_qr_and_ive_paid_fold_away_while_to_confirm(
        self, client, donate_page, pledge, esewa_qr
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        page = soup(client.get(qr_url(donate_page, pledge)))

        fold = page.select_one("details.pay-again")
        assert fold.select_one("form.qr-pay")

    def test_the_pay_page_goes_to_it(self, client, donate_page, pledge, esewa_qr, site):
        say_paid(client, donate_page, pledge, esewa_qr)

        response = client.get(f"{donate_page.url}pay/{pledge.reference}/")

        assert response.status_code == 303
        assert response.url == qr_url(donate_page, pledge)

    def test_sending_it_twice_makes_one_payment(self, client, donate_page, pledge, esewa_qr):
        say_paid(client, donate_page, pledge, esewa_qr)
        say_paid(client, donate_page, pledge, esewa_qr)

        assert pledge.payments.count() == 1

    def test_needs_the_transaction_id(self, client, donate_page, pledge, esewa_qr):
        response = say_paid(client, donate_page, pledge, esewa_qr, transaction_id="  ")

        assert response.status_code == 422
        assert "Enter the transaction ID from your receipt." in text(response)
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
        assert "Enter the transaction ID from your receipt." in error.get_text()
        assert field.find_parent("div").select_one("#id_transaction_id_error")
        alert = page.select_one("[role=alert]")
        assert alert.select_one("a")["href"] == "#id_transaction_id"
        assert "Check the transaction ID below." in alert.get_text()
        assert "Enter the transaction ID" not in alert.get_text()

    def test_the_field_has_no_error_before_anything_is_sent(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge)))

        field = page.select_one("input[name=transaction_id]")
        assert not field.has_attr("aria-invalid")
        assert page.select("#id_transaction_id_error") == []

    def test_a_mistake_opens_the_fold_it_was_made_in(
        self, client, donate_page, pledge, esewa_qr, django_user_model
    ):
        pledge.claim_paid(esewa_qr, "TXN-8841").mark_not_found(
            django_user_model.objects.create_user(username="ram")
        )

        page = soup(say_paid(client, donate_page, pledge, esewa_qr, transaction_id=" "))

        assert page.select_one("details.pay-again").has_attr("open")

    def test_only_names_a_code_on_the_page(self, client, donate_page, pledge, esewa_qr):
        response = client.post(
            qr_url(donate_page, pledge, "paid/"), {"code": "9999", "transaction_id": "TXN"}
        )

        assert response.status_code == 422
        assert pledge.payments.count() == 0

    def test_isnt_a_get(self, client, donate_page, pledge, esewa_qr):
        assert client.get(qr_url(donate_page, pledge, "paid/")).status_code == 405

    def test_not_once_paid(self, client, donate_page, pledge, esewa_qr):
        pledge.start_payment("esewa", live=False).record("paid", "000AWEO")

        response = say_paid(client, donate_page, pledge, esewa_qr)

        assert response.status_code == 303
        assert pledge.payments.count() == 1

    def test_the_online_page_folds_its_buttons_while_to_confirm(
        self, client, donate_page, pledge, esewa_qr, fake_provider
    ):
        say_paid(client, donate_page, pledge, esewa_qr)

        page = soup(client.get(f"{donate_page.url}pay/{pledge.reference}/online/"))

        assert page.select_one("details.pay-again form")
        assert "You've told us you paid by scanning our QR code" in page.get_text()


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
            {"received_on": "2026-10-15", "amount": "2500", "reference": "RBB-77"},
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
