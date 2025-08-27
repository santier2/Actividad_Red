from netmiko import ConnectHandler

# Datos de conexión comunes
devices = {
    "SW1": {
        "device_type": "cisco_ios",
        "host": "10.10.12.2",
        "username": "admin",
        "password": "1234",
    },
    "SW2": {
        "device_type": "cisco_ios",
        "host": "10.10.12.3",
        "username": "admin",
        "password": "1234",
    },
    "R1": {
        "device_type": "mikrotik_routeros",
        "host": "10.10.12.1",
        "username": "admin",
        "password": "1234",
    },
    "R2": {
        "device_type": "mikrotik_routeros",
        "host": "10.10.12.4",
        "username": "admin",
        "password": "1234",
    }
}

# Configuración de SW1
cfg_sw1 = [
    "vlan 110", "name VENTAS",
    "vlan 120", "name TECNICA",
    "vlan 130", "name VISITANTES",

    # VLANs ya creadas: 1299 (gestion), 239 (nativa trunk)

    # Puertos access
    "interface Ethernet0/1",
    " switchport mode access",
    " switchport access vlan 110",
    " no shutdown",
    "exit",

    "interface Ethernet0/2",
    " switchport mode access",
    " switchport access vlan 120",
    " no shutdown",
    "exit",

    "interface Ethernet0/3",
    " switchport mode access",
    " switchport access vlan 130",
    " no shutdown",
    "exit",

    # Trunk hacia R1
    "interface Ethernet0/0",
    " switchport trunk encapsulation dot1q",
    " switchport mode trunk",
    " switchport trunk native vlan 239",
    " switchport trunk allowed vlan 239,110,120,130,1299",
    " no shutdown",
    "exit",
]

# Configuración de SW2 (solo trunk + puerto usuario remoto)
cfg_sw2 = [
    "vlan 110", "name VENTAS",
    "vlan 120", "name TECNICA",
    "vlan 130", "name VISITANTES",

    "interface Ethernet0/1",
    " switchport mode access",
    " switchport access vlan 110",  # ejemplo: usuario remoto en VLAN Ventas
    " no shutdown",
    "exit",

    "interface Ethernet0/0",
    " switchport trunk encapsulation dot1q",
    " switchport mode trunk",
    " switchport trunk native vlan 239",
    " switchport trunk allowed vlan 239,110,120,130,1299",
    " no shutdown",
    "exit",
]

# Configuración de R1 (Router-on-a-Stick + NAT + DHCP)
cfg_r1 = [
    # Subinterfaces
    "/interface vlan add name=VLAN110 vlan-id=110 interface=ether2",
    "/interface vlan add name=VLAN120 vlan-id=120 interface=ether2",
    "/interface vlan add name=VLAN130 vlan-id=130 interface=ether2",
    "/interface vlan add name=VLAN1299 vlan-id=1299 interface=ether2",

    # Direccionamiento (ejemplo de bloque /24 subdividido con VLSM)
    "/ip address add address=192.168.110.1/26 interface=VLAN110",
    "/ip address add address=192.168.120.1/27 interface=VLAN120",
    "/ip address add address=192.168.130.1/29 interface=VLAN130",
    "/ip address add address=10.10.12.1/29 interface=VLAN1299",

    # NAT solo para Ventas y Técnica
    "/ip firewall nat add chain=srcnat src-address=192.168.110.0/26 action=masquerade out-interface=ether1",
    "/ip firewall nat add chain=srcnat src-address=192.168.120.0/27 action=masquerade out-interface=ether1",

    # DHCP para Ventas y Técnica
    "/ip pool add name=POOL_VLAN110 ranges=192.168.110.10-192.168.110.62",
    "/ip dhcp-server add name=DHCP110 interface=VLAN110 lease-time=1h address-pool=POOL_VLAN110",
    "/ip dhcp-server network add address=192.168.110.0/26 gateway=192.168.110.1 dns-server=8.8.8.8",

    "/ip pool add name=POOL_VLAN120 ranges=192.168.120.10-192.168.120.30",
    "/ip dhcp-server add name=DHCP120 interface=VLAN120 lease-time=1h address-pool=POOL_VLAN120",
    "/ip dhcp-server network add address=192.168.120.0/27 gateway=192.168.120.1 dns-server=8.8.8.8",
]

# Configuración de R2 (remoto, solo gestión + trunk)
cfg_r2 = [
    "/interface vlan add name=VLAN1299 vlan-id=1299 interface=ether1",
    "/ip address add address=10.10.12.4/29 interface=VLAN1299",
]

# Comandos de verificación
verify_cmds = {
    "SW1": ["show vlan brief", "show ip interface brief"],
    "SW2": ["show vlan brief", "show ip interface brief"],
    "R1": ["/ip address print", "/ip route print", "/ip dhcp-server print"],
    "R2": ["/ip address print", "/ip route print"],
}

# Ejecución
for name, device in devices.items():
    print(f"\n###### Conectando a {name} ######")
    with ConnectHandler(**device) as conn:
        if name == "SW1":
            conn.send_config_set(cfg_sw1)
        elif name == "SW2":
            conn.send_config_set(cfg_sw2)
        elif name == "R1":
            for cmd in cfg_r1:
                conn.send_command(cmd)
        elif name == "R2":
            for cmd in cfg_r2:
                conn.send_command(cmd)

        print(f"\n-- Verificación en {name} --")
        for vcmd in verify_cmds[name]:
            output = conn.send_command(vcmd)
            print(f"\n{name}# {vcmd}\n{output}\n")
