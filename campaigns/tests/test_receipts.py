"""The receipt screenshot a supporter can send with "I've paid" (#197, part 2): what's taken, where
it's kept, who can see it, and when it's deleted."""

import datetime
import io
import os

import pytest
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from campaigns.models import RECEIPT_MAX_PIXELS, RECEIPT_WIDTH, Payment, PaymentStatus, Pledge
from campaigns.tests.test_qr import checking_url, make_code, qr_url, soup, text

pytestmark = pytest.mark.django_db


def screenshot(image_format="PNG", name="receipt.png", size=(1080, 2400)):
    saved = io.BytesIO()
    Image.new("RGB", size, "white").save(saved, format=image_format)
    return SimpleUploadedFile(name, saved.getvalue())


@pytest.fixture
def esewa_qr():
    return make_code("eSewa")


@pytest.fixture
def pledge(donate_page):
    return Pledge.objects.create(
        page=donate_page, amount=2500, currency="NPR", name="Sita Sharma", email="sita@example.com"
    )


def say_paid(client, donate_page, pledge, code, transaction_id="", receipt=None):
    fields = {"code": code.pk, "transaction_id": transaction_id}
    if receipt:
        fields["receipt"] = receipt
    return client.post(qr_url(donate_page, pledge, "paid/"), fields)


@pytest.fixture
def claimed(client, donate_page, pledge, esewa_qr):
    """A QR payment the supporter sent a screenshot with, waiting for the team."""
    say_paid(client, donate_page, pledge, esewa_qr, receipt=screenshot())
    return pledge.payments.get()


def stored(payment):
    return payment.receipt.storage.exists(payment.receipt.name)


class TestSendingIt:
    @pytest.mark.parametrize(
        ("transaction_id", "receipt"),
        [("TXN-8841", False), ("", True), ("TXN-8841", True)],
        ids=["id", "screenshot", "both"],
    )
    def test_the_transaction_id_or_a_screenshot_will_do(
        self, client, donate_page, pledge, esewa_qr, transaction_id, receipt
    ):
        response = say_paid(
            client, donate_page, pledge, esewa_qr, transaction_id, receipt and screenshot()
        )

        assert response.status_code == 303
        payment = pledge.payments.get()
        assert payment.status == PaymentStatus.TO_CONFIRM
        assert payment.supporters_reference == transaction_id
        assert bool(payment.receipt) is receipt

    @pytest.mark.parametrize(
        "upload",
        [
            SimpleUploadedFile("receipt.png", b"not a picture at all"),
            SimpleUploadedFile("receipt.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>"),
        ],
        ids=["text", "svg"],
    )
    def test_refuses_what_isnt_a_picture(self, client, donate_page, pledge, esewa_qr, upload):
        response = say_paid(client, donate_page, pledge, esewa_qr, "TXN-8841", upload)

        assert response.status_code == 422
        page = soup(response)
        field = page.select_one("input[name=receipt]")
        assert field["aria-invalid"] == "true"
        assert "id_receipt_error" in field["aria-describedby"].split()
        assert (
            "Upload a JPEG, PNG or WebP image of up to 5 MB."
            in page.select_one("#id_receipt_error").get_text()
        )
        alert = page.select_one("[role=alert]")
        assert alert.select_one("a[href='#id_receipt']")
        assert "Check the screenshot below." in alert.get_text()
        assert pledge.payments.count() == 0

    def test_refuses_a_picture_bigger_than_a_phone_makes(
        self, client, donate_page, pledge, esewa_qr
    ):
        # A few KB that would decode to a picture filling the server's memory.
        saved = io.BytesIO()
        side = int(RECEIPT_MAX_PIXELS**0.5) + 1
        Image.new("1", (side, side), 1).save(saved, format="PNG")
        upload = SimpleUploadedFile("receipt.png", saved.getvalue())

        response = say_paid(client, donate_page, pledge, esewa_qr, "TXN-8841", upload)

        assert response.status_code == 422
        assert (
            "This picture is too large: upload a smaller one."
            in soup(response).select_one("#id_receipt_error").get_text()
        )
        assert pledge.payments.count() == 0

    @pytest.mark.parametrize(
        "size",
        [(4608, 3456), (5712, 4284)],
        ids=["16-megapixel camera", "iPhone's 24 megapixels"],
    )
    def test_takes_a_photo_from_any_phone_camera(self, client, donate_page, pledge, esewa_qr, size):
        upload = screenshot("JPEG", name="photo.jpg", size=size)

        say_paid(client, donate_page, pledge, esewa_qr, receipt=upload)

        # Only the smaller copy is kept, never the photo as it came.
        receipt = pledge.payments.get().receipt
        assert Image.open(receipt).size == (2000, round(2000 * size[1] / size[0]))

    def test_is_saved_afresh_under_a_name_of_our_own(self, client, donate_page, pledge, esewa_qr):
        upload = screenshot("JPEG", name="sita-sharma-receipt.jpg", size=(1440, 3200))

        say_paid(client, donate_page, pledge, esewa_qr, receipt=upload)

        receipt = pledge.payments.get().receipt
        assert "sita" not in receipt.name
        assert receipt.name.endswith(".jpg")
        assert max(Image.open(receipt).size) == RECEIPT_WIDTH

    def test_step_2_asks_for_either_and_can_send_a_file(
        self, client, donate_page, pledge, esewa_qr
    ):
        page = soup(client.get(qr_url(donate_page, pledge, "paid/")))

        form = page.select_one("form.qr-paid")
        assert form["enctype"] == "multipart/form-data"
        assert "Give the transaction ID, a screenshot of the receipt, or both." in " ".join(
            form.get_text().split()
        )
        assert not form.select_one("input[name=transaction_id]").has_attr("required")
        field = form.select_one("input[name=receipt]")
        assert field["type"] == "file"
        assert field["accept"] == "image/jpeg,image/png,image/webp"
        assert form.select_one("label[for=id_receipt]").get_text(strip=True) == (
            "Screenshot of the receipt"
        )
        assert (
            "A JPEG, PNG or WebP image of up to 5 MB."
            in page.select_one("#receipt-help").get_text()
        )

    @pytest.mark.parametrize(
        ("transaction_id", "said"),
        [
            ("", "You sent us a screenshot of the receipt."),
            (
                "TXN-8841",
                "You sent us the transaction ID TXN-8841 and a screenshot of the receipt.",
            ),
        ],
    )
    def test_the_checking_page_says_a_screenshot_was_sent(
        self, client, donate_page, pledge, esewa_qr, transaction_id, said
    ):
        say_paid(client, donate_page, pledge, esewa_qr, transaction_id, screenshot())

        assert said in text(client.get(checking_url(donate_page, pledge)))


class TestSeeingIt:
    def receipt_url(self, payment):
        return reverse("pledges:receipt", args=[payment.pledge_id, payment.pk])

    def test_a_moderator_sees_it_on_the_pledge(self, client, moderator, claimed):
        client.force_login(moderator)

        page = BeautifulSoup(
            client.get(reverse("pledges:inspect", args=[claimed.pledge_id])).content, "html.parser"
        )
        image = page.select_one(f"img[src='{self.receipt_url(claimed)}']")
        assert image["alt"] == "The supporter's screenshot of their receipt"

        response = client.get(self.receipt_url(claimed))
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert "no-store" in response["Cache-Control"]
        assert Image.open(io.BytesIO(b"".join(response.streaming_content))).format == "PNG"

    def test_an_editor_only_reads_that_one_was_sent(self, client, editor, claimed):
        client.force_login(editor)

        html = client.get(reverse("pledges:inspect", args=[claimed.pledge_id])).content.decode()
        response = client.get(self.receipt_url(claimed))

        assert self.receipt_url(claimed) not in html
        assert "Only people who can confirm payments can see it." in html
        # Wagtail sends a user without permission back to the dashboard.
        assert (response.status_code, response.url) == (302, reverse("wagtailadmin_home"))

    def test_a_visitor_cant(self, client, claimed):
        response = client.get(self.receipt_url(claimed))

        assert response.status_code == 302
        assert response.url.startswith(reverse("wagtailadmin_login"))

    def test_there_is_none_to_see_without_one(self, client, moderator, pledge, esewa_qr):
        payment = pledge.claim_paid(esewa_qr, "TXN-8841")
        client.force_login(moderator)

        assert client.get(self.receipt_url(payment)).status_code == 404

    def test_a_missing_file_is_not_found(self, client, moderator, claimed):
        claimed.receipt.storage.delete(claimed.receipt.name)
        client.force_login(moderator)

        assert client.get(self.receipt_url(claimed)).status_code == 404


class TestDeletingIt:
    @pytest.fixture
    def team(self, django_user_model):
        return django_user_model.objects.create_user(username="ram")

    def test_once_marked_paid(self, claimed, team, django_capture_on_commit_callbacks):
        name = claimed.receipt.name

        with django_capture_on_commit_callbacks(execute=True):
            claimed.mark_paid(team, timezone.localdate(), 2500, "RBB-77")

        assert not claimed.receipt.storage.exists(name)
        assert not Payment.objects.get(pk=claimed.pk).receipt

    def test_once_marked_not_found(self, claimed, team, django_capture_on_commit_callbacks):
        name = claimed.receipt.name

        with django_capture_on_commit_callbacks(execute=True):
            claimed.mark_not_found(team)

        assert not claimed.receipt.storage.exists(name)
        assert not Payment.objects.get(pk=claimed.pk).receipt

    def test_with_its_pledge(self, claimed, django_capture_on_commit_callbacks):
        name = claimed.receipt.name

        with django_capture_on_commit_callbacks(execute=True):
            claimed.pledge.delete()

        assert not claimed.receipt.storage.exists(name)

    def test_after_30_days_unchecked(
        self, client, donate_page, esewa_qr, claimed, django_capture_on_commit_callbacks
    ):
        newer = Pledge.objects.create(page=donate_page, amount=1500, currency="NPR", name="Hari")
        say_paid(client, donate_page, newer, esewa_qr, receipt=screenshot())
        kept = newer.payments.get()
        Payment.objects.filter(pk=claimed.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=30, minutes=1)
        )
        Payment.objects.filter(pk=kept.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=29)
        )

        with django_capture_on_commit_callbacks(execute=True):
            call_command("delete_old_receipts", stdout=io.StringIO())

        assert not stored(claimed)
        assert not Payment.objects.get(pk=claimed.pk).receipt
        # Still to confirm: only the screenshot goes.
        assert Payment.objects.get(pk=claimed.pk).status == PaymentStatus.TO_CONFIRM
        assert stored(Payment.objects.get(pk=kept.pk))

    def test_a_file_no_payment_points_at_after_30_days(self, tmp_path, monkeypatch):
        # Left behind by a request that broke after saving it.
        field = Payment._meta.get_field("receipt")
        monkeypatch.setattr(field, "storage", FileSystemStorage(location=tmp_path))
        old, new = field.storage.save("old.png", ContentFile(b"x")), "new.png"
        field.storage.save(new, ContentFile(b"x"))
        month_ago = (timezone.now() - datetime.timedelta(days=31)).timestamp()
        os.utime(tmp_path / old, (month_ago, month_ago))

        call_command("delete_old_receipts", stdout=io.StringIO())

        assert sorted(path.name for path in tmp_path.iterdir()) == ["new.png"]
