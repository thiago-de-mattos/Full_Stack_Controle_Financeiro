from django.db.models.deletion import ProtectedError
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import Account
from .serializers import AccountSerializer


class AccountListCreate(generics.ListCreateAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        return Account.objects.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AccountDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        return Account.objects.for_user(self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": (
                        "Esta conta possui lançamentos e não pode ser excluída. "
                        "Você pode desativá-la."
                    )
                }
            )