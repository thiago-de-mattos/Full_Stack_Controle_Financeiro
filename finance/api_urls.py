from django.urls import path

from .api_views import (
    AccountDetail, AccountListCreate, CategoryDetail, CategoryListCreate,
    TransactionDetail, TransactionListCreate, TransferCreate,
)

app_name = "finance_api"

urlpatterns = [
    path("contas/", AccountListCreate.as_view(), name="account_list"),
    path("contas/<int:pk>/", AccountDetail.as_view(), name="account_detail"),
    path("categorias/", CategoryListCreate.as_view(), name="category_list"),
    path("categorias/<int:pk>/", CategoryDetail.as_view(), name="category_detail"),
    path("lancamentos/", TransactionListCreate.as_view(), name="transaction_list"),
    path("lancamentos/<int:pk>/", TransactionDetail.as_view(), name="transaction_detail"),
    path("transferencias/", TransferCreate.as_view(), name="transfer_create"),
]