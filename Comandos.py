#!/usr/bin/env python3
from netmiko import ConnectHandler
import time, sys

# --------------------------
# Credenciales unificadas
# --------------------------
USERNAME = "admin"
PASSWORD = "1234"

# --------------------------
# Dispositivos
# --------------------------
sw1 = {'device_type': 'cisco_ios','host': '10.10.12.2','username': USERNAME,'password': PASSWORD}
sw2 = {'device_type': 'cisco_ios','host': '10.10.12.3','username': USERNAME,'password': PASSWORD}
r1  = {'device_type': 'mikrotik_routeros','host': '10.10.12.1','username': USERNAME,'password': PASSWORD}
r2  = {'device_type': 'mikrotik_routeros','host': '10.10.12.4','username': USERNAME,'password': PASSWORD}

# --------------------------
# Configuración de cada fase
# --------------------------

# SW1 VLANs + trunk transitorio
sw1_phase_transitory = [
    "vlan 230", "name VENTAS",
    "vlan 231", "name TECNICA",
    "vlan 232", "name VISITANTES",
    "interface Ethernet0/1", "switchport mode access", "switchport access vlan 230", "no shutdown",
    "interface Ethernet0/2", "switchport mode access", "switchport access vlan 231", "no shutdown",
    "interface Ethernet0/3", "switchport mode access", "switchport access vlan 232", "no shutdown",
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",
    "no shutdown",
]

# SW1 cambiar native a 239
sw1_phase_finalize = ["interface Ethernet0/0","switchport trunk native vlan 239"]

# SW2 VLANs + trunk transitorio hacia R2
sw2_phase_transitory = [
    "vlan 230","name VENTAS",
    "vlan 231","name TECNICA",
    "vlan 232","name VISITANTES",
    "interface Ethernet0/1","switchport mode access","switchport access vlan 230","no shutdown",
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",
    "no shutdown",
]

# SW2 cambiar native a 239 (opcional)
sw2_finalize = ["interface Ethernet0/0","switchport trunk native vlan 239"]

# R1 VLANs, DHCP, NAT
r1_phase1 = [
    "/interface bridge vlan add bridge=br-core vlan-ids=230 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=231 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=232 tagged=br-core,ether2",
    "/interface vlan add name=ventas230 vlan-id=230 interface=br-core",
    "/interface vlan add name=tecnica231 vlan-id=231 interface=br-core",
    "/interface vlan add name=visit232  vlan-id=232 interface=br-core",
    "/ip address add address=10.10.12.65/27 interface=ventas230",
    "/ip address add address=10.10.12.97/28 interface=tecnica231",
    "/ip address add address=10.10.12.113/29 interface=visit232",
    "/ip pool add name=pool-ventas ranges=10.10.12.66-10.10.12.94",
    "/ip pool add name=pool-tecnica ranges=10.10.12.98-10.10.12.110",
    "/ip pool add name=pool-visit  ranges=10.10.12.114-10.10.12.118",
    "/ip dhcp-server add name=dhcp-ventas interface=ventas230 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica231 address-pool=pool-tecnica disabled=no",
    "/ip dhcp-server add name=dhcp-visit  interface=visit232 address-pool=pool-visit disabled=no",
    "/ip dhcp-server network add address=10.10.12.64/27  gateway=10.10.12.65",
    "/ip dhcp-server network add address=10.10.12.96/28  gateway=10.10.12.97",
    "/ip dhcp-server network add address=10.10.12.112/29 gateway=10.10.12.113",
    "/ip firewall nat add chain=srcnat src-address=10.10.12.64/27 out-interface=ether1 action=masquerade",
    "/ip firewall nat add chain=srcnat src-address=10.10.12.96/28 out-interface=ether1 action=masquerade",
]

# R1 cambiar pvid a 239
r1_phase2 = [
    "/interface bridge port set [find interface=ether2] pvid=239",
    "/interface bridge vlan set [find vlan-ids=1299] tagged=br-core,ether2,ether3 untagged=",
    "/interface bridge vlan set [find vlan-ids=239] tagged=br-core untagged=ether2,ether3",
]

# R2 preparar VLANs
r2_phase1 = [
    # Asegurar que el bridge y puertos existen (se puede omitir si ya están creados)
    "/interface bridge add name=br-remote vlan-filtering=yes",
    "/interface bridge port add bridge=br-remote interface=ether2 pvid=239",
    "/interface bridge port add bridge=br-remote interface=ether1 pvid=1299",

    # Mantener VLANs base
    "/interface bridge vlan add bridge=br-remote vlan-ids=239 tagged=br-remote untagged=ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=1299 tagged=br-remote,ether2 untagged=ether1",

    # Agregar VLANs nuevas
    "/interface bridge vlan add bridge=br-remote vlan-ids=230 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=231 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=232 tagged=br-remote,ether2",
]

# --------------------------
# Funciones
# --------------------------
def run_cfg(device, commands):
    print(f"\n--- {device['host']} ---")
    try:
        conn = ConnectHandler(**device)
        out = conn.send_config_set(commands)
        print(out)
        conn.disconnect()
    except Exception as e:
        print(f"ERROR en {device['host']}: {e}")

def run_check(device, cmds):
    try:
        conn = ConnectHandler(**device)
        for c in cmds:
            out = conn.send_command(c)
            print(f"\n[{device['host']}] {c}\n{out}")
        conn.disconnect()
    except Exception as e:
        print(f"ERROR check {device['host']}: {e}")

# --------------------------
# Ejecución
# --------------------------
if __name__ == "__main__":
    print(">>> Verificá ping a 10.10.12.1 .2 .3 .4 ANTES de correr este script <<<")
    time.sleep(2)

    run_cfg(r1, r1_phase1)              # R1 VLANs, DHCP, NAT
    run_cfg(sw1, sw1_phase_transitory)  # SW1 VLANs y trunk nativa 1299
    run_cfg(r2, r2_phase1)              # R2 tabla VLANs
    run_cfg(r1, r1_phase2)              # R1 cambia pvid a 239
    run_cfg(sw1, sw1_phase_finalize)    # SW1 cambia native a 239
    run_cfg(sw2, sw2_phase_transitory)  # SW2 VLANs y trunk nativa 1299
    run_cfg(sw2, sw2_finalize)          # SW2 native 239 (opcional)

    # Verificaciones
    run_check(sw1, ["show vlan brief","show interface trunk"])
    run_check(sw2, ["show vlan brief","show interface trunk"])
    run_check(r1, ["/interface bridge vlan print","/ip address print","/ip dhcp-server print"])
    run_check(r2, ["/interface bridge vlan print","/ip address print"])



