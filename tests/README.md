# Tests

## Recommandations

En cas de bug, essayer de le reproduire via un test unitaire, puis, en même temps ou après faire le fix.
Cela nous permet de cranter la non réapparition du bug.

## Python

Ces tests sont organisés en deux catégories.

### unit/

Tests **fonction par fonction** qui utilisent des **mocks** pour simuler les dépendances externes (API, DB, fichiers).
Ces tests vérifient qu'une fonction fait exactement ce qu'on attend, sans effet de bord.

### integration/

Tests qui utilisent des **composants réels** (client Flask, DB).
Ces tests vérifient que les pièces s'assemblent correctement.
Pour le moment, contient surtout des tests de route d'API Flask.

### Commandes

```sh
poe test # Lancer tout les tests
pytest tests/python/unit/ # Lancer seulement les tests unitaires
pytest tests/python/integration/ # Lancer seulement les tests d'intégration
pytest -k "nom_du_test"  # Lancer un test spécifique
```

### Conventions

- Une suite de tests est préfixée par `test_`
- Un fichier de suite de tests pour un fichier python testé : config_manager.py → test_config_manager.py
- Vérifier les cas nominaux ET les erreurs

## JavaScript

Ces tests utilisent Jest. Il n y a que des tests unitaires.

### Commandes

```sh
npm test # Lancer tout les tests
npm test -- --watch # Même chose mais avec réexécution automatique à chanque modification de fichier
```

### Conventions

- Une suite de tests doit être suffixée par `.test.js`
- Un fichier de suite de tests pour un fichier javascript testé : config.js → config.test.js
- Utiliser describe() pour grouper les tests liés, par exemple par fonction testée
- Vérifier les cas nominaux ET les erreurs
