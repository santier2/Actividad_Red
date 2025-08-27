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

# SW1 - Configuración inicial con VLANs y puertos de acceso
sw1_phase1 = [
    "vlan 230",
    "name VENTAS",
    "vlan 231", 
    "name TECNICA",
    "vlan 232", 
    "name VISITANTES",
    "vlan 239",
    "name NATIVA",
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
    "no shutdown"
]

# SW1 - Configuración trunk hacia R1 (fase transitoria con VLAN 1299)
sw1_phase2 = [
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q",
    "switchport mode trunk", 
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",
    "no shutdown"
]

# SW1 - Cambiar VLAN nativa a 239 (fase final)
sw1_phase3 = [
    "interface Ethernet0/0",
    "switchport trunk native vlan 239"
]

# SW2 - Configuración inicial con VLANs
sw2_phase1 = [
    "vlan 230",
    "name VENTAS", 
    "vlan 231",
    "name TECNICA",
    "vlan 232",
    "name VISITANTES",
    "vlan 239",
    "name NATIVA",
    "interface Ethernet0/1",
    "switchport mode access",
    "switchport access vlan 230",
    "no shutdown"
]

# SW2 - Configuración trunk hacia R2 (fase transitoria)
sw2_phase2 = [
    "interface Ethernet0/0",
    "switchport trunk encapsulation dot1q", 
    "switchport mode trunk",
    "switchport trunk allowed vlan 1299,230,231,232,239",
    "switchport trunk native vlan 1299",
    "no shutdown"
]

# SW2 - Cambiar VLAN nativa a 239 (fase final)
sw2_phase3 = [
    "interface Ethernet0/0",
    "switchport trunk native vlan 239"
]

# R1 - Configuración VLANs, subinterfaces, DHCP y NAT
r1_phase1 = [
    # Configurar VLANs en el bridge
    "/interface bridge vlan add bridge=br-core vlan-ids=230 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=231 tagged=br-core,ether2", 
    "/interface bridge vlan add bridge=br-core vlan-ids=232 tagged=br-core,ether2",
    "/interface bridge vlan add bridge=br-core vlan-ids=239 tagged=br-core,ether2,ether3",
    
    # Crear subinterfaces VLAN (VLAN 239 se crea en fase separada)
    "/interface vlan add name=ventas230 vlan-id=230 interface=br-core",
    "/interface vlan add name=tecnica231 vlan-id=231 interface=br-core", 
    "/interface vlan add name=visit232 vlan-id=232 interface=br-core",
    
    # Asignar direcciones IP según VLSM
    "/ip address add address=10.10.12.65/27 interface=ventas230",    # 25 hosts
    "/ip address add address=10.10.12.97/28 interface=tecnica231",   # 14 hosts  
    "/ip address add address=10.10.12.113/29 interface=visit232",    # 6 hosts
    
    # Configurar pools DHCP
    "/ip pool add name=pool-ventas ranges=10.10.12.66-10.10.12.94",
    "/ip pool add name=pool-tecnica ranges=10.10.12.98-10.10.12.110", 
    "/ip pool add name=pool-visit ranges=10.10.12.114-10.10.12.118",
    
    # Configurar servidores DHCP
    "/ip dhcp-server add name=dhcp-ventas interface=ventas230 address-pool=pool-ventas disabled=no",
    "/ip dhcp-server add name=dhcp-tecnica interface=tecnica231 address-pool=pool-tecnica disabled=no",
    "/ip dhcp-server add name=dhcp-visit interface=visit232 address-pool=pool-visit disabled=no",
    
    # Configurar redes DHCP
    "/ip dhcp-server network add address=10.10.12.64/27 gateway=10.10.12.65",
    "/ip dhcp-server network add address=10.10.12.96/28 gateway=10.10.12.97", 
    "/ip dhcp-server network add address=10.10.12.112/29 gateway=10.10.12.113",
    
    # Configurar NAT (solo para VLAN Ventas y Técnica)
    "/ip firewall nat add chain=srcnat src-address=10.10.12.64/27 out-interface=ether1 action=masquerade comment=\"NAT VLAN Ventas\"",
    "/ip firewall nat add chain=srcnat src-address=10.10.12.96/28 out-interface=ether1 action=masquerade comment=\"NAT VLAN Tecnica\""
]

# R1 - Cambiar PVID a 239 (fase final)
r1_phase2 = [
    "/interface bridge port set [find interface=ether2] pvid=239",
    "/interface bridge port set [find interface=ether3] pvid=239"
]

# R2 - Configuración inicial del bridge y VLANs
r2_phase1 = [
    # Asegurar configuración de bridge y puertos
    "/interface bridge port set [find interface=ether2] pvid=1299",
    "/interface bridge port set [find interface=ether1] pvid=1299",
    
    # Agregar VLANs funcionales al bridge
    "/interface bridge vlan add bridge=br-remote vlan-ids=230 tagged=br-remote,ether2", 
    "/interface bridge vlan add bridge=br-remote vlan-ids=231 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=232 tagged=br-remote,ether2",
    "/interface bridge vlan add bridge=br-remote vlan-ids=239 tagged=br-remote,ether2 untagged=ether1",
    
    # Red local remota (ejemplo - ajustar según necesidades)
    "/interface vlan add name=remota vlan-id=240 interface=br-remote",
    "/interface bridge vlan add bridge=br-remote vlan-ids=240 tagged=br-remote untagged=ether1",
    "/ip address add address=10.10.12.125/30 interface=remota",
    
    # Ruta por defecto hacia R1 (usando IP de gestión por ahora)
    "/ip route add dst-address=0.0.0.0/0 gateway=10.10.12.1 comment=\"Default via R1 gestion\""
]

# R2 - Cambiar PVID a 239 (fase final)
r2_phase2 = [
    "/interface bridge port set [find interface=ether2] pvid=239",
    "/interface bridge port set [find interface=ether1] pvid=239"
]

# --------------------------
# Variables de control
# --------------------------
results = []

# --------------------------
# Funciones
# --------------------------
def run_cfg(device, commands, phase_name=""):
    print(f"\n--- Configurando {device['host']} {phase_name} ---")
    try:
        conn = ConnectHandler(**device)
        
        # Para MikroTik, enviar comandos uno por uno
        if device['device_type'] == 'mikrotik_routeros':
            for cmd in commands:
                print(f"Ejecutando: {cmd}")
                out = conn.send_command(cmd)
                if out:
                    print(f"Respuesta: {out}")
                time.sleep(0.5)  # Pausa entre comandos
        else:
            # Para Cisco, usar send_config_set
            out = conn.send_config_set(commands)
            print(out)
        
        conn.disconnect()
        results.append((device['host'], phase_name, "OK", None))
        print(f"✓ {device['host']} {phase_name} - Configurado correctamente")
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ ERROR en {device['host']} {phase_name}: {error_msg}")
        
        # Si es error de TCP connection, es esperado en fase de cambio de VLAN
        if "TCP connection" in error_msg and "239" in phase_name:
            print("   ⚠️  Esto es esperado al cambiar VLAN nativa - la configuración debería haberse aplicado")
            results.append((device['host'], phase_name, "OK (conexión perdida esperada)", error_msg))
        else:
            results.append((device['host'], phase_name, "ERROR", error_msg))

def run_check(device, cmds):
    print(f"\n>>> Verificación en {device['host']} <<<")
    try:
        conn = ConnectHandler(**device)
        for c in cmds:
            print(f"\n[{device['host']}] Ejecutando: {c}")
            out = conn.send_command(c)
            print(f"Resultado:\n{out}")
            print("-" * 50)
        conn.disconnect()
        results.append((device['host'] + " (check)", "", "OK", None))
    except Exception as e:
        print(f"✗ ERROR en verificación {device['host']}: {e}")
        results.append((device['host'] + " (check)", "", "ERROR", str(e)))

def test_connectivity():
    """Prueba de conectividad básica antes de configurar"""
    print("\n=== PRUEBA DE CONECTIVIDAD INICIAL ===")
    devices_to_test = [r1, sw1, r2, sw2]
    
    for device in devices_to_test:
        try:
            print(f"Probando conexión a {device['host']}...")
            conn = ConnectHandler(**device)
            if device['device_type'] == 'mikrotik_routeros':
                output = conn.send_command("/system identity print")
            else:
                output = conn.send_command("show version | include uptime")
            conn.disconnect()
            print(f"✓ {device['host']} - Conectado")
        except Exception as e:
            print(f"✗ {device['host']} - Error: {e}")
            return False
    return True

# --------------------------
# Ejecución principal
# --------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("SCRIPT DE CONFIGURACIÓN NETMIKO - VLANS Y ENRUTAMIENTO")
    print("=" * 60)
    print("\n>>> IMPORTANTE: Verificar conectividad a todos los dispositivos <<<")
    print("IPs de gestión: R1(10.10.12.1), SW1(10.10.12.2), SW2(10.10.12.3), R2(10.10.12.4)")
    
    # Prueba de conectividad inicial
    if not test_connectivity():
        print("\n✗ ERROR: No se puede conectar a todos los dispositivos")
        print("Verificar configuración de red de gestión antes de continuar")
        sys.exit(1)
    
    print("\n✓ Conectividad verificada. Iniciando configuración...")
    print("⚠️  ADVERTENCIA: Durante la Fase 3, la conectividad SSH puede perderse temporalmente")
    print("   al cambiar las VLANs nativas. Esto es normal y esperado.")
    time.sleep(5)

    # FASE 1: Configuración inicial de VLANs y subinterfaces
    print("\n" + "=" * 50)
    print("FASE 1: CONFIGURACIÓN INICIAL")
    print("=" * 50)
    
    run_cfg(sw1, sw1_phase1, "VLANs y puertos de acceso")
    time.sleep(2)
    
    run_cfg(sw2, sw2_phase1, "VLANs y puertos de acceso") 
    time.sleep(2)
    
    run_cfg(r1, r1_phase1, "VLANs, DHCP y NAT")
    time.sleep(3)
    
    run_cfg(r2, r2_phase1, "Bridge y VLANs")
    time.sleep(3)

    # FASE 2: Configuración de trunks con VLAN nativa transitoria
    print("\n" + "=" * 50)
    print("FASE 2: CONFIGURACIÓN DE TRUNKS")
    print("=" * 50)
    
    run_cfg(sw1, sw1_phase2, "Trunk hacia R1")
    time.sleep(2)
    
    run_cfg(sw2, sw2_phase2, "Trunk hacia R2")
    time.sleep(2)

    # FASE 3: Cambio a VLAN nativa definitiva (orden crítico)
    print("\n" + "=" * 50)
    print("FASE 3: CAMBIO A VLAN NATIVA 239")
    print("=" * 50)
    print("NOTA: Se configurará primero la interfaz VLAN 239 en routers")
    print("antes de cambiar los PVIDs para mantener conectividad")
    
    # Primero crear las interfaces VLAN 239 sin cambiar PVIDs aún
    print("\n-- Configurando interfaz VLAN 239 en routers --")
    run_cfg(r1, [
        "/interface vlan add name=nativa239 vlan-id=239 interface=br-core",
        "/ip address add address=10.10.12.121/30 interface=nativa239"
    ], "Crear interfaz VLAN 239")
    time.sleep(2)
    
    run_cfg(r2, [
        "/interface vlan add name=enlace239 vlan-id=239 interface=br-remote", 
        "/ip address add address=10.10.12.122/30 interface=enlace239"
    ], "Crear interfaz VLAN 239")
    time.sleep(2)
    
    # Ahora cambiar switches a VLAN nativa 239
    print("\n-- Cambiando VLAN nativa en switches --")
    run_cfg(sw1, sw1_phase3, "VLAN nativa 239")
    time.sleep(2)
    
    run_cfg(sw2, sw2_phase3, "VLAN nativa 239") 
    time.sleep(2)
    
    # Finalmente cambiar PVIDs en routers 
    print("\n-- Cambiando PVIDs en routers --")
    print("ADVERTENCIA: Puede perderse conectividad SSH temporalmente")
    
    run_cfg(r1, r1_phase2, "Cambio PVID a 239")
    time.sleep(3)
    
    run_cfg(r2, r2_phase2, "Cambio PVID a 239")
    time.sleep(3)

    # VERIFICACIONES
    print("\n" + "=" * 50)
    print("VERIFICACIONES FINALES")
    print("=" * 50)
    
    # Verificación SW1
    run_check(sw1, [
        "show vlan brief",
        "show interfaces trunk", 
        "show ip interface brief"
    ])
    
    # Verificación SW2
    run_check(sw2, [
        "show vlan brief",
        "show interfaces trunk",
        "show ip interface brief"
    ])
    
    # Verificación R1
    run_check(r1, [
        "/interface bridge vlan print",
        "/interface vlan print", 
        "/ip address print",
        "/ip dhcp-server print",
        "/ip firewall nat print",
        "/ip route print"
    ])
    
    # Verificación R2
    run_check(r2, [
        "/interface bridge vlan print",
        "/interface vlan print",
        "/ip address print", 
        "/ip route print"
    ])

    # RESUMEN FINAL
    print("\n" + "=" * 60)
    print("RESUMEN FINAL DE CONFIGURACIÓN")
    print("=" * 60)
    
    success_count = 0
    total_count = len(results)
    
    for host, phase, status, err in results:
        phase_str = f" ({phase})" if phase else ""
        if status == "OK":
            print(f"✓ {host:25}{phase_str:20} -> Configurado correctamente")
            success_count += 1
        else:
            print(f"✗ {host:25}{phase_str:20} -> ERROR: {err}")
    
    print(f"\nResultado: {success_count}/{total_count} configuraciones exitosas")
    
    if success_count == total_count:
        print("\n ¡CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
        print("\nVLANs configuradas:")
        print("- VLAN 230 (Ventas): 10.10.12.64/27 - 25 hosts")
        print("- VLAN 231 (Técnica): 10.10.12.96/28 - 14 hosts") 
        print("- VLAN 232 (Visitantes): 10.10.12.112/29 - 6 hosts")
        print("- VLAN 239 (Nativa): Enlace R1-R2")
        print("- VLAN 1299 (Gestión): 10.10.12.0/29 - 5 hosts")
        print("\nServicios habilitados:")
        print("- DHCP en VLANs 230, 231, 232")
        print("- NAT para VLANs 230 (Ventas) y 231 (Técnica)")
        print("- Enrutamiento estático hacia red remota")
    else:
        print(f"\n  CONFIGURACIÓN INCOMPLETA: {total_count - success_count} errores encontrados")
        print("Revisar los errores mostrados arriba y corregir manualmente si es necesario")
