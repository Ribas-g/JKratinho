"""
Debug: Mostrar qual ponto do path esta sendo escolhido
"""
import sys
import cv2
import numpy as np

# Simular posicao do player
x_player = 203
y_player = 1215

# Destino
x_destino = 374
y_destino = 1342

print(f"Player: ({x_player}, {y_player})")
print(f"Destino: ({x_destino}, {y_destino})")

# Carregar mapa e criar pathfinder
from pathfinding_astar import AStarPathfinder

mapa_pb = cv2.imread('MAPA PRETO E BRANCO.png', 0)
pathfinder = AStarPathfinder(mapa_pb)

# Calcular path
path = pathfinder.find_path(x_player, y_player, x_destino, y_destino)
print(f"\nPath: {len(path)} pontos")

# Simular a logica de escolha
map_width = 1600
map_height = 900

# Escalas (aproximadas)
escala_x = map_width / mapa_pb.shape[1]
escala_y = map_height / mapa_pb.shape[0]

raio_visivel_x = int((map_width / escala_x) * 0.25)
raio_visivel_y = int((map_height / escala_y) * 0.25)

x_min_visivel = x_player - raio_visivel_x
x_max_visivel = x_player + raio_visivel_x
y_min_visivel = y_player - raio_visivel_y
y_max_visivel = y_player + raio_visivel_y

dist_minima = 50
dist_maxima = 200

print(f"\nArea visivel:")
print(f"  X: {x_min_visivel} a {x_max_visivel}")
print(f"  Y: {y_min_visivel} a {y_max_visivel}")
print(f"  Raio X: {raio_visivel_x}px")
print(f"  Raio Y: {raio_visivel_y}px")

print(f"\nDistancias:")
print(f"  Minima: {dist_minima}px")
print(f"  Maxima: {dist_maxima}px")

# Percorrer path
ponto_escolhido = None
dist_escolhida = 0
pontos_analisados = []

print(f"\n--- Analisando primeiros 50 pontos do path ---")

for i, (px, py) in enumerate(path[:50]):
    dist = np.sqrt((px - x_player)**2 + (py - y_player)**2)

    # Verificar condicoes
    muito_perto = dist < dist_minima
    muito_longe = dist > dist_maxima
    visivel_x = x_min_visivel <= px <= x_max_visivel
    visivel_y = y_min_visivel <= py <= y_max_visivel
    visivel = visivel_x and visivel_y

    status = "OK"
    if muito_perto:
        status = "MUITO_PERTO"
    elif muito_longe:
        status = "MUITO_LONGE"
    elif not visivel:
        status = "NAO_VISIVEL"

    # Armazenar
    pontos_analisados.append({
        'index': i,
        'pos': (px, py),
        'dist': dist,
        'status': status,
        'escolhido': False
    })

    # Logica de escolha
    if muito_perto:
        continue

    if muito_longe:
        print(f"  [{i:2d}] ({px:4d},{py:4d}) dist={dist:6.1f}px -> PAROU (muito longe)")
        break

    if visivel:
        ponto_escolhido = (px, py)
        dist_escolhida = dist
        pontos_analisados[-1]['escolhido'] = True
        print(f"  [{i:2d}] ({px:4d},{py:4d}) dist={dist:6.1f}px -> ACEITO (continua)")
    else:
        print(f"  [{i:2d}] ({px:4d},{py:4d}) dist={dist:6.1f}px -> PAROU (nao visivel)")
        break

print(f"\n=== RESULTADO ===")
if ponto_escolhido:
    print(f"Ponto escolhido: {ponto_escolhido}")
    print(f"Distancia: {dist_escolhida:.1f}px")
else:
    print("NENHUM ponto escolhido!")

# Gerar imagem visual
mapa_colorido = cv2.imread('MINIMAPA CERTOPRETO.png')
if len(mapa_colorido.shape) == 2:
    vis = cv2.cvtColor(mapa_colorido, cv2.COLOR_GRAY2BGR)
else:
    vis = mapa_colorido.copy()

# Desenhar path completo (cinza)
for i in range(len(path) - 1):
    cv2.line(vis, path[i], path[i+1], (128, 128, 128), 1)

# Desenhar pontos analisados
for info in pontos_analisados:
    px, py = info['pos']
    if info['escolhido']:
        cv2.circle(vis, (px, py), 8, (0, 255, 0), -1)  # Verde = escolhido
    elif info['status'] == "OK":
        cv2.circle(vis, (px, py), 4, (255, 255, 0), -1)  # Amarelo = valido
    elif info['status'] == "MUITO_PERTO":
        cv2.circle(vis, (px, py), 3, (255, 0, 0), -1)  # Azul = muito perto
    elif info['status'] == "MUITO_LONGE":
        cv2.circle(vis, (px, py), 4, (0, 0, 255), -1)  # Vermelho = muito longe
    else:
        cv2.circle(vis, (px, py), 3, (128, 0, 128), -1)  # Roxo = nao visivel

# Player
cv2.circle(vis, (x_player, y_player), 15, (255, 0, 0), -1)
cv2.putText(vis, "PLAYER", (x_player + 20, y_player), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

# Destino
cv2.circle(vis, (x_destino, y_destino), 15, (0, 255, 255), -1)

# Ponto escolhido
if ponto_escolhido:
    cv2.circle(vis, ponto_escolhido, 20, (0, 255, 0), 3)
    cv2.putText(vis, "ESCOLHIDO", (ponto_escolhido[0] + 25, ponto_escolhido[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

# Crop
margin = 300
x_min = max(0, min(x_player, x_destino) - margin)
x_max = min(vis.shape[1], max(x_player, x_destino) + margin)
y_min = max(0, min(y_player, y_destino) - margin)
y_max = min(vis.shape[0], max(y_player, y_destino) + margin)

crop = vis[y_min:y_max, x_min:x_max]
cv2.imwrite('debug_escolha_ponto.png', crop)

print(f"\nImagem salva: debug_escolha_ponto.png")
print(f"  Azul = Muito perto")
print(f"  Amarelo = Valido mas nao escolhido")
print(f"  Verde GRANDE = PONTO ESCOLHIDO")
print(f"  Vermelho = Muito longe")
print(f"  Roxo = Nao visivel")
