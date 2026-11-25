from django import forms
from django.db.models import Q

from core.forms import HtmlDateInput, IsoDateFieldsMixin

from .models import Account, Category, Transaction
from .validators import (
    validate_account_name, validate_category,
    validate_positive_amount, validate_transaction,
)

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["name", "kind", "initial_balance", "is_active"]
        labels = {
            "name": "Nome da conta",
            "kind": "Tipo",
            "initial_balance": "Saldo inicial",
            "is_active": "Conta ativa",
        }
        help_texts = {
            "initial_balance": "Quanto já tinha nessa conta antes de começar a usar o app.",
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        return validate_account_name(
            name=self.cleaned_data["name"],
            user=self.user,
            instance=self.instance,
        )

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "kind", "parent", "is_active"]
        labels = {
            "name": "Nome",
            "kind": "Tipo",
            "parent": "Subcategoria de",
            "is_active": "Categoria ativa",
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        qs = Category.objects.for_user(user)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = qs
        self.fields["parent"].required = False

    def clean(self):
        cleaned = super().clean()
        validate_category(
            name=cleaned.get("name"), kind=cleaned.get("kind"),
            parent=cleaned.get("parent"), user=self.user, instance=self.instance,
        )
        return cleaned


class TransactionForm(IsoDateFieldsMixin, forms.ModelForm):
    iso_date_fields = ("date",)

    class Meta:
        model = Transaction
        fields = [
            "kind",
            "account",
            "category",
            "amount",
            "date",
            "description",
            "is_settled",
            "notes",
        ]
        widgets = {
            "date": HtmlDateInput(),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "description": forms.TextInput(attrs={"placeholder": "Ex: mercado da esquina"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "kind": "Tipo",
            "account": "Conta",
            "category": "Categoria",
            "amount": "Valor",
            "date": "Data",
            "description": "Descrição",
            "notes": "Observações",
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Sem isso, da pra mandar no POST o id da conta de outra pessoa.
        self.fields["account"].queryset = Account.objects.for_user(user).filter(
            Q(is_active=True) | Q(pk=self.instance.account_id)
        )
        self.fields["category"].queryset = Category.objects.for_user(user).filter(
            Q(is_active=True) | Q(pk=self.instance.category_id)
        )
        self.fields["category"].required = False

    def clean_amount(self):
        return validate_positive_amount(self.cleaned_data["amount"])

    def clean(self):
        cleaned = super().clean()
        validate_transaction(
            kind=cleaned.get("kind"), category=cleaned.get("category"),
            instance=self.instance,
        )
        return cleaned


class TransferForm(IsoDateFieldsMixin, forms.Form):
    iso_date_fields = ("date",)

    from_account = forms.ModelChoiceField(queryset=Account.objects.none(), label="Sai de")
    to_account = forms.ModelChoiceField(queryset=Account.objects.none(), label="Entra em")
    amount = forms.DecimalField(
        label="Valor",
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
    )
    date = forms.DateField(label="Data", widget=HtmlDateInput())
    description = forms.CharField(
        label="Descrição",
        max_length=140,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Opcional"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        contas = Account.objects.for_user(user).active()
        self.fields["from_account"].queryset = contas
        self.fields["to_account"].queryset = contas

    def clean(self):
        cleaned = super().clean()
        origem = cleaned.get("from_account")
        destino = cleaned.get("to_account")
        if origem and destino and origem == destino:
            self.add_error("to_account", "Escolha uma conta diferente da de origem.")
        return cleaned
