from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.mixins import OwnerFormMixin, OwnerQuerysetMixin, UserFormKwargsMixin
from core.utils import month_from_request, month_label, shift_month

from .forms import BudgetForm
from .models import Budget


class BudgetListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Budget
    context_object_name = "orcamentos"

    def get_queryset(self):
        self.ref = month_from_request(self.request)
        return (
            super()
            .get_queryset()
            .filter(month=self.ref)
            .with_spent(self.ref)
            .select_related("category")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orcamentos = ctx["orcamentos"]
        ctx.update(
            {
                "ref": self.ref,
                "ref_label": month_label(self.ref),
                "mes_anterior": shift_month(self.ref, -1).strftime("%Y-%m"),
                "mes_seguinte": shift_month(self.ref, 1).strftime("%Y-%m"),
                "total_limite": sum((o.limit_amount for o in orcamentos), 0),
                "total_gasto": sum((o.spent_value for o in orcamentos), 0),
            }
        )
        return ctx


class BudgetCreateView(
    LoginRequiredMixin, UserFormKwargsMixin, OwnerFormMixin, CreateView
):
    model = Budget
    form_class = BudgetForm
    success_url = reverse_lazy("budget:budget_list")
    extra_context = {"titulo": "Novo orçamento", "acao": "Criar orçamento"}

    def get_initial(self):
        return {"month": month_from_request(self.request)}


class BudgetUpdateView(
    LoginRequiredMixin, OwnerQuerysetMixin, UserFormKwargsMixin, UpdateView
):
    model = Budget
    form_class = BudgetForm
    success_url = reverse_lazy("budget:budget_list")
    extra_context = {"titulo": "Editar orçamento", "acao": "Salvar alterações"}


class BudgetDeleteView(LoginRequiredMixin, OwnerQuerysetMixin, DeleteView):
    model = Budget
    success_url = reverse_lazy("budget:budget_list")
    template_name = "includes/confirm_delete.html"
    extra_context = {"titulo": "Excluir orçamento"}
