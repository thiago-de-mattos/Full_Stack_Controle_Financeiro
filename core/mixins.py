from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect

from .permissions import require_financial_admin
from .utils import get_user_organization


class SafeFormSaveMixin:
    """Conflitos de gravação voltam ao formulário, sem salvar parcialmente."""

    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            form.add_error(
                None,
                "Não foi possível salvar: os dados conflitam com outro registro. "
                "Atualize a página e verifique os valores.",
            )
            return self.form_invalid(form)


class OrganizationAdminDeleteMixin:
    """Exige administrador tanto na confirmação quanto na exclusão."""

    def dispatch(self, request, *args, **kwargs):
        require_financial_admin(request.user)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Este registro possui lançamentos vinculados e não pode ser excluído. "
                "Você pode desativá-lo.",
            )
            return redirect(self.get_success_url())

class OwnerQuerysetMixin:
    """A view só enxerga objetos da organização do usuário logado.

    Deve vir ANTES da view base na lista de heranca, senao o get_queryset
    da classe base ganha e o filtro e ignorado.
    """

    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)


class OwnerFormMixin:
    """Define o usuário e a organização no servidor."""

    def form_valid(self, form):
        if not form.instance.pk:
            form.instance.user = self.request.user
            form.instance.organization = get_user_organization(self.request.user)
        return super().form_valid(form)

class UserFormKwargsMixin:
    """Passa o usuario para o form, que usa isso pra limitar as opcoes de FK."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs
