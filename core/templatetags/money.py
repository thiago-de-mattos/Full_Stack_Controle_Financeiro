from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def brl(value):
    """1234.5 -> R$ 1.234,50"""
    if value is None:
        value = 0
    return f"R$ {intcomma(floatformat(value, 2))}"
