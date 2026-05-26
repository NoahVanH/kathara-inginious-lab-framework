#!/usr/bin/env python3
"""
Script to analyze the results_failed.csv file for the lab
Groups tests by category for a more synthetic display
Adds category-specific hints in case of errors
"""

import csv
import sys
import os
from collections import defaultdict
from gettext import gettext as _

# Use for multi-language support with Babel. These strings will be extracted for translation, but are not used directly in the code.
def _babel_strings():
    _("Device existence")
    _("Startup files")
    _("Collision domains")
    _("IP addresses")
    _("Daemon status")
    _("BGP network announcements")
    _("BGP peer status")
    _("BGP routing table")
    _("BGP next-hop validation")
    _("Connectivity (ping)")
    _("Routing")
    _("Other tests")
    _("✅ Success")
    _("❌ Failure")
    _("⚠️ Partial")
    _("💡 Check that all routers and hosts are properly defined in lab.conf")
    _("💡 Make sure the .startup files are present")
    _("💡 Check the interface configuration and the connections between devices in the lab")
    _("💡 Check the IP addresses configured on each interface (CIDR format) and verify that they match the addressing plan")
    _("💡 Verify that BGP daemon (bgpd) is running on all routers")
    _("💡 Check BGP network announcements in the configuration (network statements under router bgp)")
    _("💡 Verify BGP peer configurations: remote AS, neighbor IP addresses, and ensure peers are reachable")
    _("💡 Examine the BGP routing table to ensure routes are being learned and advertised correctly")
    _("💡 Check BGP next-hop reachability and verify that next-hop addresses are resolvable")
    _("💡 Check the static routes, active interfaces, and IP addresses of remote devices")
    _("💡 Inspect the routing tables (ip route) and make sure the static routes are correctly defined")
    _("💡 Check the detailed error messages below for more information")
    _("💡 Check the configuration of the concerned devices")
    _("ERROR: CSV file not found")
    _("ERROR while analyzing the CSV")
    _("and")
    _("other error(s)")
    _("Usage: python3 extractFeedbackFromCSV.py <csv_file>")
    _("BGP export policy")
    _("BGP import policy")
    _("BGP local preference and best path selection")
    _("💡 Check the export policy configuration (route-maps, prefix-lists) and ensure that the AS advertises the correct routes")
    _("💡 Check the import policy configuration (route-maps, prefix-lists) and ensure that the AS receives/accepts the correct routes from its neighbors")
    _("💡 Check the local preference values and ensure that the best paths are correct")
    # OSPF strings
    _("OSPF adjacencies")
    _("OSPF router-id")
    _("OSPF interface state")
    _("OSPF routes and paths")
    _("Interface state and prefix")
    _("💡 Check OSPF adjacencies: verify that all expected neighbors are in Full state")
    _("💡 Check the router-id configuration. Each router must have a unique router-id")
    _("💡 Check the OSPF interface configuration: cost, passive-interface, area, network type. An interface mistakenly set to passive will not form adjacencies")
    _("💡 Check the OSPF routing table and the SPF tree. A wrong cost on an interface can change the best path used to reach a destination")
    _("💡 Check that interfaces are UP and have the correct IPv6 prefix configured. A wrong prefix length prevents adjacencies from forming")

def get_hint_for_category(categorie, stats):
    total = stats['total']
    reussis = stats['reussis']

    if reussis == total:
        return ""

    hints = {
        'Device existence': "💡 Check that all routers and hosts are properly defined in lab.conf",
        'Startup files': "💡 Make sure the .startup files are present",
        'Collision domains': "💡 Check the interface configuration and the connections between devices in the lab",
        'IP addresses': "💡 Check the IP addresses configured on each interface (CIDR format) and verify that they match the addressing plan",
        'Daemon status': "💡 Verify that daemons (bgpd, zebra, ospf6d) are running on all routers",
        'BGP network announcements': "💡 Check BGP network announcements in the configuration (network statements under router bgp)",
        'BGP peer status': "💡 Verify BGP peer configurations: remote AS, neighbor IP addresses, and ensure peers are reachable",
        'BGP routing table': "💡 Examine the BGP routing table to ensure routes are being learned and advertised correctly",
        'BGP next-hop validation': "💡 Check BGP next-hop reachability and verify that next-hop addresses are resolvable",
        'BGP export policy': "💡 Check the export policy configuration (route-maps, prefix-lists) and ensure that the AS advertises the correct routes",
        'BGP import policy': "💡 Check the import policy configuration (route-maps, prefix-lists) and ensure that the AS receives/accepts the correct routes from its neighbors",
        'BGP local preference and best path selection': "💡 Check the local preference values and ensure that the best paths are correct",
        'BGP roles': "💡 Verify that the local and remote roles of BGP neighbors are correctly configured (customer, provider, peer)",
        'OSPF adjacencies': "💡 Check OSPF adjacencies: verify that all expected neighbors are in Full state",
        'OSPF router-id': "💡 Check the router-id configuration. What is the rule for assigning a router-id?",
        'OSPF interface state': "💡 Check the OSPF interface configuration: cost, passive-interface, area, network type. An interface mistakenly set to passive will not form adjacencies",
        'OSPF routes and paths': "💡 Check the OSPF routing table and the SPF tree. A wrong cost on an interface can change the best path used to reach a destination",
        'Interface state and prefix': "💡 Check that interfaces are UP and have the correct IPv6 prefix configured. A wrong prefix length prevents adjacencies from forming",
        'Connectivity (ping)': "💡 Check the static routes, active interfaces, and IP addresses of remote devices",
        'Routing': "💡 Inspect the routing tables (ip route) and make sure the static routes are correctly defined",
        'Other tests': "💡 Check the detailed error messages below for more information"
    }

    default_hint = "💡 Check the configuration of the concerned devices"
    return hints.get(categorie, default_hint)

def categoriser_test(description):
    desc = description.lower()

    if 'existence' in desc and 'file' not in desc:
        return 'Device existence'
    elif 'file' in desc and 'startup' in desc:
        return 'Startup files'
    elif 'collision domain' in desc or 'domaine de collision' in desc:
        return 'Collision domains'
    elif 'ip address' in desc or 'adresse ip' in desc:
        return 'IP addresses'

    # Daemons (BGP, OSPF, zebra)
    elif 'bgpd is running' in desc or 'zebra is running' in desc or 'ospf6d is running' in desc:
        return 'Daemon status'

    # =====================================================================
    # OSPF categories
    # =====================================================================
    elif 'show ipv6 ospf6 neighbor' in desc:
        return 'OSPF adjacencies'

    elif 'show ipv6 ospf6 route' in desc:
        return 'OSPF routes and paths'

    elif 'show ipv6 ospf6 interface' in desc:
        return 'OSPF interface state'

    elif 'show running-config' in desc:
        # router-id check (or other OSPF config check via running-config)
        return 'OSPF router-id'

    elif 'ip -6 addr show' in desc or 'ip addr show' in desc:
        return 'Interface state and prefix'

    # =====================================================================
    # BGP categories
    # =====================================================================
    elif 'bgpd network' in desc:
        return 'BGP network announcements'
    elif 'show bgp ipv6 summary' in desc:
        if 'regex' in desc or 'check' in desc:
            return 'BGP peer status'
        else:
            return 'BGP routing table'
    elif 'show bgp ipv6 unicast json' in desc:
        return 'BGP next-hop validation'

    elif 'show bgp neighbors' in desc and 'advertised-routes' in desc:
        return 'BGP export policy'

    elif 'show bgp neighbors' in desc and 'prefix-counts' in desc:
        return 'BGP import policy'

    elif 'show bgp ipv6 json' in desc:
        return 'BGP local preference and best path selection'

    elif 'show bgp neighbor' in desc and ('localrole' in desc or 'remoterole' in desc):
        return 'BGP roles'

    # Generic categories (compatibility)
    elif 'reachable' in desc or 'ping' in desc or 'connect' in desc:
        return 'Connectivity (ping)'
    elif 'routing' in desc or 'forwarding' in desc or 'route' in desc:
        return 'Routing'

    else:
        print(f"WARNING: Test description not categorized: '{description}'")
        return 'Other tests'


def generer_lignes_test(fichier_csv):
    if not os.path.exists(fichier_csv):
        print("ERROR: CSV file not found", file=sys.stderr)
        return []

    categories = defaultdict(lambda: {'total': 0, 'reussis': 0, 'commentaires': [], 'details_erreurs': []})

    try:
        with open(fichier_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for ligne in reader:
                description = ligne.get('Test Description', '')
                passed = ligne.get('Passed', 'True')
                raison = ligne.get('Reason', '')

                if not description:
                    continue

                categorie = categoriser_test(description)

                categories[categorie]['total'] += 1
                if passed.lower() in ['true', '1', 'ok']:
                    categories[categorie]['reussis'] += 1

                if passed.lower() not in ['true', '1', 'ok'] and raison and raison not in ['OK', '']:
                    categories[categorie]['commentaires'].append(raison)
                    categories[categorie]['details_erreurs'].append(f"{description}: {raison}")

    except Exception as e:
        print(f"ERROR while analyzing the CSV: {e}", file=sys.stderr)
        return []

    lignes = []

    # Order of display: setup → daemons → OSPF → BGP → connectivity → other
    ordre_categories = [
        'Device existence',
        'Startup files',
        'Collision domains',
        'IP addresses',
        'Interface state and prefix',
        'Daemon status',
        # OSPF block
        'OSPF adjacencies',
        'OSPF router-id',
        'OSPF interface state',
        'OSPF routes and paths',
        # BGP block
        'BGP network announcements',
        'BGP peer status',
        'BGP routing table',
        'BGP next-hop validation',
        'BGP export policy',
        'BGP import policy',
        'BGP local preference and best path selection',
        'BGP roles',
        # Connectivity / generic
        'Connectivity (ping)',
        'Routing',
        'Other tests'
    ]

    SEP = "|"

    for categorie in ordre_categories:
        if categorie in categories:
            stats = categories[categorie]
            total = stats['total']
            reussis = stats['reussis']

            if reussis == total:
                statut = "✅ Success"
            elif reussis == 0:
                statut = "❌ Failure"
            else:
                statut = "⚠️ Partial"

            poids = f"{reussis}/{total}"
            commentaire = get_hint_for_category(categorie, stats)

            lignes.append(f"{categorie}{SEP}{statut}{SEP}{poids}{SEP}{commentaire}")

    return lignes


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extractFeedbackFromCSV.py <csv_file>", file=sys.stderr)
        sys.exit(1)

    fichier_csv = sys.argv[1]
    lignes = generer_lignes_test(fichier_csv)

    if not lignes:
        print("")
        return

    output = "\n".join(lignes)
    print(output.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`'))


if __name__ == "__main__":
    main()