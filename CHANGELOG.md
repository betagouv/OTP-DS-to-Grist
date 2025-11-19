# Changelog

## [0.4.0](https://github.com/betagouv/OTP-DS-to-Grist/compare/v0.3.0...v0.4.0) (2025-11-19)


### Features

* **Help:** Changement de terme pour les onglets ([323c64f](https://github.com/betagouv/OTP-DS-to-Grist/commit/323c64fbee07e4539cc97075a64ee35ab0bbdbd5))
* **Help:** Mise à jour des images ([970ad82](https://github.com/betagouv/OTP-DS-to-Grist/commit/970ad8233ae30b12f2755c28c6c332215f31fb9a))
* **Layout:** Afficher le bloc de configuration DS sous forme de volet d'accordéon ([105e6d2](https://github.com/betagouv/OTP-DS-to-Grist/commit/105e6d2240a5b7284a2882369f28949d27b1c455))
* **Layout:** Afficher le bloc de configuration Grist sous forme de volet d'accordéon ([6c5443e](https://github.com/betagouv/OTP-DS-to-Grist/commit/6c5443ed6bd099f02297aa8a3fb24116bb75bd7a))
* **Layout:** Afficher le bloc de paramètres sous forme de volet d'accordéon ([dac8a4a](https://github.com/betagouv/OTP-DS-to-Grist/commit/dac8a4a6d7d7f9c4f8969a0b56a593fe0b1d5c4d))
* **Layout:** Ajout d'étoiles pour les champs obligatoires ([4172160](https://github.com/betagouv/OTP-DS-to-Grist/commit/4172160347385daecac8a39adf85523c439bfb13))
* **Layout:** Déplacement du statut de la configuration ([ec16677](https://github.com/betagouv/OTP-DS-to-Grist/commit/ec166775d6551b49c18c95d7c32efecc89e086bc))
* **Layout:** Maj du dom des tests de configuration ([dd650bb](https://github.com/betagouv/OTP-DS-to-Grist/commit/dd650bbb700fc02c50620da1b2ff20aefe56a5dc))
* **Layout:** Sauvegarde et vérifie la configuration à chaque changement ([6b3a4d2](https://github.com/betagouv/OTP-DS-to-Grist/commit/6b3a4d2ac176bbf142a9f4173fce1a02c0a9dffe))
* **Layout:** Suppression du bloc configuration avancée ([8dcd140](https://github.com/betagouv/OTP-DS-to-Grist/commit/8dcd140bfb83828fc41423c4dd907f5479684677))
* **Layout:** Suppression du titre ([d8bd7ec](https://github.com/betagouv/OTP-DS-to-Grist/commit/d8bd7ec47e7376aa24bd06a1f1c5d89ff6cbec04))
* **Sync-auto:** Activation de la case à cocher juste après la configuration initiale ([3e2ae52](https://github.com/betagouv/OTP-DS-to-Grist/commit/3e2ae528fc07886b168b8b87ae4fdf976b558e2c))
* **Sync-auto:** Affichage du statut de la dernière synchronisation ([77914d7](https://github.com/betagouv/OTP-DS-to-Grist/commit/77914d7e11870343ac1cb2699f2f4b65a0d4cd71))
* **Sync-auto:** Ajout de la dépendance APScheduler ([a3b985a](https://github.com/betagouv/OTP-DS-to-Grist/commit/a3b985a08cc03f759a764e0368da671f9c910f33))
* **Sync-auto:** Ajout des nouveaux modèles pour les nouvelles tables ([3ff8409](https://github.com/betagouv/OTP-DS-to-Grist/commit/3ff840929688d115489ec028e18e67a595e37968))
* **Sync-auto:** Correction de blocages DB dans les jobs planifiés ([a1ede12](https://github.com/betagouv/OTP-DS-to-Grist/commit/a1ede129893bfa1a1114dc5ae27e5b403bee78f5))
* **Sync-auto:** Correction de blocages de tâche ([10a6e22](https://github.com/betagouv/OTP-DS-to-Grist/commit/10a6e22edfeb923212048f98616d12265c4c6684))
* **Sync-auto:** Correction de blocages de tâches si chevauchantes ([a28bd94](https://github.com/betagouv/OTP-DS-to-Grist/commit/a28bd946f7720ee88901a976806e3b46057868f4))
* **Sync-auto:** Décaler les tâches sur le même doc tout le temps, pas seulement la première fois ([e666333](https://github.com/betagouv/OTP-DS-to-Grist/commit/e666333e89d16a2361c5ab2d4c82041fa35f4ad6))
* **Sync-auto:** Documentation ([39a5430](https://github.com/betagouv/OTP-DS-to-Grist/commit/39a543051326d2c7e618c3374487bb25a9a186dc))
* **Sync-auto:** Exception si DATABASE_URL n'est pas défini ([f6633b6](https://github.com/betagouv/OTP-DS-to-Grist/commit/f6633b6509451e1b3524b6c9365e145ee2f9e986))
* **Sync-auto:** Implémentation des fonctions de synchro auto ([b29ce6d](https://github.com/betagouv/OTP-DS-to-Grist/commit/b29ce6dde2d3e4325010765d3debc936f4f894f0))
* **Sync-auto:** Modification du schéma de la base de données ([4b8fa71](https://github.com/betagouv/OTP-DS-to-Grist/commit/4b8fa71e106565c5c7c5cc44319654309c2cc492))
* **Sync-auto:** Nouvelle route pour sauvegarder la synchronisation ([ea0b720](https://github.com/betagouv/OTP-DS-to-Grist/commit/ea0b7202feef872847d0345786953763ffebc4ef))
* **Sync-auto:** Plus de précisions sur certaines fonctions de synchronisation ([4de9a84](https://github.com/betagouv/OTP-DS-to-Grist/commit/4de9a84189e437a2d161c27bf6c1ff1bb967e5bc))
* **Sync-auto:** poetry lock ([7445394](https://github.com/betagouv/OTP-DS-to-Grist/commit/744539435e5fa4d1c5c3f2205242ee7e141575ed))
* **Sync-auto:** Possibilité de régler l'heure de synchronisation via l'environnement ([669a7d0](https://github.com/betagouv/OTP-DS-to-Grist/commit/669a7d087680de00d007a2107ed065ba7785951c))
* **Sync-auto:** Restauration de code perdu ([2d9c022](https://github.com/betagouv/OTP-DS-to-Grist/commit/2d9c0222a4589a31af01be7192395167e779da17))


### Bug Fixes

* **DB:** Ajoute la colonne id même si la table existe ([ad60122](https://github.com/betagouv/OTP-DS-to-Grist/commit/ad601224b8c497bde91f51d23a042bdde05169f1))
* **Sync-auto:** Correction de l'affichage de l'heure de la dernière synchronisation ([5cd8931](https://github.com/betagouv/OTP-DS-to-Grist/commit/5cd8931ccc8adfdc9cca22383b8ad5a741bc8a01))
* **Sync-auto:** Démarrage du scheduler dans tous les cas ([84dec47](https://github.com/betagouv/OTP-DS-to-Grist/commit/84dec47bed574c8324ca1efc019259e7b8c1cab6))
* **Sync-auto:** Précision du time zone ([d6b985a](https://github.com/betagouv/OTP-DS-to-Grist/commit/d6b985a33521282fc212c92a1e4c7a5a0dcf804d))

## [0.3.0](https://github.com/betagouv/OTP-DS-to-Grist/compare/v0.2.0...v0.3.0) (2025-11-05)


### Features

* **debug:** Mise en page ([4d7ea15](https://github.com/betagouv/OTP-DS-to-Grist/commit/4d7ea15362e1b05684a0a6566b6b626be3ccefb7))
* **debug:** Suppression de la partie affichant la configuration ([904121c](https://github.com/betagouv/OTP-DS-to-Grist/commit/904121c43cfce9cb5290abaf9dad2d9b5f1cdf19))
* **debug:** Suppression de la partie informations système ([cad053b](https://github.com/betagouv/OTP-DS-to-Grist/commit/cad053b42dbd0c4b57dc0225b2dd8f392c900054))
* **debug:** Suppression de la partie recherche de fichier ([2c39b06](https://github.com/betagouv/OTP-DS-to-Grist/commit/2c39b06453e2bf727faaea48fbacb479226ed315))
* **debug:** Suppression de la partie répertoire et dépendances ([1c70597](https://github.com/betagouv/OTP-DS-to-Grist/commit/1c705975574ef8703210950700b18e168458256f))
* **Doc:** Mise en place des images ([fcebac9](https://github.com/betagouv/OTP-DS-to-Grist/commit/fcebac993458ddc6c0ea3b538d4f0f7276239646))
* **Doc:** Mise en place des puces ([6ed5b4b](https://github.com/betagouv/OTP-DS-to-Grist/commit/6ed5b4bc6b3f7d6b9585cc767a927bb6d3bdd9fb))
* **Doc:** Mise en place des titres ([bc83725](https://github.com/betagouv/OTP-DS-to-Grist/commit/bc837250ac0fa820f60f46ae0eb045cca36de283))
* **Doc:** Mise en place du menu ([f614777](https://github.com/betagouv/OTP-DS-to-Grist/commit/f61477728db174e4613a406343aeb40485415b16))
* **Doc:** Nouvelle route pour la documentation utilisateur ([ebddd97](https://github.com/betagouv/OTP-DS-to-Grist/commit/ebddd975f496efcd1ba7f17978e4be8923207947))
* **Doc:** Surbrillance du bon élément du sous menu ([68d9d64](https://github.com/betagouv/OTP-DS-to-Grist/commit/68d9d64389d06aa06377429ad03f2761992d0ba5))
* **Layout:** Afficher un bandeau d'alerte version beta ([b02beaa](https://github.com/betagouv/OTP-DS-to-Grist/commit/b02beaad3a1f6f63b570981612f3774d7ba9dfaa))
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
