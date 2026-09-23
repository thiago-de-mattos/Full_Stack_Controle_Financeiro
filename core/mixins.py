class OwnerQuerysetMixin:
    """A view so enxerga objetos do usuario logado.

    Deve vir ANTES da view base na lista de heranca, senao o get_queryset
    da classe base ganha e o filtro e ignorado.
    """

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class OwnerFormMixin:
    """Preenche o dono do objeto no save, sem confiar no que veio do POST."""

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class UserFormKwargsMixin:
    """Passa o usuario para o form, que usa isso pra limitar as opcoes de FK."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs
