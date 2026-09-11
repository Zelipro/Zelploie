# Build Android — notes complémentaires

Les étapes de build complètes sont dans le README principal du dépôt, section "Build > Android".
Ce fichier ne contient que des points de vérification complémentaires.

## Checklist manifeste (après patch)

Après avoir lancé `flet-android-notifications-patch --project-root build/flutter`, vérifier dans
`build/flutter/android/app/src/main/AndroidManifest.xml` :

- [ ] `<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />`
- [ ] `<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />`
- [ ] `<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />`
- [ ] `<uses-permission android:name="android.permission.USE_FULL_SCREEN_INTENT" />`
- [ ] Présence du `<receiver android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver">`
      avec l'intent-filter `BOOT_COMPLETED` (c'est lui qui reprogramme les alarmes après un
      redémarrage du téléphone — sans lui, tout ce qui était programmé avant l'extinction est
      silencieusement perdu).

Les 4 permissions sont déjà déclarées automatiquement par `flet build` via la section
`[tool.flet.android.permission]` de `pyproject.toml` — cette checklist sert juste à confirmer
qu'elles sont bien passées dans le manifeste final après le patch, pas à les ajouter à la main.

## Test sur appareil physique, pas seulement émulateur

Le comportement plein écran + réveil d'écran + verrouillage varie significativement entre
émulateur et matériel réel (et d'un OEM à l'autre — Samsung OneUI en particulier a des
comportements de notification spécifiques, voir les docstrings de
`flet_android_notifications.show_notification` sur le paramètre `color`/`colorized`). Toujours
valider sur le téléphone réel de Zeli avant de considérer une version comme fiable.
