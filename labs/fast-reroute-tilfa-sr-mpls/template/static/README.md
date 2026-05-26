# Enabling MPLS on the Host Machine

Required before running any Kathara lab that uses SR-MPLS or TI-LFA.  
Do this **once** on your machine. Steps 1, 2 and 3 survive until the next reboot.
Step 4 makes them permanent.

---

## 0. Configure MPLS Segment Routing

The first step of this project is to configure Segment Routing, using MPLS as backend.

Before starting, follow the steps described below on how to enable MPLS in the kernel. This is from the documentation [FRRouting mpls kernel modules](https://docs.frrouting.org/projects/dev-guide/en/latest/building-frr-for-ubuntu2204.html#add-mpls-kernel-modules) 

After this, check the [Segment Routing](https://docs.frrouting.org/en/latest/isisd.html#segment-routing) section of IS-IS to understand how to enable MPLS Segment Routing. 

## 1. Check your kernel has the modules

```bash
find /lib/modules/$(uname -r) -name "mpls_router*" -o -name "mpls_iptunnel*"
```

You should see two `.ko` or `.ko.zst` files. If the output is empty, install the extra modules package:

```bash
sudo apt install linux-modules-extra-$(uname -r)
```

---

## 2. Load the modules

```bash
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel
```

Verify:

```bash
lsmod | grep mpls
```

Expected output (order may vary):

```
mpls_iptunnel   ...
mpls_router     ...
```

---

## 3. Set the label table size

```bash
sudo sysctl -w net.mpls.platform_labels=100000
```

Verify:

```bash
cat /proc/sys/net/mpls/platform_labels   
# should print 100000
```

---

## 4. Make it permanent across reboots

```bash
echo -e "mpls_router\nmpls_iptunnel" | sudo tee /etc/modules-load.d/mpls.conf
echo "net.mpls.platform_labels=100000"  | sudo tee /etc/sysctl.d/99-mpls.conf
```

---

## 5. Start the lab

Because MPLS forwarding requires elevated privileges inside containers, always start the lab with:

```bash
sudo kathara lstart --privileged
```

> **Note:** `kathara connect` and all other commands do not need `sudo`.

---

## Quick sanity check inside a container

After `sudo kathara lstart --privileged`, connect to any router and run:

With privileged mode, terminals don't open automatically. You must open a terminal with kathara connect "node"

```bash
sysctl net.mpls.platform_labels   
# expected: 100000

sysctl net.mpls.conf.eth0.input   
# expected: 1

vtysh -c "show mpls table"        
# expected: SR label entries (16002, 16003, ...)
```

If `platform_labels` is 0, re-run steps 2–3 on the host and restart the lab.

You can check if the startup commands works with :

```bash
cat var/log/startup.log 
```

