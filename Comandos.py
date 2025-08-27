from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

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
    " switchport access vlan 110",   # ejemplo: usuario remoto en VLAN Ventas
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
# Se asume que la VLAN de gestión 1299 (gestion1299 con IP 10.10.12.1/29)
# ya está configurada sobre el bridge (br-core) en la configuración inicial.
cfg_r1 = [
    # Subinterfaces para VLANs de usuario (estas sí se añaden sobre ether2)
    "/interface vlan add name=VLAN110 vlan-id=110 interface=ether2",
    "/interface vlan add name=VLAN120 vlan-id=120 interface=ether2",
    "/interface vlan add name=VLAN130 vlan-id=130 interface=ether2",

    # Las siguientes líneas se COMENTAN porque la VLAN de gestión 1299
    # ya debería estar configurada en la interfaz 'gestion1299' sobre 'br-core'
    # en la configuración inicial del MikroTik.
    # Si se ejecutan, intentarían crear una nueva interfaz VLAN con el mismo ID
    # y la misma IP en 'ether2', lo que podría causar conflictos o romper la conectividad.
    # "/interface vlan add name=VLAN1299 vlan-id=1299 interface=ether2",
    # "/ip address add address=10.10.12.1/29 interface=VLAN1299", # Esta IP ya está en gestion1299

    # Direccionamiento para las VLANs de usuario
    "/ip address add address=192.168.110.1/26 interface=VLAN110",
    "/ip address add address=192.168.120.1/27 interface=VLAN120",
    "/ip address add address=192.168.130.1/29 interface=VLAN130",

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
# Se asume que la VLAN de gestión 1299 (gestion1299 con IP 10.10.12.4/29)
# ya está configurada sobre el bridge (br-remote) en la configuración inicial.
cfg_r2 = [
    # Las siguientes líneas se COMENTAN por la misma razón que en R1.
    # La VLAN de gestión 1299 ya debería estar configurada en la interfaz
    # 'gestion1299' sobre 'br-remote' en la configuración inicial.
    # "/interface vlan add name=VLAN1299 vlan-id=1299 interface=ether1",
    # "/ip address add address=10.10.12.4/29 interface=VLAN1299",
]

# Comandos de verificación
verify_cmds = {
    "SW1": ["show vlan brief", "show ip interface brief"],
    "SW2": ["show vlan brief", "show ip interface brief"],
    "R1": ["/ip address print", "/ip route print", "/ip dhcp-server print", "/interface vlan print"],
    "R2": ["/ip address print", "/ip route print", "/interface vlan print"],
}

# Ejecución
for name, device in devices.items():
    print(f"\n###### Conectando a {name} ({device['host']}) ######")
    try:
        with ConnectHandler(**device) as conn:
            if name == "SW1":
                print(f"--- Aplicando configuración a {name} ---")
                output = conn.send_config_set(cfg_sw1)
                print(output) # Imprime la salida de la configuración
            elif name == "SW2":
                print(f"--- Aplicando configuración a {name} ---")
                output = conn.send_config_set(cfg_sw2)
                print(output) # Imprime la salida de la configuración
            elif name == "R1":
                print(f"--- Aplicando configuración a {name} ---")
                for cmd in cfg_r1:
                    print(f"Ejecutando: {cmd}")
                    output = conn.send_command(cmd)
                    if output: # Solo imprime si hay salida
                        print(f"Output: {output}")
            elif name == "R2":
                print(f"--- Aplicando configuración a {name} ---")
                for cmd in cfg_r2:
                    print(f"Ejecutando: {cmd}")
                    output = conn.send_command(cmd)
                    if output: # Solo imprime si hay salida
                        print(f"Output: {output}")

            print(f"\n-- Verificación en {name} --")
            for vcmd in verify_cmds[name]:
                print(f"\n{name}# {vcmd}")
                output = conn.send_command(vcmd)
                print(f"{output}\n")

    except NetmikoTimeoutException:
        print(f"ERROR: Timeout al conectar con {name} ({device['host']}). Verifique la conectividad y las credenciales.")
    except NetmikoAuthenticationException:
        print(f"ERROR: Autenticación fallida para {name} ({device['host']}). Verifique el usuario y la contraseña.")
    except Exception as e:
        print(f"ERROR: Ocurrió un error inesperado al conectar o configurar {name}: {e}")

print("\n##### Proceso de configuración completado #####")
