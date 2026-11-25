from django import forms
from django.db.models import Q

from finance.models import Category
from finance.validators import validate_positive_amount

from .models import Budget
from .validators import normalize_month, validate_budget


class BudgetForm(forms.ModelForm):
    month = forms.DateField(
        label="Mês de referência",
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
        input_formats=["%Y-%m", "%Y-%m-%d"],
        help_text="O orçamento vale para o mês inteiro.",
    )

    class Meta:
        model = Budget
        fields = ["category", "month", "limit_amount"]
        widgets = {
            "limit_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }
        labels = {"category": "Categoria", "limit_amount": "Limite do mês"}

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Orcamento so faz sentido em categoria de despesa.
        self.fields["category"].queryset = Category.objects.for_user(user).expenses().filter(
            Q(is_active=True) | Q(pk=self.instance.category_id)
        )

    def clean_month(self):
        # Normaliza pro dia 1: e o que a UniqueConstraint espera.
        return normalize_month(self.cleaned_data["month"])

    def clean_limit_amount(self):
        return validate_positive_amount(
            self.cleaned_data["limit_amount"], "O limite precisa ser maior que zero."
        )

    def clean(self):
        cleaned = super().clean()
        validate_budget(
            category=cleaned.get("category"), month=cleaned.get("month"),
            user=self.user, instance=self.instance,
        )
        return cleaned
