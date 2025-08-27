from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

# -----------------------------
# Credenciales
# -----------------------------
USERNAME_CISCO = "netadmin"
PASSWORD_CISCO = "Adm1n#Lab"

USERNAME_TIK   = "admin"
PASSWORD_TIK   = "Adm1n#Lab"

# -----------------------------
# Dispositivos en orden
# -----------------------------
devices = [
    {
        "device_type": "cisco_ios",
        "host": "10.10.12.2",   # SW1 primero
        "username": USERNAME_CISCO,
        "password": PASSWORD_CISCO,
        "secret": PASSWORD_CISCO,
    },
    {
        "device_type": "mikrotik_routeros",  # R1
        "host": "10.10.12.1",
        "username": USERNAME_TIK,
        "password": PASSWORD_TIK,
    },
    {
        "device_type": "mikrotik_routeros",  # R2
        "host": "10.10.12.4",
        "username": USERNAME_TIK,
        "password": PASSWORD_TIK,
    },
    {
        "device_type": "cisco_ios",   # SW2 al final
        "host": "10.10.12.3",
        "username": USERNAME_CISCO,
        "password": PASSWORD_CISCO,
        "secret": PASSWORD_CISCO,
    }
]

# -----------------------------
# Configuracion en Switches
# -----------------------------
cfg_sw = [
    "vlan 230",
    " name VENTAS",
    "vlan 231",
    " name TECNICA",
    "vlan 232",
    " name VISITANTES",
    "interface ethernet0/1",
    " switchport mode access",
    " switchport access vlan 230",
    " no shutdown",
    "interface ethernet0/2",
    " switchport mode access",
    " switchport access vlan 231",
    " no shutdown",
    "interface ethernet0/3",
    " switchport mode access",
    " switchport access vlan 232",
    " no shutdown",
]

cfg_trunk_sw1 = [
    "interface ethernet0/0",
    " switchport trunk encapsulation dot1q",
    " switchport mode trunk",
    " switchport trunk allowed vlan 230,231,232,1299",
    " no shutdown"
]

cfg_trunk_sw2 = [
    "interface ethernet0/0",
    " switchport trunk encapsulation dot1q",
    " switchport mode trunk",
    " switchport trunk allowed vlan 230,231,232,1299",
    " no shutdown"
]

# -----------------------------
# Configuracion en MikroTik R1
# -----------------------------
cfg_r1 = [
    "/interface vlan add name=ventas230 vlan-id=230 interface=ether2",
    "/interface vlan add name=tecnica231 vlan-id=231 interface=ether2",
    "/interface vlan add name=visit232 vlan-id=232 interface=ether2",

    "/ip address add address=10.10.12.65/27 interface=ventas230",
    "/ip address add address=10.10.12.97/28 interface=tecnica231",
    "/ip address add address=10.10.12.113/29 interface=visit232",

    "/ip pool add name=pool-ventas ranges=10.10.12.66-10.10.12.94",
    "/ip pool add name=pool-tecnica ranges=10.10.12.98-10.10.12.110",
    "/ip dhcp-server add name=dhcp-ventas interface=ventas230 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica231 address-pool=pool-tecnica disabled=no",
    "/ip dhcp-server network add address=10.10.12.64/27 gateway=10.10.12.65",
    "/ip dhcp-server network add address=10.10.12.96/28 gateway=10.10.12.97",

    "/ip firewall nat add chain=srcnat src-address=10.10.12.64/27 out-interface=ether1 action=masquerade",
    "/ip firewall nat add chain=srcnat src-address=10.10.12.96/28 out-interface=ether1 action=masquerade",
]

# -----------------------------
# Configuracion en MikroTik R2
# -----------------------------
cfg_r2 = [
    "/ip route add dst-address=10.10.12.64/27 gateway=10.10.12.1",
    "/ip route add dst-address=10.10.12.96/28 gateway=10.10.12.1",
    "/ip route add dst-address=10.10.12.112/29 gateway=10.10.12.1",
]

# -----------------------------
# Ejecucion
# -----------------------------
for device in devices:
    print(f"\n Conectando a {device['host']}...")
    try:
        connection = ConnectHandler(**device)

        # Para Cisco: entrar a modo enable
        if device["device_type"] == "cisco_ios":
            connection.enable()

        if device["host"] == "10.10.12.2":  # SW1
            connection.send_config_set(cfg_sw)
            connection.send_config_set(cfg_trunk_sw1)
            print(connection.send_command("show vlan brief"))

        elif device["host"] == "10.10.12.1":  # MikroTik R1
            for cmd in cfg_r1:
                connection.send_command(cmd)
            print(connection.send_command("/ip address print"))
            print(connection.send_command("/ip dhcp-server print"))

        elif device["host"] == "10.10.12.4":  # MikroTik R2
            for cmd in cfg_r2:
                connection.send_command(cmd)
            print(connection.send_command("/ip route print"))

        elif device["host"] == "10.10.12.3":  # SW2
            connection.send_config_set(cfg_sw)
            connection.send_config_set(cfg_trunk_sw2)
            print(connection.send_command("show vlan brief"))

        connection.disconnect()

    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        print(f" Error al conectar con {device['host']}: {e}")

print("\n Configuracion finalizada en todos los dispositivos.")
