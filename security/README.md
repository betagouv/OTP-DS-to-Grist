# Sécurité

Ce dossier contient les protections applicatives contre les requêtes
anormales.

## Blocklist d'IP

### Durée du bannissement

`ban_duration` croît par carré de l'exposant, sans plafond : 1 h, puis 4 h,
16 h, 64 h, 256 h… La seule limite est celle de `datetime.timedelta`, qui
sature au 19ᵉ bannissement.

### Liste blanche

`parse_whitelist` accepte des IP seules ou des CIDR. Une entrée invalide lève
une erreur au démarrage plutôt que d'être ignorée : une liste blanche
silencieusement tronquée est le moyen le plus simple de se bannir soi-même.
