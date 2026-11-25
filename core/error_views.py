from django.shortcuts import render
from django.views.decorators.cache import never_cache


@never_cache
def csrf_failure(request, reason=""):
    # O middleware do Django registra o motivo técnico no log do servidor.
    return render(request, "errors/csrf.html", status=403)
