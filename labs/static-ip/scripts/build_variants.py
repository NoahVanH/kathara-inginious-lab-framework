import subprocess
from copy import deepcopy
from pathlib import Path
import ipaddress
import json
import shutil
import zipfile

import yaml
from jinja2 import Environment, FileSystemLoader


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_STATIC_DIR = ROOT_DIR / "template" / "static"
TEMPLATE_DYNAMIC_DIR = ROOT_DIR / "template" / "dynamic"
MODEL_DIR = ROOT_DIR / "variation_model"
BUILD_DIR = ROOT_DIR / "build"
VARIANTS_DIR = BUILD_DIR / "variants"
ZIPS_DIR = BUILD_DIR / "zips"
MANIFEST_PATH = BUILD_DIR / "manifest.json"
CORRECTIONS_ADMIN_DIR = BUILD_DIR / "corrections_admin"

def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_clean_build_dirs():
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
    ZIPS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_ADMIN_DIR.mkdir(parents=True, exist_ok=True)

def copy_static_tree(destination: Path):
    if TEMPLATE_STATIC_DIR.exists():
        shutil.copytree(TEMPLATE_STATIC_DIR, destination, dirs_exist_ok=True)


def zip_directory(source_dir: Path, zip_path: Path):
    excluded_files = {"metadata.json"}

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Exclude files not for students
            if "admin" in file_path.name or file_path.name in excluded_files:
                continue

            zf.write(file_path, arcname=file_path.relative_to(source_dir))


def host_cidr(subnet_cidr: str, host_offset: int) -> str:
    net = ipaddress.ip_network(subnet_cidr, strict=True)
    ip = net.network_address + host_offset
    return f"{ip}/{net.prefixlen}"


def ip_only(cidr: str) -> str:
    return cidr.split("/")[0]


def replace_prefixlen(cidr: str, new_prefixlen: int) -> str:
    return f"{ip_only(cidr)}/{new_prefixlen}"


def resolve_expected_state(base_topology: dict, scheme: dict) -> dict:
    """
    Transforme le modèle logique en état réseau concret attendu.
    """
    nodes = base_topology["nodes"]
    subnets = scheme["subnets"]

    resolved = {}

    # 1) Résoudre les interfaces
    for node_name, node_data in nodes.items():
        resolved[node_name] = {
            "interfaces": {},
            "static_routes": [],
            "default_route": None,
            "sysctl": node_data.get("sysctl", {}),
        }

        for iface_name, iface_data in node_data.get("interfaces", {}).items():
            subnet_name = iface_data["subnet"]
            subnet_cidr = subnets[subnet_name]
            cidr = host_cidr(subnet_cidr, iface_data["host_offset"])

            resolved[node_name]["interfaces"][iface_name] = {
                "cidr": cidr,
                "up": True,
            }

    # 2) Résoudre default routes et routes statiques
    for node_name, node_data in nodes.items():
        if "default_route" in node_data:
            via_node = node_data["default_route"]["via_node"]
            via_iface = node_data["default_route"]["via_interface"]
            resolved[node_name]["default_route"] = ip_only(
                resolved[via_node]["interfaces"][via_iface]["cidr"]
            )

        for route in node_data.get("static_routes", []):
            to_subnet_name = route["to_subnet"]
            to_subnet_cidr = subnets[to_subnet_name]

            via_node = route["via_node"]
            via_iface = route["via_interface"]
            via_ip = ip_only(resolved[via_node]["interfaces"][via_iface]["cidr"])

            resolved[node_name]["static_routes"].append({
                "to": to_subnet_cidr,
                "via": via_ip,
            })

    return resolved


def apply_error(student_state: dict, error_name: str, errors_def: dict):
    err = errors_def["errors"][error_name]
    node = err["node"]
    kind = err["kind"]

    if kind == "interface_prefixlen":
        iface = err["interface"]
        old_cidr = student_state[node]["interfaces"][iface]["cidr"]
        student_state[node]["interfaces"][iface]["cidr"] = replace_prefixlen(
            old_cidr, err["new_prefixlen"]
        )

    elif kind == "route_prefixlen":
        route_index = err["route_index"]
        old_to = student_state[node]["static_routes"][route_index]["to"]
        student_state[node]["static_routes"][route_index]["to"] = replace_prefixlen(
            old_to, err["new_prefixlen"]
        )

    elif kind == "interface_down":
        iface = err["interface"]
        student_state[node]["interfaces"][iface]["up"] = False

    elif kind == "remove_default_route":
        student_state[node]["default_route"] = None

    else:
        raise ValueError(f"Type d'erreur non supporté: {kind}")


def create_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DYNAMIC_DIR)),
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render_dynamic_files(env, variant_dir, expected, student, variant_id):
    """
    Rend tous les fichiers .j2 trouvés dans template/dynamic
    en conservant la structure des dossiers.
    """
    for template_path in TEMPLATE_DYNAMIC_DIR.rglob("*.j2"):
        relative_template_path = template_path.relative_to(TEMPLATE_DYNAMIC_DIR)
        output_relative_path = relative_template_path.with_suffix("")

        # rename dynamique pour correction_admin
        if output_relative_path.name == "correction_admin.yaml":
            output_relative_path = output_relative_path.with_name(
                f"correction_admin_{variant_id}.yaml"
            )

        output_path = variant_dir / output_relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = env.get_template(relative_template_path.as_posix())

        # Déterminer si on rend un fichier machine spécifique
        # Ex:
        # - r1.startup.j2 -> node_name = r1
        # - r1/frr.conf.j2 -> node_name = r1
        node_name = None
        parts = relative_template_path.parts

        if len(parts) == 1 and relative_template_path.name.endswith(".startup.j2"):
            node_name = relative_template_path.name.split(".")[0]
        elif len(parts) >= 2 and parts[0] in student:
            node_name = parts[0]

        context = {
            "expected": expected,
            "student": student,
            "node_name": node_name,
            "node": student.get(node_name) if node_name else None,
        }

        rendered = template.render(**context).rstrip() + "\n"
        output_path.write_text(rendered, encoding="utf-8")
        if output_path.name.startswith("correction_admin"):
            dest = CORRECTIONS_ADMIN_DIR / output_path.name
            shutil.copy2(output_path, dest)

def build_one_variant(env: Environment, variant: dict, base_topology: dict, schemes: dict, errors_def: dict):
    variant_id = variant["id"]
    scheme_name = variant["scheme"]
    error_names = variant.get("errors", [])

    if scheme_name not in schemes:
        raise ValueError(f"Schéma inconnu dans variant {variant_id}: {scheme_name}")

    scheme = schemes[scheme_name]
    expected = resolve_expected_state(base_topology, scheme)
    student = deepcopy(expected)

    for error_name in error_names:
        if error_name not in errors_def["errors"]:
            raise ValueError(f"Erreur inconnue dans variant {variant_id}: {error_name}")
        apply_error(student, error_name, errors_def)

    variant_dir = VARIANTS_DIR / f"variant_{variant_id}"
    variant_dir.mkdir(parents=True, exist_ok=True)

    copy_static_tree(variant_dir)
    render_dynamic_files(env, variant_dir, expected, student, variant_id)

    metadata = {
        "variant_id": variant_id,
        "scheme": scheme_name,
        "errors": error_names,
    }
    (variant_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    zip_path = ZIPS_DIR / f"variant_{variant_id}.zip"
    zip_directory(variant_dir, zip_path)

    return {
        "variant_id": variant_id,
        "scheme": scheme_name,
        "errors": error_names,
        "variant_dir": str(variant_dir.relative_to(ROOT_DIR)),
        "zip_path": str(zip_path.relative_to(ROOT_DIR)),
    }


def main():
    ensure_clean_build_dirs()
    env = create_jinja_env()

    base_topology = load_yaml(MODEL_DIR / "base_topology.yaml")
    schemes = load_yaml(MODEL_DIR / "schemes.yaml")["addressing_schemes"]
    errors_def = load_yaml(MODEL_DIR / "errors.yaml")
    variants = load_yaml(MODEL_DIR / "variants.yaml")["variants"]

    #or automaticaly
    #variants = generate_variants(schemes, errors_def)
    manifest = []

    for variant in variants:
        manifest_entry = build_one_variant(
            env=env,
            variant=variant,
            base_topology=base_topology,
            schemes=schemes,
            errors_def=errors_def,
        )
        manifest.append(manifest_entry)

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    print(f"OK: {len(manifest)} variantes générées")
    print(f"- Variants: {VARIANTS_DIR}")
    print(f"- Zips: {ZIPS_DIR}")
    print(f"- Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    subprocess.run(["python3", str(ROOT_DIR / "scripts" / "clean_build.py")], check=True)

    main()