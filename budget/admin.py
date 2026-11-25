from django.contrib import admin

from core.admin_mixins import ReadOnlyFinancialAdminMixin

from .models import Budget


@admin.register(Budget)
class BudgetAdmin(ReadOnlyFinancialAdminMixin, admin.ModelAdmin):
    list_display = ["category", "user", "month", "limit_amount"]
    list_filter = ["month"]
    search_fields = ["category__name", "user__email"]
    autocomplete_fields = ["category"]
