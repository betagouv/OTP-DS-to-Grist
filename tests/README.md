# Tests

## Python

Les tests sont organisés en deux catégories.

### unit/

Tests **fonction par fonction** qui utilisent des **mocks** pour simuler les dépendances externes (API, DB, fichiers).
Ces tests vérifient qu une fonction fait exactement ce qu on attend, sans effet de bord.

### integration/

Tests qui utilisent des **composants réels** (client Flask, DB).
Ces tests vérifient que les pièces s assemblent correctement.

### Commandes
```sh
poe test
pytest tests/python/unit/
pytest tests/python/integration/
pytest -k "nom_du_test"
```

### Conventions

- Une suite de tests est préfixée par `test_`
- Un fichier de suite de tests pour un fichier python testé : config_manager.py → test_config_manager.py
- Vérifier les cas nominaux ET les erreurs

## JavaScript

Les tests utilisent Jest. Il n y a que des tests unitaires.

### Commandes
```sh

npm test
npm test -- --watch
```

### Conventions

- Une suite de tests doit être suffixée par `.test.js`
- Un fichier de suite de tests pour un fichier javascript testé : config.js → config.test.js
- Utiliser describe() pour grouper les tests liés, par exemple par fonction testée
- Vérifier les cas nominaux ET les erreurs
