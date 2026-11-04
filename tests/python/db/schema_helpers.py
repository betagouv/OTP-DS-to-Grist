"""
Outils partagés par les tests de schéma : comparaison de la base avec les
modèles ORM.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine
from sqlalchemy.sql import ClauseElement

from database.models import Base

def assert_database_matches_models(engine: Engine) -> None:
    """
    Les modèles ORM décrivent fidèlement la base : la différence calculée par
    l'autogénération d'Alembic (colonnes, types, nullabilité, valeurs par
    défaut, index, contraintes, clés étrangères) est vide.
    """
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_server_default": True}
        )
        differences = compare_metadata(context, Base.metadata)

    assert differences == [], "Écarts entre la base et les modèles :\n" + "\n".join(
        _describe_difference(difference) for difference in differences
    )


# --- Fonctions privées ---


def _describe_difference(difference: tuple | list) -> str:
    """
    Une ligne lisible par écart détecté par Alembic. Les modifications d'une
    même colonne arrivent groupées en liste ; les autres écarts sont un tuple
    (opération, …, objet concerné).
    """
    if isinstance(difference, list):
        return "\n".join(_describe_difference(change) for change in difference)

    operation = difference[0]

    if operation.startswith("modify_"):
        _, _, table, column, _, database_value, model_value = difference
        return (
            f"- {operation} {table}.{column} : "
            f"base={_describe_value(database_value)}, "
            f"modèle={_describe_value(model_value)}"
        )

    return f"- {operation} {difference[-1]!r}"


def _describe_value(value: object) -> str:
    """Valeur par défaut (DefaultClause) rendue en SQL, sinon telle quelle."""
    argument = getattr(value, "arg", value)

    if isinstance(argument, ClauseElement):
        return str(argument)

    return repr(argument)
