#!/usr/bin/env bash
# Installe Zelploie en démarrage automatique pour l'utilisateur courant
# (§7.6, confirmé avec Zeli : app permanente + démarrage auto), via
# ~/.config/autostart (norme freedesktop.org XDG — fonctionne sur
# GNOME/Ubuntu et la plupart des environnements de bureau Linux).
#
# Usage (après `flet build linux`) :
#   ./install_autostart.sh /chemin/vers/build/linux/zelploie
#
# Pour désinstaller :
#   rm ~/.config/autostart/zelploie.desktop
set -euo pipefail

EXE_PATH="${1:?Usage: $0 /chemin/vers/executable/zelploie}"

if [ ! -e "$EXE_PATH" ]; then
    echo "Erreur : $EXE_PATH introuvable." >&2
    exit 1
fi
if [ ! -x "$EXE_PATH" ]; then
    echo "Erreur : $EXE_PATH n'est pas exécutable (chmod +x manquant ?)." >&2
    exit 1
fi

ABS_EXE_PATH="$(cd "$(dirname "$EXE_PATH")" && pwd)/$(basename "$EXE_PATH")"
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/zelploie.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Zelploie
Comment=Suivi strict de l'emploi du temps
Exec=$ABS_EXE_PATH
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "Démarrage automatique installé : $AUTOSTART_DIR/zelploie.desktop"
echo "Zelploie se lancera désormais à chaque ouverture de session."
