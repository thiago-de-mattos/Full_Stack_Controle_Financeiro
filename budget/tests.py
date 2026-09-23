from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from finance.models import Account, Category, Transaction
from finance.services import create_default_categories, create_transfer

from .models import Budget

SENHA = "cavalo-bateria-grampo-9"


class OrcamentoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="thiago@exemplo.com", password=SENHA, name="Thiago")
        create_default_categories(self.user)
        self.client.force_login(self.user)
        self.conta = Account.objects.create(user=self.user, name="Nubank")
        self.outra = Account.objects.create(user=self.user, name="Carteira")
        self.mercado = Category.objects.get(user=self.user, name="Mercado")
        self.hoje = date.today().replace(day=10)
        self.ref = self.hoje.replace(day=1)

    def _gastar(self, valor, **over):
        dados = dict(
            user=self.user, account=self.conta, category=self.mercado,
            kind=Transaction.Kind.EXPENSE, amount=Decimal(valor), date=self.hoje,
        )
        dados.update(over)
        return Transaction.objects.create(**dados)

    def _orcamento(self, limite="800.00"):
        return Budget.objects.create(
            user=self.user, category=self.mercado, month=self.ref,
            limit_amount=Decimal(limite),
        )

    def _com_gasto(self):
        return Budget.objects.for_user(self.user).with_spent(self.ref).first()

    def test_mes_e_normalizado_para_dia_1(self):
        self.client.post(reverse("budget:budget_create"), {
            "category": self.mercado.pk, "month": self.ref.strftime("%Y-%m"),
            "limit_amount": "800.00",
        })
        self.assertEqual(Budget.objects.get().month.day, 1)

    def test_gasto_e_anotado_corretamente(self):
        self._orcamento()
        self._gastar("250.50")
        self.assertEqual(self._com_gasto().spent_value, Decimal("250.50"))

    def test_orcamento_sem_gasto_fica_em_zero(self):
        self._orcamento()
        self.assertEqual(self._com_gasto().spent_value, Decimal("0.00"))

    def test_gasto_de_outro_mes_nao_conta(self):
        self._orcamento()
        self._gastar("500.00", date=self.hoje.replace(year=self.hoje.year - 1))
        self.assertEqual(self._com_gasto().spent_value, Decimal("0.00"))

    def test_gasto_previsto_nao_conta(self):
        self._orcamento()
        self._gastar("500.00", is_settled=False)
        self.assertEqual(self._com_gasto().spent_value, Decimal("0.00"))

    def test_transferencia_nao_conta_como_gasto(self):
        self._orcamento()
        create_transfer(
            user=self.user, from_account=self.conta, to_account=self.outra,
            amount=Decimal("300.00"), date=self.hoje,
        )
        self.assertEqual(self._com_gasto().spent_value, Decimal("0.00"))

    def test_percentual_e_restante(self):
        self._orcamento("800.00")
        self._gastar("200.00")
        orc = self._com_gasto()
        self.assertEqual(orc.percent, 25)
        self.assertEqual(orc.remaining, Decimal("600.00"))
        self.assertEqual(orc.status, "ok")

    def test_status_muda_conforme_o_gasto(self):
        self._orcamento("100.00")
        self._gastar("85.00")
        self.assertEqual(self._com_gasto().status, "atencao")
        self._gastar("50.00")
        orc = self._com_gasto()
        self.assertEqual(orc.status, "estourado")
        self.assertEqual(orc.bar_width, 100)
        self.assertLess(orc.remaining, 0)

    def test_orcamento_duplicado_no_mesmo_mes_e_rejeitado(self):
        self._orcamento()
        r = self.client.post(reverse("budget:budget_create"), {
            "category": self.mercado.pk, "month": self.ref.strftime("%Y-%m"),
            "limit_amount": "900.00",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Budget.objects.count(), 1)

    def test_categoria_de_receita_nao_aparece_como_opcao(self):
        salario = Category.objects.get(user=self.user, name="Salário")
        r = self.client.post(reverse("budget:budget_create"), {
            "category": salario.pk, "month": self.ref.strftime("%Y-%m"),
            "limit_amount": "900.00",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Budget.objects.count(), 0)

    def test_usuario_nao_ve_orcamento_alheio(self):
        self._orcamento()
        intruso = User.objects.create_user(email="intruso@exemplo.com", password=SENHA, name="X")
        self.client.force_login(intruso)
        r = self.client.get(reverse("budget:budget_list"))
        self.assertNotContains(r, "Mercado")
