# kathara-inginious-lab-framework

> Framework for generating Kathará network lab variants with automatic grading on INGInious.

Developed as part of a Master's thesis at UCLouvain by Noah Van Horenbeke, under the supervision of Olivier Bonaventure.

Instead of building a network configuration from scratch, students receive a pre-configured lab containing intentional errors to identify and fix. Each student is assigned a unique **variant**, a lab instance with a specific combination of injected errors and IP addressing scheme, ensuring fairness and discouraging solution sharing.

---

## Quick Start

```bash
cd labs/<lab-name>
python3 scripts/build_variants.py
```

Output is generated in `build/`:
```
build/
├── zips/               # ZIP archives distributed to students
├── variants/           # Full lab instances (useful for debugging)
├── corrections_admin/  # Per-variant test files for INGInious
└── manifest.json       # Summary of all generated variants
```

---

## Prerequisites

- Python 3.10+
- `pip install jinja2 pyyaml`
- [Kathará](https://www.kathara.org/) (for local testing)

---

## Repository Structure

```
kathara-inginious-lab-framework/
├── inginious/             # Resources for INGInious
└── labs/
    ├── 0-base-project/
    ├── ospf-adjacence/
    ├── ...
    └── each lab contains:
        ├── template/
        │   ├── static/        # Files copied as-is into each (lab.conf, topo.svg ...)
        │   └── dynamic/       # Jinja2 templates
        ├── variation_model/   # Abstract lab model 
        ├── scripts/           # Generation scripts
        ├── correction/        # Lab without errors, ready to test with kathara_lab_checker
        └── build/             # Generated output (git-ignored)
```

---

## Labs



| Lab | Description |
|-----|-------------|
| Static routing | Debug static routes with wrong prefixes, masks or next-hops on a simple topology. |
| BGP simple peering | Configure and fix eBGP sessions between stub ASes, observe prefix propagation. |
| iBGP | Fix an iBGP full-mesh where some sessions are missing or have wrong next-hop handling. |
| BGP Anycast with secure DNS (DoT/DoH) | Observe how BGP routes clients to the nearest DNS server sharing an anycast address, and compare DNS over TLS vs DNS over HTTPS. |
| BGP peering relationships | Debug route filtering between providers, peers and customers using community-based export policies. |
| BGP roles (RFC 9234) | Debug BGP roles (customer/provider/peer) and observe how route leaks are automatically prevented. |
| OSPF adjacencies | Identify and fix configuration errors that prevent OSPFv3 adjacencies from reaching Full state. |
| OSPF shortest path | Configure OSPFv3 costs to achieve a given set of expected shortest paths. |
| Network attacks : SYN Flood, Port Scan, DNS Reflection | Reproduce three classic network attacks, observe their traffic signatures. |


---

## How It Works

### 1. Define the lab model (`variation_model/`)

| File | Purpose |
|------|---------|
| `base_topology.yaml` | Logical network structure (nodes, interfaces, routes) (IP-independent) |
| `schemes.yaml` | IP addressing schemes (genereted automatically with `scripts/generate_schemes.py`) |
| `protocols.yaml` | Protocol-specific parameters (BGP neighbors, OSPF areas, etc.) |
| `errors.yaml` | Catalog of injectable errors |
| `variants.yaml` | Variant combinations generated automatically with `scripts/gen_all_combination_variants_yaml.py` |

**Example — `errors.yaml`:**
```yaml
errors:
  r1_wrong_route_mask:
    node: r1
    kind: route_prefixlen
    route_index: 0
    new_prefixlen: 30
```
For more example see [apply_error()](https://github.com/NoahVanH/kathara-inginious-lab-framework/blob/7d9173523856450f1a7a17df6ea6aaa3c61be0b4/labs/0-base-project/scripts/build_variants.py#L329) function.

### 2. Write Jinja2 templates (`template/dynamic/`)

| Template | Output |
|----------|--------|
| `router.startup.j2` | Startup commands (IP assignment) |
| `router.conf.j2` | FRRouting configuration |
| `correction_admin.yaml.j2` | Full test suite (used on INGInious) |
| `correction_student.yaml.j2` | Reduced test suite (distributed to students) |

### 3. Generate variants

```bash
python3 scripts/build_variants.py 
```


---

## INGInious Integration

Each generated lab is designed to be deployed on [INGInious](https://inginious.info.ucl.ac.be/).
The `corrections_admin/` directory contains the per-variant test files to upload to the INGInious task.

The grading pipeline is handled by the `run` script included in each INGInious task, which:

1. Identifies the student's assigned variant
2. Restores the original topology (anti-cheat)
3. Runs `kathara-lab-checker` on the submitted archive
4. Generates structured feedback

---

## Adding a New Lab

1. Copy an existing lab directory as a starting point.
2. Define your topology in `variation_model/base_topology.yaml` and `static/lab.conf`.

3. Define injectable errors in the `errors.yaml`

4. Generate the different schemes automatically using `scripts/generate_schemes.py`.

5. Generate `variants.yaml` using `scripts/gen_all_combination_variants_yaml.py`.

6. Adapt the Jinja2 templates in `dynamic/`.

7. Run `build_variants.py`.



### Optional

- Update the `build_variants` script if you introduce new error types that need to be handled explicitly.

---

## License

See `LICENSE`.

---

## Author

Noah Van Horenbeke, UCLouvain, 2025–2026  
Email : tfe@boite.top  
Promoter : Olivier Bonaventure