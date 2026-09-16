from django.contrib import admin
from .models import Conta, Categoria, Lancamento

@admin.register(Conta)
class ContaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'usuario', 'tipo', 'saldo_inicial')
    search_fields = ('nome', 'usuario__username')

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'usuario')
    list_filter = ('tipo',)

@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'valor', 'tipo', 'conta', 'categoria', 'data', 'pago')
    list_filter = ('tipo', 'pago', 'data', 'conta')
    search_fields = ('descricao',)