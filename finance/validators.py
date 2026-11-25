from django.core.exceptions import ValidationError

from core.utils import get_user_organization
from .models import Account, Category


def validate_account_name(name, user, instance=None):
    name = name.strip()

    accounts = Account.objects.for_user(user).filter(name__iexact=name)

    if instance is not None and instance.pk:
        accounts = accounts.exclude(pk=instance.pk)

    if accounts.exists():
        raise ValidationError("Já existe uma conta com esse nome nesta organização.")

    return name


def validate_positive_amount(value, message="O valor precisa ser maior que zero."):
    if value <= 0:
        raise ValidationError(message)
    return value


def validate_category(*, name, kind, parent, user, instance=None):
    errors = {}
    organization = get_user_organization(user)

    if name and kind:
        duplicates = Category.objects.for_user(user).filter(name__iexact=name, kind=kind)
        if instance is not None and instance.pk:
            duplicates = duplicates.exclude(pk=instance.pk)
        if duplicates.exists():
            errors["name"] = "Já existe uma categoria com esse nome e tipo nesta organização."

    if parent:
        if parent.organization_id != organization.pk:
            errors["parent"] = "Selecione uma categoria da sua organização."
        elif kind and parent.kind != kind:
            errors["parent"] = "A categoria pai precisa ser do mesmo tipo (receita ou despesa)."
        else:
            seen = set()
            ancestor = parent
            while ancestor is not None:
                if ancestor.pk in seen or (
                    instance is not None and instance.pk == ancestor.pk
                ):
                    errors["parent"] = "Uma categoria não pode ser descendente dela mesma."
                    break
                if ancestor.organization_id != organization.pk:
                    errors["parent"] = "Selecione uma categoria da sua organização."
                    break
                seen.add(ancestor.pk)
                ancestor = ancestor.parent

    if instance is not None and instance.pk and kind:
        if instance.children.exclude(kind=kind).exists():
            errors["kind"] = "O tipo precisa ser compatível com as subcategorias existentes."
        if instance.transactions.exclude(kind=kind).exists():
            errors["kind"] = "O tipo precisa ser compatível com os lançamentos existentes."
        if kind != Category.Kind.EXPENSE and instance.budgets.exists():
            errors["kind"] = "Uma categoria com orçamento precisa continuar sendo de despesa."

    if errors:
        raise ValidationError(errors)


def validate_transaction(*, kind, category, instance=None):
    if instance is not None and instance.pk and instance.is_transfer:
        raise ValidationError(
            "Para corrigir uma transferência, exclua-a e registre novamente."
        )
    if kind and category and category.kind != kind:
        raise ValidationError({
            "category": "Escolha uma categoria do mesmo tipo do lançamento."
        })
