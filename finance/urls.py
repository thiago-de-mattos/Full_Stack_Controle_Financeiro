from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("contas/", views.AccountListView.as_view(), name="account_list"),
    path("contas/nova/", views.AccountCreateView.as_view(), name="account_create"),
    path("contas/<int:pk>/editar/", views.AccountUpdateView.as_view(), name="account_update"),
    path("contas/<int:pk>/excluir/", views.AccountDeleteView.as_view(), name="account_delete"),

    path("categorias/", views.CategoryListView.as_view(), name="category_list"),
    path("categorias/nova/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categorias/<int:pk>/editar/", views.CategoryUpdateView.as_view(), name="category_update"),
    path("categorias/<int:pk>/excluir/", views.CategoryDeleteView.as_view(), name="category_delete"),

    path("lancamentos/", views.TransactionListView.as_view(), name="transaction_list"),
    path("lancamentos/novo/", views.TransactionCreateView.as_view(), name="transaction_create"),
    path("lancamentos/<int:pk>/editar/", views.TransactionUpdateView.as_view(), name="transaction_update"),
    path("lancamentos/<int:pk>/excluir/", views.transaction_delete, name="transaction_delete"),

    path("transferencias/nova/", views.transfer_create, name="transfer_create"),
]
