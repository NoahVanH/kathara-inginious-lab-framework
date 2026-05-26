# Lab: BGP Troubleshooting and Diagnosis

## Context
This lab focuses on diagnosing and fixing intentional BGP configuration errors within a preconfigured network infrastructure using Kathará and the `vtysh` interface to restore proper peering and prefix advertisements.

## Instructions
1. Explore the network topology by examining the `lab.conf` file to understand the connections between containers.
2. Start the lab environment and connect to each router to inspect active configurations and BGP neighbor statuses.
3. Identify and fix configuration errors inside the existing router configuration files without modifying `lab.conf` or creating new files.
4. Locally validate your modifications and verify that all test suites pass successfully using the provided verification tool.
5. Compress the corrected folder into a `.zip` file and submit your solution.

## Quick Kathará Commands
```bash
kathara lstart
kathara connect <node>
kathara wipe
```

---
**Author:** Noah Van Horenbeke  
**Email:** tfe@boite.top