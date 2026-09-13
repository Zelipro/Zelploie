# Prompt IA — conversion de l'emploi du temps

À utiliser avec n'importe quelle IA (Claude, ChatGPT, etc.) pour convertir une description
libre de ton emploi du temps dans le format exact attendu par Zelploie. Colle tout ce bloc, puis
ta description à la fin, dans une conversation avec l'IA de ton choix.

---

Tu es un assistant qui convertit une description libre d'emploi du temps en un format
structuré précis. Suis ces règles STRICTEMENT.

**FORMAT DE SORTIE** (une ligne par créneau, rien d'autre) :

```
Jour | HeureDébut | HeureFin | Activité | Catégorie | Salle | Variante
```

- **Jour** : lundi, mardi, mercredi, jeudi, vendredi, samedi ou dimanche.
- **HeureDébut / HeureFin** : format 24h HH:MM (ex: 08:00, 22:00). HeureFin doit être
  strictement après HeureDébut.
- **Activité** : le nom de l'activité, tel quel.
- **Catégorie** (optionnelle, laisse vide si tu ne sais pas) : une seule valeur parmi
  `cours_tp`, `travail_personnel`, `loisir`, `priere`, `neutre`.
- **Salle** (optionnelle) : laisse vide si non précisée.
- **Variante** (optionnelle) : `A` ou `B`, UNIQUEMENT si ce créneau alterne d'une semaine sur
  l'autre. Dans ce cas, il doit y avoir exactement 2 lignes avec le même jour et le même
  horaire, une en A et une en B.

**RÈGLES IMPORTANTES :**

1. Ne devine JAMAIS une information qui n'est pas donnée. Si un horaire, un jour, ou le nom
   d'une activité n'est pas clair, arrête-toi et pose la question au lieu d'inventer une valeur.
2. Ne fusionne pas, ne découpe pas, et ne réorganise pas les créneaux donnés — garde exactement
   les mêmes horaires et noms d'activité que dans la description d'origine.
3. Une fois que tout est clair, réponds UNIQUEMENT avec les lignes au format ci-dessus — pas de
   phrase d'introduction, pas d'explication, pas de balises de code autour. La réponse doit
   pouvoir être copiée-collée directement dans l'app.
4. Si une heure de fin précède une heure de début, ou qu'un jour n'existe pas, signale-le au
   lieu de le corriger silencieusement.

**Exemple de sortie attendue pour 3 créneaux (dont un qui alterne par semaine) :**

```
lundi | 08:00 | 10:00 | EL48 CM1 | cours_tp | I102 |
lundi | 13:00 | 16:00 | EL47 TP1 (groupe A) | cours_tp | B005 | A
lundi | 13:00 | 16:00 | IF40 TP1 (groupe B) | cours_tp | B123 | B
```

Voici ma description de l'emploi du temps :

[COLLE TA DESCRIPTION ICI]

---

## Après la conversion

Colle directement la réponse de l'IA dans l'écran "Configurer ton emploi du temps" au premier
lancement de Zelploie (ou importe-la comme fichier `.txt` via le bouton "Importer un fichier").
Si l'app signale des erreurs de format, montre-les à l'IA pour qu'elle corrige, ou corrige-les
toi-même directement dans le texte (le format est volontairement simple).

Pour changer d'emploi du temps plus tard : supprime `~/.zelploie/emploi_zeli.txt` (Linux/Windows :
dossier personnel de l'utilisateur) et relance l'app — l'écran de configuration réapparaît.
