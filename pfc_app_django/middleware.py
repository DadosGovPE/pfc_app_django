class LogUsernameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response['x-user'] = "Auth"
        else:
            response['u-user'] = "Nao auth"
        return response