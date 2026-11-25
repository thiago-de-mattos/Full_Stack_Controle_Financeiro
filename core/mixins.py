from .utils import get_user_organization

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
