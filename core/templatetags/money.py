from django import template
from django.template.defaultfilters import floatformat
from django.utils.translation import override

register = template.Library()


@register.filter
def brl(value):
    """Formata valores em reais sem aplicar agrupamento duas vezes."""
    with override("pt-br"):
        return f"R$ {floatformat(0 if value is None else value, '2g')}"
