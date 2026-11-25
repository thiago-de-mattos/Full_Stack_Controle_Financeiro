"""Consultas do painel e exportação mensal, sempre por organização."""

import csv
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse

from core.utils import shift_month
from .models import ZERO, Transaction


def dashboard_metrics(user, ref):
    base = Transaction.objects.for_user(user).without_transfers()
    month = base.in_month(ref)
    pending = month.filter(is_settled=False).aggregate(
        receber=Coalesce(Sum("amount", filter=Q(kind="income")), ZERO),
        pagar=Coalesce(Sum("amount", filter=Q(kind="expense")), ZERO),
    )
    ranking = (
        month.settled().expenses()
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"), quantidade=Count("id"))
        .order_by("-total", "category__name", "category_id")[:5]
    )

    months = [shift_month(ref, delta) for delta in range(-5, 1)]
    grouped = (
        base.settled()
        .filter(date__gte=months[0], date__lt=shift_month(ref, 1))
        .annotate(mes=TruncMonth("date"))
        .values("mes")
        .annotate(
            receitas=Coalesce(Sum("amount", filter=Q(kind="income")), ZERO),
            despesas=Coalesce(Sum("amount", filter=Q(kind="expense")), ZERO),
        )
        .order_by("mes")
    )
    by_month = {row["mes"]: row for row in grouped}
    history = []
    for month_date in months:
        row = by_month.get(month_date, {
            "mes": month_date,
            "receitas": Decimal("0.00"),
            "despesas": Decimal("0.00"),
        })
        row["resultado"] = row["receitas"] - row["despesas"]
        history.append(row)

    return {"pendencias": pending, "ranking": ranking, "historico": history}


def csv_text(value):
    """Evita interpretar textos cadastrados como fórmulas na planilha."""
    text = str(value or "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def monthly_csv(user, ref):
    records = (
        Transaction.objects.for_user(user).in_month(ref)
        .select_related("account", "category").order_by("date", "id")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="lancamentos-{ref:%Y-%m}.csv"'
    response["Cache-Control"] = "private, no-store"
    response.write("\ufeff")  # Mantém os acentos ao abrir no Excel.
    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "ID", "Data", "Conta", "Categoria", "Tipo", "Descrição",
        "Valor (R$)", "Situação", "Transferência", "Observações",
    ])
    for record in records.iterator():
        writer.writerow([
            record.pk,
            record.date.strftime("%d/%m/%Y"),
            csv_text(record.account.name),
            csv_text(record.category.name if record.category else "Sem categoria"),
            record.get_kind_display(),
            csv_text(record.description),
            format(record.signed_amount, ".2f").replace(".", ","),
            "Realizado" if record.is_settled else "Previsto",
            "Sim" if record.is_transfer else "Não",
            csv_text(record.notes),
        ])
    return response
