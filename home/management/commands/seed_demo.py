import datetime
import io
from decimal import Decimal

from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw
from wagtail.models import Site

from campaigns.models import CampaignIndexPage, CampaignPage
from contact.models import FormField, FormPage
from core.models import AnnouncementBanner, CustomImage, Partner, SiteSettings, Testimonial
from home.models import StandardPage
from news.models import NewsCategory, NewsIndexPage, NewsPage

SITE_NAME = "Brightwell Water Trust"
TODAY = datetime.date.today()


def make_image(title, colours, description, credit="Photo: Brightwell field team"):
    """Generate a simple gradient placeholder so the demo needs no binary assets."""
    width, height = 1600, 900
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    (r1, g1, b1), (r2, g2, b2) = colours
    for y in range(height):
        t = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=(int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t)),
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    filename = title.lower().replace(" ", "-") + ".jpg"
    return CustomImage.objects.create(
        title=title,
        description=description,
        credit=credit,
        consent_confirmed=True,
        file=ImageFile(buffer, name=filename),
    )


def publish(parent, page):
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


class Command(BaseCommand):
    help = "Create demo content for a fictional water charity. Safe to run more than once."

    @transaction.atomic
    def handle(self, *args, **options):
        # Also on re-runs, so an existing local database gets working full URLs.
        call_command("update_site_url", stdout=self.stdout)

        site = Site.objects.get(is_default_site=True)
        home = site.root_page.specific

        if CampaignIndexPage.objects.exists():
            self.stdout.write("Demo content already exists; nothing else to do.")
            return

        site.site_name = SITE_NAME
        site.save()

        images = {
            "hero": make_image(
                "Hero water", ((11, 85, 99), (7, 59, 69)), "A child drinking clean water from a tap"
            ),
            "well": make_image(
                "New well", ((42, 157, 143), (11, 85, 99)), "Villagers gathered around a new well"
            ),
            "flood": make_image(
                "Flood relief", ((69, 123, 157), (29, 53, 87)), "Volunteers handing out supplies"
            ),
            "school": make_image(
                "School taps", ((233, 196, 106), (244, 162, 97)), "Pupils washing hands at school"
            ),
            "logo": make_image(
                "Partner logo", ((230, 230, 230), (200, 200, 200)), "Partner logo", credit=""
            ),
        }

        about = publish(
            home,
            StandardPage(
                title="About us",
                slug="about",
                show_in_menus=True,
                introduction=(
                    "Brightwell is a fictional charity created to demonstrate Wagtail. "
                    "We help communities build and look after their own water supplies."
                ),
                search_description="Who we are and how we work.",
                body=[
                    ("heading", {"heading_text": "Our approach", "size": "h2"}),
                    (
                        "paragraph",
                        "<p>We work with local engineers and water committees, so every well "
                        "is <mark>owned and maintained by the community</mark> that uses it.</p>",
                    ),
                    (
                        "impact_stats",
                        {
                            "heading": "Since 2004",
                            "stats": [
                                {"figure": "412", "label": "wells built"},
                                {"figure": "180,000", "label": "people with clean water"},
                                {"figure": "96%", "label": "still working after 5 years"},
                            ],
                        },
                    ),
                    (
                        "quote",
                        {
                            "text": "Start small, stay local, and keep the water running.",
                            "attribution": "Our founding principle",
                        },
                    ),
                ],
            ),
        )
        donate = publish(
            home,
            StandardPage(
                title="Donate",
                slug="donate",
                introduction="Every gift helps a community get safe water that lasts.",
                body=[
                    (
                        "table",
                        {
                            "first_row_is_table_header": True,
                            "first_col_is_header": False,
                            "data": [
                                ["Where £1 goes", "Amount"],
                                ["Projects", "82p"],
                                ["Fundraising", "13p"],
                                ["Running the charity", "5p"],
                            ],
                        },
                    ),
                ],
            ),
        )

        campaigns = publish(
            home,
            CampaignIndexPage(
                title="Appeals",
                slug="appeals",
                show_in_menus=True,
                introduction="Choose an appeal and see exactly what your gift will do.",
            ),
        )
        flood = self.add_campaign(
            campaigns,
            title="Flood relief in Tana River",
            slug="flood-relief",
            summary="Families have lost their homes and their water supply to flooding.",
            hero_image=images["flood"],
            target=Decimal("50000"),
            raised=Decimal("31250"),
            start=TODAY - datetime.timedelta(days=10),
            end=TODAY + datetime.timedelta(days=9),
            amounts=[(25, "A hygiene kit for a family"), (100, "Water purification for a month")],
        )
        self.add_campaign(
            campaigns,
            title="Clean water for Kisumu",
            slug="clean-water-kisumu",
            summary="Twelve villages still walk two hours a day for water.",
            hero_image=images["well"],
            target=Decimal("80000"),
            raised=Decimal("24000"),
            start=TODAY - datetime.timedelta(days=40),
            end=None,
            amounts=[(10, "Clean water for one person for a year"), (250, "A hand pump repair")],
        )
        self.add_campaign(
            campaigns,
            title="Taps for schools",
            slug="taps-for-schools",
            summary="Handwashing stations keep children healthy and in class.",
            hero_image=images["school"],
            target=Decimal("15000"),
            raised=Decimal("9100"),
            start=TODAY - datetime.timedelta(days=20),
            end=TODAY + datetime.timedelta(days=60),
            amounts=[(40, "A handwashing station")],
        )
        self.add_campaign(
            campaigns,
            title="Winter appeal 2025",
            slug="winter-appeal-2025",
            summary="Thanks to you, 20 communities kept their water running through winter.",
            hero_image=images["hero"],
            target=Decimal("20000"),
            raised=Decimal("23400"),
            start=TODAY - datetime.timedelta(days=300),
            end=TODAY - datetime.timedelta(days=200),
            amounts=[],
        )

        news = publish(
            home,
            NewsIndexPage(
                title="News",
                slug="news",
                show_in_menus=True,
                introduction="Stories and updates from our partners and supporters.",
            ),
        )
        stories = NewsCategory.objects.create(name="Stories", slug="stories")
        press = NewsCategory.objects.create(name="Press releases", slug="press")
        self.add_story(
            news,
            "The well that brought Grace back to school",
            "Grace used to spend every morning fetching water. Now she spends it in class.",
            images["well"],
            ["water", "education"],
            [stories],
            days_ago=2,
        )
        self.add_story(
            news,
            "Brightwell responds to Tana River flooding",
            "Our teams are distributing hygiene kits and purification tablets.",
            images["flood"],
            ["emergency"],
            [press],
            days_ago=6,
        )
        self.add_story(
            news,
            "Volunteers of the year",
            "Meet the supporters who ran, baked and cycled for clean water.",
            images["school"],
            ["volunteering"],
            [stories],
            days_ago=15,
        )

        volunteer = FormPage(
            title="Volunteer with us",
            slug="volunteer",
            show_in_menus=True,
            intro="<p>Give a few hours a month at events, in our shops or from home.</p>",
            thank_you_text="<p>Thank you! Our volunteer team will be in touch within a week.</p>",
            to_address="volunteers@example.org",
            from_address="website@example.org",
            subject="New volunteer sign-up",
        )
        volunteer.form_fields = [
            FormField(label="Your name", field_type="singleline", required=True),
            FormField(label="Email address", field_type="email", required=True),
            FormField(
                label="How would you like to help?",
                field_type="checkboxes",
                choices="Events\nShops\nFrom home",
                required=False,
            ),
        ]
        publish(home, volunteer)

        for order, name in enumerate(["Rivers Foundation", "Northgate Council", "Tapwell Ltd"]):
            Partner.objects.create(
                name=name, url="https://example.org", logo=images["logo"], sort_order=order
            )
        testimonial = Testimonial(
            quote="The new well means my daughter is back at school.",
            name="Grace",
            role="Parent, Kisumu",
            live=False,
        )
        testimonial.save()
        testimonial.save_revision().publish()

        home.hero_heading = "Clean water changes everything"
        home.hero_text = "£10 gives one person safe water for a whole year."
        home.hero_image = images["hero"]
        home.hero_cta_text = "Give today"
        home.hero_cta_page = donate
        home.search_description = "A fictional water charity built with Wagtail."
        home.body = [
            (
                "impact_stats",
                {
                    "heading": "Your support in numbers",
                    "stats": [
                        {"figure": "180,000", "label": "people with clean water"},
                        {"figure": "412", "label": "wells built"},
                        {"figure": "82p", "label": "of every £1 spent on projects"},
                    ],
                },
            ),
            ("testimonial", testimonial),
            (
                "call_to_action",
                {
                    "title": "Give a few hours a month",
                    "text": "Volunteers are at the heart of everything we do.",
                    "button_text": "Volunteer with us",
                    "page": volunteer,
                    "url": "",
                },
            ),
            ("partners", {"heading": "Our partners"}),
        ]
        home.save_revision().publish()

        settings = SiteSettings.for_site(site)
        settings.charity_number = "1234567 (fictional)"
        settings.contact_email = "hello@example.org"
        settings.phone = "0123 456 7890"
        settings.address = "1 Example Street\nBirmingham\nB1 1AA"
        settings.donate_page = donate
        settings.instagram_url = "https://instagram.com/example"
        settings.save()

        banner = AnnouncementBanner.load()
        banner.enabled = True
        banner.message = "Emergency appeal: help families affected by flooding in Tana River"
        banner.link_page = flood
        banner.save()

        self.stdout.write(self.style.SUCCESS(f"Created demo content for {SITE_NAME}."))
        self.stdout.write(f"About page: {about.url}")

    def add_campaign(self, parent, *, amounts, target, raised, start, end, **fields):
        campaign = CampaignPage(
            target_amount=target,
            amount_raised=raised,
            start_date=start,
            end_date=end,
            body=[
                ("heading", {"heading_text": "Why it matters", "size": "h2"}),
                ("paragraph", f"<p>{fields['summary']} Your gift makes a lasting difference.</p>"),
            ],
            **fields,
        )
        parent.add_child(instance=campaign)
        for amount, impact in amounts:
            campaign.donation_amounts.create(amount=amount, impact=impact)
        campaign.save_revision().publish()
        return campaign

    def add_story(self, parent, title, introduction, image, tags, categories, days_ago):
        story = NewsPage(
            title=title,
            date=TODAY - datetime.timedelta(days=days_ago),
            introduction=introduction,
            hero_image=image,
            body=[("paragraph", f"<p>{introduction}</p>")],
        )
        parent.add_child(instance=story)
        story.tags.add(*tags)
        story.categories.set(categories)
        story.save_revision().publish()
        return story
