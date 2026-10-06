import datetime
import io
from decimal import Decimal
from pathlib import Path

from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont
from wagtail.images.rect import Rect
from wagtail.models import Locale, Site

from campaigns.models import CampaignIndexPage, CampaignPage, DonatePage, DonatePageAmount
from contact.models import FormField, FormPage
from core.models import AnnouncementBanner, CustomImage, Partner, SiteSettings, Testimonial
from home.models import StandardPage
from news.models import NewsCategory, NewsIndexPage, NewsPage

SITE_NAME = "Brightwell Water Trust"
TODAY = datetime.date.today()
IMAGES_DIR = Path(__file__).parent / "demo_images"
RELIEF_FUND_URL = "https://rescue.opmcm.gov.np/donations"

# Licences and source links are listed in docs/reference/demo-content.md.
# Focal points are (centre x, centre y, width, height) in pixels of the 1600px-wide file.
PHOTOS = {
    "hero": {
        "file": "hero.jpg",
        "title": "Family at a stone well",
        "description": "A woman and a young boy looking into a stone well in a garden",
        "credit": "Photo: Maxime Bouffard / Unsplash",
        "focal_point": (930, 640, 320, 520),
    },
    "well": {
        "file": "well.jpg",
        "title": "Boy at a hand pump",
        "description": "A young boy working the handle of a village hand pump",
        "credit": "Photo: bradford zak / Unsplash",
        "focal_point": (1000, 560, 700, 700),
    },
    "grace": {
        "file": "grace.jpg",
        "title": "Pupils in class",
        "description": "Pupils in school uniform raising their hands in a classroom",
        "credit": "Photo: Emmanuel Ikwuegbu / Unsplash",
        "focal_point": (770, 620, 500, 500),
    },
    "flood": {
        "file": "flood.jpg",
        "title": "Flooded camp (representative image)",
        "description": (
            "Flooded tents and shelters in a camp for displaced families. "
            "Representative image, not taken in Nepal"
        ),
        "credit": "Photo: Salah Darwish / Unsplash. Representative image, not taken in Nepal",
        "focal_point": (800, 720, 1400, 520),
    },
    "school": {
        "file": "school.jpg",
        "title": "Handwashing at an outdoor tap",
        "description": "A young child washing their hands under an outdoor tap",
        "credit": "Photo: Jonathan Shembere / Pexels",
        "focal_point": (720, 520, 700, 700),
    },
    "volunteers": {
        "file": "volunteers.jpg",
        "title": "Volunteers handing out aid",
        "description": "Volunteers in matching T-shirts handing out bottled water and aid boxes",
        "credit": "Photo: RDNE Stock project / Pexels",
        "focal_point": (720, 520, 900, 560),
    },
}

# Fictional partners: (name, logo colour, logo shape).
PARTNERS = [
    ("Rivers Foundation", (29, 111, 163), "wave"),
    ("Northgate Council", (46, 125, 50), "arch"),
    ("Tapwell Ltd", (199, 92, 18), "drop"),
]


def load_photo(file, title, description, credit, focal_point):
    """Create an image from a photo in demo_images.

    Stock licences cover copyright, not consent from the people pictured,
    so the photos are left unconsented and stay out of the API.
    """
    with open(IMAGES_DIR / file, "rb") as source:
        image = CustomImage(
            title=title,
            description=description,
            credit=credit,
            consent_confirmed=False,
            file=ImageFile(source, name=file),
        )
        if focal_point:
            image.set_focal_point(Rect.from_point(*focal_point))
        image.save()
    return image


def make_logo(name, colour, shape):
    """Draw a simple logo for a fictional partner, so the demo needs no brand assets."""
    image = Image.new("RGBA", (480, 160), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    if shape == "wave":
        for top in (40, 80, 120):
            draw.arc((10, top - 30, 65, top + 12), 200, 340, fill=colour, width=12)
            draw.arc((65, top - 12, 120, top + 30), 20, 160, fill=colour, width=12)
    elif shape == "arch":
        draw.rectangle((15, 65, 120, 145), fill=colour)
        draw.pieslice((15, 12, 120, 117), 180, 360, fill=colour)
        draw.rectangle((47, 82, 88, 145), fill=(255, 255, 255, 0))
    else:
        draw.polygon([(67, 8), (27, 88), (107, 88)], fill=colour)
        draw.ellipse((27, 58, 107, 138), fill=colour)
    font = ImageFont.load_default(size=52)
    for line, text in enumerate(name.split(" ", 1)):
        draw.text(
            (140, 18 + line * 64), text, font=font, fill=colour, stroke_width=1, stroke_fill=colour
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    slug = name.lower().replace(" ", "-")
    return CustomImage.objects.create(
        title=f"{name} logo",
        description=f"{name} logo",
        file=ImageFile(buffer, name=f"{slug}-logo.png"),
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

        images = {key: load_photo(**photo) for key, photo in PHOTOS.items()}

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
        donate = DonatePage(
            title="Donate",
            slug="donate",
            introduction="Every gift helps a community get safe water that lasts.",
            payment_notice=(
                "<p>Brightwell is a demo charity, so no payment is taken and nobody will contact "
                "you about this pledge. To help people affected by the flood in Nepal, give to "
                f'the <a href="{RELIEF_FUND_URL}">Prime Minister\'s Disaster Relief Fund</a>.</p>'
            ),
            thank_you_text=(
                "<p>Thank you for trying the pledge form. Brightwell is fictional, so nobody will "
                "contact you, but a real charity would be in touch about how to pay.</p>"
            ),
            body=[
                (
                    "table",
                    {
                        "first_row_is_table_header": True,
                        "first_col_is_header": False,
                        "data": [
                            ["Where every Rs 100 goes", "Amount"],
                            ["Projects", "Rs 82"],
                            ["Fundraising", "Rs 13"],
                            ["Running the charity", "Rs 5"],
                        ],
                    },
                ),
            ],
        )
        donate.donation_amounts = [
            DonatePageAmount(amount=1500, impact="Safe water for one person for a year"),
            DonatePageAmount(amount=2500, impact="A hygiene kit for a family"),
            DonatePageAmount(amount=10000, impact="Water purification for a month"),
        ]
        publish(home, donate)

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
            title="Flash flood relief in Nepal",
            slug="flood-relief",
            summary=(
                "A flash flood down the Bhote Koshi has destroyed homes and water supplies "
                "in Rasuwa, Nuwakot and Dhading."
            ),
            body=[
                ("heading", {"heading_text": "What happened", "size": "h2"}),
                (
                    "paragraph",
                    "<p>On 26 August 2026 part of the Langtang Lirung glacier collapsed. "
                    "The debris and floodwater that followed swept down the Bhote Koshi and "
                    "Trishuli rivers, carrying away bridges, roads and around 7,570 homes. "
                    "By 21 September, at least 1,451 people had died and 5,745 were still "
                    "missing.</p>",
                ),
                ("heading", {"heading_text": "Why clean water matters now", "size": "h2"}),
                (
                    "paragraph",
                    "<p>The flood damaged water supplies and toilets across the valley. "
                    "In early tests, five of fifteen water sources were contaminated with "
                    "E. coli, and families in crowded shelters are at risk of cholera and "
                    "other waterborne diseases.</p>",
                ),
                ("heading", {"heading_text": "How to help today", "size": "h2"}),
                (
                    "paragraph",
                    "<p>Brightwell is a demo charity and takes no donations. To help people "
                    "affected by this flood, give to the "
                    f'<a href="{RELIEF_FUND_URL}">Prime Minister\'s Disaster Relief Fund</a>, '
                    "run by the Government of Nepal.</p>",
                ),
            ],
            hero_image=images["flood"],
            target=Decimal("7500000"),
            raised=Decimal("4687500"),
            start=TODAY - datetime.timedelta(days=10),
            end=TODAY + datetime.timedelta(days=9),
            amounts=[
                (2500, "A hygiene kit for a family"),
                (10000, "Water purification for a month"),
            ],
        )
        self.add_campaign(
            campaigns,
            title="Clean water for Kisumu",
            slug="clean-water-kisumu",
            summary="Twelve villages still walk two hours a day for water.",
            hero_image=images["well"],
            target=Decimal("12000000"),
            raised=Decimal("3600000"),
            start=TODAY - datetime.timedelta(days=40),
            end=None,
            amounts=[
                (1500, "Clean water for one person for a year"),
                (35000, "A hand pump repair"),
            ],
        )
        self.add_campaign(
            campaigns,
            title="Taps for schools",
            slug="taps-for-schools",
            summary="Handwashing stations keep children healthy and in class.",
            hero_image=images["school"],
            target=Decimal("2250000"),
            raised=Decimal("1365000"),
            start=TODAY - datetime.timedelta(days=20),
            end=TODAY + datetime.timedelta(days=60),
            amounts=[(6000, "A handwashing station")],
        )
        self.add_campaign(
            campaigns,
            title="Winter appeal 2025",
            slug="winter-appeal-2025",
            summary="Thanks to you, 20 communities kept their water running through winter.",
            hero_image=images["hero"],
            target=Decimal("3000000"),
            raised=Decimal("3510000"),
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
            images["grace"],
            ["water", "education"],
            [stories],
            days_ago=2,
        )
        flood_story = self.add_story(
            news,
            "What we know about the Bhote Koshi flash flood",
            "A glacier collapse in Langtang sent a flash flood through three districts of Nepal.",
            images["flood"],
            ["emergency"],
            [press],
            days_ago=6,
        )
        self.add_story(
            news,
            "Volunteers of the year",
            "Meet the supporters who ran, baked and cycled for clean water.",
            images["volunteers"],
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
            to_address="volunteers@brightwell.example",
            from_address="website@brightwell.example",
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

        for order, (name, colour, shape) in enumerate(PARTNERS):
            Partner.objects.create(
                name=name,
                url="https://example.org",
                logo=make_logo(name, colour, shape),
                sort_order=order,
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
        home.hero_text = "Rs 1,500 gives one person safe water for a whole year."
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
                        {"figure": "Rs 82", "label": "of every Rs 100 spent on projects"},
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
        settings.contact_email = "hello@brightwell.example"
        settings.phone = "0123 456 7890"
        settings.address = "1 Example Street\nBirmingham\nB1 1AA"
        settings.donate_page = donate
        settings.currency = "NPR"
        settings.phone_country = "NP"
        settings.instagram_url = "https://instagram.example/brightwell"
        settings.save()

        banner = AnnouncementBanner.load()
        banner.enabled = True
        banner.message = "Emergency appeal: help families hit by the flash flood in Nepal"
        banner.link_page = flood
        banner.save()

        self.add_nepali_pages(home, campaigns, flood, news, flood_story)

        self.stdout.write(self.style.SUCCESS(f"Created demo content for {SITE_NAME}."))
        self.stdout.write(f"About page: {about.url}")

    def add_nepali_pages(self, home, campaigns, flood, news, flood_story):
        """Translate the home page, the flood appeal and its news story, served under /ne/.

        The rest of the site stays English only, as most of a real charity's site would be at
        first: QA needs pages in both languages and pages in one.
        """
        nepali = Locale.objects.get_or_create(language_code="ne")[0]

        def translate(page, **fields):
            translation = page.copy_for_translation(nepali)
            for name, value in fields.items():
                setattr(translation, name, value)
            translation.save_revision().publish()
            return translation

        translate(
            home,
            title="गृहपृष्ठ",
            hero_heading="सबैका लागि सफा पानी",
            hero_text="तपाईंको सहयोगले गाउँगाउँमा सुरक्षित पिउने पानी पुग्छ।",
            hero_cta_text="सहयोग गर्नुहोस्",
            body=[
                (
                    "paragraph",
                    "<p>ब्राइटवेल वाटर ट्रस्टले नेपाल र अन्य देशका समुदायसँग मिलेर खानेपानी, "
                    "शौचालय र सरसफाइका काम गर्छ।</p>",
                )
            ],
        )
        translate(
            campaigns,
            title="सहयोग अपिल",
            introduction="एउटा अपिल रोज्नुहोस् र तपाईंको सहयोगले के गर्छ, हेर्नुहोस्।",
        )
        translate(
            flood,
            title="नेपालमा आएको बाढी पीडितलाई राहत",
            summary=("भोटेकोशीमा आएको बाढीले रसुवा, नुवाकोट र धादिङमा घर र खानेपानीका संरचना बगाएको छ।"),
            body=[
                ("heading", {"heading_text": "के भयो", "size": "h2"}),
                (
                    "paragraph",
                    "<p>२०२६ अगस्ट २६ मा लाङटाङ लिरुङ हिमनदीको एक भाग खस्यो। त्यसपछि आएको "
                    "बाढीले भोटेकोशी र त्रिशूली नदी किनारका पुल, सडक र झन्डै ७,५७० घर बगायो।</p>",
                ),
                ("heading", {"heading_text": "अहिले कसरी सहयोग गर्ने", "size": "h2"}),
                (
                    "paragraph",
                    "<p>ब्राइटवेल एउटा नमुना (डेमो) संस्था हो र यसले कुनै चन्दा लिँदैन। बाढी "
                    "पीडितलाई सहयोग गर्न नेपाल सरकारको "
                    f'<a href="{RELIEF_FUND_URL}">प्रधानमन्त्री दैवी प्रकोप उद्धार कोष</a>मा '
                    "सहयोग गर्नुहोस्।</p>",
                ),
            ],
        )
        translate(news, title="समाचार", introduction="साझेदार र सहयोगीहरूका कथा र अपडेट।")
        translate(
            flood_story,
            title="भोटेकोशी बाढीबारे हामीलाई के थाहा छ",
            introduction="लाङटाङमा हिमनदी खस्दा आएको बाढी नेपालका तीन जिल्ला हुँदै बग्यो।",
            body=[
                (
                    "paragraph",
                    "<p>लाङटाङमा हिमनदी खस्दा आएको बाढी नेपालका तीन जिल्ला हुँदै बग्यो।</p>",
                )
            ],
        )

    def add_campaign(self, parent, *, amounts, target, raised, start, end, body=None, **fields):
        campaign = CampaignPage(
            target_amount=target,
            amount_raised=raised,
            start_date=start,
            end_date=end,
            body=body
            or [
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
