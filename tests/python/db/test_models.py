from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.sql import ClauseElement

from database.models import Base, OtpConfiguration, SyncLog


class TestModelsMatchDatabase:
    """
    Les modèles ORM décrivent fidèlement la base : la différence calculée par
    l'autogénération d'Alembic (colonnes, types, nullabilité, valeurs par
    défaut, index, contraintes, clés étrangères) est vide.
    """

    def test_autogenerate_detects_no_difference(self, initialized_database):
        with initialized_database.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"compare_server_default": True}
            )
            differences = compare_metadata(context, Base.metadata)

        assert differences == [], "Écarts entre la base et les modèles :\n" + "\n".join(
            _describe_difference(difference) for difference in differences
        )


class TestModelsPersistence:
    """Écriture et relecture par l'ORM, comme le font les routes de app.py"""

    def test_sync_log_round_trip_with_defaults(self, db_session):
        otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
        db_session.add(otp_config)
        db_session.flush()
        otp_config_id = otp_config.id
        db_session.add(
            SyncLog(otp_config_id=otp_config_id, status="success", success_count=3)
        )
        db_session.commit()
        db_session.expunge_all()

        sync_log = db_session.query(SyncLog).filter_by(otp_config_id=otp_config_id).one()

        assert sync_log.status == "success"
        assert sync_log.success_count == 3
        assert sync_log.auto is True
        assert sync_log.timestamp is not None

    def test_deleting_configuration_keeps_sync_logs(self, db_session):
        otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
        db_session.add(otp_config)
        db_session.flush()
        db_session.add(SyncLog(otp_config_id=otp_config.id, status="success"))
        db_session.commit()

        db_session.delete(otp_config)
        db_session.commit()
        db_session.expunge_all()

        sync_log = db_session.query(SyncLog).one()

        assert sync_log.otp_config_id is None


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
