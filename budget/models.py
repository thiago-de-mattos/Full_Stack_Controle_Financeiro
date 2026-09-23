from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from core.models import TimeStampedModel
from finance.models import MONEY, ZERO, Category, Transaction


class BudgetQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def with_spent(self, ref):
        """Anota quanto ja foi gasto na categoria no mes de referencia.

        Recebe `ref` em vez de tirar do proprio registro porque OuterRef nao
        aceita transformacoes tipo month__year.
        """
        gasto = (
            Transaction.objects.filter(
                user=OuterRef("user"),
                category=OuterRef("category"),
                kind=Transaction.Kind.EXPENSE,
                is_settled=True,
                transfer_group__isnull=True,
                date__year=ref.year,
                date__month=ref.month,
            )
            .values("category")
            .annotate(total=Sum("amount"))
            .values("total")[:1]
        )
        return self.annotate(
            spent=Coalesce(Subquery(gasto, output_field=MONEY), ZERO)
        )


class Budget(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name="usuário",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name="categoria",
    )
    month = models.DateField("mês de referência", help_text="Sempre o dia 1 do mês.")
    limit_amount = models.DecimalField("limite", max_digits=12, decimal_places=2)

    objects = BudgetQuerySet.as_manager()

    class Meta:
        verbose_name = "orçamento"
        verbose_name_plural = "orçamentos"
        ordering = ["-month", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "month"], name="unique_budget_per_month"
            )
        ]

    def __str__(self):
        return f"{self.category.name} — {self.month:%m/%Y}"

    @property
    def spent_value(self):
        return getattr(self, "spent", Decimal("0.00"))

    @property
    def remaining(self):
        return self.limit_amount - self.spent_value

    @property
    def percent(self):
        if not self.limit_amount:
            return 0
        return int(self.spent_value / self.limit_amount * 100)

    @property
    def bar_width(self):
        return min(self.percent, 100)

    @property
    def status(self):
        pct = self.percent
        if pct >= 100:
            return "estourado"
        if pct >= 80:
            return "atencao"
        return "ok"
