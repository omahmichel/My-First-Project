import uuid
from .capture import current_request, record_event

class PlatformEventMiddleware:
    def __init__(self, get_response): self.get_response=get_response
    def __call__(self, request):
        request._platform_event_id=str(uuid.uuid4())
        token=current_request.set(request)
        try:
            response=self.get_response(request)
            self.capture(request,response)
            return response
        finally: current_request.reset(token)

    def capture(self, request, response):
        code=response.status_code
        path=request.path
        if not (path.startswith('/api/') or path.startswith('/admin/')):
            # Known sensitive-path probes, not arbitrary input pattern matching.
            if code >= 400 and any(part in path.lower() for part in ('/.env','/.git/','/wp-admin','/wp-login.php')):
                record_event(category='security',action='request.suspected_probe',summary='Suspected sensitive-path probe',severity='warning',http_status=code,aggregate=True)
            return
        if request.method == 'OPTIONS': return
        if path.startswith('/api/platform-admin/') and request.method in ('GET','HEAD') and code < 400:
            return  # Viewing the log must never create more log entries.
        if code >= 500:
            category,action,summary,severity='system','request.failed','Application request failed','error'
        elif code == 429:
            category,action,summary,severity='security','request.throttled','Request blocked by rate limit; possible excessive activity','warning'
        elif code in (401,403):
            category,action,summary,severity='security','request.denied','Authentication or permission check rejected a request','warning'
        elif code in (400,409,422):
            category,action,summary,severity='validation','request.invalid','Request failed validation or conflicted with current state','warning'
        elif code >= 400:
            category,action,summary,severity='access','request.not_found','Requested resource was unavailable','info'
        else:
            category='authentication' if path.startswith('/api/auth/') or path.startswith('/admin/login') else 'access' if request.method in ('GET','HEAD') else 'business'
            action='request.completed'
            summary='Authentication step completed' if category=='authentication' else 'API read completed' if category=='access' else 'Application action completed'
            severity='info'
        # Auth endpoints can be anonymous until token issuance; actor only from trusted response.
        actor={}
        if code < 300 and path in ('/api/auth/login/verify/','/api/auth/register/verify/'):
            data=getattr(response,'data',{})
            user=data.get('user',{}) if isinstance(data,dict) else {}
            if isinstance(user,dict) and str(user.get('id','')).isdigit(): actor['actor_id']=str(user['id'])
        record_event(category=category,action=action,summary=summary,severity=severity,http_status=code,
                     aggregate=(code >= 400 or category=='access'),**actor)
