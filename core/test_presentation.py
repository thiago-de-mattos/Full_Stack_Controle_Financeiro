from decimal import Decimal

from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.utils.translation import override

from .templatetags.money import brl


class PresentationRegressionTests(SimpleTestCase):
    def test_brl_groups_thousands_and_uses_decimal_comma(self):
        self.assertEqual(brl(Decimal("1234567.89")), "R$ 1.234.567,89")
        self.assertEqual(brl(Decimal("-1234.5")), "R$ -1.234,50")

    def test_brl_handles_zero_and_rounds_cents(self):
        self.assertEqual(brl(None), "R$ 0,00")
        self.assertEqual(brl(Decimal("1.235")), "R$ 1,24")

    def test_brl_keeps_brazilian_format_and_restores_active_language(self):
        from django.utils.translation import get_language
        with override("en"):
            self.assertEqual(brl(Decimal("1234.5")), "R$ 1.234,50")
            self.assertEqual(get_language(), "en")

    def test_month_navigation_does_not_show_template_comment(self):
        html = render_to_string("partials/_nav_mes.html", {
            "ref_label": "novembro de 2026", "mes_anterior": "2026-10", "mes_seguinte": "2026-12",
        })
        self.assertNotIn("{#", html)
        self.assertNotIn("Espera ref_label", html)
        self.assertIn("novembro de 2026", html)
