from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("finance.api_urls")),
    path("api/", include("budget.api_urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("finance.urls")),
    path("", include("accounts.urls")),
    path("orcamentos/", include("budget.urls")),
]
