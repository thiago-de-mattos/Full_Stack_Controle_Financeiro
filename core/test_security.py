import os
import runpy
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.db import IntegrityError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse

from accounts.forms import LoginForm, RegisterForm
from accounts.models import Profile, User
from budget.forms import BudgetForm
from budget.models import Budget
from core.models import Organization
from finance.forms import AccountForm, CategoryForm, TransactionForm
from finance.models import Account, Category, Transaction
from finance.services import create_transfer

PASSWORD = "cavalo-bateria-grampo-9"


def broken_view(request):
    raise RuntimeError("INTERNAL_SECRET_DETAIL")


def bad_view(request):
    raise SuspiciousOperation("INTERNAL_SECRET_DETAIL")


# URLConf só dos testes: nenhuma rota de erro é adicionada à aplicação.
urlpatterns = [path("broken/", broken_view), path("bad/", bad_view)]


class SecurityFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Organização A")
        cls.user = User.objects.create_user(name="Ana", email="ana@example.test", password=PASSWORD)
        Profile.objects.create(user=cls.user, organization=cls.org, role=Profile.Role.ADMIN)
        cls.account = Account.objects.create(user=cls.user, organization=cls.org, name="Conta A")
        cls.wallet = Account.objects.create(user=cls.user, organization=cls.org, name="Carteira")
        cls.category = Category.objects.create(user=cls.user, organization=cls.org, name="Mercado", kind="expense")
        cls.entry = Transaction.objects.create(user=cls.user, organization=cls.org, account=cls.account,
                                               category=cls.category, kind="expense", amount=10, date=date(2026, 11, 1))
        cls.budget = Budget.objects.create(user=cls.user, organization=cls.org, category=cls.category,
                                          month=date(2026, 11, 1), limit_amount=100)

    def register_data(self):
        return {"organization_name": "Nova empresa", "name": "Carlos", "email": "carlos@example.test",
                "birth_date": "2000-01-01", "password1": PASSWORD, "password2": PASSWORD}

    def test_html_login_and_registration_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for url, data in [(reverse("accounts:login"), {"email": self.user.email, "password": PASSWORD}),
                          (reverse("accounts:register"), self.register_data())]:
            response = client.post(url, data)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, "Atualize a página", status_code=403)
            self.assertNotContains(response, "CSRF cookie not set", status_code=403)
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn("_auth_user_id", client.session)

    def test_registration_csrf_success_ignores_injected_privileges(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("accounts:register"))
        data = self.register_data() | {"organization": self.org.pk, "is_staff": "on", "is_superuser": "on"}
        response = client.post(reverse("accounts:register"), data,
                               HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=data["email"])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.profile.organization_id, self.org.pk)
        self.assertEqual(user.profile.role, Profile.Role.ADMIN)
        self.assertEqual(Category.objects.for_user(user).count(), 12)

    def test_registration_failure_rolls_back_user_profile_and_organization(self):
        with patch("accounts.views.create_default_categories", side_effect=IntegrityError("INTERNAL_SECRET_DETAIL")):
            with self.assertLogs("accounts.views", level="ERROR"):
                response = self.client.post(reverse("accounts:register"), self.register_data())
        self.assertContains(response, "Não foi possível concluir o cadastro")
        self.assertNotContains(response, "INTERNAL_SECRET_DETAIL")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Profile.objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_failed_login_preserves_safe_post_destination(self):
        response = self.client.post(reverse("accounts:login"), {
            "email": self.user.email, "password": "errada", "next": "/contas/",
        })
        self.assertContains(response, 'name="next" value="/contas/"')
        response = self.client.post(reverse("accounts:login"), {
            "email": self.user.email, "password": PASSWORD, "next": response.context["next"],
        })
        self.assertEqual(response["Location"], "/contas/")

    def test_unsafe_login_destinations_are_not_reflected(self):
        for destination in ["https://evil.test/", "//evil.test/", "\\\\evil.test/", "http://testserver/contas/"]:
            with self.subTest(destination=destination):
                response = self.client.post(reverse("accounts:login"), {
                    "email": self.user.email, "password": "errada", "next": destination,
                }, secure=True)
                self.assertEqual(response.context["next"], "")

    def test_empty_login_post_shows_required_fields(self):
        response = self.client.post(reverse("accounts:login"), {})
        self.assertTrue(response.context["form"].is_bound)
        self.assertIn("email", response.context["form"].errors)
        self.assertIn("password", response.context["form"].errors)

    def test_oversized_password_is_rejected_before_authentication_or_validation(self):
        with patch("accounts.forms.authenticate") as authenticate:
            form = LoginForm(data={"email": self.user.email, "password": "x" * 4097})
            self.assertFalse(form.is_valid())
            authenticate.assert_not_called()
        with patch("accounts.forms.password_validation.validate_password") as validate:
            form = RegisterForm(data=self.register_data() | {"password1": "x" * 129, "password2": "x" * 129})
            self.assertFalse(form.is_valid())
            validate.assert_not_called()

    def test_api_session_writes_require_csrf_and_valid_token_allows_create(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("finance:dashboard"))
        data = {"name": "Nova conta", "kind": "cash", "initial_balance": "0", "is_active": True}
        response = client.post("/api/contas/", data, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Account.objects.filter(name="Nova conta").exists())
        response = client.post("/api/contas/", data, content_type="application/json",
                               HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 201)

    def test_csrf_blocks_api_delete_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.delete(f"/api/contas/{self.wallet.pk}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Account.objects.filter(pk=self.wallet.pk).exists())
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)
        self.assertIn("_auth_user_id", client.session)

    def test_authenticated_pages_api_and_logout_are_not_cacheable(self):
        self.client.force_login(self.user)
        for url in ["/", "/contas/", "/api/contas/", "/orcamentos/"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("private", response["Cache-Control"])
            self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("no-store", self.client.post(reverse("accounts:logout"))["Cache-Control"])

    def test_all_html_creates_and_updates_handle_database_conflicts(self):
        self.client.force_login(self.user)
        cases = [
            (AccountForm, "finance:account_create", "finance:account_update", self.account.pk,
             {"name": "Nova", "kind": "cash", "initial_balance": "0", "is_active": "on"}),
            (CategoryForm, "finance:category_create", "finance:category_update", self.category.pk,
             {"name": "Nova categoria", "kind": "expense", "parent": "", "is_active": "on"}),
            (TransactionForm, "finance:transaction_create", "finance:transaction_update", self.entry.pk,
             {"kind": "expense", "account": self.account.pk, "category": self.category.pk,
              "amount": "25", "date": "2026-11-02", "is_settled": "on"}),
            (BudgetForm, "budget:budget_create", "budget:budget_update", self.budget.pk,
             {"category": self.category.pk, "month": "2026-12", "limit_amount": "200"}),
        ]

        def duplicate_write(*args, **kwargs):
            # A primeira escrita deve ser desfeita quando a segunda conflitar.
            values = {"user": self.user, "organization": self.org, "name": "Parcial"}
            Account.objects.create(**values)
            Account.objects.create(**values)

        for form_class, create, update, pk, data in cases:
            for url in [reverse(create), reverse(update, args=[pk])]:
                with self.subTest(url=url), patch.object(form_class, "save", side_effect=duplicate_write):
                    response = self.client.post(url, data)
                    self.assertContains(response, "Não foi possível salvar")
                    self.assertNotContains(response, "Conta criada.")
                    self.assertNotContains(response, "UNIQUE constraint")
                    self.assertFalse(Account.objects.filter(name="Parcial").exists())
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.amount, Decimal("10"))

    def test_transfer_failure_rolls_back_first_movement_in_html(self):
        self.client.force_login(self.user)
        original_create = Transaction.objects.create
        calls = 0

        def fail_second(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise IntegrityError("INTERNAL_SECRET_DETAIL")
            return original_create(**kwargs)

        with patch("finance.services.Transaction.objects.create", side_effect=fail_second):
            response = self.client.post(reverse("finance:transfer_create"), {
                "from_account": self.account.pk, "to_account": self.wallet.pk,
                "amount": "25", "date": "2026-11-10", "description": "Teste",
            })
        self.assertContains(response, "Não foi possível registrar a transferência")
        self.assertNotContains(response, "INTERNAL_SECRET_DETAIL")
        self.assertFalse(Transaction.objects.filter(transfer_group__isnull=False).exists())

    def test_financial_admin_is_read_only_even_for_superuser(self):
        staff = User.objects.create_superuser(email="root@example.test", name="Suporte", password=PASSWORD)
        self.client.force_login(staff)
        request = RequestFactory().get("/admin/")
        request.user = staff
        for obj in [self.account, self.category, self.entry, self.budget]:
            model = type(obj)
            prefix = f"admin:{model._meta.app_label}_{model._meta.model_name}"
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request, obj))
            self.assertFalse(model_admin.has_delete_permission(request, obj))
            self.assertEqual(model_admin.get_actions(request), {})
            self.assertEqual(self.client.get(reverse(prefix + "_change", args=[obj.pk])).status_code, 200)
            for route, args in [("_add", []), ("_change", [obj.pk]), ("_delete", [obj.pk])]:
                self.assertEqual(self.client.post(reverse(prefix + route, args=args), {}).status_code, 403)
            obj.refresh_from_db()

    def test_admin_bulk_action_cannot_remove_half_of_transfer(self):
        outgoing, incoming = create_transfer(user=self.user, from_account=self.account,
                                             to_account=self.wallet, amount=Decimal("20"), date=date(2026, 11, 1))
        staff = User.objects.create_superuser(email="root@example.test", name="Suporte", password=PASSWORD)
        self.client.force_login(staff)
        self.client.post(reverse("admin:finance_transaction_changelist"), {
            "action": "delete_selected", "_selected_action": [outgoing.pk], "post": "yes",
        })
        self.assertTrue(Transaction.objects.filter(pk=outgoing.pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=incoming.pk).exists())

    def test_support_can_still_open_user_profile_and_organization_forms(self):
        staff = User.objects.create_superuser(email="root@example.test", name="Suporte", password=PASSWORD)
        self.client.force_login(staff)
        for url in ["admin:accounts_user_add", "admin:accounts_profile_add", "admin:core_organization_add"]:
            self.assertEqual(self.client.get(reverse(url)).status_code, 200)

    @override_settings(DEBUG=False)
    def test_public_404_does_not_show_urlconf_or_requested_text(self):
        response = self.client.get("/missing-INTERNAL_SECRET_DETAIL/")
        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertNotContains(response, "INTERNAL_SECRET_DETAIL", status_code=404)
        self.assertNotContains(response, "config.urls", status_code=404)

    @override_settings(DEBUG=False, ROOT_URLCONF=__name__)
    def test_public_400_and_500_do_not_show_exception_details(self):
        client = Client(raise_request_exception=False)
        for url, code in [("/bad/", 400), ("/broken/", 500)]:
            response = client.get(url)
            self.assertEqual(response.status_code, code)
            self.assertNotContains(response, "INTERNAL_SECRET_DETAIL", status_code=code)
            self.assertNotContains(response, "Traceback", status_code=code)
            self.assertContains(response, "Voltar ao início", status_code=code)


class ProductionConfigurationTests(SimpleTestCase):
    def load_config(self, **values):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("DJANGO_")}
        environment.update(values)
        with patch.dict(os.environ, environment, clear=True):
            return runpy.run_path(str(Path(settings.BASE_DIR) / "config" / "settings.py"))

    def test_local_development_still_starts_without_environment(self):
        self.assertTrue(self.load_config()["DEBUG"])

    def test_production_rejects_absent_default_and_weak_keys(self):
        for key in ["", "troque-esta-chave-em-producao", "a" * 60, "django-insecure-" + "abcde" * 12]:
            with self.subTest(key_type=len(key)), self.assertRaises(ImproperlyConfigured):
                self.load_config(DJANGO_DEBUG="False", DJANGO_SECRET_KEY=key, DJANGO_ALLOWED_HOSTS="app.example.test")

    def test_production_requires_explicit_hosts_without_wildcard(self):
        for hosts in ["", "*", "app.example.test,*"]:
            with self.subTest(hosts=hosts), self.assertRaises(ImproperlyConfigured):
                self.load_config(DJANGO_DEBUG="False", DJANGO_SECRET_KEY="test-only-key-" * 5, DJANGO_ALLOWED_HOSTS=hosts)

    def test_production_enables_secure_cookies_and_proxy_is_opt_in(self):
        values = {"DJANGO_DEBUG": "False", "DJANGO_SECRET_KEY": "test-only-key-" * 5,
                  "DJANGO_ALLOWED_HOSTS": "app.example.test"}
        config = self.load_config(**values)
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])
        self.assertTrue(config["SECURE_SSL_REDIRECT"])
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", config)
        config = self.load_config(**values, DJANGO_TRUST_PROXY_HTTPS="True")
        self.assertEqual(config["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
