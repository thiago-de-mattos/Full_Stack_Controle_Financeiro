from django.core.exceptions import ValidationError

from .models import Account


def validate_account_name(name, user, instance=None):
    name = name.strip()

    accounts = Account.objects.for_user(user).filter(name__iexact=name)

    if instance is not None and instance.pk:
        accounts = accounts.exclude(pk=instance.pk)

    if accounts.exists():
        raise ValidationError("Já existe uma conta com esse nome nesta organização.")

    return name
