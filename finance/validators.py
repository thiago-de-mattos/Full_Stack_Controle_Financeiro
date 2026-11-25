from django.core.exceptions import ValidationError

from ..accounts.models import Account


def validate_account_name(name, user, instance=None):
    name = name.strip()

    accounts = Account.objects.for_user(user).filter(name__iexact=name)

    if instance is not None and instance.pk:
        accounts = accounts.exclude(pk=instance.pk)

    if accounts.exists():
        raise ValidationError("Você já tem uma conta com esse nome.")

    return name