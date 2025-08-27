from netmiko import ConnectHandler

# -------------------------
# Definir dispositivos
# -------------------------
sw1 = {
    'device_type': 'cisco_ios',
    'host': '10.10.12.2',
    'username': 'admin',
    'password': 'admin',
}

sw2 = {
    'device_type': 'cisco_ios',
    'host': '10.10.12.3',
    'username': 'admin',
    'password': 'admin',
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

# -------------------------
# Comandos para cada equipo
# -------------------------

cfg_sw1_phase2 = [
    "vlan 230",
    "name VENTAS",
    "vlan 231",
    "name TECNICA",
    "vlan 232",
    "name VISITANTES",
    "vlan 239",
    "name NATIVA",
    "vlan 1299",
    "name GESTION",

    "interface ethernet0/1",
    "switchport mode access",
    "switchport access vlan 230",
    "no shutdown",

    "interface ethernet0/2",
    "switchport mode access",
    "switchport access vlan 231",
    "no shutdown",

    "interface ethernet0/3",
    "switchport mode access",
    "switchport access vlan 232",
    "no shutdown",

    # Trunk transitorio: nativa 1299
    "interface ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 230,231,232,1299,239",
    "switchport trunk native vlan 1299",
    "no shutdown",
]

cfg_sw1_phase4 = [
    "interface ethernet0/0",
    "switchport trunk native vlan 239",
]

cfg_sw2 = [
    "vlan 230",
    "name VENTAS",
    "vlan 231",
    "name TECNICA",
    "vlan 232",
    "name VISITANTES",
    "vlan 239",
    "name NATIVA",
    "vlan 1299",
    "name GESTION",

    "interface ethernet0/0",
    "switchport mode access",
    "switchport access vlan 1299",
    "no shutdown",
]

cfg_r1_phase1 = [
    # VLANs en bridge
    "/interface bridge vlan add bridge=br-core vlan-ids=230 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=231 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=232 tagged=br-core,ether2",

    # Interfaces VLAN en bridge
    "/interface vlan add name=ventas230 vlan-id=230 interface=br-core",
    "/interface vlan add name=tecnica231 vlan-id=231 interface=br-core",
    "/interface vlan add name=visit232 vlan-id=232 interface=br-core",

    # Direcciones IP
    "/ip address add address=10.10.12.65/27 interface=ventas230",
    "/ip address add address=10.10.12.97/28 interface=tecnica231",
    "/ip address add address=10.10.12.113/29 interface=visit232",

    # Pools DHCP
    "/ip pool add name=pool-ventas ranges=10.10.12.66-10.10.12.94",
    "/ip pool add name=pool-tecnica ranges=10.10.12.98-10.10.12.110",
    "/ip pool add name=pool-visit ranges=10.10.12.114-10.10.12.118",

    "/ip dhcp-server add name=dhcp-ventas interface=ventas230 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica231 address-pool=pool-tecnica disabled=no",
    "/ip dhcp-server add name=dhcp-visit interface=visit232 address-pool=pool-visit disabled=no",

    "/ip dhcp-server network add address=10.10.12.64/27 gateway=10.10.12.65",
    "/ip dhcp-server network add address=10.10.12.96/28 gateway=10.10.12.97",
    "/ip dhcp-server network add address=10.10.12.112/29 gateway=10.10.12.113",

    # NAT
    "/ip firewall nat add chain=srcnat src-address=10.10.12.64/27 out-interface=ether1 action=masquerade",
    "/ip firewall nat add chain=srcnat src-address=10.10.12.96/28 out-interface=ether1 action=masquerade",
]

cfg_r1_phase3 = [
    "/interface bridge port set [find interface=ether2] pvid=239",
    "/interface bridge vlan set [find vlan-ids=1299] tagged=br-core,ether2,ether3 untagged=",
    "/interface bridge vlan set [find vlan-ids=239] tagged=br-core untagged=ether2,ether3",
]

# -------------------------
# Función de envío
# -------------------------
def run_cfg(device, commands):
    net_connect = ConnectHandler(**device)
    output = net_connect.send_config_set(commands)
    print(f"\n### {device['host']} ###\n{output}")
    net_connect.disconnect()

# -------------------------
# Ejecución en fases
# -------------------------
if __name__ == "__main__":
    # Fase 1 - Preparar R1
    run_cfg(r1, cfg_r1_phase1)

    # Fase 2 - SW1 en trunk nativa 1299
    run_cfg(sw1, cfg_sw1_phase2)

    # Fase 3 - R1 cambia a nativa 239
    run_cfg(r1, cfg_r1_phase3)

    # Fase 4 - SW1 cambia a nativa 239
    run_cfg(sw1, cfg_sw1_phase4)

    # SW2 (solo gestión acceso 1299)
    run_cfg(sw2, cfg_sw2)

