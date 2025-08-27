#!/usr/bin/env python3
"""
Script de diagnóstico y corrección para problemas de conectividad VLAN
Analiza y corrige los problemas de conectividad durante cambios de VLAN nativa
"""

from netmiko import ConnectHandler
import time
import sys
import subprocess

# Credenciales
USERNAME = "admin"
PASSWORD = "1234"

# Dispositivos
devices = {
    'sw1': {'device_type': 'cisco_ios', 'host': '10.10.12.2', 'username': USERNAME, 'password': PASSWORD},
    'sw2': {'device_type': 'cisco_ios', 'host': '10.10.12.3', 'username': USERNAME, 'password': PASSWORD},
    'r1': {'device_type': 'mikrotik_routeros', 'host': '10.10.12.1', 'username': USERNAME, 'password': PASSWORD},
    'r2': {'device_type': 'mikrotik_routeros', 'host': '10.10.12.4', 'username': USERNAME, 'password': PASSWORD}
}

def test_ping(host):
    """Prueba conectividad básica con ping"""
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', host], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ PING OK a {host}")
            return True
        else:
            print(f"✗ PING FALLO a {host}")
            return False
    except Exception as e:
        print(f"✗ PING ERROR a {host}: {e}")
        return False

def test_ssh(device_name, device_config):
    """Prueba conectividad SSH"""
    try:
        print(f"Probando SSH a {device_name} ({device_config['host']})...")
        conn = ConnectHandler(**device_config)
        
        if device_config['device_type'] == 'mikrotik_routeros':
            output = conn.send_command("/system identity print")
        else:
            output = conn.send_command("show version | include uptime")
        
        conn.disconnect()
        print(f"✓ SSH OK a {device_name}")
        return True
    except Exception as e:
        print(f"✗ SSH FALLO a {device_name}: {e}")
        return False

def check_vlan_config(device_name, device_config):
    """Verifica configuración actual de VLANs"""
    try:
        print(f"\n=== Verificando configuración VLAN en {device_name} ===")
        conn = ConnectHandler(**device_config)
        
        if device_config['device_type'] == 'mikrotik_routeros':
            commands = [
                "/interface bridge port print",
                "/interface bridge vlan print", 
                "/interface vlan print",
                "/ip address print"
            ]
        else:
            commands = [
                "show vlan brief",
                "show interfaces trunk",
                "show ip interface brief"
            ]
        
        for cmd in commands:
            print(f"\n[{device_name}] {cmd}")
            output = conn.send_command(cmd)
            print(output)
            print("-" * 50)
        
        conn.disconnect()
        return True
        
    except Exception as e:
        print(f"✗ Error verificando {device_name}: {e}")
        return False

def fix_sw2_connectivity():
    """Corrección específica para SW2 - problema común de trunk mal configurado"""
    print("\n=== INTENTANDO CORREGIR SW2 ===")
    
    # Primero intentar por la configuración actual
    sw2_config = devices['sw2'].copy()
    
    try:
        print("Intentando conectar a SW2 para diagnóstico...")
        conn = ConnectHandler(**sw2_config)
        
        # Verificar configuración actual
        print("Verificando configuración de interfaces...")
        output = conn.send_command("show run interface ethernet0/0")
        print("Configuración Ethernet0/0:")
        print(output)
        
        # Si llegamos aquí, podemos intentar corregir
        print("\nAplicando corrección...")
        fix_commands = [
            "interface ethernet0/0",
            "no switchport trunk native vlan",
            "switchport trunk native vlan 1299",
            "switchport trunk allowed vlan 1299,230,231,232,239",
            "no shutdown"
        ]
        
        conn.send_config_set(fix_commands)
        conn.disconnect()
        print("✓ Corrección aplicada a SW2")
        return True
        
    except Exception as e:
        print(f"✗ No se pudo corregir SW2: {e}")
        return False

def fix_mikrotik_connectivity(device_name):
    """Corrección específica para MikroTiks - problema de PVID"""
    print(f"\n=== INTENTANDO CORREGIR {device_name.upper()} ===")
    
    device_config = devices[device_name].copy()
    
    try:
        conn = ConnectHandler(**device_config)
        
        print(f"Verificando configuración de bridge en {device_name}...")
        output = conn.send_command("/interface bridge port print")
        print(output)
        
        # Intentar resetear PVID a gestión
        print(f"Reseteando PVID a 1299 en {device_name}...")
        if device_name == 'r1':
            fix_commands = [
                "/interface bridge port set [find interface=ether2] pvid=1299",
                "/interface bridge port set [find interface=ether3] pvid=1299"
            ]
        else:  # r2
            fix_commands = [
                "/interface bridge port set [find interface=ether2] pvid=1299", 
                "/interface bridge port set [find interface=ether1] pvid=1299"
            ]
        
        for cmd in fix_commands:
            conn.send_command(cmd)
            time.sleep(1)
        
        conn.disconnect()
        print(f"✓ PVID reseteado en {device_name}")
        return True
        
    except Exception as e:
        print(f"✗ No se pudo corregir {device_name}: {e}")
        return False

def diagnostic_sequence():
    """Secuencia completa de diagnóstico"""
    print("=" * 60)
    print("DIAGNÓSTICO DE CONECTIVIDAD DE RED")
    print("=" * 60)
    
    # 1. Pruebas de ping básico
    print("\n1. PRUEBAS DE PING")
    print("-" * 30)
    ping_results = {}
    for name, config in devices.items():
        ping_results[name] = test_ping(config['host'])
    
    # 2. Pruebas de SSH
    print("\n2. PRUEBAS DE SSH")
    print("-" * 30)
    ssh_results = {}
    for name, config in devices.items():
        if ping_results[name]:  # Solo si ping funciona
            ssh_results[name] = test_ssh(name, config)
        else:
            ssh_results[name] = False
            print(f"✗ Saltando SSH a {name} (ping falló)")
    
    # 3. Verificación de configuraciones
    print("\n3. VERIFICACIÓN DE CONFIGURACIONES")
    print("-" * 40)
    for name, config in devices.items():
        if ssh_results[name]:
            check_vlan_config(name, config)
    
    # 4. Intentar correcciones
    print("\n4. INTENTOS DE CORRECCIÓN")
    print("-" * 30)
    
    # Corregir SW2 si tiene problemas
    if not ssh_results.get('sw2', False):
        fix_sw2_connectivity()
        time.sleep(5)
        ssh_results['sw2'] = test_ssh('sw2', devices['sw2'])
    
    # Corregir MikroTiks si tienen problemas
    for router in ['r1', 'r2']:
        if not ssh_results.get(router, False):
            fix_mikrotik_connectivity(router)
            time.sleep(5)
            ssh_results[router] = test_ssh(router, devices[router])
    
    # 5. Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN DE CONECTIVIDAD")
    print("=" * 60)
    
    working_devices = 0
    for name in devices:
        status = "✓ OK" if ssh_results.get(name, False) else "✗ FALLO"
        print(f"{name.upper():8} ({devices[name]['host']:12}) -> {status}")
        if ssh_results.get(name, False):
            working_devices += 1
    
    print(f"\nDispositivos funcionando: {working_devices}/4")
    
    if working_devices == 4:
        print("\n🎉 ¡Todos los dispositivos están accesibles!")
        return True
    else:
        print(f"\n⚠️  {4-working_devices} dispositivos requieren atención manual")
        return False

def safe_vlan_migration():
    """Migración segura de VLANs paso a paso"""
    print("\n" + "=" * 60)
    print("MIGRACIÓN SEGURA DE VLANS")
    print("=" * 60)
    
    input("\nPresiona Enter para continuar con la migración segura...")
    
    # Paso 1: Verificar conectividad inicial
    print("\nPaso 1: Verificando conectividad inicial...")
    if not diagnostic_sequence():
        print("❌ Detener: No todos los dispositivos están accesibles")
        return False
    
    # Paso 2: Configurar VLANs en switches manteniendo gestión
    print("\nPaso 2: Configurando VLANs en switches...")
    
    # SW1 - Mantener gestión funcionando
    sw1_safe_config = [
        "vlan 230", "name VENTAS",
        "vlan 231", "name TECNICA", 
        "vlan 232", "name VISITANTES",
        "vlan 239", "name NATIVA",
        # Puertos de acceso
        "interface Ethernet0/1", "switchport mode access", "switchport access vlan 230", "no shutdown",
        "interface Ethernet0/2", "switchport mode access", "switchport access vlan 231", "no shutdown", 
        "interface Ethernet0/3", "switchport mode access", "switchport access vlan 232", "no shutdown"
    ]
    
    try:
        conn = ConnectHandler(**devices['sw1'])
        conn.send_config_set(sw1_safe_config)
        conn.disconnect()
        print("✓ SW1 configurado")
    except Exception as e:
        print(f"✗ Error en SW1: {e}")
        return False
    
    # SW2 similar
    sw2_safe_config = [
        "vlan 230", "name VENTAS",
        "vlan 231", "name TECNICA",
        "vlan 232", "name VISITANTES", 
        "vlan 239", "name NATIVA",
        "interface Ethernet0/1", "switchport mode access", "switchport access vlan 230", "no shutdown"
    ]
    
    try:
        conn = ConnectHandler(**devices['sw2'])
        conn.send_config_set(sw2_safe_config)
        conn.disconnect()
        print("✓ SW2 configurado")
    except Exception as e:
        print(f"✗ Error en SW2: {e}")
        return False
    
    # Paso 3: Configurar MikroTiks
    print("\nPaso 3: Configurando routers MikroTik...")
    
    # R1 configuración completa
    r1_safe_config = [
        # VLANs en bridge (manteniendo 1299 para gestión)
        "/interface bridge vlan add bridge=br-core vlan-ids=230 tagged=br-core,ether2",
        "/interface bridge vlan add bridge=br-core vlan-ids=231 tagged=br-core,ether2",
        "/interface bridge vlan add bridge=br-core vlan-ids=232 tagged=br-core,ether2", 
        "/interface bridge vlan add bridge=br-core vlan-ids=239 tagged=br-core,ether2,ether3",
        # Interfaces VLAN
        "/interface vlan add name=ventas230 vlan-id=230 interface=br-core",
        "/interface vlan add name=tecnica231 vlan-id=231 interface=br-core",
        "/interface vlan add name=visit232 vlan-id=232 interface=br-core",
        "/interface vlan add name=nativa239 vlan-id=239 interface=br-core",
        # IPs
        "/ip address add address=10.10.12.65/27 interface=ventas230",
        "/ip address add address=10.10.12.97/28 interface=tecnica231", 
        "/ip address add address=10.10.12.113/29 interface=visit232",
        "/ip address add address=10.10.12.121/30 interface=nativa239"
    ]
    
    try:
        conn = ConnectHandler(**devices['r1'])
        for cmd in r1_safe_config:
            conn.send_command(cmd)
            time.sleep(0.5)
        conn.disconnect()
        print("✓ R1 configurado")
    except Exception as e:
        print(f"✗ Error en R1: {e}")
        return False
    
    # R2 configuración
    r2_safe_config = [
        "/interface bridge vlan add bridge=br-remote vlan-ids=230 tagged=br-remote,ether2",
        "/interface bridge vlan add bridge=br-remote vlan-ids=231 tagged=br-remote,ether2",
        "/interface bridge vlan add bridge=br-remote vlan-ids=232 tagged=br-remote,ether2",
        "/interface bridge vlan add bridge=br-remote vlan-ids=239 tagged=br-remote,ether2",
        "/interface vlan add name=enlace239 vlan-id=239 interface=br-remote",
        "/ip address add address=10.10.12.122/30 interface=enlace239"
    ]
    
    try:
        conn = ConnectHandler(**devices['r2'])
        for cmd in r2_safe_config:
            conn.send_command(cmd)
            time.sleep(0.5)
        conn.disconnect()
        print("✓ R2 configurado")
    except Exception as e:
        print(f"✗ Error en R2: {e}")
        return False
    
    # Paso 4: Configurar trunks (CRÍTICO)
    print("\nPaso 4: Configurando trunks (manteniendo gestión)...")
    
    input("⚠️  CRÍTICO: Configurar trunks puede afectar conectividad. Presiona Enter para continuar...")
    
    # SW1 trunk - permitir todas las VLANs incluyendo gestión
    sw1_trunk = [
        "interface Ethernet0/0",
        "switchport trunk encapsulation dot1q",
        "switchport mode trunk",
        "switchport trunk allowed vlan 1299,230,231,232,239",
        "switchport trunk native vlan 1299",  # Mantener gestión como nativa inicialmente
        "no shutdown"
    ]
    
    try:
        conn = ConnectHandler(**devices['sw1'])
        conn.send_config_set(sw1_trunk)
        conn.disconnect()
        print("✓ SW1 trunk configurado")
    except Exception as e:
        print(f"✗ Error configurando trunk SW1: {e}")
    
    time.sleep(3)
    
    # Verificar conectividad después de trunk SW1
    if not test_ssh('sw1', devices['sw1']):
        print("❌ Conectividad perdida con SW1 después del trunk")
        return False
    
    # SW2 trunk
    sw2_trunk = [
        "interface Ethernet0/0", 
        "switchport trunk encapsulation dot1q",
        "switchport mode trunk",
        "switchport trunk allowed vlan 1299,230,231,232,239",
        "switchport trunk native vlan 1299",
        "no shutdown"
    ]
    
    try:
        conn = ConnectHandler(**devices['sw2'])
        conn.send_config_set(sw2_trunk)
        conn.disconnect()
        print("✓ SW2 trunk configurado")
    except Exception as e:
        print(f"✗ Error configurando trunk SW2: {e}")
    
    time.sleep(3)
    
    # Verificar conectividad después de trunks
    print("\nVerificando conectividad después de configurar trunks...")
    if not (test_ssh('sw1', devices['sw1']) and test_ssh('sw2', devices['sw2'])):
        print("❌ Conectividad perdida después de configurar trunks")
        return False
    
    print("\n✅ Configuración completada. Todos los dispositivos siguen accesibles.")
    print("📋 Para cambiar VLAN nativa a 239, ejecutar manualmente cuando sea seguro:")
    print("   SW1/SW2: switchport trunk native vlan 239")
    print("   R1/R2: /interface bridge port set [find interface=etherX] pvid=239")
    
    return True

def main():
    """Función principal"""
    print("🔧 HERRAMIENTAS DE DIAGNÓSTICO Y CORRECCIÓN DE RED")
    print("=" * 60)
    
    while True:
        print("\nOpciones disponibles:")
        print("1. Diagnóstico completo de conectividad")
        print("2. Migración segura de VLANs")
        print("3. Verificar configuración específica")
        print("4. Intentar corrección manual")
        print("5. Salir")
        
        choice = input("\nSelecciona una opción (1-5): ").strip()
        
        if choice == '1':
            diagnostic_sequence()
        elif choice == '2':
            safe_vlan_migration()
        elif choice == '3':
            device = input("Dispositivo (sw1/sw2/r1/r2): ").strip().lower()
            if device in devices:
                check_vlan_config(device, devices[device])
            else:
                print("Dispositivo no válido")
        elif choice == '4':
            print("Correcciones manuales disponibles:")
            print("a. Corregir SW2")
            print("b. Corregir R1")
            print("c. Corregir R2")
            subchoice = input("Selecciona (a/b/c): ").strip().lower()
            
            if subchoice == 'a':
                fix_sw2_connectivity()
            elif subchoice == 'b':
                fix_mikrotik_connectivity('r1')
            elif subchoice == 'c':
                fix_mikrotik_connectivity('r2')
        elif choice == '5':
            break
        else:
            print("Opción no válida")

if __name__ == "__main__":
    main()
