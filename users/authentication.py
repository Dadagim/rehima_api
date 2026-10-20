import jwt
from django.conf import settings
from jwt.exceptions import PyJWKClientError
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .clerk import ClerkConfigurationError, sync_clerk_user


def verify_clerk_token(token):
    missing_settings = [
        name for name, value in (
            ('CLERK_ISSUER', settings.CLERK_ISSUER),
            ('CLERK_JWKS_URL', settings.CLERK_JWKS_URL),
            ('CLERK_AUTHORIZED_PARTIES', settings.CLERK_AUTHORIZED_PARTIES),
        )
        if not value
    ]
    if missing_settings:
        raise ClerkConfigurationError(
            f"Configure {', '.join(missing_settings)} in config/.env "
            'before using Clerk-authenticated API routes.'
        )

    try:
        signing_key = jwt.PyJWKClient(
            settings.CLERK_JWKS_URL,
            cache_keys=True,
            timeout=5,
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            issuer=settings.CLERK_ISSUER,
            options={'require': ['exp', 'iat', 'sub']},
            leeway=5,
        )
    except (jwt.InvalidTokenError, PyJWKClientError) as exc:
        raise AuthenticationFailed('The Clerk session token is invalid or expired.') from exc

    authorized_parties = settings.CLERK_AUTHORIZED_PARTIES
    if authorized_parties and claims.get('azp') not in authorized_parties:
        raise AuthenticationFailed('This application is not an authorized Clerk session origin.')
    if not isinstance(claims.get('sub'), str) or not claims['sub']:
        raise AuthenticationFailed('The Clerk session token has no user identity.')
    return claims


class ClerkAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if parts[0].lower() != b'bearer':
            return None
        if len(parts) != 2:
            raise AuthenticationFailed('Invalid Authorization header.')

        claims = verify_clerk_token(parts[1].decode('utf-8'))
        user = sync_clerk_user(claims['sub'])
        return user, claims

    def authenticate_header(self, request):
        return 'Bearer'
