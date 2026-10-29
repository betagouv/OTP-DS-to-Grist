# tests/python/conftest.py
import os
import sys

import pytest
from sqlalchemy import make_url

from tests.python.db.runner import TEST_DATABASE_SUFFIX, TEST_DATABASE_URL_ENV

# Configuration de test explicite
# L'URL est intentionnellement invalide pour indiquer qu'aucune vraie DB n'est utilisée,
# sauf pour les tests sur base réelle (tests/python/db/) : `poe test-db` fournit
# TEST_DATABASE_URL, que l'application reçoit alors comme DATABASE_URL
_test_database_url = os.getenv(TEST_DATABASE_URL_ENV)

# Garde-fou : les tests sur base réelle suppriment les tables, ils refusent toute
# base dont le nom ne signale pas explicitement une base de test
if _test_database_url and not (make_url(_test_database_url).database or "").endswith(
    TEST_DATABASE_SUFFIX
):
    raise pytest.UsageError(
        f"{TEST_DATABASE_URL_ENV} doit cibler une base dont le nom se termine "
        f"par '{TEST_DATABASE_SUFFIX}'"
    )

os.environ['DATABASE_URL'] = (
    _test_database_url or 'postgresql://invalid-url-used-only-for-mocks-tests'
)
os.environ['ENCRYPTION_KEY'] = 'test-encryption-key-for-tests-32bytes'
os.environ['HELP_LINK_FAQ']='https://docs.numerique.gouv.fr/docs/f6181e26-8739-4671-85b4-eeaf3e828788/'
os.environ['HELP_LINK_DN_TOKEN_API']='https://docs.numerique.gouv.fr/docs/cd079f0c-c72b-4704-a59b-7aa5b2e77ff0/'
os.environ['HELP_LINK_GRIST_API_KEY']='https://docs.numerique.gouv.fr/docs/fb36b922-36c8-4c58-bc64-f08151fd5efe/'
# Domaines Grist autorisés dans les tests (voir tests/python/unit/grist/test_base_url.py)
os.environ['GRIST_BASE_URL_WHITELIST']=','.join([
    '*.grist.com',
    'grist.com',
    '*.test',
    '*.test.com',
    '*.example.com',
    '*.explicit.com',
    'grist.server.com',
    'grist.numerique.gouv.fr',
    'localhost',
    '127.0.0.1',
])


def pytest_sessionfinish(session, exitstatus):
    """
    Arrête le scheduler démarré à l'import d'app tant que pytest capture encore
    les logs : laissé à la sortie du process, son arrêt loggue dans un flux déjà fermé.
    """
    scheduled_sync = sys.modules.get("sync.scheduled_sync")
    if scheduled_sync and scheduled_sync.scheduler.running:
        scheduled_sync.scheduler.shutdown(wait=False)
