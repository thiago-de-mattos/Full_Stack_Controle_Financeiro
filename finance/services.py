"""Regra de negocio que nao cabe numa model nem numa view."""

import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction as db_transaction
from core.utils import get_user_organization
from .models import Account, Category, Transaction

DEFAULT_CATEGORIES = [
    ("Salário", Category.Kind.INCOME),
    ("Freelance", Category.Kind.INCOME),
    ("Rendimentos", Category.Kind.INCOME),
    ("Moradia", Category.Kind.EXPENSE),
    ("Mercado", Category.Kind.EXPENSE),
    ("Transporte", Category.Kind.EXPENSE),
    ("Alimentação", Category.Kind.EXPENSE),
    ("Saúde", Category.Kind.EXPENSE),
    ("Educação", Category.Kind.EXPENSE),
    ("Lazer", Category.Kind.EXPENSE),
    ("Assinaturas", Category.Kind.EXPENSE),
    ("Outros", Category.Kind.EXPENSE),
]


@db_transaction.atomic
def create_default_categories(user):
    organization = get_user_organization(user)

    for name, kind in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            organization=organization,
            name__iexact=name,
            kind=kind,
            defaults={"name": name, "user": user},
        )


@db_transaction.atomic
def create_transfer(
    *,
    user,
    from_account,
    to_account,
    amount,
    date,
    description="",
):
    organization = get_user_organization(user)
    if from_account.pk == to_account.pk:
        raise ValidationError("Escolha uma conta diferente da de origem.")
    if amount <= 0:
        raise ValidationError("O valor precisa ser maior que zero.")
    accounts = Account.objects.for_user(user).active().filter(
        pk__in=[from_account.pk, to_account.pk]
    )
    if accounts.count() != 2:
        raise ValidationError("Selecione duas contas ativas da sua organização.")
    group = uuid.uuid4()

    saida = Transaction.objects.create(
        user=user,
        organization=organization,
        account=from_account,
        category=None,
        kind=Transaction.Kind.EXPENSE,
        amount=amount,
        date=date,
        description=description or f"Transferência para {to_account.name}",
        transfer_group=group,
    )

    entrada = Transaction.objects.create(
        user=user,
        organization=organization,
        account=to_account,
        category=None,
        kind=Transaction.Kind.INCOME,
        amount=amount,
        date=date,
        description=description or f"Transferência de {from_account.name}",
        transfer_group=group,
    )

    return saida, entrada


@db_transaction.atomic
def delete_transaction(transaction, *, user):
    """Apagar uma perna da transferencia sem a outra deixa saldo furado."""
    organization = get_user_organization(user)
    if transaction.organization_id != organization.pk:
        raise PermissionDenied("Este lançamento não pertence à sua organização.")
    if transaction.transfer_group:
        Transaction.objects.filter(
            organization=organization, transfer_group=transaction.transfer_group
        ).delete()
    else:
        transaction.delete()


def month_summary(user, ref):
    base = (
        Transaction.objects.for_user(user)
        .in_month(ref)
        .settled()
        .without_transfers()
    )
    receitas = base.income().total()
    despesas = base.expenses().total()
    return {
        "receitas": receitas,
        "despesas": despesas,
        "resultado": receitas - despesas,
    }


def total_balance(user):
    contas = Account.objects.for_user(user).active().with_balance()
    return sum((c.balance for c in contas), Decimal("0.00"))

