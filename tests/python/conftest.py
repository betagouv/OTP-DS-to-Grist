# tests/python/conftest.py
import os

# Configuration de test explicite
# L'URL est intentionnellement invalide pour indiquer qu'aucune vraie DB n'est utilisée
os.environ['DATABASE_URL'] = 'postgresql://invalid-url-used-only-for-mocks-tests'
os.environ['ENCRYPTION_KEY'] = 'test-encryption-key-for-tests-32bytes'
os.environ['HELP_LINK_FAQ']='https://docs.numerique.gouv.fr/docs/f6181e26-8739-4671-85b4-eeaf3e828788/'
os.environ['HELP_LINK_DN_TOKEN_API']='https://docs.numerique.gouv.fr/docs/cd079f0c-c72b-4704-a59b-7aa5b2e77ff0/'
os.environ['HELP_LINK_GRIST_API_KEY']='https://docs.numerique.gouv.fr/docs/fb36b922-36c8-4c58-bc64-f08151fd5efe/'
