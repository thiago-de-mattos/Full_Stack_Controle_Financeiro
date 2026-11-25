from rest_framework.permissions import BasePermission, SAFE_METHODS

from core.permissions import can_delete_financial_data, get_financial_profile


class FinancialRecordPermission(BasePermission):
    """Operador consulta, cadastra e edita. Administrador também exclui."""

    message = "Somente administradores da organização podem excluir registros."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        get_financial_profile(request.user)
        if request.method in SAFE_METHODS or request.method in ("POST", "PUT", "PATCH"):
            return True
        if request.method == "DELETE":
            return can_delete_financial_data(request.user)
        return False
