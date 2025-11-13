"""
Debug da transformacao mundo -> tela
"""
import json

# Carregar config
with open('map_transform_config.json', 'r') as f:
    config = json.load(f)

print("="*70)
print("DEBUG: TRANSFORMACAO MUNDO -> TELA")
print("="*70)

print("\nConfiguracao carregada:")
print(f"  Centro tela: ({config['centro_mapa_tela']['x']}, {config['centro_mapa_tela']['y']})")
print(f"  Escala X: {config['escala']['x']:.6f}")
print(f"  Escala Y: {config['escala']['y']:.6f}")

# Posicoes
x_player = 253
y_player = 1207
x_waypoint = 371  # Waypoint [7]
y_waypoint = 1336

print(f"\nPlayer mundo: ({x_player}, {y_player})")
print(f"Waypoint mundo: ({x_waypoint}, {y_waypoint})")

# Calcular delta
delta_x = x_waypoint - x_player
delta_y = y_waypoint - y_player

print(f"\nDelta:")
print(f"  X: {delta_x} pixels")
print(f"  Y: {delta_y} pixels")

# Aplicar escala
centro_x = config['centro_mapa_tela']['x']
centro_y = config['centro_mapa_tela']['y']
escala_x = config['escala']['x']
escala_y = config['escala']['y']

clique_x = int(centro_x + delta_x * escala_x)
clique_y = int(centro_y + delta_y * escala_y)

print(f"\nTransformacao:")
print(f"  Centro + (delta * escala)")
print(f"  X: {centro_x} + ({delta_x} * {escala_x:.4f}) = {clique_x}")
print(f"  Y: {centro_y} + ({delta_y} * {escala_y:.4f}) = {clique_y}")

print(f"\nClique na tela: ({clique_x}, {clique_y})")

# Verificar se esta dentro da regiao do mapa
map_region = config['map_region']
print(f"\nRegiao do mapa na tela:")
print(f"  X: {map_region['x']} - {map_region['x'] + map_region['width']}")
print(f"  Y: {map_region['y']} - {map_region['y'] + map_region['height']}")
print(f"  Centro: ({map_region['x'] + map_region['width']//2}, {map_region['y'] + map_region['height']//2})")

dentro_x = map_region['x'] <= clique_x <= map_region['x'] + map_region['width']
dentro_y = map_region['y'] <= clique_y <= map_region['y'] + map_region['height']

if dentro_x and dentro_y:
    print(f"\nOK: Clique esta dentro da regiao do mapa")
else:
    print(f"\nALERTA: Clique esta FORA da regiao do mapa!")
    print(f"  X ok: {dentro_x}")
    print(f"  Y ok: {dentro_y}")

print("\n" + "="*70)
print("VERIFICACAO:")
print("="*70)
print("\nPara o player estar no centro da tela (800, 450):")
print("E o waypoint aparecer na direcao correta...")
print(f"\nO clique deveria estar em (~{clique_x}, ~{clique_y})")
print("\nCompare com o que o programa esta clicando!")
