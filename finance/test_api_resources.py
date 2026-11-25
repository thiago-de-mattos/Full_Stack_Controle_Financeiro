from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile, User
from budget.models import Budget
from core.models import Organization
from .forms import CategoryForm, TransactionForm
from .models import Account, Category, Transaction
from .serializers import CategorySerializer


class FinancialResourceAPITests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Organização A")
        self.other_org = Organization.objects.create(name="Organização B")
        self.admin = self.make_user("admin", self.org, "admin")
        self.operator = self.make_user("operator", self.org, "operator")
        self.outsider = self.make_user("outsider", self.other_org, "admin")
        self.account = Account.objects.create(user=self.admin, organization=self.org, name="Conta A")
        self.second_account = Account.objects.create(user=self.operator, organization=self.org, name="Conta B")
        self.foreign_account = Account.objects.create(user=self.outsider, organization=self.other_org, name="Conta externa")
        self.expense = Category.objects.create(user=self.admin, organization=self.org, name="Mercado", kind="expense")
        self.income = Category.objects.create(user=self.admin, organization=self.org, name="Salário", kind="income")
        self.foreign_category = Category.objects.create(user=self.outsider, organization=self.other_org, name="Externa", kind="expense")
        self.client.force_login(self.operator)

    def make_user(self, name, organization, role):
        user = User.objects.create_user(name=name, email=f"{name}@example.test")
        Profile.objects.create(user=user, organization=organization, role=role)
        return user

    def post(self, path, data):
        return self.client.post(path, data, content_type="application/json")

    def patch(self, path, data):
        return self.client.patch(path, data, content_type="application/json")

    def entry(self, **kwargs):
        data = dict(user=self.admin, organization=self.org, account=self.account,
                    category=self.expense, kind="expense", amount=10, date=date(2026, 11, 10))
        data.update(kwargs)
        return Transaction.objects.create(**data)

    def transfer_data(self, **kwargs):
        data = dict(from_account=self.account.pk, to_account=self.second_account.pk,
                    amount="20.00", date="2026-11-10", description="Transferência API")
        data.update(kwargs)
        return data

    def test_operator_creates_all_resources_with_server_ownership(self):
        cases = [
            ("/api/categorias/", Category, {"name": "Transporte", "kind": "expense"}),
            ("/api/lancamentos/", Transaction, {"account": self.account.pk, "category": self.expense.pk,
                                              "kind": "expense", "amount": "15.00", "date": "2026-11-10"}),
            ("/api/orcamentos/", Budget, {"category": self.expense.pk, "month": "2026-11", "limit_amount": "100.00"}),
        ]
        for path, model, data in cases:
            with self.subTest(path=path):
                data.update(user=self.outsider.pk, organization=self.other_org.pk, role="admin")
                response = self.post(path, data)
                self.assertEqual(response.status_code, 201, response.content)
                obj = model.objects.get(pk=response.json()["id"])
                self.assertEqual(obj.user_id, self.operator.pk)
                self.assertEqual(obj.organization_id, self.org.pk)
                self.assertNotIn("user", response.json())
                self.assertNotIn("organization", response.json())

    def test_resource_lists_and_details_are_organization_scoped(self):
        own_entry = self.entry()
        foreign_entry = self.entry(user=self.outsider, organization=self.other_org,
                                   account=self.foreign_account, category=self.foreign_category)
        own_budget = Budget.objects.create(user=self.admin, organization=self.org,
                                          category=self.expense, month="2026-11-01", limit_amount=100)
        foreign_budget = Budget.objects.create(user=self.outsider, organization=self.other_org,
                                              category=self.foreign_category, month="2026-11-01", limit_amount=200)
        self.client.force_login(self.admin)
        for path, own, foreign in [
            ("/api/categorias/", self.expense, self.foreign_category),
            ("/api/lancamentos/", own_entry, foreign_entry),
            ("/api/orcamentos/", own_budget, foreign_budget),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                ids = {item["id"] for item in response.json()}
                self.assertIn(own.pk, ids)
                self.assertNotIn(foreign.pk, ids)
                self.assertEqual(self.client.get(f"{path}{own.pk}/").status_code, 200)
                self.assertEqual(self.client.get(f"{path}{foreign.pk}/").status_code, 404)
                self.assertEqual(self.patch(f"{path}{foreign.pk}/", {}).status_code, 404)
                self.assertEqual(self.client.delete(f"{path}{foreign.pk}/").status_code, 404)

    def test_anonymous_access_is_denied_for_every_new_endpoint(self):
        self.client.logout()
        for path in ("/api/categorias/", "/api/lancamentos/", "/api/orcamentos/", "/api/transferencias/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
                self.assertEqual(self.post(path, {}).status_code, 403)

    def test_patch_preserves_omitted_values_and_creator(self):
        entry = self.entry()
        budget = Budget.objects.create(user=self.admin, organization=self.org,
                                       category=self.expense, month="2026-11-01", limit_amount=100)
        for path, obj, update in [
            ("/api/categorias/", self.expense, {"name": "Mercado atualizado"}),
            ("/api/lancamentos/", entry, {"description": "Atualizado"}),
            ("/api/orcamentos/", budget, {"limit_amount": "150.00"}),
        ]:
            with self.subTest(path=path):
                response = self.patch(f"{path}{obj.pk}/", update)
                self.assertEqual(response.status_code, 200, response.content)
                obj.refresh_from_db()
                self.assertEqual(obj.user_id, self.admin.pk)
                self.assertEqual(obj.organization_id, self.org.pk)
        self.assertEqual(entry.amount, Decimal("10.00"))
        self.assertEqual(budget.month, date(2026, 11, 1))

    def test_put_updates_complete_resource(self):
        entry = self.entry()
        response = self.client.put(f"/api/lancamentos/{entry.pk}/", {
            "account": self.second_account.pk, "category": None, "kind": "income",
            "amount": "25.00", "date": "2026-11-12", "description": "Recebido",
            "notes": "Nota", "is_settled": False,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        entry.refresh_from_db()
        self.assertEqual(entry.account_id, self.second_account.pk)
        self.assertIsNone(entry.category_id)
        self.assertFalse(entry.is_settled)

    def test_category_duplicate_and_invalid_parent_are_rejected(self):
        for data, field in [
            ({"name": "mercado", "kind": "expense"}, "name"),
            ({"name": "Nova", "kind": "expense", "parent": self.foreign_category.pk}, "parent"),
            ({"name": "Nova", "kind": "expense", "parent": self.income.pk}, "parent"),
        ]:
            with self.subTest(data=data):
                response = self.post("/api/categorias/", data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_category_cycles_are_rejected_in_api_and_form(self):
        child = Category.objects.create(user=self.operator, organization=self.org,
                                        name="Filha", kind="expense", parent=self.expense)
        for parent in (self.expense, child):
            response = self.patch(f"/api/categorias/{self.expense.pk}/", {"parent": parent.pk})
            self.assertEqual(response.status_code, 400)
            self.assertIn("parent", response.json())
        form = CategoryForm({"name": "Mercado", "kind": "expense", "parent": child.pk},
                            instance=self.expense, user=self.operator)
        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)

    def test_category_patch_checks_existing_parent(self):
        child = Category.objects.create(user=self.operator, organization=self.org,
                                        name="Filha", kind="expense", parent=self.expense)
        response = self.patch(f"/api/categorias/{child.pk}/", {"kind": "income"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("parent", response.json())

    def test_category_type_cannot_invalidate_existing_records(self):
        self.entry()
        response = self.patch(f"/api/categorias/{self.expense.pk}/", {"kind": "income"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("kind", response.json())
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.kind, "expense")

    def test_transaction_rejects_foreign_relationships_and_nonpositive_amounts(self):
        base = {"account": self.account.pk, "category": self.expense.pk,
                "kind": "expense", "amount": "10.00", "date": "2026-11-10"}
        for update, field in [
            ({"account": self.foreign_account.pk}, "account"),
            ({"category": self.foreign_category.pk}, "category"),
            ({"category": self.income.pk}, "category"),
            ({"amount": "0"}, "amount"), ({"amount": "-1"}, "amount"),
        ]:
            with self.subTest(update=update):
                response = self.post("/api/lancamentos/", {**base, **update})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertFalse(Transaction.objects.exists())

    def test_transaction_patch_validates_against_omitted_category(self):
        entry = self.entry()
        response = self.patch(f"/api/lancamentos/{entry.pk}/", {"kind": "income"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.json())
        response = self.patch(f"/api/lancamentos/{entry.pk}/", {"kind": "income", "category": None})
        self.assertEqual(response.status_code, 200)

    def test_client_cannot_create_transfer_by_forging_internal_fields(self):
        response = self.post("/api/lancamentos/", {
            "account": self.account.pk, "kind": "expense", "amount": "10.00",
            "date": "2026-11-10", "is_transfer": True,
            "transfer_group": "11111111-1111-1111-1111-111111111111",
        })
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["is_transfer"])
        self.assertIsNone(Transaction.objects.get().transfer_group)

    def test_inactive_relationships_cannot_be_selected_for_new_records(self):
        self.account.is_active = False; self.account.save()
        self.expense.is_active = False; self.expense.save()
        response = self.post("/api/lancamentos/", {
            "account": self.account.pk, "category": self.expense.pk, "kind": "expense",
            "amount": "10.00", "date": "2026-11-10",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("account", response.json()); self.assertIn("category", response.json())
        response = self.post("/api/orcamentos/", {"category": self.expense.pk,
                                                "month": "2026-11", "limit_amount": "100"})
        self.assertEqual(response.status_code, 400)

    def test_existing_inactive_relationship_can_be_preserved_on_edit(self):
        entry = self.entry()
        self.account.is_active = False; self.account.save()
        self.expense.is_active = False; self.expense.save()
        response = self.patch(f"/api/lancamentos/{entry.pk}/", {
            "account": self.account.pk, "category": self.expense.pk, "description": "Histórico"
        })
        self.assertEqual(response.status_code, 200, response.content)
        form = TransactionForm({"account": self.account.pk, "category": self.expense.pk,
                                "kind": "expense", "amount": "10.00", "date": "2026-11-10"},
                               instance=entry, user=self.operator)
        self.assertTrue(form.is_valid(), form.errors)

    def test_budget_normalizes_month_and_rejects_duplicate_for_teammate(self):
        response = self.post("/api/orcamentos/", {"category": self.expense.pk,
                                                "month": "2026-11-24", "limit_amount": "100.00"})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["month"], "2026-11-01")
        self.client.force_login(self.admin)
        response = self.post("/api/orcamentos/", {"category": self.expense.pk,
                                                "month": "2026-11", "limit_amount": "200.00"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Budget.objects.count(), 1)

    def test_budget_rejects_income_foreign_categories_and_nonpositive_limit(self):
        base = {"category": self.expense.pk, "month": "2026-11", "limit_amount": "100.00"}
        for update, field in [
            ({"category": self.income.pk}, "category"),
            ({"category": self.foreign_category.pk}, "category"),
            ({"limit_amount": "0"}, "limit_amount"),
            ({"limit_amount": "-1"}, "limit_amount"),
            ({"month": "2026-13"}, "month"),
        ]:
            with self.subTest(update=update):
                response = self.post("/api/orcamentos/", {**base, **update})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertFalse(Budget.objects.exists())

    def test_budget_patch_checks_duplicate_with_existing_category(self):
        Budget.objects.create(user=self.admin, organization=self.org, category=self.expense,
                              month="2026-11-01", limit_amount=100)
        other = Budget.objects.create(user=self.operator, organization=self.org,
                                      category=self.expense, month="2026-12-01", limit_amount=200)
        response = self.patch(f"/api/orcamentos/{other.pk}/", {"month": "2026-11-20"})
        self.assertEqual(response.status_code, 400)

    def test_operator_cannot_delete_any_new_resource(self):
        entry = self.entry()
        budget = Budget.objects.create(user=self.admin, organization=self.org,
                                       category=self.expense, month="2026-11-01", limit_amount=100)
        for path, obj in [("categorias", self.expense), ("lancamentos", entry), ("orcamentos", budget)]:
            with self.subTest(path=path):
                self.assertEqual(self.client.delete(f"/api/{path}/{obj.pk}/").status_code, 403)
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_admin_can_delete_new_resources(self):
        entry = self.entry()
        budget = Budget.objects.create(user=self.admin, organization=self.org,
                                       category=self.expense, month="2026-11-01", limit_amount=100)
        self.client.force_login(self.admin)
        for path, obj in [("orcamentos", budget), ("lancamentos", entry), ("categorias", self.expense)]:
            with self.subTest(path=path):
                self.assertEqual(self.client.delete(f"/api/{path}/{obj.pk}/").status_code, 204)
                self.assertFalse(type(obj).objects.filter(pk=obj.pk).exists())

    def test_protected_category_delete_returns_400(self):
        self.entry(); self.client.force_login(self.admin)
        response = self.client.delete(f"/api/categorias/{self.expense.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Category.objects.filter(pk=self.expense.pk).exists())

    def test_transfer_creates_pair_and_admin_delete_removes_both(self):
        response = self.post("/api/transferencias/", self.transfer_data())
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(set(response.json()), {"saida", "entrada"})
        outgoing = Transaction.objects.get(pk=response.json()["saida"]["id"])
        incoming = Transaction.objects.get(pk=response.json()["entrada"]["id"])
        self.assertEqual(outgoing.transfer_group, incoming.transfer_group)
        self.assertEqual(outgoing.organization_id, self.org.pk)
        self.assertEqual(incoming.user_id, self.operator.pk)
        balances = dict(Account.objects.for_user(self.operator).with_balance().values_list("id", "balance"))
        self.assertEqual(balances[self.account.pk], Decimal("-20.00"))
        self.assertEqual(balances[self.second_account.pk], Decimal("20.00"))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.delete(f"/api/lancamentos/{outgoing.pk}/").status_code, 204)
        self.assertFalse(Transaction.objects.exists())

    def test_transfer_rejects_same_foreign_inactive_accounts_and_zero(self):
        inactive = Account.objects.create(user=self.admin, organization=self.org,
                                          name="Inativa", is_active=False)
        for changes in [
            {"to_account": self.account.pk}, {"to_account": self.foreign_account.pk},
            {"to_account": inactive.pk}, {"amount": "0"}, {"amount": "-1"},
        ]:
            with self.subTest(changes=changes):
                response = self.post("/api/transferencias/", self.transfer_data(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertFalse(Transaction.objects.exists())

    def test_transfer_movement_cannot_be_edited_by_patch_or_put(self):
        response = self.post("/api/transferencias/", self.transfer_data())
        pk = response.json()["saida"]["id"]
        self.assertEqual(self.patch(f"/api/lancamentos/{pk}/", {"amount": "999.00"}).status_code, 400)
        self.client.force_login(self.admin)
        response = self.client.put(f"/api/lancamentos/{pk}/", {
            "account": self.account.pk, "kind": "expense", "amount": "999.00", "date": "2026-11-10",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Transaction.objects.get(pk=pk).amount, Decimal("20.00"))

    def test_transfer_rolls_back_when_second_movement_fails(self):
        original = Transaction.objects.create
        calls = []

        def failing_create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise IntegrityError("Simulated database failure")
            return original(**kwargs)

        with patch("finance.services.Transaction.objects.create", side_effect=failing_create):
            response = self.post("/api/transferencias/", self.transfer_data())
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Transaction.objects.exists())
        self.assertNotIn("Simulated", response.content.decode())

    def test_database_conflict_returns_400_and_rolls_back(self):
        before = Category.objects.count()

        def failing_create(serializer, validated_data):
            Category.objects.create(**validated_data)
            raise IntegrityError("Private database details")

        with patch.object(CategorySerializer, "create", failing_create):
            response = self.post("/api/categorias/", {"name": "Nova", "kind": "expense"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Category.objects.count(), before)
        self.assertNotIn("Private database", response.content.decode())

    def test_browsable_api_and_options_work(self):
        for path in ("/api/categorias/", "/api/lancamentos/", "/api/orcamentos/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_ACCEPT="text/html")
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Conta externa")
                self.assertNotContains(response, ">Externa<")
                self.assertEqual(self.client.options(path).status_code, 200)
        self.assertEqual(self.client.options("/api/transferencias/").status_code, 200)

    def test_invalid_category_rules_are_shared_with_html(self):
        self.entry()
        response = self.client.post(reverse("finance:category_update", args=[self.expense.pk]), {
            "name": "Mercado", "kind": "income", "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("kind", response.context["form"].errors)
