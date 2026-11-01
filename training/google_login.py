"""Google identity for public members; never authorizes training administration."""
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque

AUTH_PATHS = {
    '/api/auth/config', '/api/auth/challenge', '/api/auth/google',
    '/api/auth/me', '/api/auth/logout',
}
PUBLIC_ORIGINS = (
    'https://zenithsmart.xin',
    'https://noah-ai-web.xiao85651.workers.dev',
    'https://noah-ai.xiao85651.workers.dev',
)
CLIENT_ID = re.compile(r'^[0-9]{6,30}-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$')
JWT = re.compile(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$')


class GoogleUnavailable(Exception):
    pass


def google_verifier():
    # Use Google's signature/audience/issuer/expiry verifier, with cached public certs.
    import requests
    from cachecontrol import CacheControl
    from google.auth.transport.requests import Request
    from google.auth.exceptions import GoogleAuthError, TransportError
    from google.oauth2 import id_token
    session = CacheControl(requests.Session())
    session.headers['User-Agent'] = 'Noah-Identity-Verification/0.5'
    transport = Request(session=session)

    def certificates(*args, **kwargs):
        kwargs['timeout'] = 10
        return transport(*args, **kwargs)

    def verify(credential, audience):
        try:
            return id_token.verify_oauth2_token(credential, certificates, audience)
        except (TransportError, requests.RequestException) as error:
            raise GoogleUnavailable() from error
        except GoogleAuthError:
            raise ValueError('Invalid Google identity') from None
    return verify


class GoogleLogin:
    """Bounded in-memory member sessions, suitable for the current ephemeral pilot."""
    def __init__(self, client_id='', verifier=None, clock=time.time):
        if client_id and not CLIENT_ID.fullmatch(client_id):
            raise ValueError('Invalid NOAH_GOOGLE_CLIENT_ID')
        self.client_id = client_id
        self._verify = verifier
        self._clock = clock
        self._lock = threading.Lock()
        self._nonces = {}
        self._sessions = {}
        self._attempts = deque()

    @property
    def enabled(self):
        return bool(self.client_id)

    def _prune(self, now):
        self._nonces = {n: expiry for n, expiry in self._nonces.items() if expiry > now}
        self._sessions = {key: value for key, value in self._sessions.items() if value[0] > now}
        while self._attempts and self._attempts[0] <= now - 60:
            self._attempts.popleft()

    def challenge(self):
        if not self.enabled:
            return 503, {'error': 'google_unavailable'}
        with self._lock:
            self._prune(self._clock())
            if len(self._nonces) >= 512:
                return 429, {'error': 'try_later'}
            nonce = secrets.token_urlsafe(32)
            self._nonces[nonce] = self._clock() + 600
        return 200, {'nonce': nonce, 'expiresIn': 600}

    def login(self, body):
        if not self.enabled:
            return 503, {'error': 'google_unavailable'}
        credential, nonce = body.get('credential'), body.get('nonce')
        if (not isinstance(credential, str) or len(credential) > 16000
                or not JWT.fullmatch(credential) or not isinstance(nonce, str)):
            return 400, {'error': 'invalid_login'}
        with self._lock:
            now = self._clock()
            self._prune(now)
            if len(self._attempts) >= 120:
                return 429, {'error': 'try_later'}
            self._attempts.append(now)
            # Consume before verification so concurrent requests cannot replay it.
            if self._nonces.pop(nonce, 0) <= now:
                return 401, {'error': 'login_expired'}
        try:
            if self._verify is None:
                self._verify = google_verifier()
            claims = self._verify(credential, self.client_id)
            if (claims.get('aud') != self.client_id
                    or claims.get('iss') not in {'accounts.google.com', 'https://accounts.google.com'}
                    or float(claims.get('exp', 0)) <= self._clock()
                    or not isinstance(claims.get('nonce'), str)
                    or not hmac.compare_digest(claims['nonce'], nonce)
                    or claims.get('email_verified') is not True
                    or not isinstance(claims.get('sub'), str)
                    or not 1 <= len(claims['sub']) <= 255):
                return 401, {'error': 'invalid_login'}
        except GoogleUnavailable:
            return 503, {'error': 'google_unavailable'}
        except (ValueError, TypeError, KeyError):
            return 401, {'error': 'invalid_login'}
        user = {
            'id': 'google:' + claims['sub'],
            'name': str(claims.get('name') or 'Noah explorer')[:120],
            'email': str(claims.get('email', ''))[:320],
            'role': 'member',
        }
        token = secrets.token_urlsafe(32)
        with self._lock:
            if len(self._sessions) >= 2048:
                del self._sessions[next(iter(self._sessions))]
            self._sessions[self._digest(token)] = (self._clock() + 3600, user)
        return 200, {'token': token, 'expiresIn': 3600, 'user': user}

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def bearer(header):
        if not isinstance(header, str) or not header.startswith('Bearer '):
            return ''
        token = header[7:]
        return token if 20 <= len(token) <= 200 else ''

    def me(self, header):
        token = self.bearer(header)
        with self._lock:
            self._prune(self._clock())
            session = self._sessions.get(self._digest(token)) if token else None
        return (200, {'user': session[1]}) if session else (401, {'error': 'login_required'})

    def logout(self, header):
        token = self.bearer(header)
        if token:
            with self._lock:
                self._sessions.pop(self._digest(token), None)

