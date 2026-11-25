from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

from .managers import UserManager


class User(AbstractUser):
    # AbstractUser ja traz date_joined, last_login, is_active, is_staff.
    username = None
    first_name = None
    last_name = None

    name = models.CharField("nome", max_length=120)
    email = models.EmailField("e-mail", unique=True)
    birth_date = models.DateField("data de nascimento", null=True, blank=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]  # nunca inclui o USERNAME_FIELD aqui

    objects = UserManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split(" ")[0] if self.name else self.email

class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        OPERATOR = "operator", "Operador"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="usuário",
    )
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.PROTECT,
        related_name="profiles",
        verbose_name="organização",
    )
    role = models.CharField(
        "papel",
        max_length=20,
        choices=Role.choices,
        default=Role.OPERATOR,
    )

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self):
        return f"{self.user} — {self.organization}"