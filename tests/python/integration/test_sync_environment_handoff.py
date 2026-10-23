"""Contrat parent → sous-processus pour l'environnement de synchro.

Le vrai `run_synchronization_task` est exécuté, avec un vrai sous-processus :
la seule substitution porte sur la commande (un enfant qui dump son
`os.environ` vu de l'intérieur), le kwarg `env=` étant transmis tel quel —
l'héritage OS est réel.

Le test injecte lui-même une valeur résiduelle dans l'environnement du
process parent (shell, .env, ancien code…) pour rendre visible une fuite :
une config sans filtre ne doit jamais hériter d'une valeur qu'on ne lui a
pas donnée — au risque de filtrer silencieusement les dossiers.
"""

import json
import os
import subprocess
import sys
from unittest.mock import patch

from sync.sync_manager import SyncManager

ENV_ECHO_PREFIX = "ENV_ECHO: "

# Enfant qui reporte l'environnement qu'il voit réellement, puis une ligne de
# compteurs attendue par parse_output.
ECHO_SCRIPT = (
    "import json, os\n"
    f"print({ENV_ECHO_PREFIX!r} + json.dumps(dict(os.environ)))\n"
    "print('Dossiers traités avec succès: 1')\n"
)

# Configs réalistes : telles que ConfigManager les produit (toutes les clés
# Grist présentes), la première portant des filtres, la seconde aucun.
CONFIG_1 = {
    "otp_config_id": 1,
    "ds_api_token": "token_config_1",
    "demarche_number": "11111",
    "grist_base_url": "https://grist-config1.test",
    "grist_api_key": "key_config_1",
    "grist_doc_id": "doc_config_1",
    "grist_user_id": "user_config_1",
    "filter_date_start": "2024-01-01",
    "filter_date_end": "2024-12-31",
    "filter_statuses": "accepte,refuse",
    "filter_groups": "120382",
}
CONFIG_2 = {
    "otp_config_id": 2,
    "ds_api_token": "token_config_2",
    "demarche_number": "22222",
    "grist_base_url": "https://grist-config2.test",
    "grist_api_key": "key_config_2",
    "grist_doc_id": "doc_config_2",
    "grist_user_id": "user_config_2",
}

VALEURS_RESIDUELLES = {
    "DATE_DEPOT_DEBUT": "1999-01-01",
    "DATE_DEPOT_FIN": "1999-12-31",
    "STATUTS_DOSSIERS": "residu_statuts",
    "GROUPES_INSTRUCTEURS": "999999",
}


def _run_sync_and_capture_child_env(manager: SyncManager, config: dict) -> dict:
    """Exécute une synchro réelle et renvoie l'environnement vu par l'enfant."""
    real_popen = subprocess.Popen

    def echo_popen(command, **kwargs):
        return real_popen([sys.executable, "-c", ECHO_SCRIPT], **kwargs)

    log_lines = []
    with (
        patch("subprocess.Popen", side_effect=echo_popen),
        patch(
            "sync.sync_manager.grist_doc_access_level", return_value="owners"
        ),
        patch("sync.sync_manager.create_engine"),
        patch("sync.sync_manager.sessionmaker"),
        patch("sync.sync_manager.ConfigManager"),
    ):
        manager.run_synchronization_task(
            config,
            progress_callback=lambda _progress, _message: None,
            log_callback=log_lines.append,
        )

    echoes = [
        line for line in log_lines if line.startswith(ENV_ECHO_PREFIX)
    ]
    assert len(echoes) == 1, f"sortie enfant inattendue: {log_lines!r}"

    return json.loads(echoes[0][len(ENV_ECHO_PREFIX) :])


class TestEnvironnementSousProcessus:
    """L'enfant reçoit exactement ce que sa config lui dit, et rien d'autre."""

    def test_l_enfant_recoit_sa_config_complete(self):
        manager = SyncManager()

        env_enfant = _run_sync_and_capture_child_env(manager, CONFIG_1)

        assert env_enfant["DEMARCHES_API_TOKEN"] == "token_config_1"
        assert env_enfant["DEMARCHE_NUMBER"] == "11111"
        assert env_enfant["GRIST_BASE_URL"] == "https://grist-config1.test"
        assert env_enfant["GRIST_API_KEY"] == "key_config_1"
        assert env_enfant["GRIST_DOC_ID"] == "doc_config_1"
        assert env_enfant["GRIST_USER_ID"] == "user_config_1"
        assert env_enfant["DATE_DEPOT_DEBUT"] == "2024-01-01"
        assert env_enfant["DATE_DEPOT_FIN"] == "2024-12-31"
        assert env_enfant["STATUTS_DOSSIERS"] == "accepte,refuse"
        assert env_enfant["GROUPES_INSTRUCTEURS"] == "120382"

    def test_une_config_sans_filtre_n_herite_de_rien(self):
        manager = SyncManager()

        with patch.dict(os.environ, VALEURS_RESIDUELLES):
            _run_sync_and_capture_child_env(manager, CONFIG_1)
            env_enfant_2 = _run_sync_and_capture_child_env(manager, CONFIG_2)

        # Les quatre clés de filtre sont vidées, pas héritées de la valeur
        # résiduelle du parent ni de celles de la config 1
        assert env_enfant_2["DATE_DEPOT_DEBUT"] == ""
        assert env_enfant_2["DATE_DEPOT_FIN"] == ""
        assert env_enfant_2["STATUTS_DOSSIERS"] == ""
        assert env_enfant_2["GROUPES_INSTRUCTEURS"] == ""
        for valeur in VALEURS_RESIDUELLES.values():
            assert valeur not in env_enfant_2.values()
        for valeur in (
            "2024-01-01",
            "2024-12-31",
            "accepte,refuse",
            "120382",
        ):
            assert valeur not in env_enfant_2.values()

        # L'identité de la 2e config reste intacte
        assert env_enfant_2["DEMARCHES_API_TOKEN"] == "token_config_2"
        assert env_enfant_2["GRIST_DOC_ID"] == "doc_config_2"
        assert env_enfant_2["GRIST_USER_ID"] == "user_config_2"
