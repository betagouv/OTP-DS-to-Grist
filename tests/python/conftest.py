# tests/python/conftest.py
import os

# Configuration de test explicite
# L'URL est intentionnellement invalide pour indiquer qu'aucune vraie DB n'est utilisée
os.environ['DATABASE_URL'] = 'postgresql://invalid-url-used-only-for-mocks-tests'
os.environ['ENCRYPTION_KEY'] = 'test-encryption-key-for-tests-32bytes'