import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from database.database_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):

    @patch('database.database_manager.psycopg2.connect')
    def test_get_connection_success(self, mock_connect):
        """Test connexion réussie à la base de données"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = DatabaseManager.get_connection('test_url')

        self.assertEqual(result, mock_conn)
        mock_connect.assert_called_once_with('test_url')

    @patch('database.database_manager.psycopg2.connect')
    def test_get_connection_failure(self, mock_connect):
        """Test échec de connexion à la base de données"""
        mock_connect.side_effect = Exception('Connection failed')

        result = DatabaseManager.get_connection('test_url')

        self.assertIsNone(result)

    @patch('database.database_manager.DatabaseManager.get_connection')
    def test_init_db_success(self, mock_get_conn):
        """Test initialisation réussie de la base de données"""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        with patch('database.database_manager.DatabaseManager.create_table_if_not_exists') as mock_create:
            DatabaseManager.init_db('test_url')

            mock_get_conn.assert_called_once_with('test_url')
            mock_create.assert_called_once_with(mock_conn)
            mock_conn.close.assert_called_once()

    @patch('database.database_manager.DatabaseManager.get_connection')
    def test_init_db_connection_failure(self, mock_get_conn):
        """Test initialisation avec échec de connexion"""
        mock_get_conn.return_value = None

        DatabaseManager.init_db('test_url')

        mock_get_conn.assert_called_once_with('test_url')

    @patch('database.database_manager.DatabaseManager.get_connection')
    @patch('database.database_manager.DatabaseManager.create_table_if_not_exists')
    def test_init_db_exception_handling(self, mock_create, mock_get_conn):
        """Test gestion des exceptions lors de l'initialisation"""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_create.side_effect = Exception('Create failed')

        # L'exception est propagée, mais la connexion est fermée
        with self.assertRaises(Exception):
            DatabaseManager.init_db('test_url')

        mock_conn.close.assert_called_once()

    def test_create_table_if_not_exists(self):
        """Test création des tables"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the fetchone for id column check
        mock_cursor.fetchone.return_value = [1]  # Column exists

        # Mock count for empty table check
        mock_cursor.fetchone.side_effect = [[1], [0]]  # First for id, second for count

        DatabaseManager.create_table_if_not_exists(mock_conn)

        # Vérifier que execute a été appelé plusieurs fois
        self.assertGreater(mock_cursor.execute.call_count, 5)
        mock_conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()