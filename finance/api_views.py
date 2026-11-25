from rest_framework import generics

from core.api import OrganizationAPIMixin
from .models import Account, Category, Transaction
from .serializers import (
    AccountSerializer, CategorySerializer, TransactionSerializer, TransferSerializer,
)
from .services import delete_transaction


class AccountListCreate(OrganizationAPIMixin, generics.ListCreateAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class AccountDetail(OrganizationAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class CategoryListCreate(OrganizationAPIMixin, generics.ListCreateAPIView):
    queryset = Category.objects.select_related("parent")
    serializer_class = CategorySerializer


class CategoryDetail(OrganizationAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.select_related("parent")
    serializer_class = CategorySerializer


class TransactionListCreate(OrganizationAPIMixin, generics.ListCreateAPIView):
    queryset = Transaction.objects.select_related("account", "category")
    serializer_class = TransactionSerializer


class TransactionDetail(OrganizationAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Transaction.objects.select_related("account", "category")
    serializer_class = TransactionSerializer

    def perform_destroy(self, instance):
        delete_transaction(instance, user=self.request.user)


class TransferCreate(OrganizationAPIMixin, generics.CreateAPIView):
    serializer_class = TransferSerializer

    def perform_create(self, serializer):
        self.save_serializer(serializer)
