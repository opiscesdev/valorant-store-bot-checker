import requests
import re


class InvalidCredentialError(Exception): ...


class RateLimitedError(Exception): ...


class Auth:

    def __init__(self, auth, proxy):
        self.proxy = proxy
        self.username = auth['username']
        self.password = auth['password']

    def authenticate(self):
        session = requests.session()
        session.proxies = self.proxy
        data = {
            'client_id': 'play-valorant-web-prod',
            'nonce': '1',
            'redirect_uri': 'https://playvalorant.com/opt_in',
            'response_type': 'token id_token',
        }
        r = session.post('https://auth.riotgames.com/api/v1/authorization', timeout=10, json=data)

        # print(r.text)
        data = {
            'type': 'auth',
            'username': self.username,
            'password': self.password
        }
        r = session.put('https://auth.riotgames.com/api/v1/authorization', timeout=10, json=data)
        pattern = re.compile(
            'access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)')

        if r.json().get("error") == "rate_limited":
            raise RateLimitedError("rate limited")
        if r.json().get("error") == "auth_failure":
            raise InvalidCredentialError(f"invalid credential")
        try:
            data = pattern.findall(r.json()['response']['parameters']['uri'])[0]
        except KeyError:
            raise InvalidCredentialError(f"invalid credential")
        access_token = data[0]
        # print('Access Token: ' + access_token)

        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        r = session.post('https://entitlements.auth.riotgames.com/api/token/v1', headers=headers, json={}, timeout=10)
        entitlements_token = r.json()['entitlements_token']
        # print('Entitlements Token: ' + entitlements_token)

        r = session.post('https://auth.riotgames.com/userinfo', headers=headers, json={}, timeout=10)
        user_id = r.json()['sub']
        # print('User ID: ' + user_id)
        headers['X-Riot-Entitlements-JWT'] = entitlements_token
        session.close()

        headers[
            "X-Riot-ClientPlatform"] = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
        return user_id, headers, {}
