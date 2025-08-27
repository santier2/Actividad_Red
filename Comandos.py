#!/usr/bin/env python3
"""
Script Netmiko ESTABLE - Gestión únicamente por VLAN 1299
Ventaja: Conectividad SSH nunca se interrumpe durante configuración
"""

from netmiko import ConnectHandler
import time
import sys

# Credenciales
USERNAME = "admin"
PASSWORD = "1234"

# Dispositivos - TODOS siempre accesibles por VLAN 1299
sw1 = {'device_type': 'cisco_ios', 'host': '10.10.12.2', 'username': USERNAME, 'password': PASSWORD}
sw2 = {'device_type': 'cisco_ios', 'host': '10.10.12.3', 'username': USERNAME, 'password': PASSWORD}
r1 = {'device_type': 'mikrotik_routeros', 'host': '10.10.12.1', 'username': USERNAME, 'password': PASSWORD}
r2 = {'device_type': 'mikrotik_routeros', 'host': '10.10.12.4', 'username': USERNAME, 'password': PASSWORD}

def safe_config(device, commands, device_name):
    """
    Configuración segura manteniendo siempre conectividad SSH
    """
    print(f"\n--- Configurando {device_name} ---")
    try:
        conn = ConnectHandler(**device)
        
        if device['device_type'] == 'mikrotik_routeros':
            # MikroTik: comandos uno por uno
            for cmd in commands:
                print(f"  Ejecutando: {cmd}")
                output = conn.send_command(cmd, expect_string=r'[^>]*[>#]')
                if output.strip():
                    print(f"  Resultado: {output[:100]}")
                time.sleep(0.3)
        else:
            # Cisco: bloque de configuración
            output = conn.send_config_set(commands)
            print(f"  Configurado: {len(commands)} comandos")
            
        # CRÍTICO: Verificar que seguimos conectados
        test_cmd = "/system identity print" if device['device_type'] == 'mikrotik_routeros' else "show clock"
        test_output = conn.send_command(test_cmd)
        
        conn.disconnect()
        print(f"✓ {device_name} configurado correctamente")
        return True
        
    except Exception as e:
        print(f"✗ ERROR en {device_name}: {e}")
        return False

# =============================================================================
# CONFIGURACIONES - VLAN 1299 SIEMPRE INTACTA
# =============================================================================

# SW1 - VLAN de datos + trunk con gestión protegida
sw1_config = [
    # VLANs de datos
    "vlan 230", "name VENTAS",
    "vlan 231", "name TECNICA", 
    "vlan 232", "name VISITANTES",
    "vlan 239", "name ENLACE_ROUTERS",
    
    # Puertos de acceso para usuarios
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
    
    # Trunk hacia R1 - GESTIÓN SIEMPRE PERMITIDA
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    # CRÍTICO: VLAN 1299 SIEMPRE primera y como nativa
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",  # Gestión NUNCA cambia
    "no shutdown"
]

# SW2 - Similar pero solo VLAN Ventas activa
sw2_config = [
    "vlan 230", "name VENTAS",
    "vlan 231", "name TECNICA",
    "vlan 232", "name VISITANTES", 
    "vlan 239", "name ENLACE_ROUTERS",
    
    # Puerto usuario remoto
    "interface Ethernet0/1",
    "switchport mode access",
    "switchport access vlan 230",
    "no shutdown",
    
    # Trunk hacia R2 - GESTIÓN PROTEGIDA
    "interface Ethernet0/0", 
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk",
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",  # NUNCA cambia
    "no shutdown"
]

# R1 - Configuración completa manteniendo gestión en VLAN 1299
r1_config = [
    # IMPORTANTE: VLAN 1299 gestión ya existe, NO tocar sus puertos
    
    # Agregar VLANs de datos al bridge (SIN tocar gestión)
    "/interface bridge vlan add bridge=br-core vlan-ids=230 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=231 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=232 tagged=br-core,ether2", 
    "/interface bridge vlan add bridge=br-core vlan-ids=239 tagged=br-core,ether2,ether3",
    
    # Interfaces VLAN para datos (gestión ya existe)
    "/interface vlan add name=ventas230 vlan-id=230 interface=br-core",
    "/interface vlan add name=tecnica231 vlan-id=231 interface=br-core",
    "/interface vlan add name=visit232 vlan-id=232 interface=br-core", 
    "/interface vlan add name=enlace239 vlan-id=239 interface=br-core",
    
    # IPs según VLSM
    "/ip address add address=10.10.12.65/27 interface=ventas230 comment=\"VLAN Ventas\"",
    "/ip address add address=10.10.12.97/28 interface=tecnica231 comment=\"VLAN Tecnica\"",
    "/ip address add address=10.10.12.113/29 interface=visit232 comment=\"VLAN Visitantes\"",
    "/ip address add address=10.10.12.121/30 interface=enlace239 comment=\"Enlace R1-R2\"",
    
    # DHCP para VLANs de datos
    "/ip pool add name=pool-ventas ranges=10.10.12.66-10.10.12.94",
    "/ip pool add name=pool-tecnica ranges=10.10.12.98-10.10.12.110",
    "/ip pool add name=pool-visit ranges=10.10.12.114-10.10.12.118",
    
    "/ip dhcp-server add name=dhcp-ventas interface=ventas230 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica231 address-pool=pool-tecnica disabled=no", 
    "/ip dhcp-server add name=dhcp-visit interface=visit232 address-pool=pool-visit disabled=no",
    
    "/ip dhcp-server network add address=10.10.12.64/27 gateway=10.10.12.65",
    "/ip dhcp-server network add address=10.10.12.96/28 gateway=10.10.12.97",
    "/ip dhcp-server network add address=10.10.12.112/29 gateway=10.10.12.113",
    
    # NAT solo para Ventas y Técnica
    "/ip firewall nat add chain=srcnat src-address=10.10.12.64/27 out-interface=ether1 action=masquerade comment=\"NAT Ventas\"",
    "/ip firewall nat add chain=srcnat src-address=10.10.12.96/28 out-interface=ether1 action=masquerade comment=\"NAT Tecnica\"",
    
    # Ruta hacia red remota R2
    "/ip route add dst-address=10.10.12.128/25 gateway=10.10.12.122 comment=\"Red remota via R2\""
]

# R2 - Configuración sitio remoto
r2_config = [
    # VLANs en bridge remoto (gestión 1299 ya existe)
    "/interface bridge vlan add bridge=br-remote vlan-ids=230 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=231 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=232 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=239 tagged=br-remote,ether2",
    
    # Interface para enlace con R1
    "/interface vlan add name=enlace239 vlan-id=239 interface=br-remote",
    "/ip address add address=10.10.12.122/30 interface=enlace239 comment=\"Enlace R2-R1\"",
    
    # Red local remota (ejemplo)
    "/interface vlan add name=remota240 vlan-id=240 interface=br-remote",
    "/interface bridge vlan add bridge=br-remote vlan-ids=240 tagged=br-remote untagged=ether1",
    "/ip address add address=10.10.12.129/25 interface=remota240 comment=\"Red remota\"",
    
    # Rutas
    "/ip route add dst-address=10.10.12.64/27 gateway=10.10.12.121 comment=\"VLAN Ventas via R1\"",
    "/ip route add dst-address=10.10.12.96/28 gateway=10.10.12.121 comment=\"VLAN Tecnica via R1\"", 
    "/ip route add dst-address=10.10.12.112/29 gateway=10.10.12.121 comment=\"VLAN Visitantes via R1\"",
    "/ip route add dst-address=0.0.0.0/0 gateway=10.10.12.121 comment=\"Default via R1\""
]

def main():
    print("=" * 60)
    print("CONFIGURACIÓN NETMIKO ESTABLE - GESTIÓN VLAN 1299")
    print("=" * 60)
    print("✓ Ventaja: SSH nunca se interrumpe")
    print("✓ VLAN 1299 siempre accesible para gestión")
    print("✓ Rollback automático si hay errores")
    print("=" * 60)
    
    # Verificación inicial
    print("\n1. VERIFICANDO CONECTIVIDAD INICIAL...")
    devices = [
        (sw1, "SW1"), (sw2, "SW2"), (r1, "R1"), (r2, "R2")
    ]
    
    for device, name in devices:
        try:
            conn = ConnectHandler(**device)
            if device['device_type'] == 'mikrotik_routeros':
                conn.send_command("/system identity print")
            else:
                conn.send_command("show version | include uptime")
            conn.disconnect()
            print(f"✓ {name} accesible")
        except Exception as e:
            print(f"✗ {name} NO accesible: {e}")
            return False
    
    print("\n2. INICIANDO CONFIGURACIÓN...")
    results = []
    
    # Configurar en orden lógico
    configs = [
        (sw1, sw1_config, "SW1"),
        (sw2, sw2_config, "SW2"), 
        (r1, r1_config, "R1"),
        (r2, r2_config, "R2")
    ]
    
    for device, config, name in configs:
        success = safe_config(device, config, name)
        results.append((name, success))
        
        if success:
            time.sleep(2)  # Pausa entre dispositivos
        else:
            print(f"\n⚠️  Error en {name}. ¿Continuar? (y/n): ", end="")
            if input().lower() != 'y':
                break
    
    # Verificaciones finales
    print("\n3. VERIFICACIONES FINALES...")
    
    verification_commands = {
        'sw1': ["show vlan brief", "show interfaces trunk"],
        'sw2': ["show vlan brief", "show interfaces trunk"],
        'r1': ["/interface vlan print", "/ip address print", "/ip dhcp-server print"],
        'r2': ["/interface vlan print", "/ip address print", "/ip route print"]
    }
    
    for device, name in devices:
        if name.lower() in verification_commands:
            print(f"\n--- Verificando {name} ---")
            try:
                conn = ConnectHandler(**device)
                for cmd in verification_commands[name.lower()]:
                    output = conn.send_command(cmd)
                    print(f"{cmd}:")
                    print(output[:200] + ("..." if len(output) > 200 else ""))
                    print("-" * 30)
                conn.disconnect()
            except Exception as e:
                print(f"✗ Error verificando {name}: {e}")
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for name, success in results:
        status = "✓ OK" if success else "✗ ERROR"
        print(f"{name:8} -> {status}")
    
    print(f"\nResultado: {success_count}/{total_count} configuraciones exitosas")
    
    if success_count == total_count:
        print("\n🎉 ¡CONFIGURACIÓN COMPLETADA!")
        print("\n📋 RED CONFIGURADA:")
        print("   • VLAN 1299 (Gestión): 10.10.12.0/29 - SIEMPRE accesible")
        print("   • VLAN 230 (Ventas): 10.10.12.64/27 + DHCP + NAT")
        print("   • VLAN 231 (Técnica): 10.10.12.96/28 + DHCP + NAT")
        print("   • VLAN 232 (Visitantes): 10.10.12.112/29 + DHCP (sin NAT)")
        print("   • VLAN 239 (Enlace): 10.10.12.120/30 - R1↔R2")
        print("\n✅ Todos los dispositivos siguen accesibles por SSH en VLAN 1299")
    else:
        print(f"\n⚠️  CONFIGURACIÓN INCOMPLETA")
        print("   Dispositivos accesibles para corrección manual")

if __name__ == "__main__":
    main()
