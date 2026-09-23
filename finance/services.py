"""Regra de negocio que nao cabe numa model nem numa view."""

import uuid
from decimal import Decimal

from django.db import transaction as db_transaction

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


def create_default_categories(user):
    """Conta nova ja nasce usavel, sem tela de configuracao inicial."""
    Category.objects.bulk_create(
        [Category(user=user, name=name, kind=kind) for name, kind in DEFAULT_CATEGORIES],
        ignore_conflicts=True,
    )


@db_transaction.atomic
def create_transfer(*, user, from_account, to_account, amount, date, description=""):
    """Uma transferencia = dois lancamentos irmaos com o mesmo transfer_group.

    Fazendo assim, todo movimento de dinheiro vive na mesma tabela e o calculo
    de saldo nao precisa de caso especial.
    """
    group = uuid.uuid4()
    saida = Transaction.objects.create(
        user=user,
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
def delete_transaction(transaction):
    """Apagar uma perna da transferencia sem a outra deixa saldo furado."""
    if transaction.transfer_group:
        Transaction.objects.filter(
            user=transaction.user, transfer_group=transaction.transfer_group
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

