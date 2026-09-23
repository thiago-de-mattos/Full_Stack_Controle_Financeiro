from django.contrib import admin

from .models import Budget


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["category", "user", "month", "limit_amount"]
    list_filter = ["month"]
    search_fields = ["category__name", "user__email"]
    autocomplete_fields = ["category"]
