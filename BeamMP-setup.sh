#!/bin/bash

set -e

# ~~~ CONFIGURATION ~~~
VCPKG_DIR="$HOME/vcpkg"
BEAMMP_DIR="$HOME/BeamMP-Launcher"

echo "=== [1/6] Mise à jour des paquets et installation des outils nécessaires ==="
sudo apt update
sudo apt install -y build-essential cmake git curl

echo "### [2/6] Préparation de vcpkg ###"
if [ -d "$VCPKG_DIR" ] && [ -f "$VCPKG_DIR/bootstrap-vcpkg.sh" ]; then
    echo "    - vcpkg déjà présent dans $VCPKG_DIR"
else
    echo "    - Clonage de vcpkg dans $VCPKG_DIR"
    git clone https://github.com/microsoft/vcpkg.git "$VCPKG_DIR"
    pushd "$VCPKG_DIR"
    ./bootstrap-vcpkg.sh
    popd
fi
export VCPKG_ROOT="$VCPKG_DIR"

echo "### [3/6] Vérification du dossier BeamMP-Launcher ###"
if [ -d "$BEAMMP_DIR" ] && [ -f "$BEAMMP_DIR/CMakeLists.txt" ]; then
    echo "    - Dossier BeamMP-Launcher valide trouvé dans $BEAMMP_DIR"
else
    echo "    - Clonage du dépôt BeamMP-Launcher..."
    rm -rf "$BEAMMP_DIR" 
    git clone https://github.com/BeamMP/BeamMP-Launcher.git "$BEAMMP_DIR"
fi

echo "### [4/6] Configuration CMake avec Ninja et vcpkg ###"
mkdir -p "$BEAMMP_DIR/bin"
cd "$BEAMMP_DIR"

cmake . -B bin \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" \
    -DVCPKG_TARGET_TRIPLET=x64-linux

echo "### [5/6] Compilation du Launcher ###"
cmake --build bin --parallel
if [ -f "$BEAMMP_DIR/bin/BeamMP-Launcher" ]; then
    echo "    - L'exécutable a bien été généré : $BEAMMP_DIR/bin/BeamMP-Launcher"
else
    echo "    - Échec de la compilation : aucun exécutable trouvé."
    exit 1
fi
echo "### [6/6] Raccourci de lancement (optionnel) ###"
read -rp "🔗 Souhaitez-vous créer un raccourci global dans /usr/local/bin ? [y/N] " create_link
if [[ "$create_link" =~ ^[YyOo]$ ]]; then
    sudo ln -sf "$BEAMMP_DIR/bin/BeamMP-Launcher" /usr/local/bin/beammp
    echo "✅ Raccourci créé : vous pouvez maintenant lancer le jeu avec la commande 'beammp'"
else
    echo "ℹ️ Raccourci non créé."
fi
