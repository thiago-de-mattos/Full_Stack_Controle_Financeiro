from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from core.mixins import OwnerFormMixin, OwnerQuerysetMixin, UserFormKwargsMixin
from core.utils import month_from_request, month_label, shift_month
from .forms import AccountForm, CategoryForm, TransactionForm, TransferForm
from .models import Account, Category, Transaction
from .services import create_transfer, delete_transaction, month_summary


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, "finance/landing.html")

    ref = month_from_request(request)
    contas = Account.objects.for_user(request.user).active().with_balance()
    resumo = month_summary(request.user, ref)

    from budget.models import Budget

    orcamentos = (
        Budget.objects.for_user(request.user)
        .filter(month=ref)
        .with_spent(ref)
        .select_related("category")
    )

    ultimos = (
        Transaction.objects.for_user(request.user)
        .select_related("account", "category")[:8]
    )

    return render(
        request,
        "finance/dashboard.html",
        {
            "contas": contas,
            "saldo_total": sum((c.balance for c in contas), 0),
            "resumo": resumo,
            "orcamentos": orcamentos,
            "ultimos": ultimos,
            "ref": ref,
            "ref_label": month_label(ref),
            "mes_anterior": shift_month(ref, -1).strftime("%Y-%m"),
            "mes_seguinte": shift_month(ref, 1).strftime("%Y-%m"),
        },
    )

# contas
class AccountListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Account
    context_object_name = "contas"

    def get_queryset(self):
        return super().get_queryset().with_balance()


class AccountCreateView(
    LoginRequiredMixin, UserFormKwargsMixin, OwnerFormMixin, CreateView
):
    model = Account
    form_class = AccountForm
    success_url = reverse_lazy("finance:account_list")
    extra_context = {"titulo": "Nova conta", "acao": "Criar conta",
                     "cancelar_url": reverse_lazy("finance:account_list")}

    def form_valid(self, form):
        messages.success(self.request, "Conta criada.")
        return super().form_valid(form)


class AccountUpdateView(
    LoginRequiredMixin, OwnerQuerysetMixin, UserFormKwargsMixin, UpdateView
):
    model = Account
    form_class = AccountForm
    success_url = reverse_lazy("finance:account_list")
    extra_context = {"titulo": "Editar conta", "acao": "Salvar alterações",
                     "cancelar_url": reverse_lazy("finance:account_list")}


class AccountDeleteView(LoginRequiredMixin, OwnerQuerysetMixin, DeleteView):
    model = Account
    success_url = reverse_lazy("finance:account_list")
    extra_context = {
        "titulo": "Excluir conta",
        "cancelar_url": reverse_lazy("finance:account_list"),
    }


# Categorias
class CategoryListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Category
    context_object_name = "categorias"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        categorias = ctx["categorias"]
        ctx["grupos"] = [
            ("Despesas", [c for c in categorias if c.kind == Category.Kind.EXPENSE]),
            ("Receitas", [c for c in categorias if c.kind == Category.Kind.INCOME]),
        ]
        return ctx


class CategoryCreateView(
    LoginRequiredMixin, UserFormKwargsMixin, OwnerFormMixin, CreateView
):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy("finance:category_list")
    extra_context = {"titulo": "Nova categoria", "acao": "Criar categoria",
                     "cancelar_url": reverse_lazy("finance:category_list")}


class CategoryUpdateView(
    LoginRequiredMixin, OwnerQuerysetMixin, UserFormKwargsMixin, UpdateView
):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy("finance:category_list")
    extra_context = {"titulo": "Editar categoria", "acao": "Salvar alterações",
                     "cancelar_url": reverse_lazy("finance:category_list")}


class CategoryDeleteView(LoginRequiredMixin, OwnerQuerysetMixin, DeleteView):
    model = Category
    success_url = reverse_lazy("finance:category_list")
    extra_context = {
        "titulo": "Excluir categoria",
        "cancelar_url": reverse_lazy("finance:category_list"),
    }


# Lançamentos

class TransactionListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Transaction
    context_object_name = "lancamentos"
    paginate_by = 30

    def get_queryset(self):
        self.ref = month_from_request(self.request)
        qs = super().get_queryset().in_month(self.ref)
        kind = self.request.GET.get("tipo")
        if kind in dict(Transaction.Kind.choices):
            qs = qs.filter(kind=kind)
        conta = self.request.GET.get("conta")
        if conta and conta.isdigit():
            qs = qs.filter(account_id=int(conta))
        return qs.select_related("account", "category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = Transaction.objects.for_user(self.request.user).in_month(self.ref)
        base = base.settled().without_transfers()
        ctx.update(
            {
                "ref": self.ref,
                "ref_label": month_label(self.ref),
                "mes_anterior": shift_month(self.ref, -1).strftime("%Y-%m"),
                "mes_seguinte": shift_month(self.ref, 1).strftime("%Y-%m"),
                "total_receitas": base.income().total(),
                "total_despesas": base.expenses().total(),
                "contas": Account.objects.for_user(self.request.user).active(),
                "tipo_ativo": self.request.GET.get("tipo", ""),
                "conta_ativa": self.request.GET.get("conta", ""),
            }
        )
        return ctx


class TransactionCreateView(
    LoginRequiredMixin, UserFormKwargsMixin, OwnerFormMixin, CreateView
):
    model = Transaction
    form_class = TransactionForm
    success_url = reverse_lazy("finance:transaction_list")
    extra_context = {"titulo": "Novo lançamento", "acao": "Salvar lançamento",
                     "cancelar_url": reverse_lazy("finance:transaction_list")}

    def get_initial(self):
        from django.utils import timezone

        return {"date": timezone.localdate(), "kind": Transaction.Kind.EXPENSE}


class TransactionUpdateView(
    LoginRequiredMixin, OwnerQuerysetMixin, UserFormKwargsMixin, UpdateView
):
    model = Transaction
    form_class = TransactionForm
    success_url = reverse_lazy("finance:transaction_list")
    extra_context = {"titulo": "Editar lançamento", "acao": "Salvar alterações",
                     "cancelar_url": reverse_lazy("finance:transaction_list")}


@login_required
def transaction_delete(request, pk):
    lancamento = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        delete_transaction(lancamento)
        messages.success(request, "Lançamento excluído.")
        return redirect("finance:transaction_list")
    return render(
        request,
        "finance/transaction_confirm_delete.html",
        {
            "object": lancamento,
            "titulo": "Excluir lançamento",
            "cancelar_url": reverse_lazy("finance:transaction_list"),
        },
    )


@login_required
def transfer_create(request):
    form = TransferForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        create_transfer(
            user=request.user,
            from_account=form.cleaned_data["from_account"],
            to_account=form.cleaned_data["to_account"],
            amount=form.cleaned_data["amount"],
            date=form.cleaned_data["date"],
            description=form.cleaned_data["description"],
        )
        messages.success(request, "Transferência registrada.")
        return redirect("finance:transaction_list")

    return render(
        request,
        "finance/transfer_form.html",
        {
            "form": form,
            "titulo": "Nova transferência",
            "acao": "Transferir",
            "cancelar_url": reverse_lazy("finance:transaction_list"),
        },
    )
