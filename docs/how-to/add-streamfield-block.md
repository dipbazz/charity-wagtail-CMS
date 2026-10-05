# Add a StreamField block

Every page body uses `BaseStreamBlock` (`core/blocks.py`), so a block added there is offered on
every page type at once.

## 1. Write the tests first

In `core/tests/test_blocks.py`, following its style:

- the block renders what it should, using its `render()` helper with the block's raw data;
- any validation (for example `CallToActionBlock` refuses both a page and a URL, or neither);
- update `test_base_stream_block_offers_every_content_block`, which lists every block by name.

## 2. Write the block

```python
class FactBlock(blocks.StructBlock):
    figure = blocks.CharBlock()
    text = blocks.TextBlock(required=False)

    class Meta:
        icon = "pick"
        template = "core/blocks/fact_block.html"
```

- Add it to `BaseStreamBlock`, in the position it should appear in the editor's block menu.
- Rich text uses `RICH_TEXT_FEATURES`, which includes the custom `mark` highlight.
- Validation goes in `clean()`, raising `StructBlockValidationError` with per-field errors so the
  editor sees which field is wrong.
- Extra template context (such as a resolved link) goes in `get_context()`.
- A block that picks a snippet subclasses `SnippetChooserBlock`, like `TestimonialBlock`.

A change to `BaseStreamBlock` changes every page model's `body` field, so run
`uv run python manage.py makemigrations`. It writes one migration per app with a StreamField.

## 3. Write the template

Block templates live in `core/templates/core/blocks/`. Style the block mobile first (load the
`mobile-first` skill). An image in a block uses `{% picture %}` with a `sizes` that matches the
layout ([Images](../topics/images.md)).

## 4. Keep it fast and safe

- A block that queries the database (like `PartnersBlock`) runs that query on every page it's
  on. Use `select_related` and check the [query budgets](../topics/performance.md) still pass.
- A block that lists pages must filter `.live().public()`
  ([Security](../topics/security.md)).

## 5. Document it

Add it to the block list in the [models reference](../reference/models.md#streamfield-blocks).
