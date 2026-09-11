# Zelploie

Application de suivi strict de l'emploi du temps hebdomadaire de Zeli (EPL Lomé / UTBM) :
notification au début de chaque créneau, minuteur en direct pendant le créneau, écran de
blocage plein écran avec bouton OK obligatoire à la fin. Windows, Ubuntu et Android.
**iOS explicitement hors périmètre** (pas de Mac disponible pour compiler avec Xcode).

Construit avec [Flet](https://flet.dev) (Python) — choix assumé malgré ses limites connues
(voir "Limites connues" ci-dessous) — et [Supabase](https://supabase.com) pour la synchronisation
multi-appareils en temps réel.

## Architecture du dépôt

```
src/
  main.py                        # point d'entrée Flet
  zelploie/
    models.py                    # modèles de données (aucune dépendance Flet/réseau)
    week_rule.py                 # résolution semaine A/B (parité ISO)
    data/schedule_template.json  # LE planning — éditable sans recompiler, voir plus bas
    storage/local_db.py          # SQLite local — seule source de vérité au démarrage
    planning/occurrence_engine.py  # génération d'occurrences + résolution d'état (§5.1)
    sync/supabase_sync.py        # synchronisation temps réel multi-appareils
    notifications/               # notifications desktop (plyer) et Android (flet-android-notifications)
    ui/                          # écrans Flet (minuteur, blocage, onboarding)
    tray/desktop_tray.py         # icône de barre système desktop (pystray)
tests/                           # tests automatisés de toute la logique métier (pytest)
sql/schema.sql                   # schéma Supabase + policy RLS (documentée)
packaging/
  windows/install_autostart.ps1  # démarrage auto Windows (raccourci dans le dossier Démarrage)
  linux/install_autostart.sh     # démarrage auto Ubuntu (~/.config/autostart)
  android/                       # notes spécifiques au build Android
```

## Modifier l'emploi du temps sans recompiler

Éditer directement `src/zelploie/data/schedule_template.json`. Chaque entrée :

```json
{
  "id": "lun-07",
  "jour_semaine": "lundi",
  "heure_debut": "08:00",
  "heure_fin": "10:00",
  "nom_activite": "EL48 CM1",
  "categorie": "cours_tp",
  "salle": "I102",
  "semaine_variante": null
}
```

- `categorie` : une de `cours_tp`, `travail_personnel`, `loisir`, `priere`, `neutre` (juste pour
  la couleur affichée dans l'app — **tous les blocs déclenchent notification + écran de blocage,
  sans exception**, quelle que soit leur catégorie — confirmé par Zeli).
- `semaine_variante` : `null` (s'applique toutes les semaines), `"A"` ou `"B"` — voir ci-dessous.
- Sur desktop, l'app doit être relancée pour relire le fichier (pas de hot-reload). Sur Android,
  il faut reconstruire l'APK (le JSON est embarqué dans l'app) — si tu veux éditer le planning
  depuis ton téléphone sans reconstruire, il faudrait déplacer ce fichier vers un stockage
  externe ou une table Supabase séparée ; ce n'est pas fait actuellement (non demandé).

Aucune validation automatique de trous/chevauchements n'est faite au chargement — le script qui
a servi à générer le JSON initial (`tests/test_occurrence_engine.py::test_occurrences_cover_full_day_without_gap_or_overlap`)
sert de garde-fou : lance `pytest` après toute modification manuelle du planning.

### Alternance semaine A / semaine B

Deux créneaux du planning dépendent du type de semaine (confirmé avec Zeli) :

| Jour | Créneau | Semaine A | Semaine B |
|---|---|---|---|
| Lundi 13h00-16h00 | TP partagé | EL47 TP1 (groupe A) | IF40 TP1 (groupe B) |
| Jeudi 10h15-13h15 | TP partagé | SY45 TP1 (groupe A) | EL48 TP2 (groupe B) |

Règle appliquée (`src/zelploie/week_rule.py`) : la semaine du **7 septembre 2026 est une semaine
A** (référence confirmée par Zeli). C'est la semaine ISO n°37 (impaire) — la règle est donc
*semaine ISO impaire = A, paire = B*, en alternance continue.

⚠️ **Point non confirmé** : on ne sait pas si cette alternance continue sans interruption à
travers les vacances de Noël jusqu'au semestre de printemps (~février 2027), ou si elle redémarre
à A à ce moment-là. Si Zeli confirme un redémarrage, ajouter une deuxième entrée dans
`_REFERENCES` en haut de `week_rule.py` — le reste du moteur n'a pas à changer.

### Vacances / examens / intersemestre

Le calendrier universitaire UTBM 2026-2027 fourni par Zeli montre que le planning hebdomadaire
fixe ne s'applique pas toute l'année (vacances, semaines d'examens, intersemestre). **Ce n'était
pas couvert par la spec initiale et n'est pas implémenté** : l'app suivra actuellement le gabarit
hebdomadaire même pendant les vacances. Zeli n'a pas encore tranché s'il veut que l'app
désactive automatiquement les créneaux de cours pendant ces périodes ou s'il préfère gérer ça
manuellement — question posée, en attente de réponse.

## Icône de l'app

`src/assets/icon.png` et `src/assets/splash_android.png` sont des **placeholders génériques**
(cercle bleu + "Z", générés automatiquement, aucune donnée de Zeli inventée). À remplacer par une
vraie icône avant une diffusion au-delà d'un usage strictement personnel — Flet les redimensionne
automatiquement pour chaque plateforme au moment du build.

## Configuration Supabase

1. Créer un projet Supabase, puis exécuter `sql/schema.sql` dans l'éditeur SQL du projet.
2. Récupérer l'URL du projet et la clé **anon** (Project Settings > API).
3. Définir sur chaque appareil, avant de lancer l'app :
   ```bash
   export ZELPLOIE_SUPABASE_URL="https://xxxx.supabase.co"
   export ZELPLOIE_SUPABASE_ANON_KEY="eyJ..."
   ```
   (Sur Android, ces valeurs doivent être injectées au build — voir `flet build apk --help` pour
   passer des variables d'environnement, ou les coder en dur dans une config locale non commitée
   avant de builder si l'app est strictement personnelle.)
4. Sans ces variables, l'app fonctionne quand même **entièrement en local** (le calcul du temps
   restant ne dépend jamais du réseau, §3) — seule la synchro multi-appareils est désactivée.

**⚠️ Sécurité, à lire** : la policy RLS dans `sql/schema.sql` autorise un accès complet
(lecture+écriture, sans restriction) à quiconque présente la clé anon. C'est un choix assumé pour
un usage strictement personnel mono-utilisateur (pas d'authentification par compte) — voir les
commentaires détaillés dans `sql/schema.sql`. Ne jamais publier cette clé publiquement.

## Build

### Windows

```bash
flet build windows
packaging\windows\install_autostart.ps1 -ExePath ".\build\windows\zelploie.exe"
```

### Linux (Ubuntu)

```bash
flet build linux
chmod +x packaging/linux/install_autostart.sh
./packaging/linux/install_autostart.sh ./build/linux/zelploie
```

### Android

```bash
flet build apk
flet-android-notifications-patch --project-root build/flutter
flet build apk   # relancer le build final avec le projet patché
```

Détails importants (vérifiés directement sur le code du package
`flet-android-notifications` 0.10.1, pas seulement sur sa doc) :

- **Le patch est obligatoire après CHAQUE build propre.** `flet build apk` régénère entièrement
  le projet Flutter intermédiaire (`build/flutter`) et efface toute modification manuelle du
  manifeste. Le script `flet-android-notifications-patch` réinjecte les `BroadcastReceiver`
  nécessaires (dont celui qui reprogramme les alarmes après redémarrage du téléphone — sans lui,
  les notifications programmées ne survivent pas à un reboot) et active le *core library
  desugaring* + *multidex* dans `build.gradle.kts` (requis par `flutter_local_notifications`).
- **Bonne surprise par rapport à la veille technique initiale** : contrairement à ce qui était
  anticipé, l'intent plein écran (`full_screen_intent=True`) EST géré nativement par ce package
  — pas besoin d'éditer manuellement le manifeste pour le canal de notification. Reste
  nécessaire : déclarer la permission `USE_FULL_SCREEN_INTENT` (déjà fait dans `pyproject.toml`)
  et l'autoriser côté utilisateur sur Android 14+ (voir juste en dessous).
- **Android 14+ révoque par défaut la permission de notification plein écran.** L'app déclenche
  automatiquement l'écran de demande au premier lancement (`ui/onboarding.py`) via
  `request_full_screen_intent_permission()`. Si Zeli l'a ignoré ou refusé, il peut la réaccorder
  manuellement : *Réglages > Applications > Zelploie > Autorisations* (ou *Accès spécial >
  Notifications plein écran* selon la version d'Android).
- **Taille et démarrage** : les builds mobiles Flet embarquent un interpréteur CPython complet
  (`serious_python`). L'APK sera nettement plus gros et le démarrage plus lent qu'une app
  Flutter/Dart native — c'est une caractéristique connue de Flet, pas un bug à corriger.

Teste réellement sur un appareil physique, pas seulement un émulateur — le comportement plein
écran/verrouillage est justement le genre de chose qui diffère entre les deux (§7.2 de la spec
d'origine).

## Limites connues de l'approche Flet

- Pas de notifications Android natives dans Flet lui-même : dépendance à un package tiers
  (`flet-android-notifications`) qui wrappe `flutter_local_notifications`, avec une étape de
  patch manuel obligatoire à chaque build (voir ci-dessus).
- Aucun contrôle "icône de barre système" natif dans Flet : le tray desktop utilise `pystray` en
  parallèle de la boucle asyncio de Flet. **Non testé sur un vrai poste Windows/Ubuntu** —
  l'environnement de développement utilisé pour écrire ce code n'a pas d'écran (sandbox headless),
  donc pystray n'a pas pu être exercé visuellement. À valider en conditions réelles avant de faire
  confiance à ce module ; voir aussi le plan de test ci-dessous.
- Démarrage plus lent et poids applicatif plus important qu'une app Flutter/Dart native pure
  (interpréteur Python embarqué) — assumé, pas à "corriger".
- La synchronisation temps réel Supabase repose sur le client **asynchrone** de `supabase-py` :
  vérifié que le canal Realtime du client synchrone de la version installée (2.31.0) est un stub
  non implémenté. Ce n'est pas gênant ici (Flet tourne déjà sur asyncio), mais si `supabase-py`
  est mis à jour un jour, vérifier que cette limitation n'a pas changé avant de simplifier le code.

## Plan de test

À exécuter avant tout usage réel quotidien :

1. **Tests automatisés** (logique métier — génération d'occurrences, règle semaine A/B, calcul
   d'état, pas-de-rattrapage, stockage local) :
   ```bash
   pip install -e . --group dev   # ou : pip install pytest pytest-asyncio
   pytest
   ```
   24 tests couvrent notamment : recalcul correct après rallumage en plein milieu d'un créneau,
   et le comportement "pas de rattrapage" après un ou plusieurs créneaux entièrement ratés.

2. **Notification de début à l'heure** : programmer un créneau de test dans les 2 prochaines
   minutes (modifier temporairement `schedule_template.json`), vérifier la réception sur
   Windows, Ubuntu ET Android (verrouillé ET déverrouillé).

3. **Écran de blocage à la fin** :
   - Desktop : vérifier que la fenêtre passe bien plein écran/premier plan/sans bordure à
     `fin_datetime`, et qu'elle résiste à Alt-Tab / clic sur une autre fenêtre.
   - Android : vérifier que l'intent plein écran réveille l'écran et ouvre l'app **même
     téléphone verrouillé**, y compris après avoir accordé la permission Android 14+.

4. **Synchronisation multi-appareils** : cliquer OK sur un appareil, vérifier que l'écran de
   blocage se ferme automatiquement sur un second appareil abonné, sans avoir à recliquer OK,
   en quelques secondes.

5. **Recalcul après extinction en plein créneau** : éteindre l'appareil (ou tuer l'app) pendant
   un créneau, le rallumer à un instant `t` compris dedans, vérifier que le temps restant affiché
   correspond bien à `fin_datetime - t` (pas de dérive, pas de redémarrage du minuteur à zéro).

6. **Pas de rattrapage** : éteindre l'appareil pendant qu'un créneau se termine ET que le/les
   suivants démarrent et se terminent aussi, le rallumer bien plus tard : vérifier que l'app
   affiche directement l'état correspondant au moment du rallumage, **sans** demander d'acquitter
   rétroactivement les créneaux intermédiaires ratés.

7. **Démarrage automatique** : redémarrer le PC (Windows et Ubuntu séparément) et vérifier que
   Zelploie se relance tout seul, réduit dans la barre système.
