from django.db.models import Q
from rest_framework import serializers

from finance.models import Category
from finance.validators import validate_positive_amount
from .models import Budget
from .validators import normalize_month, validate_budget


class BudgetSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    month = serializers.DateField(input_formats=["%Y-%m", "%Y-%m-%d"])

    class Meta:
        model = Budget
        fields = ["id", "category", "month", "limit_amount"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["category"].queryset = (
                Category.objects.for_user(request.user).expenses()
                .filter(Q(is_active=True) | Q(pk=getattr(self.instance, "category_id", None)))
            )

    def validate_month(self, value):
        return normalize_month(value)

    def validate_limit_amount(self, value):
        return validate_positive_amount(value, "O limite precisa ser maior que zero.")

    def validate(self, attrs):
        validate_budget(
            category=attrs.get("category", getattr(self.instance, "category", None)),
            month=attrs.get("month", getattr(self.instance, "month", None)),
            user=self.context["request"].user,
            instance=self.instance,
        )
        return attrs
