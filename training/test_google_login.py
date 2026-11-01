import json
import threading
import unittest
import time
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from training.cloud import Settings, make_handler
from training.google_login import GoogleLogin, google_verifier

CLIENT='1234567890-noah-test.apps.googleusercontent.com'
ORIGIN='https://zenithsmart.xin'


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.now=1000000
        self.claims={}
        self.identity=GoogleLogin(CLIENT,lambda token,audience:dict(self.claims),lambda:self.now)

    def credential(self,**changes):
        _,challenge=self.identity.challenge()
        nonce=challenge['nonce']
        self.claims={'aud':CLIENT,'iss':'https://accounts.google.com','exp':self.now+100,
                     'nonce':nonce,'email_verified':True,'sub':'stable-sub',
                     'name':'Noah visitor','email':'member@example.com','role':'owner'}
        self.claims.update(changes)
        return {'credential':'header.payload.signature','nonce':nonce,'role':'owner'}

    def test_disabled_provider_cannot_mint_sessions(self):
        identity=GoogleLogin()
        self.assertEqual(identity.challenge()[0],503)
        self.assertEqual(identity.login({})[0],503)

    def test_subject_is_identity_and_role_is_always_member(self):
        status,result=self.identity.login(self.credential())
        self.assertEqual(status,200)
        self.assertEqual(result['user']['id'],'google:stable-sub')
        self.assertEqual(result['user']['role'],'member')
        self.assertEqual(self.identity.me('Bearer '+result['token'])[0],200)

    def test_replay_expired_challenge_and_wrong_nonce_are_rejected(self):
        body=self.credential()
        self.assertEqual(self.identity.login(body)[0],200)
        self.assertEqual(self.identity.login(body)[0],401)
        body=self.credential()
        self.now+=601
        self.assertEqual(self.identity.login(body)[0],401)
        body=self.credential(nonce='unrelated')
        self.assertEqual(self.identity.login(body)[0],401)

    def test_wrong_audience_issuer_expiry_and_unverified_email(self):
        for changes in ({'aud':'other'},{'iss':'https://attacker.invalid'},
                        {'exp':0},{'email_verified':False},{'sub':''}):
            with self.subTest(changes=changes):
                self.assertEqual(self.identity.login(self.credential(**changes))[0],401)

    def test_signature_failure_never_returns_a_session(self):
        body=self.credential()
        def reject(*_):raise ValueError('bad signature')
        self.identity._verify=reject
        self.assertEqual(self.identity.login(body)[0],401)
        self.assertEqual(len(self.identity._sessions),0)

    def test_google_library_checks_real_rsa_signature_audience_and_expiry(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from google.auth import crypt,jwt
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        signer=crypt.RSASigner.from_string(private,key_id='noah-test')
        claims={'iss':'https://accounts.google.com','aud':CLIENT,'sub':'signed-user','iat':int(time.time())-600,'exp':int(time.time())+60}
        class Response:
            status=200
            data=json.dumps({'noah-test':public.decode()}).encode()
        def transport(*args,**kwargs):
            self.assertEqual(kwargs.get('timeout'),10)
            return Response()
        with patch('google.auth.transport.requests.Request',return_value=transport):
            verify=google_verifier()
            token=jwt.encode(signer,claims).decode()
            self.assertEqual(verify(token,CLIENT)['sub'],'signed-user')
            with self.assertRaises(ValueError):verify(token,'another-client')
            pieces=token.split('.')
            pieces[2]=('A' if pieces[2][0]!='A' else 'B')+pieces[2][1:]
            with self.assertRaises(ValueError):verify('.'.join(pieces),CLIENT)
            claims['exp']=int(time.time())-10
            with self.assertRaises(ValueError):verify(jwt.encode(signer,claims).decode(),CLIENT)

    def test_logout_and_expiry_revoke_sessions(self):
        _,result=self.identity.login(self.credential())
        auth='Bearer '+result['token']
        self.identity.logout(auth)
        self.assertEqual(self.identity.me(auth)[0],401)
        _,result=self.identity.login(self.credential())
        self.now+=3601
        self.assertEqual(self.identity.me('Bearer '+result['token'])[0],401)

    def test_pending_challenges_have_a_memory_bound(self):
        for _ in range(512):self.assertEqual(self.identity.challenge()[0],200)
        self.assertEqual(self.identity.challenge()[0],429)
        self.now+=601
        self.assertEqual(self.identity.challenge()[0],200)

    def test_http_member_cannot_become_training_admin(self):
        settings=Settings('https://noah.example','p'*40,'j'*40,'ephemeral-test',
                          google_client_id=CLIENT,auth_origins=(ORIGIN,))
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(settings,self.identity))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        def request(path,body=None,origin=ORIGIN,token=None,method=None):
            headers={'Origin':origin}
            if body is not None:headers['Content-Type']='application/json'
            if token:headers['Authorization']='Bearer '+token
            req=Request(base+path,data=None if body is None else json.dumps(body).encode(),
                        headers=headers,method=method)
            try:response=urlopen(req,timeout=3)
            except HTTPError as error:response=error
            with response:return response.status,response.headers,response.read()
        try:
            status,headers,_=request('/api/auth/config')
            self.assertEqual(status,200)
            self.assertEqual(headers['Access-Control-Allow-Origin'],ORIGIN)
            self.assertEqual(request('/api/auth/challenge',origin='https://attacker.invalid')[0],403)
            self.assertEqual(request('/api/auth/google',{},origin='https://attacker.invalid')[0],403)
            body=self.credential()
            status,_,raw=request('/api/auth/google',body)
            self.assertEqual(status,200)
            token=json.loads(raw)['token']
            status,headers,_=request('/api/status',token=token)
            self.assertEqual(status,401)
            self.assertIn('Basic',headers['WWW-Authenticate'])
            self.assertEqual(request('/api/training',{'active':True},token=token)[0],401)
            status,headers,_=request('/api/auth/me',token='invalid-token')
            self.assertEqual(status,401)
            self.assertIsNone(headers.get('WWW-Authenticate'))
            self.assertEqual(request('/api/auth/me',token=token)[0],200)
            self.assertEqual(request('/api/auth/logout',{},token=token)[0],204)
            self.assertEqual(request('/api/auth/me',token=token)[0],401)
            self.assertEqual(request('/api/auth/google',method='OPTIONS')[0],204)
        finally:
            server.shutdown();server.server_close();thread.join(3)


if __name__=='__main__':unittest.main()
