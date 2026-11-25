from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile, User
from budget.models import Budget
from core.models import Organization
from .models import Account, Category, Transaction
from .services import create_transfer, delete_transaction


class FinancialPermissionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Organização A")
        self.other_org = Organization.objects.create(name="Organização B")
        self.admin = self.make_user("admin", self.org, Profile.Role.ADMIN)
        self.operator = self.make_user("operator", self.org, Profile.Role.OPERATOR)
        self.foreign_admin = self.make_user("foreign", self.other_org, Profile.Role.ADMIN)
        self.account = Account.objects.create(
            user=self.admin, organization=self.org, name="Conta sem lançamentos"
        )
        self.used_account = Account.objects.create(
            user=self.admin, organization=self.org, name="Conta em uso"
        )
        self.category = Category.objects.create(
            user=self.admin, organization=self.org, name="Categoria livre", kind="expense"
        )
        self.used_category = Category.objects.create(
            user=self.admin, organization=self.org, name="Categoria em uso", kind="expense"
        )
        self.entry = Transaction.objects.create(
            user=self.admin, organization=self.org, account=self.used_account,
            category=self.used_category, kind="expense", amount=10, date=date.today(),
        )
        self.budget = Budget.objects.create(
            user=self.admin, organization=self.org, category=self.used_category,
            month=date.today().replace(day=1), limit_amount=100,
        )

    def make_user(self, name, organization, role):
        user = User.objects.create_user(email=f"{name}@example.test", name=name)
        Profile.objects.create(user=user, organization=organization, role=role)
        return user

    def delete_targets(self):
        return [
            ("finance:account_delete", self.account),
            ("finance:category_delete", self.category),
            ("finance:transaction_delete", self.entry),
            ("budget:budget_delete", self.budget),
        ]

    def test_operator_cannot_open_or_submit_any_delete_page(self):
        self.client.force_login(self.operator)
        for route, obj in self.delete_targets():
            url = reverse(route, args=[obj.pk])
            for method in (self.client.get, self.client.post):
                with self.subTest(route=route, method=method.__name__):
                    response = method(url)
                    self.assertEqual(response.status_code, 403)
                    self.assertTemplateUsed(response, "403.html")
                    self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_admin_can_open_and_submit_delete_pages(self):
        self.client.force_login(self.admin)
        for route, obj in self.delete_targets():
            with self.subTest(route=route):
                url = reverse(route, args=[obj.pk])
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.post(url).status_code, 302)
                self.assertFalse(type(obj).objects.filter(pk=obj.pk).exists())

    def test_foreign_admin_cannot_open_or_submit_delete_pages(self):
        self.client.force_login(self.foreign_admin)
        for route, obj in self.delete_targets():
            url = reverse(route, args=[obj.pk])
            with self.subTest(route=route):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url).status_code, 404)
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_anonymous_delete_pages_require_login(self):
        for route, obj in self.delete_targets():
            url = reverse(route, args=[obj.pk])
            with self.subTest(route=route):
                self.assertEqual(self.client.get(url).status_code, 302)
                self.assertEqual(self.client.post(url).status_code, 302)
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_api_operator_create_read_update_allowed_delete_denied(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            "/api/contas/", {"name": "Criada pelo operador"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        pk = response.json()["id"]
        url = f"/api/contas/{pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(
            url, {"name": "Editada"}, content_type="application/json"
        ).status_code, 200)
        self.assertEqual(self.client.put(
            url, {"name": "Atualizada", "kind": "cash", "initial_balance": "10.00",
                  "is_active": True}, content_type="application/json"
        ).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertTrue(Account.objects.filter(pk=pk).exists())

    def test_api_admin_can_delete(self):
        self.client.force_login(self.admin)
        pk = self.account.pk
        self.assertEqual(self.client.delete(f"/api/contas/{pk}/").status_code, 204)
        self.assertFalse(Account.objects.filter(pk=pk).exists())

    def test_api_foreign_admin_cannot_delete(self):
        self.client.force_login(self.foreign_admin)
        self.assertEqual(self.client.delete(
            f"/api/contas/{self.account.pk}/"
        ).status_code, 404)
        self.assertTrue(Account.objects.filter(pk=self.account.pk).exists())

    def test_api_forged_role_does_not_grant_delete(self):
        self.client.force_login(self.operator)
        response = self.client.delete(
            f"/api/contas/{self.account.pk}/",
            {"role": "admin", "is_superuser": True}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Profile.objects.get(user=self.operator).role, Profile.Role.OPERATOR)
        self.assertTrue(Account.objects.filter(pk=self.account.pk).exists())

    def test_delete_links_hidden_for_operator_visible_for_admin(self):
        pages = [
            ("finance:account_list", "finance:account_delete", self.account),
            ("finance:category_list", "finance:category_delete", self.category),
            ("finance:transaction_list", "finance:transaction_delete", self.entry),
            ("budget:budget_list", "budget:budget_delete", self.budget),
        ]
        for user, visible in [(self.operator, False), (self.admin, True)]:
            self.client.force_login(user)
            for page, route, obj in pages:
                with self.subTest(user=user.email, page=page):
                    response = self.client.get(reverse(page))
                    link = f'href="{reverse(route, args=[obj.pk])}"'
                    if visible:
                        self.assertContains(response, link)
                    else:
                        self.assertNotContains(response, link)

    def test_operator_can_use_creation_and_update_pages(self):
        self.client.force_login(self.operator)
        paths = [
            reverse("finance:account_create"),
            reverse("finance:category_create"),
            reverse("finance:transaction_create"),
            reverse("finance:transfer_create"),
            reverse("budget:budget_create"),
            reverse("finance:account_update", args=[self.account.pk]),
            reverse("finance:category_update", args=[self.category.pk]),
            reverse("finance:transaction_update", args=[self.entry.pk]),
            reverse("budget:budget_update", args=[self.budget.pk]),
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_operator_cannot_delete_transfer_even_through_service(self):
        outgoing, incoming = create_transfer(
            user=self.operator, from_account=self.account, to_account=self.used_account,
            amount=Decimal("10.00"), date=date.today(),
        )
        with self.assertRaises(PermissionDenied):
            delete_transaction(outgoing, user=self.operator)
        self.assertEqual(Transaction.objects.filter(pk__in=[outgoing.pk, incoming.pk]).count(), 2)

    def test_admin_can_delete_operator_transfer(self):
        outgoing, incoming = create_transfer(
            user=self.operator, from_account=self.account, to_account=self.used_account,
            amount=Decimal("10.00"), date=date.today(),
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("finance:transaction_delete", args=[outgoing.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Transaction.objects.filter(pk__in=[outgoing.pk, incoming.pk]).exists())

    def test_admin_protected_deletes_show_message_instead_of_server_error(self):
        self.client.force_login(self.admin)
        for route, obj in [
            ("finance:account_delete", self.used_account),
            ("finance:category_delete", self.used_category),
        ]:
            with self.subTest(route=route):
                response = self.client.post(reverse(route, args=[obj.pk]), follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "possui lançamentos vinculados")
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_staff_and_superuser_do_not_replace_organization_role(self):
        self.operator.is_staff = True
        self.operator.is_superuser = True
        self.operator.save()
        self.client.force_login(self.operator)
        self.assertEqual(self.client.delete(
            f"/api/contas/{self.account.pk}/"
        ).status_code, 403)
        self.assertEqual(self.client.post(reverse(
            "finance:account_delete", args=[self.account.pk]
        )).status_code, 403)

    def test_missing_or_unknown_role_is_denied(self):
        unknown = self.make_user("unknown", self.org, "invalid")
        no_profile = User.objects.create_user(email="missing@example.test", name="Missing")
        for user in (unknown, no_profile):
            self.client.force_login(user)
            with self.subTest(user=user.email):
                self.assertEqual(self.client.get("/api/contas/").status_code, 403)
                self.assertEqual(self.client.post(reverse(
                    "finance:account_delete", args=[self.account.pk]
                )).status_code, 403)

    def test_role_change_takes_effect_on_next_request(self):
        self.client.force_login(self.admin)
        Profile.objects.filter(user=self.admin).update(role=Profile.Role.OPERATOR)
        self.assertEqual(self.client.delete(
            f"/api/contas/{self.account.pk}/"
        ).status_code, 403)

    def test_admin_session_still_requires_csrf_for_delete(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.delete(
            f"/api/contas/{self.account.pk}/"
        ).status_code, 403)
        self.assertTrue(Account.objects.filter(pk=self.account.pk).exists())
