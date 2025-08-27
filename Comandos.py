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
# (tu configuración queda igual)
# --------------------------

# --------------------------
# Resultados
# --------------------------
results = []

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
        results.append((device['host'], "OK", None))
    except Exception as e:
        print(f"ERROR en {device['host']}: {e}")
        results.append((device['host'], "ERROR", str(e)))

def run_check(device, cmds):
    print(f"\n>>> Verificación en {device['host']} <<<")
    try:
        conn = ConnectHandler(**device)
        for c in cmds:
            out = conn.send_command(c)
            print(f"\n[{device['host']}] {c}\n{out}")
        conn.disconnect()
        results.append((device['host'] + " (check)", "OK", None))
    except Exception as e:
        print(f"ERROR check {device['host']}: {e}")
        results.append((device['host'] + " (check)", "ERROR", str(e)))

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

    # --------------------------
    # Resumen final
    # --------------------------
    print("\n========== RESUMEN FINAL ==========")
    for host, status, err in results:
        if status == "OK":
            print(f"{host:20} -> ✅ Configurado correctamente")
        else:
            print(f"{host:20} -> ❌ ERROR: {err}")
