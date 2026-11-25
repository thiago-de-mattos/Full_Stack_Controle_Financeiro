from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

from accounts.models import Profile


def get_financial_profile(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Faça login para continuar.")

    try:
        profile = user.profile
    except ObjectDoesNotExist:
        raise PermissionDenied(
            "Seu usuário não está vinculado a uma organização."
        ) from None

    if profile.role not in Profile.Role.values:
        raise PermissionDenied("Seu perfil não possui um papel válido.")

    return profile


def can_delete_financial_data(user):
    try:
        profile = get_financial_profile(user)
    except PermissionDenied:
        return False
    return profile.role == Profile.Role.ADMIN


def require_financial_admin(user):
    if not can_delete_financial_data(user):
        raise PermissionDenied(
            "Somente administradores da organização podem excluir registros."
        )
