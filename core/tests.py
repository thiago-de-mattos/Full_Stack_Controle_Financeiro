from datetime import date

from django.test import SimpleTestCase

from .utils import month_label, shift_month
from .validators import CommonPortuguesePasswordValidator
from django.core.exceptions import ValidationError


class ShiftMonthTests(SimpleTestCase):
    def test_avanca_dentro_do_ano(self):
        self.assertEqual(shift_month(date(2026, 3, 1), 1), date(2026, 4, 1))

    def test_vira_o_ano_pra_frente(self):
        self.assertEqual(shift_month(date(2026, 12, 1), 1), date(2027, 1, 1))

    def test_vira_o_ano_pra_tras(self):
        self.assertEqual(shift_month(date(2026, 1, 1), -1), date(2025, 12, 1))

    def test_salto_grande(self):
        self.assertEqual(shift_month(date(2026, 5, 1), 14), date(2027, 7, 1))

    def test_rotulo_em_portugues(self):
        self.assertEqual(month_label(date(2026, 9, 1)), "setembro de 2026")


class ValidadorSenhaTests(SimpleTestCase):
    def setUp(self):
        self.v = CommonPortuguesePasswordValidator()

    def test_rejeita_palavra_comum_disfarcada(self):
        for senha in ["Senha@123", "senha123", "s3nha", "Brasil2026!", "@mor1"]:
            with self.subTest(senha=senha):
                with self.assertRaises(ValidationError):
                    self.v.validate(senha)

    def test_aceita_frase_longa(self):
        self.v.validate("cavalo-bateria-grampo-9")
        self.v.validate("meu gato dorme na janela")
