import csv
import io
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile, User
from budget.models import Budget
from core.models import Organization
from .models import Account, Category, Transaction
from .reports import dashboard_metrics
from .services import create_transfer


class DashboardReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Equipe A")
        cls.other_org = Organization.objects.create(name="Equipe B")
        cls.admin = cls.make_user("admin", cls.org, Profile.Role.ADMIN)
        cls.member = cls.make_user("member", cls.org, Profile.Role.OPERATOR)
        cls.other = cls.make_user("other", cls.other_org, Profile.Role.ADMIN)
        cls.account = Account.objects.create(
            user=cls.admin, organization=cls.org, name="Conta da equipe", initial_balance="100.00"
        )
        cls.wallet = Account.objects.create(user=cls.member, organization=cls.org, name="Carteira")
        cls.foreign_account = Account.objects.create(
            user=cls.other, organization=cls.other_org, name="Conta secreta"
        )
        cls.category = Category.objects.create(
            user=cls.admin, organization=cls.org, name="Mercado", kind="expense"
        )
        cls.foreign_category = Category.objects.create(
            user=cls.other, organization=cls.other_org, name="Categoria secreta", kind="expense"
        )
        cls.ref = date(2026, 11, 1)

    @classmethod
    def make_user(cls, name, organization, role):
        user = User.objects.create_user(email=f"{name}@example.test", name=name)
        Profile.objects.create(user=user, organization=organization, role=role)
        return user

    def setUp(self):
        self.client.force_login(self.member)

    def record(self, **kwargs):
        fields = {
            "user": self.admin, "organization": self.org, "account": self.account,
            "category": self.category, "kind": "expense", "amount": Decimal("30.00"),
            "date": date(2026, 11, 10), "description": "Compra do mês",
        }
        fields.update(kwargs)
        return Transaction.objects.create(**fields)

    def dashboard(self, month="2026-11"):
        return self.client.get(reverse("finance:dashboard"), {"mes": month})

    def export(self, month="2026-11"):
        return self.client.get(reverse("finance:transaction_export"), {"mes": month})

    def csv_rows(self, response):
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))

    def test_metrics_share_organization_and_exclude_foreign_records(self):
        self.record(amount="30.00")
        self.record(user=self.member, amount="20.00")
        self.record(
            user=self.other, organization=self.other_org, account=self.foreign_account,
            category=self.foreign_category, amount="999.00", description="SEGREDO",
        )
        Budget.objects.create(
            user=self.admin, organization=self.org, category=self.category,
            month=self.ref, limit_amount="100.00",
        )
        response = self.dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["resumo"]["despesas"], Decimal("50.00"))
        self.assertEqual(response.context["ranking"][0]["total"], Decimal("50.00"))
        self.assertEqual(response.context["ranking"][0]["quantidade"], 2)
        self.assertEqual(response.context["historico"][-1]["despesas"], Decimal("50.00"))
        self.assertEqual(response.context["orcamentos"][0].spent, Decimal("50.00"))
        self.assertNotContains(response, "SEGREDO")
        self.assertNotContains(response, "secreta")

    def test_pending_separate_from_settled_and_transfers(self):
        self.record(amount="30.00")
        self.record(kind="income", category=None, amount="200.00")
        self.record(is_settled=False, amount="70.00")
        self.record(is_settled=False, kind="income", category=None, amount="80.00")
        self.record(is_settled=False, amount="500.00", date=date(2026, 10, 1))
        create_transfer(
            user=self.admin, from_account=self.account, to_account=self.wallet,
            amount=Decimal("10.00"), date=self.ref,
        )
        response = self.dashboard()
        self.assertEqual(response.context["pendencias"], {"receber": Decimal("80"), "pagar": Decimal("70")})
        self.assertEqual(response.context["resumo"], {
            "receitas": Decimal("200"), "despesas": Decimal("30"), "resultado": Decimal("170")
        })
        self.assertEqual(response.context["ranking"][0]["total"], Decimal("30"))
        self.assertEqual(response.context["historico"][-1]["resultado"], Decimal("170"))
        self.assertEqual(response.context["saldo_total"], Decimal("270"))

    def test_history_crosses_year_and_fills_empty_months(self):
        self.record(date=date(2025, 8, 1), amount="999.00")
        self.record(date=date(2025, 9, 1), amount="20.00")
        self.record(date=date(2025, 12, 31), kind="income", category=None, amount="90.00")
        self.record(date=date(2026, 2, 28), amount="12.00")
        self.record(date=date(2026, 3, 1), amount="999.00")
        history = self.dashboard("2026-02").context["historico"]
        self.assertEqual([row["mes"] for row in history], [
            date(2025, 9, 1), date(2025, 10, 1), date(2025, 11, 1),
            date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1),
        ])
        self.assertEqual([row["resultado"] for row in history], [-20, 0, 0, 90, 0, -12])

    def test_ranking_top_five_includes_uncategorized_and_disabled_categories(self):
        self.record(category=None, amount="100.00")
        for i in range(6):
            category = Category.objects.create(
                user=self.admin, organization=self.org, name=f"Grupo {i}",
                kind="expense", is_active=False,
            )
            self.record(category=category, amount=10 * (i + 1))
        ranking = list(self.dashboard().context["ranking"])
        self.assertEqual(len(ranking), 5)
        self.assertEqual([row["total"] for row in ranking], [100, 60, 50, 40, 30])
        self.assertIsNone(ranking[0]["category_id"])

    def test_latest_records_follow_selected_month_and_limit_to_eight(self):
        self.record(date=date(2026, 12, 1), description="Mês seguinte")
        self.record(date=date(2026, 10, 31), description="Mês anterior")
        for day in range(1, 11):
            self.record(date=date(2026, 11, day))
        response = self.dashboard()
        self.assertEqual([r.date.day for r in response.context["ultimos"]], list(range(10, 2, -1)))
        self.assertNotContains(response, "Mês seguinte")
        # The navigation's accessible label also says Mês anterior.
        self.assertNotContains(response, "<td>Mês anterior</td>", html=True)

    def test_balance_remains_accumulated_when_month_changes(self):
        self.record(date=date(2026, 10, 1), amount="10.00")
        self.record(date=date(2026, 11, 1), amount="20.00")
        october = self.dashboard("2026-10").context
        november = self.dashboard().context
        self.assertEqual(october["saldo_total"], Decimal("70"))
        self.assertEqual(november["saldo_total"], Decimal("70"))
        self.assertEqual(october["resumo"]["despesas"], Decimal("10"))
        self.assertEqual(november["resumo"]["despesas"], Decimal("20"))

    def test_empty_dashboard_has_zero_totals_and_six_months(self):
        response = self.dashboard()
        self.assertEqual(response.context["pendencias"], {"receber": 0, "pagar": 0})
        self.assertEqual(list(response.context["ranking"]), [])
        self.assertEqual(len(response.context["historico"]), 6)
        self.assertTrue(all(row["resultado"] == 0 for row in response.context["historico"]))
        self.assertContains(response, "Nenhuma despesa realizada neste mês.")
        self.assertContains(response, "Nenhum lançamento registrado neste mês.")

    def test_invalid_or_extreme_month_falls_back_without_error(self):
        with patch("core.utils.current_month", return_value=self.ref):
            for value in ["banana", "2026-13", "0001-01", "9999-12"]:
                with self.subTest(month=value):
                    response = self.dashboard(value)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context["ref"], self.ref)
                    self.assertEqual(self.export(value).status_code, 200)

    def test_leap_day_is_included_in_monthly_export_and_metrics(self):
        record = self.record(date=date(2024, 2, 29), amount="42.00")
        self.assertEqual(self.dashboard("2024-02").context["resumo"]["despesas"], Decimal("42"))
        self.assertEqual(self.csv_rows(self.export("2024-02"))[1][0], str(record.pk))

    def test_export_is_scoped_and_uses_portuguese_csv_format(self):
        record = self.record(description='Almoço; "equipe"\nCentro', notes="Café", amount="12.50")
        self.record(date=date(2026, 10, 31))
        self.record(user=self.other, organization=self.other_org, account=self.foreign_account,
                    category=self.foreign_category, description="SEGREDO")
        response = self.export()
        rows = self.csv_rows(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1], [str(record.pk), "10/11/2026", "Conta da equipe", "Mercado",
                                  "Despesa", 'Almoço; "equipe"\nCentro', "-12,50", "Realizado", "Não", "Café"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("lancamentos-2026-11.csv", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(b"SEGREDO", response.content)

    def test_export_distinguishes_pending_and_transfer_pairs(self):
        self.record(is_settled=False)
        create_transfer(user=self.admin, from_account=self.account, to_account=self.wallet,
                        amount=Decimal("15.00"), date=self.ref)
        rows = self.csv_rows(self.export())[1:]
        self.assertEqual(len(rows), 3)
        transfers = [row for row in rows if row[8] == "Sim"]
        self.assertEqual(len(transfers), 2)
        self.assertEqual(sum(Decimal(row[6].replace(",", ".")) for row in transfers), 0)
        self.assertEqual(rows[-1][7], "Previsto")

    def test_export_neutralizes_formula_prefixes_in_all_free_text_fields(self):
        self.account.name = '=HYPERLINK("https://example.test")'
        self.account.save()
        self.category.name = "+1+1"
        self.category.save()
        for value in ["=1+1", "+1", "-1", "@SUM(1)", "  =1", "\tX", "\nX", "\rX"]:
            self.record(description=value, notes=value)
        rows = self.csv_rows(self.export())[1:]
        for row in rows:
            for index in [2, 3, 5, 9]:
                self.assertTrue(row[index].startswith("'"), row)

    def test_anonymous_and_missing_profile_cannot_export(self):
        self.client.logout()
        self.assertEqual(self.export().status_code, 302)
        no_profile = User.objects.create_user(email="no-profile@example.test", name="Sem perfil")
        self.client.force_login(no_profile)
        self.assertEqual(self.export().status_code, 403)
        self.assertEqual(self.dashboard().status_code, 403)

    def test_admin_and_operator_can_read_but_export_rejects_post(self):
        for user in [self.admin, self.member]:
            self.client.force_login(user)
            self.assertEqual(self.dashboard().status_code, 200)
            self.assertEqual(self.export().status_code, 200)
            self.assertEqual(self.client.post(reverse("finance:transaction_export")).status_code, 405)

    def test_dashboard_escapes_names_and_disables_cache(self):
        self.category.name = '<script>alert("x")</script>'
        self.category.save()
        self.record()
        response = self.dashboard()
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, reverse("finance:transaction_export") + "?mes=2026-11")

    def test_metrics_use_grouped_queries_instead_of_one_query_per_month(self):
        # Resolve profile once, so this measures only report queries.
        self.member.profile.organization
        with self.assertNumQueries(3):
            result = dashboard_metrics(self.member, self.ref)
            list(result["ranking"])
