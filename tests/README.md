# Tests

## Recommandations

En cas de bug, essayer de le reproduire via un test unitaire, puis, en même temps ou après faire le fix.
Cela nous permet de cranter la non réapparition du bug.

- Grouper les tests par fonction testée (ou préoccupation logique) : une classe Python ou un `describe()` JavaScript par fonction.

## Python

Ces tests sont organisés en deux catégories.

### unit/

Tests **fonction par fonction** qui utilisent des **mocks** pour simuler les dépendances externes (API, DB, fichiers).
Ces tests vérifient qu'une fonction fait exactement ce qu'on attend, sans effet de bord.

### integration/

Tests qui utilisent des **composants réels** (client Flask, DB).
Ces tests vérifient que les pièces s'assemblent correctement.
Pour le moment, contient surtout des tests de route d'API Flask.

### db/

Tests sur une **vraie base PostgreSQL** (service docker `db`), lancés
uniquement par `poe test-db` et exclus de `poe test`. Voir [python/db/README.md](python/db/README.md).

### Commandes

```sh
poe test # Lancer tout les tests
pytest tests/python/unit/ # Lancer seulement les tests unitaires
pytest tests/python/integration/ # Lancer seulement les tests d'intégration
poe test-db # Lancer les tests sur base réelle (démarre le service docker db)
pytest -k "nom_du_test"  # Lancer un test spécifique
```

### Conventions

- Une suite de tests est préfixée par `test_`
- Un fichier de suite de tests pour un fichier python testé : config_manager.py → test_config_manager.py
- Vérifier les cas nominaux ET les erreurs

## JavaScript

Tests du front Vue (`front/`), avec Vitest. Il n'y a que des tests unitaires, placés
dans un dossier `__tests__/` à côté du code testé.

### Commandes

```sh
npm run test:vue # Lancer tous les tests, avec réexécution automatique à chaque modification de fichier
cd front && npx vitest run # Lancer tous les tests une seule fois
```

### Conventions

- Une suite de tests doit être suffixée par `.spec.js`
- Un fichier de suite de tests pour un fichier javascript testé : dates.js → dates.spec.js
- Utiliser describe() pour grouper les tests liés, par exemple par fonction testée
- Vérifier les cas nominaux ET les erreurs
