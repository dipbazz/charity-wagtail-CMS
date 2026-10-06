# Demo content

`manage.py seed_demo` builds the demo site that development, the tests, CI's Lighthouse job and
the live demo all use. See [Management commands](management-commands.md#seed_demo-home).

## The charity is fictional

- Brightwell Water Trust, its people, figures and charity number are fictional. Amounts are in
  Nepalese rupees (Site settings → Currency).
- Use `brightwell.example` for the charity's own addresses, and `example.org` or `example.com`
  for third parties. These are reserved domains that never reach a real inbox or site.
- The flood appeal describes the real flash flood in Nepal on 26 August 2026. The page says
  Brightwell takes no donations and links to the Government of Nepal's relief fund instead. The
  Donate page's pledge form works, but its notice says no payment is taken and nobody will be
  in touch.
  No freely licensed photo of that flood exists, so the appeal uses a representative photo of a
  flooded camp, labelled as such in its caption and alt text.

## Nepali pages

The home page, the appeals and news index pages, the flood appeal and its news story have Nepali
translations under `/ne/`. Everything else is English only, as most of a real charity's site
would be at first, so QA has pages in both languages and pages in one. The Nepali appeal is as
honest as the English one: Brightwell takes no donations, and it links to the same relief fund.

## Demo photos

`seed_demo` loads these photos from `home/management/commands/demo_images/`, resized to 1600px
wide. They're used under their sites' free licences, which cover copyright but not consent from
the people pictured, so the demo leaves them unconsented and they stay out of the API.

| File | Photographer | Source | Licence |
|---|---|---|---|
| `hero.jpg` | Maxime Bouffard | [Unsplash](https://unsplash.com/photos/man-in-white-t-shirt-sitting-on-brown-wooden-bench-during-daytime-i1PR2CjWV1E) | [Unsplash License](https://unsplash.com/license) |
| `well.jpg` | bradford zak | [Unsplash](https://unsplash.com/photos/girl-in-pink-and-white-stripe-shirt-standing-on-brown-concrete-floor-during-daytime-uvtt5gxPDtg) | [Unsplash License](https://unsplash.com/license) |
| `grace.jpg` | Emmanuel Ikwuegbu | [Unsplash](https://unsplash.com/photos/children-in-white-tank-top-sitting-on-brown-wooden-bench-M-4lFg1Xfag) | [Unsplash License](https://unsplash.com/license) |
| `flood.jpg` | Salah Darwish | [Unsplash](https://unsplash.com/photos/a-large-group-of-tents-in-the-middle-of-a-field-MH7AVzl97AM) | [Unsplash License](https://unsplash.com/license) |
| `school.jpg` | Jonathan Shembere | [Pexels](https://www.pexels.com/photo/boy-standing-by-faucet-on-wall-and-washing-hands-15204073/) | [Pexels License](https://www.pexels.com/license/) |
| `volunteers.jpg` | RDNE Stock project | [Pexels](https://www.pexels.com/photo/three-people-donating-goods-6646918/) | [Pexels License](https://www.pexels.com/license/) |

The partner logos are drawn by `seed_demo` for the fictional partners.

## Tests that depend on it

`home/tests/test_seed_demo.py` checks that every page it creates renders, that every photo is
credited and unconsented, and that running it twice doesn't duplicate content. The query budgets
in `charity/tests/test_query_budgets.py` are measured on the full demo site.
