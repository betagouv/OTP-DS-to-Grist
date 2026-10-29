import pytest
from sqlalchemy import inspect

from database.database_manager import DatabaseManager
from database.models import Base


@pytest.fixture
def initialized_inspector(empty_database, database_url):
    """Inspecteur sur un schéma créé par le SQL de DatabaseManager."""
    DatabaseManager.init_db(database_url)

    return inspect(empty_database)


class TestModelsMatchSchema:
    """
    Les modèles ORM décrivent le schéma créé en SQL brut par DatabaseManager :
    les deux sont maintenus à la main et peuvent diverger.
    """

    @pytest.mark.parametrize("table", Base.metadata.sorted_tables, ids=str)
    def test_same_columns(self, initialized_inspector, table):
        db_columns = {
            column["name"] for column in initialized_inspector.get_columns(table.name)
        }

        assert db_columns == set(table.columns.keys())

    @pytest.mark.parametrize("table", Base.metadata.sorted_tables, ids=str)
    def test_same_python_types(self, initialized_inspector, table):
        db_types = {
            column["name"]: column["type"].python_type
            for column in initialized_inspector.get_columns(table.name)
        }
        model_types = {
            column.name: column.type.python_type for column in table.columns
        }

        assert db_types == model_types
