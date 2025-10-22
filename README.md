![CI](https://github.com/betagouv/OTP-DS-to-Grist/actions/workflows/ci.yml/badge.svg)

# 🦄 One Trick Pony DS to Grist - Installation Locale

One Trick Pony DS to Grist (OTP) est un gestionnaire de connecteur entre [Démarches Simplifiées](https://www.demarches-simplifiees.fr/admin/procedures) et [Grist](https://lasuite.numerique.gouv.fr/services/grist).

Il permet d'exporter des données de Démarches Simplifiées vers Grist pour une personne ayant des droits d'administration d'une démarche simplifiée et des droits d'un document Grist. 

## 🚀 Installation

Voir [doc installation](./docs/install.md)

## 🔑 Obtention des tokens API

### Token Démarches Simplifiées

1. **Connectez-vous** à votre compte DS administrateur
2. **Accédez** aux paramètres de votre compte
3. **Générez** un nouveau token API dans la section "Jeton d'accès"
4. **Copiez** le token généré (format : `MGQ...`)

### Numéro de démarche

1. **Connectez-vous** à votre compte DS administrateur
2. **Accédez** à "Mes démarches"
3. **Copiez** le numéro figurant dans la *carte* de la démarche N° xxx xxx (en haut à droite)

### Clé API Grist

1. **Connectez-vous** à votre instance Grist
2. **Accédez** à votre profil utilisateur
3. **Générez** une nouvelle clé API
4. **Copiez** la clé générée (format : `17...`)

### ID Document Grist & Base url

1. **Ouvrez** votre document Grist de destination
2. **Copiez l'ID** se trouvant dans les paramètres du document, section `API`
    - L'ID ressemble à : `mYMMb...`
3. **Copiez** l'URL de base se trouvant dans le menu déroulant `API`


## 🎛️ Utilisation de l'interface

### 1. Page de configuration (`/`)

- **Vérifiez** que tous les paramètres sont correctement affichés
- **Testez** les connexions DS et Grist
- **Modifiez** la configuration si nécessaire (mode local uniquement)

⚠️ S'assurer de donner un accès complet au document Grist.

### 2. Page d'exécution (`/execution`)

1. **Configurez les filtres** selon vos besoins :
   - Dates de dépôt (début/fin)
   - Statuts des dossiers
   - Groupes instructeurs

2. **Lancez la synchronisation**
3. **Suivez la progression** en temps réel
4. **Consultez les logs** détaillés

### 3. Page de débogage (`/debug`)

- **Vérifiez** l'état des fichiers système
- **Consultez** les variables d'environnement
- **Testez** la connectivité WebSocket


## Communauté

- **Code source** : Projet démarré par DRAAF Occitanie

---

**Prochaines étapes :**
1. Testez la synchronisation avec quelques dossiers
2. Ajustez les paramètres selon vos besoins
3. Explorez les données dans Grist
4. Configurez des synchronisations automatiques

---
