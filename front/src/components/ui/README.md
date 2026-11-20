# ui

Composants d'interface génériques : ils habillent un élément d'interface
(alerte, icône, bouton…) aux conventions du DSFR, sans rien connaître du
métier (démarches, synchronisation, Grist). Le composant qui les utilise leur
transmet libellés et données, et réagit à leurs événements.

Chaque composant a un fichier `.spec.js` associé dans `__tests__/`.
