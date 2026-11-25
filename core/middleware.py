from django.utils.cache import patch_cache_control


class PrivateResponseMiddleware:
    """Não permite armazenar respostas da sessão, inclusive após sair."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        was_authenticated = request.user.is_authenticated
        response = self.get_response(request)
        if was_authenticated or request.user.is_authenticated:
            patch_cache_control(response, private=True, no_store=True)
        return response
