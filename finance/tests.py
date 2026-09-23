from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from budget.models import Budget

from .models import Account, Category, Transaction
from .services import create_default_categories, create_transfer, month_summary

SENHA = "cavalo-bateria-grampo-9"


class BaseFinanceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="thiago@exemplo.com", password=SENHA, name="Thiago")
        create_default_categories(self.user)
        self.client.force_login(self.user)

        self.nubank = Account.objects.create(
            user=self.user, name="Nubank", kind=Account.Kind.CHECKING,
            initial_balance=Decimal("1000.00"),
        )
        self.carteira = Account.objects.create(
            user=self.user, name="Carteira", kind=Account.Kind.CASH,
            initial_balance=Decimal("50.00"),
        )
        self.mercado = Category.objects.get(user=self.user, name="Mercado")
        self.salario = Category.objects.get(user=self.user, name="Salário")
        self.hoje = date.today().replace(day=10)

    def saldos(self):
        return {a.name: a.balance for a in Account.objects.for_user(self.user).with_balance()}


class SaldoTests(BaseFinanceTest):
    def test_saldo_inicial_sem_lancamentos(self):
        self.assertEqual(self.saldos()["Nubank"], Decimal("1000.00"))

    def test_receita_soma_e_despesa_subtrai(self):
        Transaction.objects.create(
            user=self.user, account=self.nubank, category=self.salario,
            kind=Transaction.Kind.INCOME, amount=Decimal("3000.00"), date=self.hoje,
        )
        Transaction.objects.create(
            user=self.user, account=self.nubank, category=self.mercado,
            kind=Transaction.Kind.EXPENSE, amount=Decimal("250.50"), date=self.hoje,
        )
        self.assertEqual(self.saldos()["Nubank"], Decimal("3749.50"))

    def test_lancamento_nao_liquidado_fica_fora_do_saldo(self):
        Transaction.objects.create(
            user=self.user, account=self.nubank, category=self.mercado,
            kind=Transaction.Kind.EXPENSE, amount=Decimal("100.00"),
            date=self.hoje, is_settled=False,
        )
        self.assertEqual(self.saldos()["Nubank"], Decimal("1000.00"))


class TransferenciaTests(BaseFinanceTest):
    def test_transferencia_cria_duas_pernas_ligadas(self):
        saida, entrada = create_transfer(
            user=self.user, from_account=self.nubank, to_account=self.carteira,
            amount=Decimal("200.00"), date=self.hoje,
        )
        self.assertEqual(saida.transfer_group, entrada.transfer_group)
        self.assertEqual(Transaction.objects.filter(transfer_group__isnull=False).count(), 2)

    def test_transferencia_move_saldo_sem_mudar_o_total(self):
        create_transfer(
            user=self.user, from_account=self.nubank, to_account=self.carteira,
            amount=Decimal("200.00"), date=self.hoje,
        )
        saldos = self.saldos()
        self.assertEqual(saldos["Nubank"], Decimal("800.00"))
        self.assertEqual(saldos["Carteira"], Decimal("250.00"))
        self.assertEqual(sum(saldos.values()), Decimal("1050.00"))

    def test_transferencia_nao_entra_como_despesa_no_resumo(self):
        Transaction.objects.create(
            user=self.user, account=self.nubank, category=self.mercado,
            kind=Transaction.Kind.EXPENSE, amount=Decimal("250.50"), date=self.hoje,
        )
        create_transfer(
            user=self.user, from_account=self.nubank, to_account=self.carteira,
            amount=Decimal("200.00"), date=self.hoje,
        )
        self.assertEqual(month_summary(self.user, self.hoje)["despesas"], Decimal("250.50"))

    def test_mesma_conta_nas_duas_pontas_e_rejeitada(self):
        r = self.client.post(reverse("finance:transfer_create"), {
            "from_account": self.nubank.pk, "to_account": self.nubank.pk,
            "amount": "10.00", "date": self.hoje.isoformat(), "description": "",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_apagar_uma_perna_apaga_a_outra(self):
        saida, _ = create_transfer(
            user=self.user, from_account=self.nubank, to_account=self.carteira,
            amount=Decimal("200.00"), date=self.hoje,
        )
        self.client.post(reverse("finance:transaction_delete", args=[saida.pk]))
        self.assertEqual(Transaction.objects.count(), 0)


class ValidacaoTests(BaseFinanceTest):
    def _lancamento(self, **over):
        dados = {
            "kind": "expense", "account": self.nubank.pk, "category": self.mercado.pk,
            "amount": "50.00", "date": self.hoje.isoformat(),
            "description": "teste", "is_settled": "on", "notes": "",
        }
        dados.update(over)
        return self.client.post(reverse("finance:transaction_create"), dados)

    def test_lancamento_valido_e_salvo(self):
        self._lancamento()
        self.assertEqual(Transaction.objects.count(), 1)

    def test_valor_negativo_e_rejeitado(self):
        self._lancamento(amount="-50.00")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_valor_zero_e_rejeitado(self):
        self._lancamento(amount="0")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_categoria_de_tipo_incompativel_e_rejeitada(self):
        self._lancamento(kind="expense", category=self.salario.pk)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_nome_de_conta_duplicado_e_rejeitado(self):
        r = self.client.post(reverse("finance:account_create"), {
            "name": "nubank", "kind": "cash", "initial_balance": "0", "is_active": "on",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Account.objects.filter(user=self.user).count(), 2)


class IsolamentoEntreUsuariosTests(BaseFinanceTest):
    """A parte que mais importa: ninguem enxerga o dinheiro de outra pessoa."""

    def setUp(self):
        super().setUp()
        self.lancamento = Transaction.objects.create(
            user=self.user, account=self.nubank, category=self.mercado,
            kind=Transaction.Kind.EXPENSE, amount=Decimal("99.00"), date=self.hoje,
            description="Compras do Thiago",
        )
        self.intruso = User.objects.create_user(
            email="intruso@exemplo.com", password=SENHA, name="Intruso"
        )
        self.client.force_login(self.intruso)

    def test_nao_abre_lancamento_alheio(self):
        r = self.client.get(reverse("finance:transaction_update", args=[self.lancamento.pk]))
        self.assertEqual(r.status_code, 404)

    def test_nao_apaga_lancamento_alheio(self):
        self.client.post(reverse("finance:transaction_delete", args=[self.lancamento.pk]))
        self.assertTrue(Transaction.objects.filter(pk=self.lancamento.pk).exists())

    def test_nao_lanca_na_conta_alheia_mesmo_forjando_o_post(self):
        self.client.post(reverse("finance:transaction_create"), {
            "kind": "expense", "account": self.nubank.pk, "category": self.mercado.pk,
            "amount": "5.00", "date": self.hoje.isoformat(),
            "description": "injetado", "is_settled": "on", "notes": "",
        })
        self.assertFalse(Transaction.objects.filter(description="injetado").exists())

    def test_listagem_nao_mostra_conta_alheia(self):
        r = self.client.get(reverse("finance:account_list"))
        self.assertNotContains(r, "Nubank")

    def test_nao_apaga_conta_alheia(self):
        self.client.post(reverse("finance:account_delete", args=[self.nubank.pk]))
        self.assertTrue(Account.objects.filter(pk=self.nubank.pk).exists())


class AcessoAnonimoTests(TestCase):
    def test_paginas_exigem_login(self):
        for nome in [
            "finance:transaction_list", "finance:account_list",
            "finance:category_list", "budget:budget_list",
            "finance:transfer_create",
        ]:
            with self.subTest(url=nome):
                r = self.client.get(reverse(nome))
                self.assertEqual(r.status_code, 302)
                self.assertIn("/entrar/", r["Location"])

    def test_raiz_mostra_apresentacao_sem_quebrar(self):
        r = self.client.get(reverse("finance:dashboard"))
        self.assertEqual(r.status_code, 200)


class PaginasTests(BaseFinanceTest):
    def test_todas_as_paginas_respondem(self):
        urls = [
            reverse("finance:dashboard"),
            reverse("finance:transaction_list"),
            reverse("finance:transaction_create"),
            reverse("finance:account_list"),
            reverse("finance:account_create"),
            reverse("finance:account_update", args=[self.nubank.pk]),
            reverse("finance:category_list"),
            reverse("finance:category_create"),
            reverse("finance:transfer_create"),
            reverse("budget:budget_list"),
            reverse("budget:budget_create"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_navegacao_de_mes_funciona(self):
        r = self.client.get(reverse("finance:transaction_list") + "?mes=2025-01")
        self.assertEqual(r.status_code, 200)

    def test_mes_invalido_cai_no_mes_atual_sem_quebrar(self):
        r = self.client.get(reverse("finance:transaction_list") + "?mes=banana")
        self.assertEqual(r.status_code, 200)


class ConvencaoDeTemplateTests(BaseFinanceTest):
    """Garante que as views resolvem o template pela convenção do Django.

    Se alguém renomear um arquivo (list.html em vez de account_list.html),
    estes testes quebram antes de a tela quebrar no navegador.
    """

    def test_cada_view_usa_o_template_esperado(self):
        esperado = {
            reverse("finance:dashboard"): "finance/dashboard.html",
            reverse("finance:account_list"): "finance/account_list.html",
            reverse("finance:account_create"): "finance/account_form.html",
            reverse("finance:account_update", args=[self.nubank.pk]): "finance/account_form.html",
            reverse("finance:account_delete", args=[self.nubank.pk]): "finance/account_confirm_delete.html",
            reverse("finance:category_list"): "finance/category_list.html",
            reverse("finance:category_create"): "finance/category_form.html",
            reverse("finance:transaction_list"): "finance/transaction_list.html",
            reverse("finance:transaction_create"): "finance/transaction_form.html",
            reverse("finance:transfer_create"): "finance/transfer_form.html",
            reverse("budget:budget_list"): "budget/budget_list.html",
            reverse("budget:budget_create"): "budget/budget_form.html",
        }
        for url, template in esperado.items():
            with self.subTest(url=url):
                self.assertTemplateUsed(self.client.get(url), template)

    def test_paginas_herdam_da_base(self):
        r = self.client.get(reverse("finance:account_list"))
        self.assertTemplateUsed(r, "base.html")
        self.assertTemplateUsed(r, "partials/_sidebar.html")

    def test_partials_sao_reaproveitados(self):
        r = self.client.get(reverse("budget:budget_list"))
        self.assertTemplateUsed(r, "partials/_nav_mes.html")
        r = self.client.get(reverse("finance:transaction_create"))
        self.assertTemplateUsed(r, "layouts/form_page.html")
        self.assertTemplateUsed(r, "partials/_campos_form.html")
