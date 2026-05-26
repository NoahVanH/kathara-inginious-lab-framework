#!/usr/bin/env python3
"""
Generate variants.yaml with all combinations of:
  - addressing schemes (from schemes.yaml)
  - error sets (from errors.yaml)

Each variant has exactly 4 errors, one per required kind:
  - sr_disabled
  - sr_wrong_index
  - tilfa_interface_disabled
  - tilfa_no_node_protection

Usage:
    python generate_variants.py
    python generate_variants.py --max-variants 50  # Limite à 50 variants
"""

import argparse
import itertools
from pathlib import Path
import random
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT_DIR / "variation_model"
SCHEMES_FILE = MODEL_DIR / "schemes.yaml"
ERRORS_FILE = MODEL_DIR / "errors.yaml"
VARIANTS_FILE = MODEL_DIR / "variants.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    """Load a YAML file safely."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def build_variants(
    scheme_names: list[str],
    errors_def: dict,
    required_kinds: list[str],
    max_variants: int = None,
) -> list[dict]:
    """
    Generate variants with exactly 4 errors, one per required kind.
    Each variant is a combination of:
      - 1 error from sr_disabled
      - 1 error from sr_wrong_index
      - 1 error from tilfa_interface_disabled
      - 1 error from tilfa_no_node_protection

    Args:
        scheme_names: List of addressing scheme names.
        errors_def: Dictionary of errors from errors.yaml.
        required_kinds: List of required error kinds (must have at least one error each).
        max_variants: Maximum number of variants to generate (None = all combinations).

    Returns:
        List of variant dictionaries.
    """
    # Group errors by their kind
    errors_by_kind = {}
    for name, cfg in errors_def["errors"].items():
        kind = cfg.get("kind")
        if kind in required_kinds:
            errors_by_kind.setdefault(kind, []).append(name)

    # Check if we have at least one error per required kind
    missing_kinds = [kind for kind in required_kinds if kind not in errors_by_kind or not errors_by_kind[kind]]
    if missing_kinds:
        raise ValueError(f"No errors found for required kinds: {missing_kinds}")

    # Generate all possible combinations (one error per kind)
    kind_combinations = list(itertools.product(
        *[errors_by_kind[kind] for kind in required_kinds]
    ))

    # Build all possible variants (scheme × error_combination)
    all_variants = []
    for variant_id, (scheme, error_combo) in enumerate(
        itertools.product(scheme_names, kind_combinations)
    ):
        all_variants.append({
            "id": variant_id,
            "scheme": scheme,
            "errors": list(error_combo)  # Convert tuple to list
        })

    # Limit the number of variants if max_variants is specified
    if max_variants is not None and len(all_variants) > max_variants:
        all_variants = random.sample(all_variants, max_variants)

    # Shuffle the final list of variants
    random.shuffle(all_variants)

    # Reassign IDs to ensure they are sequential after shuffling
    for i, variant in enumerate(all_variants):
        variant["id"] = i

    return all_variants

def dump_variants(variants: list[dict], out_path: Path) -> None:
    """Dump variants to YAML with clean formatting."""
    data = {"variants": variants}

    class InlineListDumper(yaml.Dumper):
        """Custom dumper to avoid YAML anchors and improve readability."""
        def ignore_aliases(self, data):
            return True

    def represent_list(dumper, data):
        """
        Render short lists inline (flow style) for readability:
        errors: [err1, err2, err3, err4]
        """
        if len(data) <= 5 and all(isinstance(i, str) and len(i) < 50 for i in data):
            return dumper.represent_sequence(
                "tag:yaml.org,2002:seq", data, flow_style=True
            )
        return dumper.represent_sequence(
            "tag:yaml.org,2002:seq", data, flow_style=False
        )

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
    parser = argparse.ArgumentParser(
        description="Generate variants.yaml with combinations of schemes and errors."
    )
    parser.add_argument(
        "--schemes",
        default=str(SCHEMES_FILE),
        help=f"Input schemes.yaml (default: {SCHEMES_FILE})",
    )
    parser.add_argument(
        "--errors",
        default=str(ERRORS_FILE),
        help=f"Input errors.yaml (default: {ERRORS_FILE})",
    )
    parser.add_argument(
        "--out",
        default=str(VARIANTS_FILE),
        help=f"Output file (default: {VARIANTS_FILE})",
    )
    parser.add_argument(
        "--max-variants",
        type=int,
        default=None,
        help="Maximum number of variants to generate (randomly selected if exceeded).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility.",
    )

    args = parser.parse_args()

    # Set random seed if specified
    if args.seed is not None:
        random.seed(args.seed)

    # Load input data
    schemes_data = load_yaml(Path(args.schemes))
    errors_data = load_yaml(Path(args.errors))

    scheme_names = list(schemes_data["addressing_schemes"].keys())

    # Required kinds (one error per kind in each variant)
    required_kinds = [
        "sr_disabled",
        "sr_wrong_index",
        "tilfa_interface_disabled",
        "tilfa_no_node_protection"
    ]

    print(f"Schemes ({len(scheme_names)}): {scheme_names}")
    print(f"Required kinds: {required_kinds}")
    if args.max_variants:
        print(f"Max variants: {args.max_variants}")

    # Generate variants
    variants = build_variants(
        scheme_names,
        errors_data,
        required_kinds=required_kinds,
        max_variants=args.max_variants,
    )

    # Save output
    out_path = Path(args.out)
    dump_variants(variants, out_path)

    print(f"\n✓ {len(variants)} variants written to '{out_path}'")

if __name__ == "__main__":
    main()