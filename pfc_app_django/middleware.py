class LogUsernameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response['X-User'] = "Auth"
        else:
            response['X-User'] = "Nao auth"
        return response