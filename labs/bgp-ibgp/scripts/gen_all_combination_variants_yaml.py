"""
generate_variants.py
--------------------
Génère variants.yaml avec toutes les combinaisons possibles de :
  - addressing schemes  (depuis schemes.yaml)
  - error sets          (depuis errors.yaml, + cas baseline sans erreur)

Usage :
    python generate_variants.py
    python generate_variants.py --schemes schemes.yaml --errors errors.yaml --out variants.yaml
    python generate_variants.py --max-errors 2   # combinaisons jusqu'à 2 erreurs simultanées
"""

import argparse
import itertools
from math import comb
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

ROOT_DIR  = Path(__file__).resolve().parent
ROOT_DIR  = ROOT_DIR.parent
MODEL_DIR = ROOT_DIR / "variation_model"

SCHEMES_FILE  = MODEL_DIR / "schemes.yaml"
ERRORS_FILE   = MODEL_DIR / "errors.yaml"
VARIANTS_FILE = MODEL_DIR / "variants.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_variants(
    scheme_names: list[str],
    error_names: list[str],
    max_errors: int = 1,
) -> list[dict]:
    """
    Génère toutes les combinaisons (scheme x sous-ensemble d'erreurs).

    max_errors : taille maximale des sous-ensembles d'erreurs à considérer.
                 0  -> baseline seulement (aucune erreur)
                 1  -> baseline + erreurs simples (1 à la fois)  [défaut]
                 2  -> idem + paires d'erreurs
                 -1 -> toutes les combinaisons (2^N sous-ensembles)
    """
    if max_errors < 0:
        max_errors = len(error_names)

    error_subsets: list[list[str]] = []  # Pas de baseline
    for size in range(1, max_errors + 1):
        for combo in itertools.combinations(error_names, size):
            error_subsets.append(list(combo))

    variants = []
    variant_id = 0
    for scheme in scheme_names:
        for error_set in error_subsets:
            variants.append({"id": variant_id, "scheme": scheme, "errors": error_set})
            variant_id += 1

    return variants


def dump_variants(variants: list[dict], out_path: Path) -> None:
    data = {"variants": variants}

    class InlineListDumper(yaml.Dumper):
        # Désactive les ancres/alias YAML (évite &id001 / *id001)
        def ignore_aliases(self, data):
            return True

    def represent_list(dumper, data):
        # Listes courtes (<=5 éléments courts) -> style flow [...]
        if len(data) <= 5 and all(isinstance(i, str) and len(i) < 30 for i in data):
            return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)
        return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=False)

    InlineListDumper.add_representer(list, represent_list)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=InlineListDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Génère variants.yaml exhaustif.")
    parser.add_argument(
        "--schemes",
        default=str(SCHEMES_FILE),
        help=f"Fichier schemes.yaml source (défaut : {SCHEMES_FILE})",
    )
    parser.add_argument(
        "--errors",
        default=str(ERRORS_FILE),
        help=f"Fichier errors.yaml source (défaut : {ERRORS_FILE})",
    )
    parser.add_argument(
        "--out",
        default=str(VARIANTS_FILE),
        help=f"Fichier de sortie (défaut : {VARIANTS_FILE})",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=1,
        help=(
            "Nombre max d'erreurs simultanées par variant. "
            "0 = baseline uniquement, -1 = toutes combinaisons (exponentiel !)."
        ),
    )
    args = parser.parse_args()

    schemes_data = load_yaml(Path(args.schemes))
    errors_data  = load_yaml(Path(args.errors))

    scheme_names: list[str] = list(schemes_data["addressing_schemes"].keys())
    error_names:  list[str] = list(errors_data["errors"].keys())

    print(f"Schemes  ({len(scheme_names)}) : {scheme_names}")
    print(f"Errors   ({len(error_names)})  : {error_names}")
    print(f"Max errors par variant        : {args.max_errors}")

    variants = build_variants(scheme_names, error_names, max_errors=args.max_errors)

    max_e = len(error_names) if args.max_errors < 0 else args.max_errors
    total_error_subsets = sum(comb(len(error_names), k) for k in range(1, max_e + 1))
    expected = len(scheme_names) * total_error_subsets
    assert len(variants) == expected, f"Attendu {expected}, obtenu {len(variants)}"

    out_path = Path(args.out)
    dump_variants(variants, out_path)

    print(f"\n✓ {len(variants)} variants écrits dans « {out_path} »")
    print(f"  ({len(scheme_names)} schemes x {total_error_subsets} sous-ensembles d'erreurs)")


if __name__ == "__main__":
    main()