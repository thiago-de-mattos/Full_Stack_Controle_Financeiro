from django import forms

from finance.models import Category

from .models import Budget


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
        self.fields["category"].queryset = Category.objects.for_user(user).active().expenses()

    def clean_month(self):
        # Normaliza pro dia 1: e o que a UniqueConstraint espera.
        return self.cleaned_data["month"].replace(day=1)

    def clean_limit_amount(self):
        valor = self.cleaned_data["limit_amount"]
        if valor <= 0:
            raise forms.ValidationError("O limite precisa ser maior que zero.")
        return valor

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        month = cleaned.get("month")
        if category and month:
            qs = Budget.objects.for_user(self.user).filter(
                category=category, month=month
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "category", "Já existe um orçamento dessa categoria nesse mês."
                )
        return cleaned
