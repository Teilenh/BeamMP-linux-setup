# BeamMP-Helper

Helper Linux pour configurer, installer et lancer BeamMP avec BeamNG.drive.

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

Prérequis minimum : un shell compatible Bash et un accès réseau au premier lancement si les dépendances ne sont pas déjà présentes localement.
