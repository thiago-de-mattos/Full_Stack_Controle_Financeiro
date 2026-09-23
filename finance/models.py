from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import (Case, DecimalField, ExpressionWrapper, F, Q, Sum, Value, When,)
from django.db.models.functions import Coalesce
from core.models import TimeStampedModel

MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Value(Decimal("0.00"), output_field=MONEY)


class AccountQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def active(self):
        return self.filter(is_active=True)

    def with_balance(self):
        """Saldo = saldo inicial + movimento ja liquidado.

        Transferencia entra naturalmente aqui: ela vira uma saida numa conta
        e uma entrada na outra, entao as duas pontas se anulam no total.
        """
        movement = Sum(
            Case(
                When(
                    transactions__kind=Transaction.Kind.INCOME,
                    then=F("transactions__amount"),
                ),
                When(
                    transactions__kind=Transaction.Kind.EXPENSE,
                    then=-F("transactions__amount"),
                ),
                default=ZERO,
                output_field=MONEY,
            ),
            filter=Q(transactions__is_settled=True),
        )
        return self.annotate(
            balance=ExpressionWrapper(
                F("initial_balance") + Coalesce(movement, ZERO), output_field=MONEY
            )
        )


class Account(TimeStampedModel):
    class Kind(models.TextChoices):
        CHECKING = "checking", "Conta corrente"
        SAVINGS = "savings", "Poupança"
        CASH = "cash", "Dinheiro"
        CREDIT_CARD = "credit_card", "Cartão de crédito"
        INVESTMENT = "investment", "Investimento"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
        verbose_name="usuário",
    )
    name = models.CharField("nome", max_length=60)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices, default=Kind.CHECKING)
    initial_balance = models.DecimalField(
        "saldo inicial", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    is_active = models.BooleanField("ativa", default=True)

    objects = AccountQuerySet.as_manager()

    class Meta:
        verbose_name = "conta"
        verbose_name_plural = "contas"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_account_per_user")
        ]

    def __str__(self):
        return self.name


class CategoryQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def active(self):
        return self.filter(is_active=True)

    def income(self):
        return self.filter(kind=Category.Kind.INCOME)

    def expenses(self):
        return self.filter(kind=Category.Kind.EXPENSE)


class Category(TimeStampedModel):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name="usuário",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name="categoria pai",
    )
    name = models.CharField("nome", max_length=60)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    color = models.CharField("cor", max_length=7, default="#6b7269")
    is_active = models.BooleanField("ativa", default=True)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "kind"], name="unique_category_per_user"
            )
        ]

    def __str__(self):
        return self.name


class TransactionQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def settled(self):
        return self.filter(is_settled=True)

    def in_month(self, ref):
        return self.filter(date__year=ref.year, date__month=ref.month)

    def without_transfers(self):
        """Transferencia move dinheiro entre contas suas: nao e receita nem
        despesa. Todo relatorio de gasto precisa tirar ela fora."""
        return self.filter(transfer_group__isnull=True)

    def income(self):
        return self.filter(kind=Transaction.Kind.INCOME)

    def expenses(self):
        return self.filter(kind=Transaction.Kind.EXPENSE)

    def total(self):
        return self.aggregate(total=Coalesce(Sum("amount"), ZERO))["total"]


class Transaction(TimeStampedModel):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="usuário",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="conta",
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="categoria",
    )
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    amount = models.DecimalField("valor", max_digits=12, decimal_places=2)
    date = models.DateField("data")
    description = models.CharField("descrição", max_length=140, blank=True)
    notes = models.TextField("observações", blank=True)
    is_settled = models.BooleanField(
        "já pago / recebido",
        default=True,
        help_text="Desmarque para registrar algo previsto que ainda não aconteceu.",
    )
    transfer_group = models.UUIDField(null=True, blank=True, editable=False, db_index=True)

    objects = TransactionQuerySet.as_manager()

    class Meta:
        verbose_name = "lançamento"
        verbose_name_plural = "lançamentos"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["user", "date"])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="amount_gt_zero"),
        ]

    def __str__(self):
        return f"{self.description or self.get_kind_display()} — {self.amount}"

    @property
    def is_transfer(self):
        return self.transfer_group is not None

    @property
    def signed_amount(self):
        return self.amount if self.kind == self.Kind.INCOME else -self.amount
