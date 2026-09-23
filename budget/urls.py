from django.urls import path

from . import views

app_name = "budget"

urlpatterns = [
    path("", views.BudgetListView.as_view(), name="budget_list"),
    path("novo/", views.BudgetCreateView.as_view(), name="budget_create"),
    path("<int:pk>/editar/", views.BudgetUpdateView.as_view(), name="budget_update"),
    path("<int:pk>/excluir/", views.BudgetDeleteView.as_view(), name="budget_delete"),
]
