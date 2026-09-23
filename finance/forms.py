from django import forms

from core.forms import HtmlDateInput, IsoDateFieldsMixin

from .models import Account, Category, Transaction


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
        name = self.cleaned_data["name"].strip()
        qs = Account.objects.for_user(self.user).filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Você já tem uma conta com esse nome.")
        return name


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
        parent = cleaned.get("parent")
        kind = cleaned.get("kind")
        if parent and kind and parent.kind != kind:
            self.add_error(
                "parent", "A categoria pai precisa ser do mesmo tipo (receita ou despesa)."
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
        self.fields["account"].queryset = Account.objects.for_user(user).active()
        self.fields["category"].queryset = Category.objects.for_user(user).active()
        self.fields["category"].required = False

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("O valor precisa ser maior que zero.")
        return amount

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        category = cleaned.get("category")
        if kind and category and category.kind != kind:
            self.add_error(
                "category",
                f"'{category.name}' é uma categoria de "
                f"{category.get_kind_display().lower()}. Escolha uma de "
                f"{Transaction.Kind(kind).label.lower()}.",
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
