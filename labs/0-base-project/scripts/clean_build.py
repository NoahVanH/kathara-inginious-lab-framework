#!/usr/bin/env python3
# Auxiliary script to clean build/ directory without deleting the directory itself.

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / "build"


def clean_directory(path: Path):
    for item in path.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            clean_directory(item)


def main():
    if not BUILD_DIR.exists():
        print(f"[INFO] build/ n'existe pas : {BUILD_DIR}")
        return

    print(f"[INFO] Nettoyage de {BUILD_DIR}")
    clean_directory(BUILD_DIR)
    print("[OK] Tous les fichiers supprimés, dossiers conservés")


if __name__ == "__main__":
    main()