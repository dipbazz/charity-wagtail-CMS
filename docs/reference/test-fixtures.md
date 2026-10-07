# Test fixtures and factories

## Fixtures in the root `conftest.py`

| Fixture | |
|---|---|
| `site` | The default Wagtail `Site`, created by the home app's data migration |
| `home_page` | The `HomePage` at the root of that site; the parent for test pages |
| `nepali_locale` | The Nepali `Locale`. English is the main language in tests, so Nepali pages are under `/ne/` |
| `nepali_home_page` | The home page's published Nepali translation, served at `/ne/`; the parent for Nepali test pages |
| `privacy_notice` | A published privacy notice page under `home_page`, chosen in Site settings, so the footer and forms link to it |
| `editor` | A user in Wagtail's Editors group, as the charity's editors are: not a superuser |
| `moderator` | A user in Wagtail's Moderators group, who approves and publishes editors' work |
| `cold_cache_queries` | A function: `cold_cache_queries(path)` returns how many queries that page runs on a just-started server, with image renditions looked up in the database |
| `clear_cache` | Automatic: clears the cache after every test, because the database rolls back but the cache doesn't, and Wagtail caches Site root URLs there |

pytest-django adds its own, such as `client`, `admin_client`, `django_user_model`, `settings`
and `django_assert_max_num_queries`.

## Factories

Built on [wagtail-factories](https://github.com/wagtail/wagtail-factories):

- `campaigns/tests/factories.py`: `CampaignIndexPageFactory`, `CampaignPageFactory` (an open
  appeal with a 10,000 target and 2,500 raised, started 30 days ago).
- `news/tests/factories.py`: `NewsIndexPageFactory`, `NewsPageFactory`, `NewsCategoryFactory`.
- From wagtail-factories directly: `ImageFactory`, `DocumentFactory` and others.

Create pages under a parent: `CampaignPageFactory(parent=index, title="Winter appeal")`.

## Settings under test

`charity.settings.test` uses `InMemoryStorage` for media, which has no file paths. A test of
anything that reads files from disk (for example Wagtail's document serve view) must set
`MEDIA_ROOT` to `tmp_path` and the default storage to `FileSystemStorage`; see
`core/tests/test_media.py`.

Mail goes to Django's locmem mailer, so tests read sent messages from `django.core.mail.outbox`.
