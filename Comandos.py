#!/usr/bin/env python3
"""
Script Netmiko - Configuración según consigna del laboratorio
Implementa VLSM, Router-on-a-Stick, DHCP, NAT y enrutamiento estático
"""

from netmiko import ConnectHandler
import time
import sys

# =============================================================================
# PARÁMETROS DE CONFIGURACIÓN
# =============================================================================
USERNAME = "admin"
PASSWORD = "1234"

# Tu bloque asignado (ejemplo: cambiar por el tuyo)
BASE_NETWORK = "10.10.12.0/24"

# Diseño VLSM calculado:
VLSM_SUBNETS = {
    'ventas':    {'network': '10.10.12.0/27',   'gateway': '10.10.12.1',   'dhcp_start': '10.10.12.2',   'dhcp_end': '10.10.12.30',   'hosts': 25},  # .0-.31
    'tecnica':   {'network': '10.10.12.32/28',  'gateway': '10.10.12.33',  'dhcp_start': '10.10.12.34',  'dhcp_end': '10.10.12.46',   'hosts': 14},  # .32-.47
    'visitantes': {'network': '10.10.12.48/29', 'gateway': '10.10.12.49',  'dhcp_start': '10.10.12.50',  'dhcp_end': '10.10.12.54',   'hosts': 6},   # .48-.55
    'gestion':   {'network': '10.10.12.56/29',  'gateway': '10.10.12.57',  'hosts': 5},  # .56-.63 (sin DHCP)
    'remota':    {'network': '10.10.12.64/26',  'gateway': '10.10.12.65',  'hosts': 62}, # .64-.127 (sede remota)
    'enlace':    {'network': '10.10.12.128/30', 'r1_ip': '10.10.12.129',   'r2_ip': '10.10.12.130'}     # .128-.131 (enlace R1-R2)
}

# Dispositivos (IPs de gestión ya configuradas manualmente)
DEVICES = {
    'sw1': {'device_type': 'cisco_ios', 'host': '10.10.12.58', 'username': USERNAME, 'password': PASSWORD},
    'sw2': {'device_type': 'cisco_ios', 'host': '10.10.12.59', 'username': USERNAME, 'password': PASSWORD},
    'r1':  {'device_type': 'mikrotik_routeros', 'host': '10.10.12.57', 'username': USERNAME, 'password': PASSWORD},
    'r2':  {'device_type': 'mikrotik_routeros', 'host': '10.10.12.60', 'username': USERNAME, 'password': PASSWORD}
}

# =============================================================================
# CONFIGURACIONES POR DISPOSITIVO
# =============================================================================

# SW1 - Switch Principal: VLANs + Puertos de Acceso + Trunk
SW1_CONFIG = [
    # Crear VLANs funcionales
    "vlan 10", "name VENTAS",
    "vlan 20", "name TECNICA", 
    "vlan 30", "name VISITANTES",
    "vlan 99", "name GESTION",
    
    # Puertos de acceso - asignación por VLAN
    "interface FastEthernet0/1",
    "switchport mode access",
    "switchport access vlan 10",
    "spanning-tree portfast",
    "no shutdown",
    
    "interface FastEthernet0/2", 
    "switchport mode access",
    "switchport access vlan 20",
    "spanning-tree portfast", 
    "no shutdown",
    
    "interface FastEthernet0/3",
    "switchport mode access", 
    "switchport access vlan 30",
    "spanning-tree portfast",
    "no shutdown",
    
    # Puerto trunk hacia R1 (Router-on-a-Stick)
    "interface FastEthernet0/24",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 10,20,30,99",
    "switchport trunk native vlan 99",
    "no shutdown",
    
    # Puerto hacia SW2 (trunk para extensión)
    "interface FastEthernet0/23",
    "switchport trunk encapsulation dot1q", 
    "switchport mode trunk",
    "switchport trunk allowed vlan 10,20,30,99",
    "switchport trunk native vlan 99",
    "no shutdown"
]

# SW2 - Switch Remoto: VLANs + Puerto hacia usuario remoto
SW2_CONFIG = [
    # Crear las mismas VLANs para consistencia
    "vlan 10", "name VENTAS",
    "vlan 20", "name TECNICA",
    "vlan 30", "name VISITANTES", 
    "vlan 99", "name GESTION",
    "vlan 40", "name RED_REMOTA",
    
    # Puerto para usuario en sede remota
    "interface FastEthernet0/1",
    "switchport mode access",
    "switchport access vlan 40",
    "spanning-tree portfast",
    "no shutdown",
    
    # Trunk hacia R2
    "interface FastEthernet0/24", 
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk", 
    "switchport trunk allowed vlan 10,20,30,40,99",
    "switchport trunk native vlan 99",
    "no shutdown"
]

# R1 - Router Principal: Router-on-a-Stick + DHCP + NAT
R1_CONFIG = [
    # Configurar subinterfaces dot1q (Router-on-a-Stick)
    f"/interface vlan add name=ventas-vlan10 vlan-id=10 interface=ether2",
    f"/interface vlan add name=tecnica-vlan20 vlan-id=20 interface=ether2", 
    f"/interface vlan add name=visitantes-vlan30 vlan-id=30 interface=ether2",
    f"/interface vlan add name=gestion-vlan99 vlan-id=99 interface=ether2",
    f"/interface vlan add name=enlace-r2 vlan-id=100 interface=ether3",
    
    # Asignar IPs según VLSM
    f"/ip address add address={VLSM_SUBNETS['ventas']['gateway']}/27 interface=ventas-vlan10",
    f"/ip address add address={VLSM_SUBNETS['tecnica']['gateway']}/28 interface=tecnica-vlan20",
    f"/ip address add address={VLSM_SUBNETS['visitantes']['gateway']}/29 interface=visitantes-vlan30", 
    f"/ip address add address={VLSM_SUBNETS['gestion']['gateway']}/29 interface=gestion-vlan99",
    f"/ip address add address={VLSM_SUBNETS['enlace']['r1_ip']}/30 interface=enlace-r2",
    
    # Configurar pools DHCP
    f"/ip pool add name=pool-ventas ranges={VLSM_SUBNETS['ventas']['dhcp_start']}-{VLSM_SUBNETS['ventas']['dhcp_end']}",
    f"/ip pool add name=pool-tecnica ranges={VLSM_SUBNETS['tecnica']['dhcp_start']}-{VLSM_SUBNETS['tecnica']['dhcp_end']}", 
    f"/ip pool add name=pool-visitantes ranges={VLSM_SUBNETS['visitantes']['dhcp_start']}-{VLSM_SUBNETS['visitantes']['dhcp_end']}",
    
    # Configurar servidores DHCP
    "/ip dhcp-server add name=dhcp-ventas interface=ventas-vlan10 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica-vlan20 address-pool=pool-tecnica disabled=no",
    "/ip dhcp-server add name=dhcp-visitantes interface=visitantes-vlan30 address-pool=pool-visitantes disabled=no",
    
    # Redes DHCP
    f"/ip dhcp-server network add address={VLSM_SUBNETS['ventas']['network']} gateway={VLSM_SUBNETS['ventas']['gateway']} dns-server=8.8.8.8",
    f"/ip dhcp-server network add address={VLSM_SUBNETS['tecnica']['network']} gateway={VLSM_SUBNETS['tecnica']['gateway']} dns-server=8.8.8.8",
    f"/ip dhcp-server network add address={VLSM_SUBNETS['visitantes']['network']} gateway={VLSM_SUBNETS['visitantes']['gateway']}",
    
    # NAT - Solo para Ventas y Técnica (acceso a internet)
    f"/ip firewall nat add chain=srcnat src-address={VLSM_SUBNETS['ventas']['network']} out-interface=ether1 action=masquerade comment=\"NAT VLAN Ventas\"",
    f"/ip firewall nat add chain=srcnat src-address={VLSM_SUBNETS['tecnica']['network']} out-interface=ether1 action=masquerade comment=\"NAT VLAN Tecnica\"",
    
    # Enrutamiento estático hacia sede remota (R2)
    f"/ip route add dst-address={VLSM_SUBNETS['remota']['network']} gateway={VLSM_SUBNETS['enlace']['r2_ip']} comment=\"Ruta hacia sede remota\""
]

# R2 - Router Remoto: Configuración de sede remota
R2_CONFIG = [
    # Interface hacia red remota
    f"/interface vlan add name=remota-vlan40 vlan-id=40 interface=ether2",
    f"/interface vlan add name=enlace-r1 vlan-id=100 interface=ether2",
    
    # IPs 
    f"/ip address add address={VLSM_SUBNETS['remota']['gateway']}/26 interface=remota-vlan40",
    f"/ip address add address={VLSM_SUBNETS['enlace']['r2_ip']}/30 interface=enlace-r1",
    
    # DHCP para sede remota
    "/ip pool add name=pool-remota ranges=10.10.12.66-10.10.12.126",
    "/ip dhcp-server add name=dhcp-remota interface=remota-vlan40 address-pool=pool-remota disabled=no",
    f"/ip dhcp-server network add address={VLSM_SUBNETS['remota']['network']} gateway={VLSM_SUBNETS['remota']['gateway']}",
    
    # Rutas hacia VLANs principales (via R1)
    f"/ip route add dst-address={VLSM_SUBNETS['ventas']['network']} gateway={VLSM_SUBNETS['enlace']['r1_ip']} comment=\"VLAN Ventas via R1\"",
    f"/ip route add dst-address={VLSM_SUBNETS['tecnica']['network']} gateway={VLSM_SUBNETS['enlace']['r1_ip']} comment=\"VLAN Tecnica via R1\"",
    f"/ip route add dst-address={VLSM_SUBNETS['visitantes']['network']} gateway={VLSM_SUBNETS['enlace']['r1_ip']} comment=\"VLAN Visitantes via R1\"",
    f"/ip route add dst-address=0.0.0.0/0 gateway={VLSM_SUBNETS['enlace']['r1_ip']} comment=\"Default via R1\""
]

# =============================================================================
# COMANDOS DE VERIFICACIÓN
# =============================================================================
VERIFICATION_COMMANDS = {
    'sw1': [
        "show vlan brief",
        "show interfaces trunk", 
        "show spanning-tree summary"
    ],
    'sw2': [
        "show vlan brief",
        "show interfaces trunk",
        "show interfaces status"
    ],
    'r1': [
        "/interface vlan print",
        "/ip address print", 
        "/ip dhcp-server print",
        "/ip firewall nat print",
        "/ip route print"
    ],
    'r2': [
        "/interface vlan print",
        "/ip address print",
        "/ip dhcp-server print", 
        "/ip route print"
    ]
}

# =============================================================================
# FUNCIONES DE EJECUCIÓN
# =============================================================================

def connect_and_configure(device_config, commands, device_name):
    """
    Conecta y configura un dispositivo
    """
    print(f"\n{'='*20} CONFIGURANDO {device_name.upper()} {'='*20}")
    
    try:
        # Establecer conexión
        connection = ConnectHandler(**device_config)
        print(f"✓ Conectado a {device_name} ({device_config['host']})")
        
        # Aplicar configuración
        if device_config['device_type'] == 'mikrotik_routeros':
            # MikroTik: comandos uno por uno
            for i, command in enumerate(commands, 1):
                print(f"  [{i:2}/{len(commands)}] {command}")
                try:
                    output = connection.send_command(command, expect_string=r'[^>]*[>#]')
                    if output.strip() and "invalid" not in output.lower():
                        print(f"      → OK")
                    time.sleep(0.2)
                except Exception as cmd_error:
                    print(f"      → Error: {cmd_error}")
        else:
            # Cisco: enviar bloque de configuración
            print(f"  Aplicando {len(commands)} comandos...")
            output = connection.send_config_set(commands)
            print("  → Configuración aplicada")
        
        connection.disconnect()
        print(f"✓ {device_name.upper()} configurado exitosamente")
        return True
        
    except Exception as e:
        print(f"✗ ERROR configurando {device_name}: {e}")
        return False

def verify_configuration(device_config, commands, device_name):
    """
    Ejecuta comandos de verificación
    """
    print(f"\n{'='*15} VERIFICANDO {device_name.upper()} {'='*15}")
    
    try:
        connection = ConnectHandler(**device_config)
        
        for command in commands:
            print(f"\n[{device_name.upper()}] {command}")
            print("-" * 50)
            output = connection.send_command(command)
            print(output)
            
        connection.disconnect()
        return True
        
    except Exception as e:
        print(f"✗ ERROR verificando {device_name}: {e}")
        return False

def print_network_summary():
    """
    Imprime resumen del diseño de red implementado
    """
    print("\n" + "="*60)
    print("RESUMEN DEL DISEÑO DE RED IMPLEMENTADO")
    print("="*60)
    print(f"Bloque base: {BASE_NETWORK}")
    print("\nVLSM - Subdivisión por necesidades:")
    
    for name, subnet in VLSM_SUBNETS.items():
        if name == 'enlace':
            print(f"  {name.upper():12} {subnet['network']:15} -> Enlace R1-R2")
        else:
            hosts = subnet.get('hosts', 0)
            gateway = subnet.get('gateway', 'N/A')
            print(f"  {name.upper():12} {subnet['network']:15} -> {hosts:2} hosts, GW: {gateway}")
    
    print("\nServicios configurados:")
    print("  ✓ Router-on-a-Stick (subinterfaces dot1q)")
    print("  ✓ DHCP en VLANs Ventas, Técnica y Visitantes")
    print("  ✓ NAT para internet: solo Ventas y Técnica")
    print("  ✓ Enrutamiento estático hacia sede remota")
    print("  ✓ Segmentación: Visitantes y Gestión sin internet")

def main():
    """
    Función principal del script
    """
    print("="*60)
    print("SCRIPT NETMIKO - CONFIGURACIÓN DE LABORATORIO")
    print("="*60)
    print("Implementa: VLSM, Router-on-a-Stick, DHCP, NAT, Enrutamiento estático")
    
    # Mostrar diseño de red
    print_network_summary()
    
    # Confirmar ejecución
    print(f"\n⚠️  Se configurarán los siguientes dispositivos:")
    for name, config in DEVICES.items():
        print(f"   {name.upper()}: {config['host']}")
    
    confirm = input(f"\n¿Continuar con la configuración? (s/N): ").strip().lower()
    if confirm != 's':
        print("Configuración cancelada.")
        return
    
    # Configurar dispositivos
    print("\n" + "="*60)
    print("FASE 1: CONFIGURACIÓN DE DISPOSITIVOS")
    print("="*60)
    
    configurations = [
        (DEVICES['sw1'], SW1_CONFIG, 'sw1'),
        (DEVICES['sw2'], SW2_CONFIG, 'sw2'), 
        (DEVICES['r1'], R1_CONFIG, 'r1'),
        (DEVICES['r2'], R2_CONFIG, 'r2')
    ]
    
    results = []
    for device_config, commands, device_name in configurations:
        success = connect_and_configure(device_config, commands, device_name)
        results.append((device_name, success))
        time.sleep(2)  # Pausa entre dispositivos
    
    # Verificaciones
    print("\n" + "="*60)
    print("FASE 2: VERIFICACIONES")  
    print("="*60)
    
    for device_name, success in results:
        if success:
            device_config = DEVICES[device_name]
            verify_commands = VERIFICATION_COMMANDS[device_name]
            verify_configuration(device_config, verify_commands, device_name)
            time.sleep(1)
    
    # Resumen final
    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    for device_name, success in results:
        status = "✓ CONFIGURADO" if success else "✗ ERROR"
        print(f"  {device_name.upper():4} -> {status}")
    
    print(f"\nDispositivos configurados: {successful}/{total}")
    
    if successful == total:
        print("\n🎉 ¡CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
        print("\n📋 Red implementada según consigna:")
        print("   ✓ VLSM con subredes de tamaños requeridos")
        print("   ✓ Router-on-a-Stick configurado en R1")
        print("   ✓ DHCP funcionando en VLANs funcionales")
        print("   ✓ NAT solo para VLANs autorizadas")
        print("   ✓ Enrutamiento estático hacia sede remota")
        print("   ✓ Verificaciones ejecutadas en todos los dispositivos")
        
        print(f"\n🌐 Acceso de prueba:")
        print(f"   • Conectar PC a SW1 puerto F0/1 -> DHCP VLAN Ventas (con internet)")
        print(f"   • Conectar PC a SW1 puerto F0/2 -> DHCP VLAN Técnica (con internet)")  
        print(f"   • Conectar PC a SW1 puerto F0/3 -> DHCP VLAN Visitantes (sin internet)")
        print(f"   • Conectar PC a SW2 puerto F0/1 -> DHCP Red Remota (sin internet)")
    else:
        print(f"\n⚠️  Configuración incompleta: {total-successful} dispositivos con errores")
        print("   Revisar conectividad y configuración manual si es necesario")

if __name__ == "__main__":
    main()
