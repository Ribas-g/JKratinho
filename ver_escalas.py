import sys
sys.path.insert(0, '.')

import cv2

# Simular o que o navegador faz
mapa_pb = cv2.imread('MAPA PRETO E BRANCO.png', 0)

# Map region (hardcoded do codigo)
map_region = {
    'x': 0,
    'y': 0,
    'width': 1600,
    'height': 900
}

print(f"Mapa mundo: {mapa_pb.shape[1]}x{mapa_pb.shape[0]} pixels")
print(f"Mapa visivel na tela: {map_region['width']}x{map_region['height']} pixels")

# Calcular escala
escala_x = map_region['width'] / mapa_pb.shape[1]
escala_y = map_region['height'] / mapa_pb.shape[0]

print(f"\nEscala calculada:")
print(f"  X: {escala_x:.6f}")
print(f"  Y: {escala_y:.6f}")

print(f"\nIsso significa:")
print(f"  1 pixel mundo = {escala_x:.3f} pixels tela (X)")
print(f"  1 pixel mundo = {escala_y:.3f} pixels tela (Y)")

print(f"\nExemplo: mover 100px no mundo")
print(f"  Tela X: 100 * {escala_x:.3f} = {100*escala_x:.1f} pixels")
print(f"  Tela Y: 100 * {escala_y:.3f} = {100*escala_y:.1f} pixels")
