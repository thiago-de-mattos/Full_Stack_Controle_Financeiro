from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile, User
from budget.models import Budget
from core.models import Organization
from .forms import CategoryForm
from .models import Account, Category, Transaction
from .services import create_default_categories, create_transfer, delete_transaction


class OrganizationAccessTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Organização A")
        self.other_org = Organization.objects.create(name="Organização B")
        self.owner = self.make_user("owner", self.org, Profile.Role.ADMIN)
        self.member = self.make_user("member", self.org)
        self.outsider = self.make_user("outsider", self.other_org, Profile.Role.ADMIN)
        self.account = Account.objects.create(
            user=self.owner, organization=self.org, name="Conta A"
        )
        self.member_account = Account.objects.create(
            user=self.member, organization=self.org, name="Conta colega"
        )
        self.foreign_account = Account.objects.create(
            user=self.outsider, organization=self.other_org, name="Conta externa"
        )
        self.category = Category.objects.create(
            user=self.owner, organization=self.org, name="Mercado", kind="expense"
        )
        self.foreign_category = Category.objects.create(
            user=self.outsider, organization=self.other_org,
            name="Mercado", kind="expense"
        )
        self.client.force_login(self.member)

    def make_user(self, name, organization, role=Profile.Role.OPERATOR):
        user = User.objects.create_user(email=f"{name}@example.test", name=name)
        Profile.objects.create(user=user, organization=organization, role=role)
        return user

    def test_api_lists_organization_accounts(self):
        response = self.client.get("/api/contas/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.json()},
            {self.account.pk, self.member_account.pk},
        )

    def test_api_denies_foreign_detail_update_and_delete(self):
        self.client.force_login(self.owner)
        url = f"/api/contas/{self.foreign_account.pk}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(
            url, {"name": "Alterado"}, content_type="application/json"
        ).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Account.objects.filter(pk=self.foreign_account.pk).exists())

    def test_api_edit_keeps_creator_and_organization(self):
        response = self.client.patch(
            f"/api/contas/{self.account.pk}/",
            {"name": "Conta editada", "user": self.member.pk,
             "organization": self.other_org.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.account.refresh_from_db()
        self.assertEqual(self.account.user_id, self.owner.pk)
        self.assertEqual(self.account.organization_id, self.org.pk)

    def test_api_create_ignores_forged_ownership(self):
        response = self.client.post(
            "/api/contas/", {"name": "Nova", "user": self.outsider.pk,
                             "organization": self.other_org.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        account = Account.objects.get(pk=response.json()["id"])
        self.assertEqual(account.user_id, self.member.pk)
        self.assertEqual(account.organization_id, self.org.pk)

    def test_duplicate_account_rejected_for_teammate(self):
        response = self.client.post(
            "/api/contas/", {"name": "conta a"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Account.objects.create(
                user=self.member, organization=self.org, name="CONTA A"
            )

    def test_category_duplicate_rejected_for_teammate(self):
        form = CategoryForm(
            {"name": "mercado", "kind": "expense", "is_active": True},
            user=self.member,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_html_edit_keeps_creator(self):
        response = self.client.post(
            reverse("finance:account_update", args=[self.account.pk]),
            {"name": "Conta atualizada", "kind": "checking",
             "initial_balance": "10.00", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.user_id, self.owner.pk)
        self.assertEqual(self.account.organization_id, self.org.pk)

    def test_transaction_form_accepts_teammate_account(self):
        response = self.client.post(reverse("finance:transaction_create"), {
            "account": self.account.pk, "category": self.category.pk,
            "kind": "expense", "amount": "20.00", "date": "2026-11-01",
            "is_settled": "on",
        })
        self.assertEqual(response.status_code, 302)
        entry = Transaction.objects.get()
        self.assertEqual(entry.organization_id, self.org.pk)
        self.assertEqual(entry.user_id, self.member.pk)

    def test_forms_reject_foreign_relationships(self):
        response = self.client.post(reverse("finance:transaction_create"), {
            "account": self.foreign_account.pk, "category": self.foreign_category.pk,
            "kind": "expense", "amount": "20.00", "date": "2026-11-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        form = CategoryForm(
            {"name": "Nova", "kind": "expense", "parent": self.foreign_category.pk},
            user=self.member,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)
        response = self.client.post(reverse("budget:budget_create"), {
            "category": self.foreign_category.pk, "month": "2026-11",
            "limit_amount": "100.00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Budget.objects.exists())

    def test_model_validation_rejects_foreign_links(self):
        entry = Transaction(
            user=self.member, organization=self.org, account=self.foreign_account,
            category=self.foreign_category, kind="expense", amount=10,
            date=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError) as error:
            entry.full_clean()
        self.assertIn("account", error.exception.message_dict)
        self.assertIn("category", error.exception.message_dict)

    def test_budget_counts_teammate_expenses(self):
        ref = date(2026, 11, 1)
        budget = Budget.objects.create(
            user=self.owner, organization=self.org, category=self.category,
            month=ref, limit_amount=100,
        )
        for user, organization, account, category, amount in [
            (self.owner, self.org, self.account, self.category, 10),
            (self.member, self.org, self.member_account, self.category, 20),
            (self.outsider, self.other_org, self.foreign_account, self.foreign_category, 90),
        ]:
            Transaction.objects.create(
                user=user, organization=organization, account=account,
                category=category, kind="expense", amount=amount, date=ref,
            )
        result = Budget.objects.for_user(self.member).with_spent(ref).get(pk=budget.pk)
        self.assertEqual(result.spent_value, Decimal("30.00"))
        self.assertEqual(result.remaining, Decimal("70.00"))
        response = self.client.get(reverse("finance:dashboard"), {"mes": "2026-11"})
        self.assertEqual(response.context["resumo"]["despesas"], Decimal("30.00"))

    def test_budget_duplicate_rejected_for_teammate(self):
        Budget.objects.create(
            user=self.owner, organization=self.org, category=self.category,
            month=date(2026, 11, 1), limit_amount=100,
        )
        response = self.client.post(reverse("budget:budget_create"), {
            "category": self.category.pk, "month": "2026-11", "limit_amount": "200",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Budget.objects.count(), 1)

    def test_transfer_works_across_members_and_delete_removes_both(self):
        outgoing, incoming = create_transfer(
            user=self.member, from_account=self.account, to_account=self.member_account,
            amount=Decimal("10.00"), date=date(2026, 11, 1),
        )
        self.client.force_login(self.owner)
        response = self.client.post(reverse("finance:transaction_delete", args=[outgoing.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Transaction.objects.filter(pk__in=[outgoing.pk, incoming.pk]).exists())

    def test_transfer_rejects_foreign_account_without_partial_writes(self):
        with self.assertRaises(ValidationError):
            create_transfer(
                user=self.member, from_account=self.account, to_account=self.foreign_account,
                amount=Decimal("10.00"), date=date(2026, 11, 1),
            )
        self.assertFalse(Transaction.objects.exists())

    def test_foreign_user_cannot_delete_transfer_through_service(self):
        outgoing, _ = create_transfer(
            user=self.member, from_account=self.account, to_account=self.member_account,
            amount=Decimal("10.00"), date=date(2026, 11, 1),
        )
        with self.assertRaises(PermissionDenied):
            delete_transaction(outgoing, user=self.outsider)
        self.assertEqual(Transaction.objects.count(), 2)

    def test_editing_one_transfer_movement_is_rejected(self):
        outgoing, _ = create_transfer(
            user=self.member, from_account=self.account, to_account=self.member_account,
            amount=Decimal("10.00"), date=date(2026, 11, 1),
        )
        response = self.client.post(reverse("finance:transaction_update", args=[outgoing.pk]), {
            "account": self.account.pk, "kind": "expense", "amount": "999.00",
            "date": "2026-11-01", "is_settled": "on",
        })
        self.assertEqual(response.status_code, 200)
        outgoing.refresh_from_db()
        self.assertEqual(outgoing.amount, Decimal("10.00"))

    def test_default_categories_are_shared_and_idempotent(self):
        create_default_categories(self.owner)
        create_default_categories(self.member)
        self.assertEqual(Category.objects.filter(organization=self.org).count(), 12)

    def test_missing_profile_denies_access(self):
        user = User.objects.create_user(email="no-profile@example.test", name="Sem perfil")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/contas/").status_code, 403)
        self.assertEqual(self.client.get(reverse("finance:dashboard")).status_code, 403)

    def test_change_of_organization_revokes_old_access(self):
        Profile.objects.filter(user=self.owner).update(organization=self.other_org)
        self.client.force_login(User.objects.get(pk=self.owner.pk))
        self.assertEqual(self.client.get(f"/api/contas/{self.account.pk}/").status_code, 404)

    def test_anonymous_api_access_is_denied(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/contas/").status_code, 403)
