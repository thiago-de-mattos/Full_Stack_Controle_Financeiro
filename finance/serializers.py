from rest_framework import serializers

from .models import Account


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
        