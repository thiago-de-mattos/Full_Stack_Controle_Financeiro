from django.urls import path

from .api_views import BudgetDetail, BudgetListCreate

app_name = "budget_api"

urlpatterns = [
    path("orcamentos/", BudgetListCreate.as_view(), name="budget_list"),
    path("orcamentos/<int:pk>/", BudgetDetail.as_view(), name="budget_detail"),
]
