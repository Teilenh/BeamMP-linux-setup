#!/bin/bash

set -e

# === CONFIGURATION ===
VCPKG_DIR="$HOME/vcpkg"
BEAMMP_DIR="$HOME/BeamMP-Launcher"

echo "=== [1/6] Mise à jour des paquets et installation des outils nécessaires ==="
sudo apt update
sudo apt install -y build-essential cmake git curl ninja-build

echo "=== [2/6] Préparation de vcpkg ==="
if [ -d "$VCPKG_DIR" ] && [ -f "$VCPKG_DIR/bootstrap-vcpkg.sh" ]; then
    echo "✅ vcpkg déjà présent dans $VCPKG_DIR"
else
    echo "📦 Clonage de vcpkg dans $VCPKG_DIR"
    git clone https://github.com/microsoft/vcpkg.git "$VCPKG_DIR"
    pushd "$VCPKG_DIR"
    ./bootstrap-vcpkg.sh
    popd
fi
export VCPKG_ROOT="$VCPKG_DIR"

# Ajout à .bashrc si pas déjà présent
if ! grep -q "export VCPKG_ROOT=" "$HOME/.bashrc"; then
    echo "export VCPKG_ROOT=$VCPKG_DIR" >> "$HOME/.bashrc"
    echo "✅ Variable VCPKG_ROOT ajoutée à ~/.bashrc"
else
    echo "🔁 Variable VCPKG_ROOT déjà présente dans ~/.bashrc"
fi

echo "=== [4/6] Vérification du dossier BeamMP-Launcher ==="
if [ -d "$BEAMMP_DIR" ] && [ -f "$BEAMMP_DIR/CMakeLists.txt" ]; then
    echo "✅ Dossier BeamMP-Launcher valide trouvé dans $BEAMMP_DIR"
else
    echo "📦 Clonage du dépôt BeamMP-Launcher..."
    rm -rf "$BEAMMP_DIR"  # Supprime l'ancien s'il est vide ou incomplet
    git clone https://github.com/BeamMP/BeamMP-Launcher.git "$BEAMMP_DIR"
fi

echo "=== [5/6] Configuration CMake avec Ninja et vcpkg ==="
mkdir -p "$BEAMMP_DIR/bin"
cd "$BEAMMP_DIR"

cmake -G Ninja . -B bin \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" \
    -DVCPKG_TARGET_TRIPLET=x64-linux

echo "=== [6/6] Compilation du Launcher ==="
ninja -C bin

echo "✅ Compilation réussie !"
echo "👉 Exécutable disponible ici : $BEAMMP_DIR/bin"
