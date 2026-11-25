from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError

from .utils import get_user_organization


class OrganizationAPIMixin:
    """Escopo e gravação comuns aos CRUDs financeiros."""

    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)

    def perform_create(self, serializer):
        self.save_serializer(
            serializer,
            user=self.request.user,
            organization=get_user_organization(self.request.user),
        )

    def perform_update(self, serializer):
        self.save_serializer(serializer)

    def save_serializer(self, serializer, **kwargs):
        try:
            with transaction.atomic():
                serializer.save(**kwargs)
        except DjangoValidationError as error:
            detail = getattr(error, "message_dict", {"non_field_errors": error.messages})
            raise ValidationError(detail) from error
        except IntegrityError as error:
            raise ValidationError({
                "non_field_errors": [
                    "Não foi possível salvar: os dados conflitam com outro registro. "
                    "Atualize a consulta e verifique os valores."
                ]
            }) from error

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise ValidationError({
                "detail": "Este registro possui lançamentos vinculados e não pode "
                          "ser excluído. Você pode desativá-lo."
            }) from error
