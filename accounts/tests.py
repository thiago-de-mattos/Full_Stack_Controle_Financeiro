from datetime import date

from django.test import TestCase
from django.urls import reverse

from finance.models import Category

from .models import User

SENHA = "cavalo-bateria-grampo-9"


class CadastroTests(TestCase):
    def _dados(self, **over):
        base = {
            "name": "Thiago",
            "email": "Thiago@Exemplo.COM",
            "birth_date": "2003-04-15",
            "password1": SENHA,
            "password2": SENHA,
        }
        base.update(over)
        return base

    def test_cadastro_valido_cria_usuario_e_loga(self):
        r = self.client.post(reverse("accounts:register"), self._dados(), follow=True)
        self.assertRedirects(r, reverse("finance:dashboard"))
        self.assertTrue(User.objects.filter(email="thiago@exemplo.com").exists())

    def test_email_e_normalizado_para_minusculo(self):
        self.client.post(reverse("accounts:register"), self._dados())
        self.assertTrue(User.objects.filter(email="thiago@exemplo.com").exists())

    def test_senha_nao_fica_em_texto_puro(self):
        self.client.post(reverse("accounts:register"), self._dados())
        user = User.objects.get(email="thiago@exemplo.com")
        self.assertNotIn(SENHA, user.password)
        self.assertTrue(user.check_password(SENHA))

    def test_categorias_padrao_sao_criadas(self):
        self.client.post(reverse("accounts:register"), self._dados())
        user = User.objects.get(email="thiago@exemplo.com")
        self.assertEqual(Category.objects.filter(user=user).count(), 12)

    def test_email_duplicado_e_rejeitado(self):
        User.objects.create_user(email="thiago@exemplo.com", password=SENHA, name="Outro")
        r = self.client.post(reverse("accounts:register"), self._dados())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_senhas_diferentes_sao_rejeitadas(self):
        r = self.client.post(
            reverse("accounts:register"), self._dados(password2="outra-coisa-9")
        )
        self.assertFormError(r.context["form"], "password2", "As senhas não coincidem.")

    def test_senha_comum_em_portugues_e_rejeitada(self):
        r = self.client.post(
            reverse("accounts:register"), self._dados(password1="Senha@123", password2="Senha@123")
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_senha_parecida_com_o_email_e_rejeitada(self):
        r = self.client.post(
            reverse("accounts:register"),
            self._dados(password1="thiago@exemplo.com", password2="thiago@exemplo.com"),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_data_de_nascimento_no_futuro_e_rejeitada(self):
        futuro = date.today().replace(year=date.today().year + 1)
        r = self.client.post(reverse("accounts:register"), self._dados(birth_date=futuro.isoformat()))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_menor_de_16_e_rejeitado(self):
        nascimento = date.today().replace(year=date.today().year - 10)
        r = self.client.post(reverse("accounts:register"), self._dados(birth_date=nascimento.isoformat()))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_data_de_nascimento_e_opcional(self):
        r = self.client.post(reverse("accounts:register"), self._dados(birth_date=""), follow=True)
        self.assertRedirects(r, reverse("finance:dashboard"))


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="thiago@exemplo.com", password=SENHA, name="Thiago"
        )

    def test_login_com_email(self):
        r = self.client.post(
            reverse("accounts:login"), {"email": "thiago@exemplo.com", "password": SENHA}, follow=True
        )
        self.assertRedirects(r, reverse("finance:dashboard"))

    def test_login_aceita_email_em_caixa_alta(self):
        r = self.client.post(
            reverse("accounts:login"), {"email": "THIAGO@Exemplo.com", "password": SENHA}, follow=True
        )
        self.assertRedirects(r, reverse("finance:dashboard"))

    def test_senha_errada_da_mensagem_generica(self):
        r = self.client.post(
            reverse("accounts:login"), {"email": "thiago@exemplo.com", "password": "errada-9"}
        )
        self.assertContains(r, "E-mail ou senha inválidos")

    def test_usuario_inativo_nao_entra_e_nao_se_revela(self):
        self.user.is_active = False
        self.user.save()
        r = self.client.post(
            reverse("accounts:login"), {"email": "thiago@exemplo.com", "password": SENHA}
        )
        self.assertContains(r, "E-mail ou senha inválidos")
        self.assertNotContains(r, "desativada")

    def test_sessao_e_rotacionada_no_login(self):
        self.client.get(reverse("accounts:login"))
        antes = self.client.session.session_key
        self.client.post(reverse("accounts:login"), {"email": "thiago@exemplo.com", "password": SENHA})
        self.assertNotEqual(antes, self.client.session.session_key)

    def test_next_interno_e_respeitado(self):
        r = self.client.post(
            reverse("accounts:login") + "?next=/contas/",
            {"email": "thiago@exemplo.com", "password": SENHA},
        )
        self.assertEqual(r["Location"], "/contas/")

    def test_next_externo_e_ignorado(self):
        r = self.client.post(
            reverse("accounts:login") + "?next=https://site-malicioso.test/x",
            {"email": "thiago@exemplo.com", "password": SENHA},
        )
        self.assertNotIn("site-malicioso", r["Location"])

    def test_logout_recusa_get(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("accounts:logout"))
        self.assertEqual(r.status_code, 405)

    def test_logout_por_post_funciona(self):
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
