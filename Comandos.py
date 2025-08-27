#!/usr/bin/env python3
from netmiko import ConnectHandler
import time
import sys

# --------------------------
# Dispositivos (ACTUALIZAR credenciales si hace falta)
# --------------------------
sw1 = {
    'device_type': 'cisco_ios',
    'host': '10.10.12.2',
    'username': 'admin1',
    'password': '1234',
}

sw2 = {
    'device_type': 'cisco_ios',
    'host': '10.10.12.3',
    'username': 'admin2',
    'password': '1234',
}

r1 = {
    'device_type': 'mikrotik_routeros',
    'host': '10.10.12.1',
    'username': 'admin',
    'password': '1234',
}

r2 = {
    'device_type': 'mikrotik_routeros',
    'host': '10.10.12.4',
    'username': 'admin',
    'password': '1234',
}

# --------------------------
# SW1: crear VLANs funcionales y trunk TRANSITORIO (native=1299)
# --------------------------
sw1_phase_transitory = [
    "vlan 230", "name VENTAS",
    "vlan 231", "name TECNICA",
    "vlan 232", "name VISITANTES",
    # asignar puertos de ejemplo (reemplazar por reales)
    "interface Ethernet0/1",
    "switchport mode access",
    "switchport access vlan 230",
    "no shutdown",
    "interface Ethernet0/2",
    "switchport mode access",
    "switchport access vlan 231",
    "no shutdown",
    "interface Ethernet0/3",
    "switchport mode access",
    "switchport access vlan 232",
    "no shutdown",
    # trunk hacia R1 (transitorio: native = 1299)
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",
    "no shutdown",
]

# --------------------------
# SW1: cambiar native a 239 (final)
# --------------------------
sw1_phase_finalize = [
    "interface Ethernet0/0",
    "switchport trunk native vlan 239",
]

# --------------------------
# SW2: crear VLANs funcionales y trunk TRANSITORIO hacia R2 (native=1299)
# --------------------------
sw2_phase_transitory = [
    "vlan 230", "name VENTAS",
    "vlan 231", "name TECNICA",
    "vlan 232", "name VISITANTES",
    # ejemplo puertos locales (ajustar)
    "interface Ethernet0/1",
    "switchport mode access",
    "switchport access vlan 230",
    "no shutdown",
    # trunk hacia R2 (transitorio)
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",
    "no shutdown",
]

# --------------------------
# R1 (MikroTik): crear VLANs en br-core (interfaces sobre br-core), DHCP, NAT
# (asegurar que br-core existe y ether2 pvid=1299 todavía)
# --------------------------
r1_phase1 = [
    # añadir VLANs taggeadas en ether2 (para que SW1 trunk taggee las VLANs)
    "/interface bridge vlan add bridge=br-core vlan-ids=230 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=231 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=232 tagged=br-core,ether2",

    # crear interfaces VLAN sobre br-core
    "/interface vlan add name=ventas230 vlan-id=230 interface=br-core",
    "/interface vlan add name=tecnica231 vlan-id=231 interface=br-core",
    "/interface vlan add name=visit232  vlan-id=232 interface=br-core",

    # direcciones IP (VLSM segun enunciado)
    "/ip address add address=10.10.12.65/27 interface=ventas230",
    "/ip address add address=10.10.12.97/28 interface=tecnica231",
    "/ip address add address=10.10.12.113/29 interface=visit232",

    # DHCP pools y servidores
    "/ip pool add name=pool-ventas ranges=10.10.12.66-10.10.12.94",
    "/ip pool add name=pool-tecnica ranges=10.10.12.98-10.10.12.110",
    "/ip pool add name=pool-visit  ranges=10.10.12.114-10.10.12.118",

    "/ip dhcp-server add name=dhcp-ventas interface=ventas230 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica231 address-pool=pool-tecnica disabled=no",
    "/ip dhcp-server add name=dhcp-visit interface=visit232 address-pool=pool-visit disabled=no",

    "/ip dhcp-server network add address=10.10.12.64/27 gateway=10.10.12.65",
    "/ip dhcp-server network add address=10.10.12.96/28 gateway=10.10.12.97",
    "/ip dhcp-server network add address=10.10.12.112/29 gateway=10.10.12.113",

    # NAT: Ventas y Técnica salen a Internet por ether1 (ajustar salida si es otra)
/ip firewall nat add chain=srcnat src-address=10.10.12.64/27 out-interface=ether1 action=masquerade
/ip firewall nat add chain=srcnat src-address=10.10.12.96/28 out-interface=ether1 action=masquerade
]

# --------------------------
# R1: cambiar pvid de ether2 a 239 y ajustar bridge-vlan (cuando SW1 ya esté trunk)
# --------------------------
r1_phase2 = [
    "/interface bridge port set [find interface=ether2] pvid=239",
    "/interface bridge vlan set [find vlan-ids=1299] tagged=br-core,ether2,ether3 untagged=",
    "/interface bridge vlan set [find vlan-ids=239] tagged=br-core untagged=ether2,ether3",
]

# --------------------------
# R2: preparar tabla VLAN (tag 1299/239) y eventual creación de subinterfaces si corresponde
# --------------------------
r2_phase1 = [
    "/interface bridge vlan add bridge=br-remote vlan-ids=230 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=231 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=232 tagged=br-remote,ether2",
    # (si querés: crear interfaces vlan sobre br-remote y asignar IPs en remoto)
]

# --------------------------
# SW2 final: cambiar native a 239 si el diseño lo requiere (opcional)
# --------------------------
sw2_finalize = [
    "interface Ethernet0/0",
    "switchport trunk native vlan 239",
]

# --------------------------
# Funciones utilitarias
# --------------------------
def run_cfg(device, commands):
    print(f"\n--- Conectando a {device['host']} ---")
    try:
        conn = ConnectHandler(**device)
    except Exception as e:
        print(f"ERROR conectando {device['host']}: {e}")
        sys.exit(1)
    try:
        out = conn.send_config_set(commands)
        print(out)
    except Exception as e:
        print(f"ERROR aplicando config en {device['host']}: {e}")
    finally:
        conn.disconnect()

def run_check(device, cmds):
    try:
        conn = ConnectHandler(**device)
    except Exception as e:
        print(f"ERROR (check) conexión {device['host']}: {e}")
        return
    for c in cmds:
        try:
            out = conn.send_command(c)
            print(f"\n--- {device['host']} : {c} ---\n{out}")
        except Exception as e:
            print(f"ERROR ejecutando {c} en {device['host']}: {e}")
    conn.disconnect()

# --------------------------
# Flujo principal (respetar orden)
# --------------------------
if __name__ == "__main__":
    print("VERIFICÁ MANUALMENTE que desde la PC podés hacer ping a 10.10.12.1, .2, .3, .4")
    time.sleep(2)

    # 1) R1: crear VLANs en bridge y subinterfaces + DHCP/NAT (no corta mgmt)
    print("\n>>> R1: crear VLANs/subinterfaces/DHCP/NAT (fase 1)")
    run_cfg(r1, r1_phase1)
    time.sleep(2)

    # 2) SW1: crear VLANs funcionales y trunk TRANSITORIO (native=1299)
    print("\n>>> SW1: configurar VLANs y trunk transitorio (native=1299)")
    run_cfg(sw1, sw1_phase_transitory)
    time.sleep(2)

    # 3) R2: preparar tabla VLAN (fase 1)
    print("\n>>> R2: preparar tabla VLAN (fase 1)")
    run_cfg(r2, r2_phase1)
    time.sleep(2)

    # 4) Cambiar pvid ether2 en R1 a 239 (coordinado)
    print("\n>>> R1: cambiar pvid ether2 a 239")
    run_cfg(r1, r1_phase2)
    time.sleep(2)

    # 5) SW1: cambiar native a 239 (final)
    print("\n>>> SW1: cambiar native a 239")
    run_cfg(sw1, sw1_phase_finalize)
    time.sleep(2)

    # 6) SW2: configurar VLANs y trunk transitorio hacia R2
    print("\n>>> SW2: configurar VLANs y trunk transitorio (native=1299)")
    run_cfg(sw2, sw2_phase_transitory)
    time.sleep(2)

    # 7) (Opcional) SW2 final native=239 si lo querés alinear
    print("\n>>> SW2: (opcional) cambiar native a 239")
    run_cfg(sw2, sw2_finalize)

    # 8) Verificaciones (muestra)
/*
    # En cisco: show vlan brief / show interface trunk
    # En mikrotik: /interface bridge vlan print ; /ip address print ; /ip dhcp-server print
*/
    print("\n>>> Verificaciones:")
    run_check(sw1, ["show vlan brief", "show interface trunk"])
    run_check(sw2, ["show vlan brief", "show interface trunk"])
    run_check(r1, ["/interface bridge vlan print", "/ip address print", "/ip dhcp-server print"])
    run_check(r2, ["/interface bridge vlan print", "/ip address print", "/ip route print"])

    print("\n>>> FIN. Comprobá pings desde la PC Sysadmin y accesos SSH.")
