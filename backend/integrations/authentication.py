from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from businesses.access import get_business_and_role_for_user

from .models import ApiCredential
from .security import verify_api_key


class StockFlowApiKeyAuthentication(BaseAuthentication):
    keyword = "StockFlow"

    def authenticate(self, request):
        header = get_authorization_header(request).decode("utf-8").strip()
        if not header:
            return None
        parts = header.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            return None

        raw_key = parts[1].strip()
        if "." not in raw_key:
            raise AuthenticationFailed("Invalid StockFlow API key.")
        key_prefix = raw_key.split(".", 1)[0]
        credential = (
            ApiCredential.objects.select_related("business", "business__owner")
            .filter(key_prefix=key_prefix, is_active=True, revoked_at__isnull=True)
            .first()
        )
        if not credential or not verify_api_key(raw_key, credential.secret_hash):
            raise AuthenticationFailed("Invalid StockFlow API key.")

        now = timezone.now()
        if credential.expires_at and credential.expires_at <= now:
            raise AuthenticationFailed("This StockFlow API key has expired.")

        try:
            get_business_and_role_for_user(
                user=credential.business.owner,
                business_id=credential.business_id,
            )
        except Exception as exc:
            raise AuthenticationFailed(
                "This business is unavailable for public API access."
            ) from exc

        ApiCredential.objects.filter(id=credential.id).update(last_used_at=now)
        credential.last_used_at = now
        return credential.business.owner, credential

    def authenticate_header(self, request):
        return self.keyword
