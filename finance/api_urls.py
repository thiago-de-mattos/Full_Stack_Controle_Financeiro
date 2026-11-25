from django.urls import path

from .api_views import AccountDetail, AccountListCreate

app_name = "finance_api"

urlpatterns = [
    path("contas/", AccountListCreate.as_view(), name="account_list"),
    path("contas/<int:pk>/", AccountDetail.as_view(), name="account_detail"),
]