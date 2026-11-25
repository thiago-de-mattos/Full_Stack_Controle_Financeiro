from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers

from .models import Account, Category, Transaction
from .services import create_transfer
from .validators import (
    validate_account_name, validate_category,
    validate_positive_amount, validate_transaction,
)


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


class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )

    class Meta:
        model = Category
        fields = ["id", "name", "kind", "parent", "is_active"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["parent"].queryset = Category.objects.for_user(request.user)

    def validate(self, attrs):
        validate_category(
            name=attrs.get("name", getattr(self.instance, "name", None)),
            kind=attrs.get("kind", getattr(self.instance, "kind", None)),
            parent=attrs.get("parent", getattr(self.instance, "parent", None)),
            user=self.context["request"].user,
            instance=self.instance,
        )
        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )
    is_transfer = serializers.BooleanField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "kind", "account", "category", "amount", "date",
            "description", "notes", "is_settled", "is_transfer",
        ]
        read_only_fields = ["id", "is_transfer"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["account"].queryset = Account.objects.for_user(request.user).filter(
                Q(is_active=True) | Q(pk=getattr(self.instance, "account_id", None))
            )
            self.fields["category"].queryset = Category.objects.for_user(request.user).filter(
                Q(is_active=True) | Q(pk=getattr(self.instance, "category_id", None))
            )

    def validate_amount(self, value):
        return validate_positive_amount(value)

    def validate(self, attrs):
        validate_transaction(
            kind=attrs.get("kind", getattr(self.instance, "kind", None)),
            category=attrs.get("category", getattr(self.instance, "category", None)),
            instance=self.instance,
        )
        return attrs


class TransferSerializer(serializers.Serializer):
    from_account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    to_account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    date = serializers.DateField()
    description = serializers.CharField(max_length=140, required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            accounts = Account.objects.for_user(request.user).active()
            self.fields["from_account"].queryset = accounts
            self.fields["to_account"].queryset = accounts

    def create(self, validated_data):
        try:
            return create_transfer(user=self.context["request"].user, **validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"non_field_errors": error.messages}) from error

    def to_representation(self, instance):
        outgoing, incoming = instance
        return {
            "saida": TransactionSerializer(outgoing, context=self.context).data,
            "entrada": TransactionSerializer(incoming, context=self.context).data,
        }
