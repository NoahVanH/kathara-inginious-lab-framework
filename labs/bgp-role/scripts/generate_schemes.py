#!/usr/bin/env python3
"""
generate_schemes.py
Generates a schemes.yaml (to OUTPUT_PATH) addressing file from a Kathara lab.conf (located in LAB_CONF_PATH).

Usage:
    python3 generate_schemes.py [--ipv4] [--ipv6] [--output schemes.yaml]
    python3 generate_schemes.py                # interactive mode

IPv6 schemes generated:
  scheme_db8_a  : 2001:db8:<rand2B>::/64  /  loopbacks 2001:db8:1::<id>/128
  scheme_db8_b  : 2001:db8:<letter><rand2B>::/64  /  loopbacks 2001:db8:100::<id>/128
  scheme_3fff_a : 3fff:<rand2B>::/64  /  loopbacks 3fff:1::<id>/128
  scheme_3fff_b : 3fff:<letter><rand2B>::/64  /  loopbacks 3fff:100::<id>/128

IPv4 schemes generated (configurable prefixes):
  scheme_v4_a   : <prefix>.0.0/24 one octet per subnet (sequential or random)
  scheme_v4_b   : <prefix2>.0.0/24 with different base

Options:
  --ipv4              Generate IPv4 schemes
  --ipv6              Generate IPv6 schemes
  --output FILE       Output file (default: schemes.yaml)
  --ipv4-prefix A.B   First two octets for v4 scheme_a (default: 10.0)
  --ipv4-prefix2 A.B  First two octets for v4 scheme_b (default: 172.16)
  --lo-prefix A.B.C   First three octets for v4 loopbacks scheme_a (default: 10.0.0)
  --lo-prefix2 A.B.C  First three octets for v4 loopbacks scheme_b (default: 172.16.0)
  --seed INT          Random seed for reproducibility (optional)
"""

import re
import random
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
LAB_CONF_PATH = ROOT_DIR / "template" / "static" / "lab.conf"
OUTPUT_PATH = ROOT_DIR / "variation_model" / "schemes.yaml"
# ---------------------------------------------------------------------------
# lab.conf parser
# ---------------------------------------------------------------------------

def parse_lab_conf(path: str) -> dict:
    """
    Returns:
        {
            'nodes': ['r1', 'r2', ..., 'd1'],   # ordered
            'domains': ['A', 'B', ..., 'K'],    # ordered, unique collision domains
        }
    """
    nodes_order = []
    nodes_seen = set()
    domains_order = []
    domains_seen = set()

    with open(LAB_CONF_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Match  nodename[key]="value"
            m = re.match(r'^(\w+)\[(\w+)\]\s*=\s*"([^"]*)"', line)
            if not m:
                continue
            node, key, value = m.group(1), m.group(2), m.group(3)

            # Skip LAB_* meta keys
            if node.upper().startswith('LAB'):
                continue

            if node not in nodes_seen:
                nodes_seen.add(node)
                nodes_order.append(node)

            # Numeric keys are interface→domain assignments
            if key.isdigit():
                domain = value.strip()
                if domain and domain not in domains_seen:
                    domains_seen.add(domain)
                    domains_order.append(domain)

    return {'nodes': nodes_order, 'domains': sorted(domains_order)}


# ---------------------------------------------------------------------------
# Address generators
# ---------------------------------------------------------------------------

def rand_hex2(used: set) -> str:
    """Return a unique random 16-bit hex group (exactly 4 hex chars, e.g. 'a3b2')."""
    while True:
        v = random.randint(0x1000, 0xFFFF)   # always 4 hex digits
        h = format(v, 'x')
        if h not in used:
            used.add(h)
            return h


def rand_hex_prefix(used: set) -> str:
    """Return a unique random 8-bit hex group (exactly 2 hex chars, e.g. '2d')."""
    HEX_CHARS = '0123456789abcdef'
    while True:
        p = random.choice(HEX_CHARS[1:]) + random.choice(HEX_CHARS)  # avoid leading 0
        if p not in used:
            used.add(p)
            return p



def build_node_ids(nodes: list) -> dict:
    """
    Assign unique loopback IDs to nodes.
    Uses the numeric suffix when unique across all nodes (r1→1, r2→2…).
    Any collision gets the next available integer instead.
    Returns {node_name: id}.
    """
    id_map = {}
    used_ids = set()
    conflicts = []

    for node in nodes:
        m = re.match(r'^[a-zA-Z]+(\d+)$', node)
        if m:
            nid = int(m.group(1))
            if nid not in used_ids:
                id_map[node] = nid
                used_ids.add(nid)
            else:
                conflicts.append(node)
        else:
            conflicts.append(node)

    counter = 1
    for node in conflicts:
        while counter in used_ids:
            counter += 1
        id_map[node] = counter
        used_ids.add(counter)
        counter += 1

    return id_map


# ---- IPv6 ----

def ipv6_schemes(domains: list, nodes: list) -> dict:
    schemes = {}

    # Prefixes: (subnet_base_fn, loopback_base)
    variants = [
        ('db8_a',  False, '2001:db8:1',   lambda p, h: f'2001:db8:{h}::/64'),
        ('db8_b',  True,  '2001:db8:100', lambda p, h: f'2001:db8:{p}:{h}::/64'),
        ('3fff_a', False, '3fff:1',       lambda p, h: f'3fff:{h}::/64'),
        ('3fff_b', True,  '3fff:100',     lambda p, h: f'3fff:{p}:{h}::/64'),
    ]

    node_ids = build_node_ids(nodes)

    for name, use_prefix, lo_base, subnet_fn in variants:
        used_hex = set()
        used_pfx = set()
        subnets = {}

        for d in domains:
            h = rand_hex2(used_hex)
            p = rand_hex_prefix(used_pfx) if use_prefix else ''
            subnets[f'{d}_net'] = subnet_fn(p, h)

        for n in nodes:
            nid = node_ids[n]
            subnets[f'{n}_lo'] = f'{lo_base}::{hex(nid)[2:]}/128'

        schemes[f'scheme_{name}'] = {'subnets': subnets}

    return schemes


# ---- IPv4 ----

def ipv4_schemes(domains: list, nodes: list,
                 prefix_a: str = '10.0',
                 prefix_b: str = '172.16',
                 lo_prefix_a: str = '10.0.0',
                 lo_prefix_b: str = '172.16.0') -> dict:
    """
    scheme_v4_a : <prefix_a>.<rand_octet>.0/24   subnets
                  <lo_prefix_a>.<id>/32           loopbacks
    scheme_v4_b : <prefix_b>.<rand_octet>.0/24   subnets
                  <lo_prefix_b>.<id>/32           loopbacks
    """
    schemes = {}

    for scheme_name, prefix, lo_pfx in [('scheme_v4_a', prefix_a, lo_prefix_a), ('scheme_v4_b', prefix_b, lo_prefix_b)]:
        used_thirds = set()
        subnets = {}

        for d in domains:
            while True:
                third = random.randint(1, 254)
                if third not in used_thirds:
                    used_thirds.add(third)
                    break
            subnets[f'{d}_net'] = f'{prefix}.{third}.0/24'

        node_ids = build_node_ids(nodes)
        for n in nodes:
            nid = node_ids[n]
            subnets[f'{n}_lo'] = f'{lo_pfx}.{nid}/32'

        schemes[scheme_name] = {'subnets': subnets}

    return schemes


# ---------------------------------------------------------------------------
# YAML writer  (hand-rolled to avoid dependency on ruamel/pyyaml ordering)
# ---------------------------------------------------------------------------

def dict_to_yaml(data: dict, indent: int = 0) -> str:
    lines = []
    pad = ' ' * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{pad}{key}:')
            lines.append(dict_to_yaml(value, indent + 2))
        else:
            lines.append(f'{pad}{key}: {value}')
    return '\n'.join(lines)


def build_yaml(all_schemes: dict) -> str:
    """Build the full YAML string."""
    lines = ['addressing_schemes:']
    for scheme_name, scheme_data in all_schemes.items():
        lines.append(f'  {scheme_name}:')
        lines.append(f'    subnets:')
        subnets = scheme_data['subnets']

        # Separate nets from loopbacks for a blank line between them
        nets = {k: v for k, v in subnets.items() if k.endswith('_net')}
        los  = {k: v for k, v in subnets.items() if k.endswith('_lo')}

        for k, v in nets.items():
            lines.append(f'      {k}: {v}')
        if los:
            lines.append('')
        for k, v in los.items():
            lines.append(f'      {k}: {v}')
        lines.append('')   # blank line between schemes

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description='Generate schemes.yaml from a Kathara lab.conf')
    p.add_argument('lab_conf', nargs='?', default='lab.conf',
                   help='Path to lab.conf (default: lab.conf)')
    p.add_argument('--ipv4', action='store_true', help='Generate IPv4 schemes')
    p.add_argument('--ipv6', action='store_true', help='Generate IPv6 schemes')
    p.add_argument('--output', default='schemes.yaml',
                   help='Output file (default: schemes.yaml)')
    p.add_argument('--ipv4-prefix',  default='10.0',
                   help='First two octets for IPv4 scheme_a (default: 10.0)')
    p.add_argument('--ipv4-prefix2', default='172.16',
                   help='First two octets for IPv4 scheme_b (default: 172.16)')
    p.add_argument('--lo-prefix',  default='10.0.0',
                   help='First three octets for IPv4 loopbacks scheme_a (default: 10.0.0)')
    p.add_argument('--lo-prefix2', default='172.16.0',
                   help='First three octets for IPv4 loopbacks scheme_b (default: 172.16.0)')
    p.add_argument('--seed', type=int, default=None,
                   help='Random seed for reproducibility')
    return p.parse_args()


def interactive_mode(lab_conf_path: str) -> tuple:
    """Ask user what to generate when no flags given. Returns (do_ipv6, do_ipv4)."""
    print('\n=== schemes.yaml generator ===')
    print(f'Lab conf : {lab_conf_path}')
    print()
    print('What do you want to generate?')
    print('  1) IPv6 only')
    print('  2) IPv4 only')
    print('  3) Both IPv4 and IPv6')
    choice = input('Choice [1/2/3, default=3]: ').strip() or '3'
    return (
        choice in ('1', '3'),  # ipv6
        choice in ('2', '3'),  # ipv4
    )


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    lab_conf_path = LAB_CONF_PATH
    if not Path(lab_conf_path).exists():
        print(f'Error: lab.conf not found at "{lab_conf_path}"', file=sys.stderr)
        sys.exit(1)

    lab = parse_lab_conf(lab_conf_path)
    domains = lab['domains']
    nodes   = lab['nodes']

    print(f'Parsed lab.conf:')
    print(f'  Nodes   : {", ".join(nodes)}')
    print(f'  Domains : {", ".join(domains)}')

    # Determine what to generate
    do_ipv6, do_ipv4 = args.ipv6, args.ipv4
    if not do_ipv6 and not do_ipv4:
        do_ipv6, do_ipv4 = interactive_mode(lab_conf_path)

    all_schemes = {}

    if do_ipv6:
        all_schemes.update(ipv6_schemes(domains, nodes))
        print(f'  → {len([k for k in all_schemes if "3fff" in k or "db8" in k])} IPv6 schemes generated')

    if do_ipv4:
        v4 = ipv4_schemes(domains, nodes,
                          prefix_a=args.ipv4_prefix,
                          prefix_b=args.ipv4_prefix2,
                          lo_prefix_a=args.lo_prefix,
                          lo_prefix_b=args.lo_prefix2)
        all_schemes.update(v4)
        print(f'  → 2 IPv4 schemes generated')

    yaml_content = build_yaml(all_schemes)

    #out_path = args.output
    out_path = OUTPUT_PATH
    with open(out_path, 'w') as f:
        f.write(yaml_content)

    print(f'\nDone! Written to: {out_path}')


if __name__ == '__main__':
    main()