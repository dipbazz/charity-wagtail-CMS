"""The hidden box that tells a simple script from a person on the public forms (#104). What a filled
box does to a pledge or a sign-up is in each app's own tests."""

import logging

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.core.cache import caches
from django.template import Context, Template
from django.template.loader import get_template
from django.utils import translation
from wagtail.contrib.forms.models import FormMixin

from campaigns.models import DonatePage
from core import honeypot

pytestmark = pytest.mark.django_db


class TestFilled:
    @pytest.mark.parametrize(("data", "is_filled"), [({}, False), ({"hp-leave-blank": ""}, False)])
    def test_a_missing_or_empty_box_is_a_person(self, data, is_filled):
        """A page cached from before the box, or a script posting only the fields, still sends."""
        assert honeypot.filled(data) is is_filled

    def test_anything_typed_is_a_script(self):
        assert honeypot.filled({"hp-leave-blank": "x"})

    def test_the_name_has_nothing_a_password_manager_fills(self):
        """A filled box drops the send, so autofill must never reach it by its name."""
        for word in ("name", "mail", "phone", "tel", "address", "website", "url", "company"):
            assert word not in honeypot.NAME


class TestLog:
    def test_says_once_per_window_which_page(self, home_page, caplog):
        with caplog.at_level(logging.WARNING, logger="core"):
            honeypot.dropped(home_page)
            honeypot.dropped(home_page)

        assert [r.levelname for r in caplog.records] == ["WARNING"]
        assert str(home_page.pk) in caplog.text

    def test_a_broken_cache_doesn_t_raise_and_says_so_once_per_window(
        self, home_page, monkeypatch, caplog
    ):
        """As core/limits.py does: drops that go unsaid must still leave a trace."""

        def broken(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(caches["limits"], "add", broken)
        monkeypatch.setattr(honeypot, "broken_logged_in", None)
        monkeypatch.setattr(honeypot.time, "time", lambda: 1000.0)
        with caplog.at_level(logging.ERROR, logger="core"):
            honeypot.dropped(home_page)
            honeypot.dropped(home_page)

        assert [r.levelname for r in caplog.records] == ["ERROR"]

        monkeypatch.setattr(honeypot.time, "time", lambda: 1300.0)
        with caplog.at_level(logging.ERROR, logger="core"):
            honeypot.dropped(home_page)

        assert len(caplog.records) == 2


def template_source(name):
    return get_template(name).template.source


class TestEveryForm:
    def test_every_form_page_type_drops_a_filled_box(self):
        """A new form type (#167, #168) needs the mixin before Wagtail's, and the box in its
        template. FormMixin serves both AbstractForm and AbstractEmailForm."""
        form_types = [
            model
            for model in apps.get_models()
            if issubclass(model, FormMixin) and not model._meta.abstract
        ]
        assert form_types
        for model in form_types:
            mro = model.__mro__
            assert honeypot.HoneypotFormMixin in mro and mro.index(
                honeypot.HoneypotFormMixin
            ) < mro.index(FormMixin), f"{model.__name__} lacks HoneypotFormMixin before FormMixin"
            assert "{% honeypot %}" in template_source(model.template), (
                f"{model.template} lacks {{% honeypot %}}"
            )

    def test_the_pledge_form_has_the_box(self):
        assert "{% honeypot %}" in template_source(DonatePage.template)


def box(language="en"):
    with translation.override(language):
        html = Template("{% load honeypot_tags %}{% honeypot %}").render(Context())
    return BeautifulSoup(html, "html.parser")


class TestTheBox:
    def test_hidden_from_sight_keyboards_screen_readers_and_autofill(self):
        """`hidden`, not CSS: a box moved off-screen can still be autofilled, and a real
        supporter's pledge dropped."""
        html = box()
        wrapper = html.find()
        field = html.find("input")

        assert wrapper.has_attr("hidden")
        assert field["name"] == "hp-leave-blank"
        assert field["tabindex"] == "-1"
        assert field["autocomplete"] == "off"
        assert html.find("label", attrs={"for": field["id"]}).get_text(strip=True) == (
            "Leave this blank"
        )

    def test_its_label_is_in_nepali_too(self):
        assert box("ne").find("label").get_text(strip=True) == "यो खाली छोड्नुहोस्"
