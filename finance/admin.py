from django.contrib import admin

from core.admin_mixins import ReadOnlyFinancialAdminMixin

from .models import Account, Category, Transaction


@admin.register(Account)
class AccountAdmin(ReadOnlyFinancialAdminMixin, admin.ModelAdmin):
    list_display = ["name", "user", "kind", "initial_balance", "is_active"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "user__email"]


@admin.register(Category)
class CategoryAdmin(ReadOnlyFinancialAdminMixin, admin.ModelAdmin):
    list_display = ["name", "user", "kind", "parent", "is_active"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "user__email"]


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyFinancialAdminMixin, admin.ModelAdmin):
    list_display = ["date", "description", "kind", "amount", "account", "category", "is_settled"]
    list_filter = ["kind", "is_settled", "date", "account"]
    search_fields = ["description", "notes", "user__email"]
    date_hierarchy = "date"
    autocomplete_fields = ["account", "category"]
