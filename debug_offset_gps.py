"""
DEBUG DE OFFSET DO GPS

Verifica se o GPS está retornando posição correta
e se a conversão tela→mundo está certa
"""

import numpy as np
import sys
from pathlib import Path

# Adicionar FARM ao path
sys.path.insert(0, str(Path(__file__).parent))

# Coordenadas do problema
print("=" * 80)
print("🔍 DEBUG DE OFFSET DO GPS")
print("=" * 80)

# Dados do usuário
print("\n📋 DADOS REPORTADOS PELO SISTEMA:")
print("   Player (GPS): (361, 1243)")
print("   Target (mob): (366, 1235)")
print("   Target tela: (941, 258)")
print()

# Carregar matriz
dados = np.load('FARM/mapa_mundo_processado.npz')
matriz = dados['walkable']

# Verificar as coordenadas reportadas
print("📊 VERIFICAÇÃO NA MATRIZ:")
print(f"   matriz[361, 1243] = {matriz[361, 1243]} {'✅ ANDÁVEL' if matriz[361, 1243] == 1 else '❌ PAREDE'} (player)")
print(f"   matriz[366, 1235] = {matriz[366, 1235]} {'✅ ANDÁVEL' if matriz[366, 1235] == 1 else '❌ PAREDE'} (mob)")
print()

# Calcular onde DEVERIA estar para ser andável
print("🔍 PROCURANDO OFFSET CORRETO:")
print("   Testando offsets de Y para encontrar área andável...")
print()

# Testar diferentes offsets
offsets_testados = []
for offset_y in range(-50, 51):
    player_y_test = 1243 + offset_y
    mob_y_test = 1235 + offset_y

    # Verificar se ambos estão em área andável
    if 0 <= player_y_test < matriz.shape[1] and 0 <= mob_y_test < matriz.shape[1]:
        player_val = matriz[361, player_y_test]
        mob_val = matriz[366, mob_y_test]

        # Se AMBOS andáveis, possível offset correto
        if player_val == 1 and mob_val == 1:
            offsets_testados.append((offset_y, player_y_test, mob_y_test))

            # Verificar área 3x3 ao redor do mob também
            mob_area_ok = True
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    x_check = 366 + dx
                    y_check = mob_y_test + dy
                    if 0 <= x_check < matriz.shape[0] and 0 <= y_check < matriz.shape[1]:
                        if matriz[x_check, y_check] == 0:
                            mob_area_ok = False
                            break

            if mob_area_ok:
                print(f"   ✅ Offset Y = {offset_y:+3d}: Player({361}, {player_y_test}), Mob({366}, {mob_y_test}) - ÁREA LIVRE!")

print()

if offsets_testados:
    print("=" * 80)
    print("🎯 OFFSETS POSSÍVEIS ENCONTRADOS:")
    print("=" * 80)

    for offset_y, player_y, mob_y in offsets_testados:
        print(f"   Offset Y: {offset_y:+3d}")
        print(f"   Player correto: (361, {player_y}) - atual: (361, 1243)")
        print(f"   Mob correto:    (366, {mob_y}) - atual: (366, 1235)")
        print()

    # Offset mais provável (mais próximo de -29)
    offset_provavel = min(offsets_testados, key=lambda x: abs(x[0] + 29))
    print(f"   🎯 OFFSET MAIS PROVÁVEL: {offset_provavel[0]:+3d} pixels no Y")
    print(f"      (mais próximo do esperado -29)")
    print()
else:
    print("   ❌ Nenhum offset encontrado onde ambos seriam andáveis!")
    print()

# Análise da conversão tela→mundo
print("=" * 80)
print("🧮 ANÁLISE DA CONVERSÃO TELA→MUNDO")
print("=" * 80)

# Dados da conversão
centro_x, centro_y = 800, 450  # Centro da tela
escala = 25.0  # px/tile

print(f"\n📐 CONFIGURAÇÃO ATUAL:")
print(f"   Centro tela: ({centro_x}, {centro_y})")
print(f"   Escala: {escala}")
print(f"   Player mundo (GPS): (361, 1243)")
print()

# Calcular conversão tela→mundo manualmente
target_tela_x, target_tela_y = 941, 258
delta_tela_x = target_tela_x - centro_x
delta_tela_y = target_tela_y - centro_y

print(f"🎯 CONVERSÃO TARGET (MOB):")
print(f"   Target tela: ({target_tela_x}, {target_tela_y})")
print(f"   Delta tela: ({delta_tela_x:+4d}, {delta_tela_y:+4d})")
print(f"   Delta tela ÷ escala: ({delta_tela_x/escala:+6.1f}, {delta_tela_y/escala:+6.1f})")
print()

# Converter para mundo
delta_mundo_x = delta_tela_x / escala
delta_mundo_y = delta_tela_y / escala

target_mundo_x = 361 + delta_mundo_x
target_mundo_y = 1243 + delta_mundo_y

print(f"   Target mundo calculado: ({target_mundo_x:.1f}, {target_mundo_y:.1f})")
print(f"   Target mundo reportado: (366.0, 1235.0)")
print(f"   Diferença: ({target_mundo_x - 366:.1f}, {target_mundo_y - 1235:.1f})")
print()

# Verificar se a escala está correta
print("=" * 80)
print("🔬 VERIFICAÇÃO DE ESCALA")
print("=" * 80)

print(f"\n   Delta mundo esperado: (366-361, 1235-1243) = (5, -8)")
print(f"   Delta tela: ({delta_tela_x}, {delta_tela_y})")
print(f"   Escala calculada X: {delta_tela_x / 5:.1f} (esperado: 25.0)")
print(f"   Escala calculada Y: {delta_tela_y / -8:.1f} (esperado: 25.0)")
print()

# VERIFICAÇÃO CRÍTICA: O GPS pode estar com offset
print("=" * 80)
print("🚨 HIPÓTESES DO PROBLEMA")
print("=" * 80)

print("""
1️⃣ OFFSET NO GPS:
   - GPS retorna Y com erro de ~29 pixels
   - Posição real: ~29px acima do reportado
   - Causa: Possível problema no processamento do mapa ou crop

2️⃣ ESCALA Y ERRADA:
   - Escala Y pode estar ligeiramente diferente
   - Causa diferença acumulativa em Y

3️⃣ MATRIZ COM OFFSET:
   - Matriz pode ter sido gerada com offset
   - Menos provável (testamos e estava correto)

TESTE RECOMENDADO:
   - Usar GPS para pegar posição atual
   - Andar para área CONHECIDA (ex: spawn)
   - Verificar se offset persiste
   - Se sim, corrigir GPS ou adicionar offset de compensação
""")

print("=" * 80)
