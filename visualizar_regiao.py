"""
VISUALIZAR REGIÃO DA MATRIZ

Mostra a região ao redor das coordenadas reportadas pelo usuário
para entender se realmente é parede ou não
"""

import numpy as np
import cv2

# Carregar matriz
dados = np.load('FARM/mapa_mundo_processado.npz')
matriz = dados['walkable']

print("=" * 80)
print("🔍 ANÁLISE DA REGIÃO ATUAL DO JOGO")
print("=" * 80)

# Coordenadas reportadas pelo usuário
player_x, player_y = 361, 1243
target_x, target_y = 366, 1235

print(f"\n📍 POSIÇÃO DO PLAYER: ({player_x}, {player_y})")
print(f"🎯 POSIÇÃO DO TARGET (MOB): ({target_x}, {target_y})")

# Verificar área 10x10 ao redor do player
print(f"\n{'='*80}")
print(f"📊 ÁREA 20x20 AO REDOR DO PLAYER ({player_x}, {player_y})")
print(f"{'='*80}")

# Criar visualização ASCII
print("\n   X →")
print("Y ↓")

for dy in range(-10, 11):
    y = player_y + dy
    linha = f"{y:4d} | "
    for dx in range(-10, 11):
        x = player_x + dx

        # Marcar posições especiais
        if x == player_x and y == player_y:
            linha += "P"  # Player
        elif x == target_x and y == target_y:
            linha += "M"  # Mob/Target
        else:
            # Verificar se é andável
            if 0 <= x < matriz.shape[0] and 0 <= y < matriz.shape[1]:
                valor = matriz[x, y]
                linha += "█" if valor == 1 else "░"
            else:
                linha += "X"

    print(linha)

print("\nLegenda:")
print("  P = Player (você)")
print("  M = Mob/Target (onde está clicando)")
print("  █ = Andável (chão)")
print("  ░ = Parede")
print("  X = Fora dos limites")

# Verificar especificamente as coordenadas
print(f"\n{'='*80}")
print(f"🔍 VERIFICAÇÃO ESPECÍFICA")
print(f"{'='*80}")

coords_check = [
    (player_x, player_y, "Player"),
    (target_x, target_y, "Target (mob)"),
]

for x, y, descricao in coords_check:
    if 0 <= x < matriz.shape[0] and 0 <= y < matriz.shape[1]:
        valor = matriz[x, y]
        status = "✅ ANDÁVEL" if valor == 1 else "❌ PAREDE"
        print(f"   {descricao:15s} ({x:3d}, {y:4d}): {valor} {status}")
    else:
        print(f"   {descricao:15s} ({x:3d}, {y:4d}): ❌ FORA DOS LIMITES")

# Criar PNG da região
print(f"\n{'='*80}")
print(f"🖼️ GERANDO IMAGEM DA REGIÃO")
print(f"{'='*80}")

# Região 100x100 ao redor do player
margin = 50
x_min = max(0, player_x - margin)
x_max = min(matriz.shape[0], player_x + margin)
y_min = max(0, player_y - margin)
y_max = min(matriz.shape[1], player_y + margin)

# Extrair região
regiao = matriz[x_min:x_max, y_min:y_max]

# Criar imagem (transpor para visualização correta)
img = np.zeros((y_max - y_min, x_max - x_min, 3), dtype=np.uint8)

for x in range(x_max - x_min):
    for y in range(y_max - y_min):
        x_abs = x_min + x
        y_abs = y_min + y

        # Cor base: branco=andável, preto=parede
        if regiao[x, y] == 1:
            img[y, x] = [255, 255, 255]  # Branco
        else:
            img[y, x] = [0, 0, 0]  # Preto

# Marcar player (azul)
player_x_local = player_x - x_min
player_y_local = player_y - y_min
if 0 <= player_x_local < (x_max - x_min) and 0 <= player_y_local < (y_max - y_min):
    cv2.circle(img, (player_x_local, player_y_local), 3, (255, 0, 0), -1)  # BGR: azul
    cv2.putText(img, "P", (player_x_local + 5, player_y_local + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

# Marcar target (vermelho)
target_x_local = target_x - x_min
target_y_local = target_y - y_min
if 0 <= target_x_local < (x_max - x_min) and 0 <= target_y_local < (y_max - y_min):
    cv2.circle(img, (target_x_local, target_y_local), 3, (0, 0, 255), -1)  # BGR: vermelho
    cv2.putText(img, "M", (target_x_local + 5, target_y_local + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

# Ampliar imagem para melhor visualização (4x)
img_ampliada = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)

# Salvar
output_path = 'FARM/debug_regiao_player.png'
cv2.imwrite(output_path, img_ampliada)

print(f"   ✅ Imagem salva: {output_path}")
print(f"   📐 Tamanho: {img_ampliada.shape[1]}x{img_ampliada.shape[0]}px")
print(f"   📍 Região: X=[{x_min}-{x_max}], Y=[{y_min}-{y_max}]")
print("\n   Legenda da imagem:")
print("   - Branco = andável (chão)")
print("   - Preto = parede")
print("   - P (azul) = Player")
print("   - M (vermelho) = Mob/Target")

print(f"\n{'='*80}")
