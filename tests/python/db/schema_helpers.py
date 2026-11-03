"""
Outils partagés par les tests de schéma : base historique de référence et
comparaison de la base avec les modèles ORM.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlalchemy.sql import ClauseElement

from database.models import Base

# Schéma tel que le créait la première version de DatabaseManager (commit
# a4229ea) : état de départ des bases déployées avant les migrations suivantes
LEGACY_SCHEMA = """
    CREATE TABLE otp_configurations (
        id SERIAL PRIMARY KEY,
        ds_api_token TEXT,
        demarche_number TEXT,
        grist_base_url TEXT,
        grist_api_key TEXT,
        grist_doc_id TEXT,
        grist_user_id TEXT DEFAULT ''
    );
    CREATE TABLE user_schedules (
        id SERIAL PRIMARY KEY,
        otp_config_id INTEGER,
        frequency TEXT DEFAULT 'daily',
        enabled BOOLEAN DEFAULT FALSE,
        last_run TIMESTAMP,
        next_run TIMESTAMP,
        last_status TEXT,
        FOREIGN KEY (otp_config_id) REFERENCES otp_configurations(id) ON DELETE SET NULL
    );
    CREATE TABLE sync_logs (
        id SERIAL PRIMARY KEY,
        grist_user_id TEXT,
        grist_doc_id TEXT,
        status TEXT,
        message TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

LEGACY_DATA = """
    INSERT INTO otp_configurations
        (id, demarche_number, grist_doc_id, grist_user_id)
        VALUES (1, '123', 'docA', 'userA');
    INSERT INTO user_schedules (otp_config_id, enabled, last_status)
        VALUES (1, TRUE, 'success');
    INSERT INTO sync_logs (grist_user_id, grist_doc_id, status)
        VALUES ('userA', 'docA', 'success');
"""

# Données de LEGACY_DATA relues après mise à niveau : configuration,
# planification, puis log dont la colonne NOT NULL `auto`, ajoutée après coup,
# est remplie par sa valeur par défaut
EXPECTED_LEGACY_ROWS = (("123", "docA", "userA"), (1, True), ("docA", "success", True))


def create_legacy_tables(engine: Engine) -> None:
    """Crée le schéma historique et ses données dans une base vide."""
    with engine.begin() as connection:
        connection.execute(text(LEGACY_SCHEMA))
        connection.execute(text(LEGACY_DATA))


def read_legacy_rows(engine: Engine) -> tuple[tuple, ...]:
    """Relit les données de LEGACY_DATA, au format d'EXPECTED_LEGACY_ROWS."""
    with engine.connect() as connection:
        otp_configuration = connection.execute(
            text(
                "SELECT demarche_number, grist_doc_id, grist_user_id "
                "FROM otp_configurations WHERE id = 1"
            )
        ).one()
        schedule = connection.execute(
            text("SELECT otp_config_id, enabled FROM user_schedules")
        ).one()
        sync_log = connection.execute(
            text("SELECT grist_doc_id, status, auto FROM sync_logs")
        ).one()

    return tuple(otp_configuration), tuple(schedule), tuple(sync_log)


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
