"""
##########################################################################
# wrong_cost and wrong_mtu errors are forced in all variants.
##########################################################################
generate_variants.py
--------------------
Generate variants.yaml with all combinations of:
  - addressing schemes (from schemes.yaml)
  - error sets         (from errors.yaml)

Supports:
  - minimum number of errors per variant
  - maximum number of errors per variant

Usage:
    python generate_variants.py
    python generate_variants.py --min-errors 2 --max-errors 2
    python generate_variants.py --max-errors 3
    python generate_variants.py --min-errors 0 --max-errors 2   # includes baseline
"""

import argparse
import itertools
from math import comb
from pathlib import Path
import random
import yaml


# ---------------------------------------------------------------------------
# Paths
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
    """Load a YAML file safely."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_variants(
    scheme_names: list[str],
    error_names: list[str],
    min_errors: int = 1,
    max_errors: int = 1,
    required_kinds: list[str] = None,   # <-- nouveau paramètre
    errors_def: dict = None,            # <-- nouveau paramètre
) -> list[dict]:
    """
    Generate all combinations of (scheme × subset of errors).

    Parameters:
        min_errors:
            Minimum number of errors per variant.
            0 -> includes baseline (no errors)

        max_errors:
            Maximum number of errors per variant.
            -1 -> all possible combinations (2^N)

    Examples:
        min=2, max=2 -> exactly 2 errors
        min=1, max=2 -> 1 or 2 errors
        min=0, max=0 -> only baseline
    """

    # If max_errors is -1, allow all combinations
    if max_errors < 0:
        max_errors = len(error_names)

    # Safety bounds
    min_errors = max(0, min_errors)
    max_errors = min(len(error_names), max_errors)
    error_subsets: list[list[str]] = []
    # required_kinds = ["wrong_ospf_cost"]  for this lab, we want to force this error type in all variants
    if required_kinds and errors_def:
        errors_by_kind = {}
        for name, cfg in errors_def["errors"].items():
            kind = cfg.get("kind")
            if kind in required_kinds:
                errors_by_kind.setdefault(kind, []).append(name)

        required_kind_groups = [
            errors_by_kind[k] for k in required_kinds if k in errors_by_kind
        ]
        optional_errors = [
            name for name in error_names
            if not any(name in group for group in required_kind_groups)
        ]
    else:
        required_kind_groups = []
        optional_errors = error_names

    # Generate combinations of errors
# après
    n_required = len(required_kind_groups)  # nombre de kinds, pas d'erreurs
    for size in range(max(min_errors, n_required), max_errors + 1):
        n_optional = size - n_required
        for req_combo in itertools.product(*required_kind_groups):
            for opt_combo in itertools.combinations(optional_errors, n_optional):
                error_subsets.append(list(req_combo) + list(opt_combo))

    # Build final variants (scheme × error subsets)
   

    all_pairs = [
        (scheme, error_set)
        for scheme in scheme_names
        for error_set in error_subsets
    ]
    random.shuffle(all_pairs)

    variants = []
    for variant_id, (scheme, error_set) in enumerate(all_pairs):
        variants.append({
            "id": variant_id,
            "scheme": scheme,
            "errors": error_set
        })

    return variants


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
        errors: [err1, err2]
        """
        if len(data) <= 5 and all(isinstance(i, str) and len(i) < 30 for i in data):
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
        "--min-errors",
        type=int,
        default=1,
        help="Minimum number of errors per variant (0 includes baseline).",
    )

    parser.add_argument(
        "--max-errors",
        type=int,
        default=1,
        help=(
            "Maximum number of errors per variant. "
            "-1 = all combinations (exponential!)."
        ),
    )

    args = parser.parse_args()

    # Load input data
    schemes_data = load_yaml(Path(args.schemes))
    errors_data  = load_yaml(Path(args.errors))

    scheme_names: list[str] = list(schemes_data["addressing_schemes"].keys())
    error_names:  list[str] = list(errors_data["errors"].keys())

    print(f"Schemes ({len(scheme_names)}): {scheme_names}")
    print(f"Errors  ({len(error_names)}): {error_names}")
    print(f"Min errors per variant: {args.min_errors}")
    print(f"Max errors per variant: {args.max_errors}")

    # Generate variants
    variants = build_variants(
        scheme_names,
        error_names,
        min_errors=args.min_errors,
        max_errors=args.max_errors,
        required_kinds=["wrong_mtu"],   # <-- force this error types in all variant
        errors_def=errors_data,
    )

    # Compute expected number of combinations
    min_e = max(0, args.min_errors)
    max_e = len(error_names) if args.max_errors < 0 else args.max_errors

    total_error_subsets = 0
    for k in range(min_e, max_e + 1):
        total_error_subsets += comb(len(error_names), k)

    expected = len(scheme_names) * total_error_subsets

    # assert len(variants) == expected, (
    #     f"Expected {expected}, got {len(variants)}"
    # )

    # Save output
    out_path = Path(args.out)
    dump_variants(variants, out_path)

    print(f"\n✓ {len(variants)} variants written to '{out_path}'")
    print(f"  ({len(scheme_names)} schemes × {total_error_subsets} error subsets)")


if __name__ == "__main__":
    main()