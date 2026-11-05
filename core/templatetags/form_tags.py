from django import template

register = template.Library()


@register.simple_tag
def error_summary(form):
    """What's wrong with a sent form, for `includes/error_summary.html` (#167): each message once,
    with the id of the field it links to. Form-wide messages come first, linking to the first
    field that shows the same message (None if none does); then each field's own. A radio or
    checkbox group links to its first choice, as the group has no box of its own."""
    fields = [(field.id_for_label or f"{field.auto_id}_0", field.errors) for field in form]
    targets = {}
    for target, errors in fields:
        for message in errors:
            targets.setdefault(message, target)
    form_wide = form.non_field_errors()
    entries = [{"message": message, "target": targets.get(message)} for message in form_wide]
    for target, errors in fields:
        entries += [
            {"message": message, "target": target} for message in errors if message not in form_wide
        ]
    return entries
