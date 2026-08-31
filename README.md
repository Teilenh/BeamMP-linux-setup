# BeamMP-Helper

Helper Linux pour configurer, installer et lancer BeamMP avec BeamNG.drive.
## Compatibilité | Compatibility 
🇨🇵 Compatible avec plus d'un package manager ( pour installer les dépendances de BeamMP et de quoi le build ), apt/pacman/dnf
🇬🇧 Compatibility with more than one package manager, Apt/Pacman/dnf 

⚠️ attempt to be okay on Fedora atomic with rpm-ostree, install the right package, but, after reboot, the build fail, so feel free to test, and make a PR

## Lancement portable

Depuis la racine du projet :

```bash
./BeamMP-Helper
```

Le launcher prépare automatiquement l'environnement local du projet :

- réutilise `.venv` s'il est déjà valide ;
- recrée `.venv` si le venv a été déplacé ou pointe vers un Python absent ;
- utilise `uv` si disponible ;
- installe un `uv` local dans `.tools/uv` si nécessaire ;
- retombe sur `python -m venv` + `pip` quand c'est disponible.

Commandes utiles :

```bash
BeamMP-Helper
BeamMP-Helper tui    # similaire a ne rien mettre
BeamMP-Helper check
BeamMP-Helper install
BeamMP-Helper launch
BeamMP-Helper set-path /chemin/vers/BeamNG.drive
```

Prérequis minimum : un shell ( narmol lul ) et un accès réseau au premier lancement si les dépendances ne sont pas déjà présentes.

## Distribution testé : 
[] Fedora - dnf 
[X] Fedora Atomic - rpm-ostree | a amélioré, c'est bancal
[X] Debian sid - apt | testé sur PikaOS, base debian bleeding-edge, a voir sur base debian stable
[] Debian stable - apt | devrait aussi fonctionner, mais a voir
[] Arch - Pacman 
[] OpenSUSE - zypper | inconnus complet pour moi - test en VM prévus 
