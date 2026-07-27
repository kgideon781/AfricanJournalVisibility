from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(mapping, key):
    """Django templates can't index dicts by variable key. This unblocks that."""
    if mapping is None:
        return []
    try:
        return mapping.get(key, [])
    except AttributeError:
        return []
