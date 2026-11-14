"""Authenticate an existing synthetic account without putting secrets in argv."""
import getpass

import httpx

from app.core.config import Settings


def main():
    settings = Settings()
    url = settings.supabase_url
    email = input('Synthetic account email: ')
    password = getpass.getpass('Password: ')
    with httpx.Client(trust_env=False, timeout=15, follow_redirects=False) as client:
        response = client.post(url + '/auth/v1/token?grant_type=password',
                               headers={'apikey': settings.supabase_publishable_key.get_secret_value()},
                               json={'email': email, 'password': password})
    if response.status_code != 200:
        raise SystemExit('Supabase sign-in failed; no credentials were printed')
    # Private, ignored file. Never emit access or refresh tokens to terminal/logs.
    path = '.env.auth-test'
    with open(path, 'w', encoding='utf-8') as output:
        output.write('SHIELDRAG_ACCESS_TOKEN=' + response.json()['access_token'] + '\n')
    print(f'Access token saved to {path}; keep private and delete after testing.')


if __name__ == '__main__':
    main()
