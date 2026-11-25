from django.core.exceptions import ValidationError

from finance.models import Category
from .models import Budget


def normalize_month(value):
    return value.replace(day=1)


def validate_budget(*, category, month, user, instance=None):
    if category and category.kind != Category.Kind.EXPENSE:
        raise ValidationError({"category": "Selecione uma categoria de despesa."})

    if category and month:
        duplicates = Budget.objects.for_user(user).filter(category=category, month=month)
        if instance is not None and instance.pk:
            duplicates = duplicates.exclude(pk=instance.pk)
        if duplicates.exists():
            raise ValidationError({
                "category": "Já existe um orçamento dessa categoria nesse mês."
            })
