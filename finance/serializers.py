from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Account
from .validators import validate_account_name


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "kind",
            "initial_balance",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_name(self, value):
        try:
            return validate_account_name(
                name=value,
                user=self.context["request"].user,
                instance=self.instance,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error