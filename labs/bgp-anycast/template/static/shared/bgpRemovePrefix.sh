#!/bin/bash

# This script is intended to be run inside the current DNS server used, to show the switching of server

# usage: ./bgp_withdraw.sh <as_number> <anycast_prefix>
# ex:    ./bgp_withdraw.sh 100 2001:db8:1::53/128

vtysh -c "conf t" -c "router bgp $1" -c "address-family ipv6 unicast" -c "no network $2"
