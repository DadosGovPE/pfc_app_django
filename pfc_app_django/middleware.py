class LogUsernameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user_obj = getattr(request, 'user', None)
        response.set_cookie('_tag', user_obj.username if user_obj else 'Anonymous')
        return response