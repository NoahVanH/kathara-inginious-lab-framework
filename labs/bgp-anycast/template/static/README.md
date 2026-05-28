# Anycast with BGP

This lab demonstrates Anycast routing using BGP. The same concept applies to OSPF and IS-IS (focus on the Anycast behavior, not BGP specifics).

## Theory
- [BGP Anycast: How It Works and Why It Matters](https://medium.com/@james-tang/bgp-anycast-how-it-works-and-why-it-matters-c9c35ac8c91f)
- [BGP Anycast Explained](https://www.noction.com/blog/bgp-anycast)

## Topology
Two DNS servers share the same IP address and advertise the same prefix:
- **ns1** - DNS over HTTPS (DoH)
- **ns2** - DNS over TLS (DoT)



## Lab Objective
Observe the differences between DoH and DoT. Configuration files are correct, answer questions on Inginious.

## Helper Script
`bgpRemovePrefix.sh` - toggles Anycast prefix advertisement between ns1 and ns2.

## Useful Commands

`PREFIX` = Anycast prefix shared by both NS

```bash
# Standard DNS over IPv6
dig -6 lab.be @PREFIX

# DNS over HTTPS (DoH)
dig -6 @PREFIX -p 443 +https lab.be

# DNS over TLS (DoT)
dig -6 @PREFIX -p 853 +tls lab.be
```

## Trafic Inspection

```bash
# Standard DNS : cleartext on port 53
tcpdump -i eth0 -n port 53

# DoT : opaque TLS on port 853
tcpdump -i eth0 -n port 853

# DoH : indistinguishable from normal HTTPS on port 443
tcpdump -i eth0 -n port 443
```