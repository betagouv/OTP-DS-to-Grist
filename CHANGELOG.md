# Changelog

## [0.3.0](https://github.com/betagouv/OTP-DS-to-Grist/compare/v0.2.0...v0.3.0) (2025-10-31)


### Features

* **Layout:** Cartes sur fond gris et ajout de séparateurs ([800fc9f](https://github.com/betagouv/OTP-DS-to-Grist/commit/800fc9f41fd038860aea35f335f85a79a419d0dc))
* **Layout:** Fusion de la partie configuration et exécution ([bfa8240](https://github.com/betagouv/OTP-DS-to-Grist/commit/bfa8240e2e236ea6aaf4a2f9548e46fe9c9cba99))
* **Layout:** Maj du statut de la configuration après la sauvegarde ([bdd519d](https://github.com/betagouv/OTP-DS-to-Grist/commit/bdd519d9283ee632825f9243ce793f7902c7b2ad))
* **Layout:** Masquage de certains champs ([ca5f3ab](https://github.com/betagouv/OTP-DS-to-Grist/commit/ca5f3abf22bbaf31814c1ffd191413d3a8ccd0a4))
* **Layout:** Style du haut de la page ([39aff88](https://github.com/betagouv/OTP-DS-to-Grist/commit/39aff88b3a6e58bf321f5858fd22703002d13928))
* **Layout:** Suppression de la couleur et des pictos des sous-titres ([76a3f16](https://github.com/betagouv/OTP-DS-to-Grist/commit/76a3f16eb5140f3a56be44a843d1a79720a5bf4f))
* **Layout:** Suppression des pictos sur les boutons ([660ffe3](https://github.com/betagouv/OTP-DS-to-Grist/commit/660ffe3e9287fab134f8acbab915506883611e0a))


### Bug Fixes

* **Tests:** Prise en compte de `checkConfiguration` dans les tests de `saveConfiguration` ([ef368e5](https://github.com/betagouv/OTP-DS-to-Grist/commit/ef368e5a368b69d3aa9df059f54f4d9996a1f9aa))

## [0.2.0](https://github.com/betagouv/OTP-DS-to-Grist/compare/v0.1.0...v0.2.0) (2025-10-29)


### Features

* **Config:** Small refactor ([729dd85](https://github.com/betagouv/OTP-DS-to-Grist/commit/729dd85b857d9f7928641893333d80163f0a400d))
* **Logs:** Small refactoring ([854b114](https://github.com/betagouv/OTP-DS-to-Grist/commit/854b114cae30345db0306bb49a54506aef696c09))


### Bug Fixes

* **JS:** Extract applyFilters to filters.js file ([5355d02](https://github.com/betagouv/OTP-DS-to-Grist/commit/5355d024e1c56e94ef7f4d9f7ce1fde7de573600))
* **JS:** Extract checkConfiguration function to a dedicated file ([d51caba](https://github.com/betagouv/OTP-DS-to-Grist/commit/d51cabaf516d882f419d33b20ee738d92c21ba03))
* **JS:** Extract extractStatsFromLog to logs.js file ([0bb6d2f](https://github.com/betagouv/OTP-DS-to-Grist/commit/0bb6d2f652a3b307b42bc28d1049153d620918e7))
* **JS:** Extract formatDate to utils.js file ([54e48c8](https://github.com/betagouv/OTP-DS-to-Grist/commit/54e48c85486ed8f0735165c9f2ee2642a66876de))
* **JS:** Extract load loadGroupes function to filter.js file ([5edb22d](https://github.com/betagouv/OTP-DS-to-Grist/commit/5edb22d139a43de113dbdfb531f70a7fc112487b))
* **JS:** Extract resetFilters to filters.js file ([4dcaaf7](https://github.com/betagouv/OTP-DS-to-Grist/commit/4dcaaf74860df4784208867b1bac191d4341ae25))
* **JS:** Extract startSync function to sync.js file ([a1e9290](https://github.com/betagouv/OTP-DS-to-Grist/commit/a1e9290ecd8163ffe12e90194a4c2acbc1c06742))
* **JS:** Extract toggleLogs to logs.js file ([4c3bb24](https://github.com/betagouv/OTP-DS-to-Grist/commit/4c3bb24d69210559708d4bb8b51a4bcf53b94613))
* **JS:** Extract updateTaskProgress function to sync.js file ([75f41c7](https://github.com/betagouv/OTP-DS-to-Grist/commit/75f41c7da50d5fd6834d824016f97dc34de7453c))
* **Logs:** Correction du numéro de tâche en cours perdu ([28ec77b](https://github.com/betagouv/OTP-DS-to-Grist/commit/28ec77be3cc462f701f60b519ed33ee54f7cd36e))
* **Logs:** Correction du style des messages en erreur (ou pas) ([eb9bf10](https://github.com/betagouv/OTP-DS-to-Grist/commit/eb9bf10de58f06e144c40be441713bb6ab8da5bf))

## 0.1.0 (2025-10-23)


### Features

* **Cache:** Désactivation du cache navigateur et affichage de la date du build ([7f85cd5](https://github.com/betagouv/OTP-DS-to-Grist/commit/7f85cd5e5b3614e6fffd804600912244d2a83d52))
* **Configuration:** Chargement contextualisé de la configuration dans la partie exécution ([5f226e7](https://github.com/betagouv/OTP-DS-to-Grist/commit/5f226e7e90c1e6ba89becbcd3fd2020ee20207d4))
* **Configuration:** Ne plus charger d'après le fichier .env ([9155e64](https://github.com/betagouv/OTP-DS-to-Grist/commit/9155e641c53fd29685a5112e995a86701c08022c))
* **Configuration:** Ne plus sauvegarder dans le fichier .env ([33e00da](https://github.com/betagouv/OTP-DS-to-Grist/commit/33e00dab085a88167a86f3db14707c5bb60855fb))
* **Configuration:** Prévenir l'utilisateur d'autoriser le widget ([d0bb5be](https://github.com/betagouv/OTP-DS-to-Grist/commit/d0bb5bef69bcbe6ad7abe8f666438a72678c085a))
* **Configuration:** Synchronise avec les bons filtres d'utilisateur Grist ([fc4e586](https://github.com/betagouv/OTP-DS-to-Grist/commit/fc4e58694772318de8b34497f22427d6715acf6f))


### Bug Fixes

* **Champs répétables:** Un titre de section avec accent ne pose plus de problème ([1a18f70](https://github.com/betagouv/OTP-DS-to-Grist/commit/1a18f70d2c9536f7edabb7200d4d37ebdcff7fee))
* **Champs-répétables:** Éviter les échecs avec des champs titres ([9ebf6ba](https://github.com/betagouv/OTP-DS-to-Grist/commit/9ebf6baaed498f0bc96018f020ebbb2f9eaf53f3))
* **CI:** Ajout de permissions pour le workflow release please ([99f516e](https://github.com/betagouv/OTP-DS-to-Grist/commit/99f516eace961485ba28fd08fdb9fdd2647e2a75))
* **Dépendance:** Ajout de la librairie manquante Gevent ([6982bc4](https://github.com/betagouv/OTP-DS-to-Grist/commit/6982bc491ef3771466629a610f8cf764f4b1b23f))
* **Encryption-key:** Ne pas générer la clé de cryptage si elle n'existe pas ([4aefdc3](https://github.com/betagouv/OTP-DS-to-Grist/commit/4aefdc346a8870ed1b5cc68160ededf15764200a))
* **Pièce jointe:** Récupération des évolutions de la "V13.1" ([b70ad3d](https://github.com/betagouv/OTP-DS-to-Grist/commit/b70ad3d294e0d0ce1622824a4fb00dd507ea4bb8))
* **Security:** Copy socket.io into the project ([7bde960](https://github.com/betagouv/OTP-DS-to-Grist/commit/7bde960096fe2d2e5123725f3aaf944335e20c87))
* **Security:** Échappement du texte du récapitulatif des filtres ([dd0a238](https://github.com/betagouv/OTP-DS-to-Grist/commit/dd0a2383d287d2e8a9706e8e2ca943b4c6d239b8))
* **Test-connexion:** Charger le bon contexte de configuration ([38839e3](https://github.com/betagouv/OTP-DS-to-Grist/commit/38839e36e90b0213803a6be7f93e281d630dacaf))


### Documentation

* **CI:** Affichage du statut des tests dans le README ([e2ddef8](https://github.com/betagouv/OTP-DS-to-Grist/commit/e2ddef8e8bf0e7093892af2e99214ad738f52609))
* Mise à jour des documentations ([3070e29](https://github.com/betagouv/OTP-DS-to-Grist/commit/3070e2942e7bee4eb53cb8fa5288c30d3f843d4e))
