from django.contrib.auth.models import AbstractUser
from django.db import models

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
