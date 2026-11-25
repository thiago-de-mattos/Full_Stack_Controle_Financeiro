from .permissions import can_delete_financial_data


def financial_permissions(request):
    return {
        "can_delete_financial_data": can_delete_financial_data(request.user),
    }
