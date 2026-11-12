class PrivateResponses:
    def __init__(self,get_response):
        self.get_response = get_response
    def __call__(self,request):
        response = self.get_response(request)
        response['Cache-Control'] = 'no-store'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'same-origin'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith('/api/search-widget/'):
            response['X-Frame-Options']='SAMEORIGIN'
            response['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; frame-ancestors 'self'; sandbox allow-popups allow-popups-to-escape-sandbox"
        return response
