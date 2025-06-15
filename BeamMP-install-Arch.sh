#!/bin/bash

set -e

# ~~~ CONFIGURATION ~~~
VCPKG_DIR="$HOME/vcpkg"
BEAMMP_DIR="$HOME/BeamMP-Launcher"

echo "=== [1/6] Mise à jour des paquets et installation des outils nécessaires ==="
sudo pacman -Syu cmake git curl

