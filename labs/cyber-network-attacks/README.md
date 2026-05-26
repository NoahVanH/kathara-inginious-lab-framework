
# Network Attacks Lab - Quick Reference

## Context
Virtualized network lab with 4 machines (attacker, target, DNS, monitor).  


## Instructions

1. **Implement 3 attacks** in `shared/attacks.py`:
   - SYN Flood
   - TCP Port Scan (under 5 minutes, not all 65535 ports)
   - DNS Reflection/Amplification

2. **Capture traffic** on target BEFORE launching attacks:
   ```tcpdump -i eth0 -w /shared/capture.pcap```

3. **Run attacks** from attacker:
   ```python3 /shared/attacks.py```

4. **Submit** `capture.pcap` for grading

### Quick Kathará Commands
```bash
# Start lab
kathara lstart   

# Open terminal         
kathara connect <machine>  

# Stop everything 
kathara wipe                
```
---
**Author:** Noah Van Horenbeke  
**Email:** tfe@boite.top