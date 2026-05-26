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


def copy_static_tree(destination: Path, base_topology: dict):
    if not TEMPLATE_STATIC_DIR.exists():
        return

    # copie tout sauf shared
    for item in TEMPLATE_STATIC_DIR.iterdir():
        if item.name == "shared":
            continue

        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    # copie shared dans chaque node
    shared_dir = TEMPLATE_STATIC_DIR / "shared"
    if shared_dir.exists():
        for node_name in base_topology["nodes"].keys():
            node_target = destination / node_name
            shutil.copytree(shared_dir, node_target, dirs_exist_ok=True)


def zip_directory(source_dir: Path, zip_path: Path):
    excluded_files = {"metadata.json"}

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

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


def normalize_session(a: str, b: str):
    return tuple(sorted((a, b)))


def resolve_expected_state(base_topology: dict, scheme: dict) -> dict:
    """
    Transforme le modèle logique en état réseau concret attendu.
    Supporte :
    - interfaces classiques avec host_offset
    - loopbacks /128 sans host_offset
    """
    nodes = base_topology["nodes"]
    subnets = scheme["subnets"]

    resolved = {}

    # 1) Interfaces
    for node_name, node_data in nodes.items():
        resolved[node_name] = {
            "image": node_data.get("image"),
            "daemons": node_data.get("daemons", []),
            "interfaces": {},
            "static_routes": [],
            "default_route": None,
            "sysctl": node_data.get("sysctl", {}),
        }

        for iface_name, iface_data in node_data.get("interfaces", {}).items():
            subnet_name = iface_data["subnet"]
            subnet_cidr = subnets[subnet_name]

            if "host_offset" in iface_data:
                cidr = host_cidr(subnet_cidr, iface_data["host_offset"])
            else:
                cidr = subnet_cidr

            resolved[node_name]["interfaces"][iface_name] = {
                "cidr": cidr,
                "up": True,
            }

    # 2) Routes statiques / default routes
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


def enrich_with_protocols(expected: dict, protocols: dict):
    """
    Ajoute template/ospf6/bgp à expected à partir de protocols.yaml
    """
    for node_name, proto in protocols.items():
        if node_name not in expected:
            continue

        expected[node_name]["template"] = proto.get("template")
        expected[node_name]["ospf6"] = proto.get("ospf6")
        expected[node_name]["bgp"] = None

        # enrichissement interfaces OSPF
        ospf6 = proto.get("ospf6")
        if ospf6 and "interfaces" in ospf6:
            for ifname, ifcfg in ospf6["interfaces"].items():
                if ifname in expected[node_name]["interfaces"]:
                    expected[node_name]["interfaces"][ifname]["ospf6"] = deepcopy(ifcfg)

        # enrichissement BGP
        bgp = proto.get("bgp")
        if bgp:
            bgp_state = {
                "local_as": bgp["local_as"],
                "router_id": bgp["router_id"],
                "networks": [],
                "ebgp_neighbors": [],
                "ibgp_neighbors": [],
               
            }

            for ifname in bgp.get("network_interfaces", []):
                bgp_state["networks"].append(expected[node_name]["interfaces"][ifname]["cidr"])

            for neigh in bgp.get("ebgp_neighbors", []):
                neigh_ip = ip_only(
                    expected[neigh["neighbor_node"]]["interfaces"][neigh["neighbor_interface"]]["cidr"]
                )
                bgp_state["ebgp_neighbors"].append({
                    "neighbor_node": neigh["neighbor_node"],
                    "ip": neigh_ip,
                    "remote_as": neigh["remote_as"],
                    "local_interface": neigh.get("local_interface"),
                    "neighbor_interface": neigh.get("neighbor_interface"),
                    "activate": neigh.get("activate", True),
                    "local_preference": neigh.get("local_preference"),
                    "relationship": neigh.get("relationship"),
                    #"import_policy": neigh.get("relationship"),
                    #"export_policy": neigh.get("relationship"),
                    "apply_import_route_map": True,
                    "import_route_map_direction": "in",
                    
                    "apply_export_route_map": True,
                    "export_route_map_type": "standard",
   
                })

            for neigh in bgp.get("ibgp_neighbors", []):
                neigh_ip = ip_only(expected[neigh["neighbor_node"]]["interfaces"]["lo"]["cidr"])
                bgp_state["ibgp_neighbors"].append({
                    "neighbor_node": neigh["neighbor_node"],
                    "ip": neigh_ip,
                    "remote_as": bgp["local_as"],
                    "update_source_lo": neigh.get("update_source", "lo") == "lo",
                    "activate": neigh.get("activate", True),
                    "next_hop_self": neigh.get("next_hop_self", True),
                })

            expected[node_name]["bgp"] = bgp_state


def remove_ibgp_session_one_way(state: dict, src_node: str, dst_node: str):
    bgp = state[src_node].get("bgp")
    if not bgp:
        return
    bgp["ibgp_neighbors"] = [
        n for n in bgp.get("ibgp_neighbors", [])
        if n["neighbor_node"] != dst_node
    ]


def remove_ibgp_session_both_ways(state: dict, a: str, b: str):
    remove_ibgp_session_one_way(state, a, b)
    remove_ibgp_session_one_way(state, b, a)


def find_ibgp_neighbor(state: dict, src_node: str, dst_node: str):
    bgp = state[src_node].get("bgp")
    if not bgp:
        return None
    for neigh in bgp.get("ibgp_neighbors", []):
        if neigh["neighbor_node"] == dst_node:
            return neigh
    return None

def find_ebgp_neighbor(state: dict, src_node: str, dst_node: str):
    bgp = state[src_node].get("bgp")
    if not bgp:
        return None

    for neigh in bgp.get("ebgp_neighbors", []):
        if neigh["neighbor_node"] == dst_node:
            return neigh

    return None

def apply_error(student_state: dict, error_name: str, errors_def: dict):
    err = errors_def["errors"][error_name]
    kind = err["kind"]

    # =========================
    # LAYER 3 / STATIC ERRORS
    # =========================
    if kind == "interface_prefixlen":
        node = err["node"]
        iface = err["interface"]
        old_cidr = student_state[node]["interfaces"][iface]["cidr"]
        student_state[node]["interfaces"][iface]["cidr"] = replace_prefixlen(
            old_cidr, err["new_prefixlen"]
        )

    elif kind == "route_prefixlen":
        node = err["node"]
        route_index = err["route_index"]
        old_to = student_state[node]["static_routes"][route_index]["to"]
        student_state[node]["static_routes"][route_index]["to"] = replace_prefixlen(
            old_to, err["new_prefixlen"]
        )

    elif kind == "interface_down":
        node = err["node"]
        iface = err["interface"]
        student_state[node]["interfaces"][iface]["up"] = False

    elif kind == "remove_default_route":
        node = err["node"]
        student_state[node]["default_route"] = None

    # =========================
    # iBGP ERRORS
    # =========================
    elif kind == "ibgp_remove_all":
        for node in err["nodes"]:
            if student_state[node].get("bgp"):
                student_state[node]["bgp"]["ibgp_neighbors"] = []

    elif kind == "ibgp_keep_only_direct_neighbors":
        direct_neighbors = err["direct_neighbors"]
        for node in err["nodes"]:
            if not student_state[node].get("bgp"):
                continue
            allowed = set(direct_neighbors.get(node, []))
            student_state[node]["bgp"]["ibgp_neighbors"] = [
                n for n in student_state[node]["bgp"].get("ibgp_neighbors", [])
                if n["neighbor_node"] in allowed
            ]

    elif kind == "ibgp_remove_sessions":
        for a, b in err["sessions"]:
            remove_ibgp_session_both_ways(student_state, a, b)

    elif kind == "ibgp_remove_next_hop_self":
        for node in err["nodes"]:
            bgp = student_state[node].get("bgp")
            if not bgp:
                continue
            for neigh in bgp.get("ibgp_neighbors", []):
                neigh["next_hop_self"] = False

    elif kind == "ibgp_remove_update_source":
        for node in err["nodes"]:
            bgp = student_state[node].get("bgp")
            if not bgp:
                continue
            for neigh in bgp.get("ibgp_neighbors", []):
                neigh["update_source_lo"] = False

    elif kind == "ibgp_wrong_remote_as":
        for a, b in err["sessions"]:
            neigh_a = find_ibgp_neighbor(student_state, a, b)
            neigh_b = find_ibgp_neighbor(student_state, b, a)
            if neigh_a:
                neigh_a["remote_as"] = err["wrong_as"]
            if neigh_b:
                neigh_b["remote_as"] = err["wrong_as"]

    # =========================
    # eBGP IMPORT ERRORS
    # =========================
    elif kind == "bgp_wrong_local_pref":
        node = err["node"]
        for dst in err["neighbors"]:
            neigh = find_ebgp_neighbor(student_state, node, dst)
            if neigh:
                neigh["local_preference"] = err["value"]

    elif kind == "bgp_remove_local_pref":
        node = err["node"]
        for dst in err["neighbors"]:
            neigh = find_ebgp_neighbor(student_state, node, dst)
            if neigh:
                neigh["local_preference"] = None
                neigh["apply_import_route_map"] = False

    elif kind == "bgp_remove_route_map":
        node = err["node"]
        for dst in err["neighbors"]:
            neigh = find_ebgp_neighbor(student_state, node, dst)
            if neigh:
                neigh["apply_import_route_map"] = False
                neigh["apply_export_route_map"] = False

    elif kind == "bgp_wrong_route_map_direction":
        node = err["node"]
        for dst in err["neighbors"]:
            neigh = find_ebgp_neighbor(student_state, node, dst)
            if neigh:
                #print(f"Applying wrong_route_map_direction error on {node} -> {dst}")
                neigh["import_route_map_direction"] = "out"

    # =========================
    # eBGP EXPORT ERRORS (COMMUNITIES / LEAKS)
    # =========================
    elif kind == "bgp_export_all_to_peer":
        node = err["node"]
        neighbor = err["neighbor"]

        neigh = find_ebgp_neighbor(student_state, node, neighbor)
        if neigh:
            neigh["export_route_map_type"] = "all"

    elif kind == "bgp_export_provider_to_peer":
        node = err["node"]
        neighbor = err["neighbor"]

        neigh = find_ebgp_neighbor(student_state, node, neighbor)
        if neigh:
            neigh["export_route_map_type"] = "provider_leak"

    elif kind == "bgp_remove_export_filter": # SAME AS EXPORT ALL TO PEER, BUT DIFFERENT NAME FOR CLARITY
        node = err["node"]
        neighbor = err["neighbor"]

        neigh = find_ebgp_neighbor(student_state, node, neighbor)
        if neigh:
            neigh["export_route_map_type"] = "all"

    else:
        raise ValueError(f"Type d'erreur non supporté: {kind}")


def create_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DYNAMIC_DIR)),
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render_generic_frr_configs(env: Environment, variant_dir: Path, expected: dict, student: dict):
    """
    Rend les frr.conf à partir de 2 templates génériques :
    - router_ospf6_bgp.conf.j2
    - router_bgp_only.conf.j2
    """
    template_map = {
        "router_ospf6_bgp": "router_ospf6_bgp.conf.j2",
        "router_bgp_only": "router_bgp_only.conf.j2",
    }

    for node_name, node in student.items():
        template_key = node.get("template")
        if not template_key:
            continue

        template_name = template_map.get(template_key)
        if not template_name:
            raise ValueError(f"Template inconnu pour {node_name}: {template_key}")

        template = env.get_template(template_name)
        output_path = variant_dir / node_name / "etc" / "frr" / "frr.conf"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        context = {
            "expected": expected,
            "student": student,
            "node_name": node_name,
            "node": node,
        }

        rendered = template.render(**context).rstrip() + "\n"
        output_path.write_text(rendered, encoding="utf-8")


def render_generic_startups(env: Environment, variant_dir: Path, expected: dict, student: dict):
    template = env.get_template("router.startup.j2")

    for node_name, node in student.items():
        output_path = variant_dir / f"{node_name}.startup"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        context = {
            "expected": expected,
            "student": student,
            "node_name": node_name,
            "node": node,
        }

        rendered = template.render(**context).rstrip() + "\n"
        output_path.write_text(rendered, encoding="utf-8")

def render_dynamic_files(env, variant_dir, expected, student, variant_id):
    """
    Rend tous les .j2 sauf les templates génériques FRR,
    puis rend les frr.conf via les templates génériques.
    """
    generic_template_names = {
        "router_ospf6_bgp.conf.j2",
        "router_bgp_only.conf.j2",
        "router.startup.j2",
    }

    for template_path in TEMPLATE_DYNAMIC_DIR.rglob("*.j2"):
        if template_path.name in generic_template_names:
            continue

        relative_template_path = template_path.relative_to(TEMPLATE_DYNAMIC_DIR)
        output_relative_path = relative_template_path.with_suffix("")

        if output_relative_path.name == "correction_admin.yaml":
            output_relative_path = output_relative_path.with_name(
                f"correction_admin_{variant_id}.yaml"
            )

        output_path = variant_dir / output_relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = env.get_template(relative_template_path.as_posix())

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
            "ip_only": ip_only,
        }

        rendered = template.render(**context).rstrip() + "\n"
        output_path.write_text(rendered, encoding="utf-8")

        if output_path.name.startswith("correction_admin"):
            dest = CORRECTIONS_ADMIN_DIR / output_path.name
            shutil.copy2(output_path, dest)

    render_generic_frr_configs(env, variant_dir, expected, student)
    render_generic_startups(env, variant_dir, expected, student)


def build_one_variant(env: Environment, variant: dict, base_topology: dict, protocols: dict, schemes: dict, errors_def: dict):
    variant_id = variant["id"]
    scheme_name = variant["scheme"]
    error_names = variant.get("errors", [])

    if scheme_name not in schemes:
        raise ValueError(f"Schéma inconnu dans variant {variant_id}: {scheme_name}")

    scheme = schemes[scheme_name]
    expected = resolve_expected_state(base_topology, scheme)
    enrich_with_protocols(expected, protocols)
    student = deepcopy(expected)

    for error_name in error_names:
        if error_name not in errors_def["errors"]:
            raise ValueError(f"Erreur inconnue dans variant {variant_id}: {error_name}")
        apply_error(student, error_name, errors_def)

    variant_dir = VARIANTS_DIR / f"variant_{variant_id}"
    variant_dir.mkdir(parents=True, exist_ok=True)

    copy_static_tree(variant_dir, base_topology)
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
    protocols = load_yaml(MODEL_DIR / "protocols.yaml")["protocols"]
    schemes = load_yaml(MODEL_DIR / "schemes.yaml")["addressing_schemes"]
    errors_def = load_yaml(MODEL_DIR / "errors.yaml")
    variants = load_yaml(MODEL_DIR / "variants.yaml")["variants"]

    manifest = []

    for variant in variants:
        manifest_entry = build_one_variant(
            env=env,
            variant=variant,
            base_topology=base_topology,
            protocols=protocols,
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