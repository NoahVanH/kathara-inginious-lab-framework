# This file is the description of the lab, written in reStructuredText format. 
# It gives the variant assigned to the student with an html tag.
# Don't forget to put to "1" the Random parameters of the task.
.. admonition:: primary
   :title: 🎯 Learning Objectives

   This lab will allow you to:

   * **Design**: choose **OSPFv3 interface costs** that produce a specific set of best paths.
   * **Diagnose**: use **vtysh** to inspect the **OSPFv3 routing table** and verify that SPF selects the expected next-hop interfaces.

   In this lab, you will need to verify and enforce the following **intradomain routing property**:

   * From every router, the **next-hop interface used to reach each destination loopback** must match the reference table given below.



In this lab, **all OSPFv3 adjacencies are correct by construction**.
You should not encounter any neighbor stuck below the Full state. There is nothing to debug at the adjacency level.
The only thing you have to configure is **the OSPFv3 interface cost on each link**, so that SPF computes the expected best paths.


Lab Presentation
=============================

.. image:: /course/tfe-vanhorenbeke/ospf-shortestpath/topo.svg
   :alt: Lab network topology
   :align: center
   :width: 60%

This image represents the topology used by the lab. All adjacencies will form correctly as soon as the lab is started; your job is to assign costs.

.. admonition:: note
   :class: note

   **About OSPF costs:** the correction is **not based on exact cost values**.
   Several different cost configurations can produce the same shortest paths.
   The correction validates that, from each router, the next-hop interface used to reach each destination matches the reference table.



Reference: Expected Best Paths
==============================

The following table indicates, for each (source, destination) pair, the **interface of the source router** used in the SPF best path.
This is the reference used by the automatic correction.

.. csv-table::
   :header: "Source \\ Dest", "R1 lo", "R2 lo", "R3 lo", "R4 lo", "R5 lo"
   :widths: 5, 3, 3, 3, 3, 3
   :align: center


   R1, local, eth0, eth0, eth0, eth1
   R2, eth0, local, eth0, eth0, eth0
   R3, eth0, eth0, local, eth1, eth1
   R4, eth1, eth0, eth0, local, eth1
   R5, eth0, eth1, eth0, eth0, local


Routing Policy
==============================

.. admonition:: primary
   :title: Operator choices

   The most counter-intuitive entry of the reference table is **R2 → R5**, which is forced to traverse R3 and R4 instead of taking the direct link R2-R5. The operator's rationale is the following:

   * The **direct R2–R5 link** is a low-bandwidth fallback line. R2 must **not** prefer it for transit traffic, but only as a backup.
   * R2's traffic to R5 must exit via R2's interface toward R3, and be forwarded along the R3 → R4 backbone, even though this path is one hop longer.
   * Note that R2 has a direct link to R1. However, R1's uplink is reserved for R1's own egress traffic: any cost assignment that would route R2 → R5 traffic through R1 is therefore invalid, even if it satisfies the interface constraint.

   Your cost assignment must be consistent with this intent for every entry of the table, not only for the R2 → R5 case. [#csp]_



📥 **Download the Base Lab**
+++++++++++++++++++++++++++++++++++++++++++++

.. admonition:: primary
   :title: Download the starting archive

     To **begin the exercise**, you need to download the archive. It contains the base configuration with errors to fix.

    .. raw:: html

        <script>
          const NB_VARIANTS = 40;
          const rand = input["@random"][0];
          const index = Math.floor(rand * NB_VARIANTS);
          const selected = `variant_${index}.zip`;
          const url = "https://inginious.info.ucl.ac.be/course/tfe-vanhorenbeke/ospf-shortestpath/variations/" + selected;
          document.write(`<a href="${url}">Download your lab (${selected})</a>`);
        </script>

Diagnostic Tools
=====================

**vtysh** is the unified command-line interface of FRRouting.

Useful commands for validating SPF results:

.. code:: bash

   # Access vtysh
   root@r1:/# vtysh
   r1#

   # Show running configuration (router-id, interfaces, costs)
   show running-config

   # Show the OSPFv3 routing table (SPF result, with next-hop interface)
   show ipv6 ospf6 route

   # Inspect interface-level OSPF state (notably the configured cost)
   show ipv6 ospf6 interface <ifname>

   # Confirm that adjacencies are healthy (sanity check, should all be Full)
   show ipv6 ospf6 neighbor

.. admonition:: note
   :class: note

   Focus on the **next-hop interface** of each route in ``show ipv6 ospf6 route``.
   That field, not the absolute cost, is what the correction compares against the reference table.

Recommended Approach
======================

1.  **Explore the topology**

    Examine the ``lab.conf`` file to understand connectivity and map interfaces to links.

2.  **Connect to containers**

    .. code:: bash

       cd ./variant_X
       kathara lstart
       kathara connect [node_name]
       kathara wipe

3.  **Derive a cost assignment** that produces the expected best paths

4.  **Apply the costs** in the FRRouting configuration files of the relevant routers

5.  **Validate SPF paths against the reference**

    On each router, run ``show ipv6 ospf6 route`` and check that every destination is reached via the interface specified in the reference table.

6. 📌 **Important Rules:**

    - ❌ Do not modify ``lab.conf``
    - ❌ Do not create new files
    - ✅ Only adjust existing configuration files (interface cost statements)

7.  **Validate your configuration locally**

    .. code:: bash

       cd ./variant
       kathara_lab_checker --config correction_student.yaml --no-cache --lab .
       or
       python3 -m kathara_lab_checker --config correction_student.yaml --no-cache --lab .

8.  **Submit your solution**

    Compress the configured ``variant_X`` folder and upload it.

.. admonition:: primary
   :title: 🔗 Useful Links

   - **Kathara**: https://github.com/KatharaFramework/Kathara/wiki
   - **FRRouting Documentation (OSPFv3)**: https://docs.frrouting.org/en/latest/ospf6d.html
   - **RFC 5340 (OSPF for IPv6)**: https://datatracker.ietf.org/doc/rfc5340/

----

.. [#csp] Finding cost values that satisfy all 10 entries by hand is feasible but it don't scale well with large network. The problem can be modelled as a **constraint satisfaction problem (CSP)** and solved in milliseconds with a tool such as ``pycsp3``. See the `Constraint Programming course <https://uclouvain.be/en-cours-2025-linfo2365>`_ for the underlying theory.