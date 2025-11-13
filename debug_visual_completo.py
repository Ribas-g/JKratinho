"""
DEBUG VISUAL COMPLETO
Mostra lado a lado:
1. Mapa P&B (pathfinding)
2. Mapa Colorido (validacao)
3. Path calculado
4. Margem de segurança das paredes
5. Transformacao mundo -> tela

USO:
    python debug_visual_completo.py [destino_x destino_y]
    
    Se destino não fornecido, usa destino padrão (374, 1342) - Deserto
"""
import cv2
import numpy as np
import sys
import io
from pathfinding_astar import AStarPathfinder
from gps_ncc_realtime import GPSRealtimeNCC

print("="*70)
print("DEBUG VISUAL COMPLETO - ANALISE DE SOBREPOSICAO + MARGEM PAREDES")
print("="*70)

# MARGEM DE SEGURANCA (ajustável)
WALL_MARGIN = 5  # pixels de margem das paredes

# 0. OBTER POSIÇÃO ATUAL DO GPS
print("\n[0] Obtendo posicao atual do GPS...")
gps = None
try:
    # Redirecionar stdout temporariamente para evitar erro de encoding com emojis
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    # Inicializar GPS (prints vão para buffer)
    gps = GPSRealtimeNCC()
    
    # Restaurar stdout
    sys.stdout = old_stdout
    
    # Agora pegar posição (sem prints verbosos)
    pos_atual = gps.get_current_position(keep_map_open=False, verbose=False)
    x_player = pos_atual['x']
    y_player = pos_atual['y']
    print(f"  [OK] Posicao atual: ({x_player}, {y_player}) - {pos_atual['zone']}")
except Exception as e:
    # Restaurar stdout em caso de erro
    if 'old_stdout' in locals():
        sys.stdout = old_stdout
    
    # Remover todos os emojis da mensagem de erro
    error_msg = str(e)
    # Remover emojis comuns
    emojis = ['\U0001f680', '\U0001f4f1', '\U0001f4cb', '\U0001f5fa', '\u2705', '\u26a0', '\u274c', '\U0001f3af', '\U0001f4cd']
    for emoji in emojis:
        error_msg = error_msg.replace(emoji, '')
    
    print(f"  [ERRO] Nao foi possivel obter posicao do GPS: {error_msg}")
    print(f"  [FALLBACK] Usando valores padrao...")
    x_player = 253
    y_player = 1207
    # Tentar criar GPS apenas para pegar calibração depois (sem prints)
    try:
        old_stdout_temp = sys.stdout
        sys.stdout = io.StringIO()
        gps = GPSRealtimeNCC()
        sys.stdout = old_stdout_temp
    except:
        if 'old_stdout_temp' in locals():
            sys.stdout = old_stdout_temp
        pass

# Destino (pode ser passado como argumento ou usar padrão)
if len(sys.argv) >= 3:
    try:
        x_destino = int(sys.argv[1])
        y_destino = int(sys.argv[2])
        print(f"  [INFO] Destino fornecido via argumento: ({x_destino}, {y_destino})")
    except:
        x_destino = 374
        y_destino = 1342
        print(f"  [INFO] Argumentos invalidos, usando destino padrao")
else:
    # Destino padrão (Deserto)
    x_destino = 374
    y_destino = 1342
    print(f"  [INFO] Destino padrao: ({x_destino}, {y_destino}) - Deserto")
    print(f"  [DICA] Para usar outro destino: python debug_visual_completo.py X Y")

print(f"\nPlayer: ({x_player}, {y_player})")
print(f"Destino: ({x_destino}, {y_destino})")
print(f"Margem de seguranca das paredes: {WALL_MARGIN}px")

# 1. CARREGAR MAPAS
print("\n[1] CARREGANDO MAPAS")
mapa_pb = cv2.imread('MAPA PRETO E BRANCO.png', 0)
mapa_colorido = cv2.imread('MINIMAPA CERTOPRETO.png')

print(f"  Mapa P&B: {mapa_pb.shape}")
print(f"  Mapa Colorido: {mapa_colorido.shape}")

# Verificar se dimensoes sao iguais
if mapa_pb.shape != mapa_colorido.shape[:2]:
    print(f"  ALERTA: Dimensoes diferentes!")
else:
    print(f"  OK: Dimensoes iguais")

# 2. PATHFINDING COM MARGEM
print("\n[2] CALCULANDO PATH A* (com margem de seguranca)")
pathfinder = AStarPathfinder(mapa_pb, wall_margin=WALL_MARGIN)
path_raw = pathfinder.find_path(x_player, y_player, x_destino, y_destino)
path_simp = None
if path_raw:
    path_simp = pathfinder.simplify_path(path_raw, 150)
    print(f"  [OK] Path com margem: {len(path_raw)} pontos -> {len(path_simp)} waypoints")
else:
    print(f"  [ERRO] Path com margem NAO encontrado! Destino muito proximo da parede?")
    # Tentar sem margem para comparação
    print(f"  [SUGESTAO] Reduza WALL_MARGIN ou ajuste destino")

# Pathfinder SEM margem (para comparação)
print("\n[2b] CALCULANDO PATH A* (SEM margem - comparacao)")
pathfinder_sem_margem = AStarPathfinder(mapa_pb, wall_margin=0)
path_simp_sem_margem = None
try:
    path_raw_sem = pathfinder_sem_margem.find_path(x_player, y_player, x_destino, y_destino)
    if path_raw_sem:
        path_simp_sem_margem = pathfinder_sem_margem.simplify_path(path_raw_sem, 150)
        print(f"  [OK] Path sem margem: {len(path_raw_sem)} pontos -> {len(path_simp_sem_margem)} waypoints")
except Exception as e:
    print(f"  [AVISO] Erro ao calcular path sem margem: {e}")

# Se path_simp não existe, usar path_simp_sem_margem para visualização
if path_simp is None:
    if path_simp_sem_margem:
        print(f"  [AVISO] Usando path sem margem para visualizacao...")
        path_simp = path_simp_sem_margem
        pathfinder = pathfinder_sem_margem  # Usar pathfinder sem margem
    else:
        print(f"  [ERRO] Nenhum path encontrado! Encerrando...")
        exit(1)

# 3. GERAR VISUALIZACOES
print("\n[3] GERANDO VISUALIZACOES")

# Crop area
margin = 200
x_min = max(0, min(x_player, x_destino) - margin)
x_max = min(mapa_pb.shape[1], max(x_player, x_destino) + margin)
y_min = max(0, min(y_player, y_destino) - margin)
y_max = min(mapa_pb.shape[0], max(y_player, y_destino) + margin)

# --- VIS 1: Mapa P&B com path E margem de segurança ---
vis_pb = cv2.cvtColor(mapa_pb, cv2.COLOR_GRAY2BGR)

# VISUALIZAR MARGEM DE SEGURANCA (apenas se tiver margem)
if WALL_MARGIN > 0 and hasattr(pathfinder, 'walkable_mask'):
    # Mostrar áreas não-walkables após aplicar margem (vermelho translúcido)
    mask_margem = pathfinder.walkable_mask
    
    # Criar pathfinder sem margem para comparação
    pathfinder_sem = AStarPathfinder(mapa_pb, wall_margin=0)
    mask_sem_margem = pathfinder_sem.walkable_mask
    
    # Áreas que são walkable sem margem mas bloqueadas pela margem
    zones_proximas_parede = (mask_sem_margem > 0) & (mask_margem == 0)
    
    # Desenhar zonas próximas às paredes (margem de segurança)
    overlay_margem = vis_pb.copy()
    for y in range(zones_proximas_parede.shape[0]):
        for x in range(zones_proximas_parede.shape[1]):
            if zones_proximas_parede[y, x]:
                cv2.circle(overlay_margem, (x, y), 1, (0, 0, 255), -1)  # Vermelho = margem
    vis_pb = cv2.addWeighted(vis_pb, 0.7, overlay_margem, 0.3, 0)

# Path raw (cinza) - apenas se existir
if path_raw:
    for i in range(len(path_raw) - 1):
        cv2.line(vis_pb, path_raw[i], path_raw[i+1], (128, 128, 128), 1)

# Path simplificado (amarelo)
for i in range(len(path_simp) - 1):
    cv2.line(vis_pb, path_simp[i], path_simp[i+1], (0, 255, 255), 3)

# Path SEM margem (magenta) - para comparação
if path_simp_sem_margem:
    for i in range(len(path_simp_sem_margem) - 1):
        cv2.line(vis_pb, path_simp_sem_margem[i], path_simp_sem_margem[i+1], (255, 0, 255), 2, cv2.LINE_AA)

# Waypoints (verde)
for i, (px, py) in enumerate(path_simp):
    cv2.circle(vis_pb, (px, py), 8, (0, 255, 0), -1)
    if i < 10:  # Numerar primeiros
        cv2.putText(vis_pb, str(i), (px+12, py), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

# Player e destino
cv2.circle(vis_pb, (x_player, y_player), 15, (255, 0, 0), -1)
cv2.putText(vis_pb, "P", (x_player+20, y_player), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
cv2.circle(vis_pb, (x_destino, y_destino), 15, (0, 0, 255), -1)
cv2.putText(vis_pb, "D", (x_destino+20, y_destino), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

# Legenda
cv2.putText(vis_pb, f"MAPA P&B (Margem: {WALL_MARGIN}px)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.putText(vis_pb, "Preto=Walkable | Branco=Parede | Vermelho=Margem", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
cv2.putText(vis_pb, "Amarelo=Path com margem | Magenta=Path sem margem", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

crop_pb = vis_pb[y_min:y_max, x_min:x_max]

# --- VIS 2: Mapa Colorido com path E margem ---
vis_col = mapa_colorido.copy()

# VISUALIZAR MARGEM no mapa colorido também (apenas se tiver margem)
if WALL_MARGIN > 0:
    overlay_margem_col = vis_col.copy()
    if 'zones_proximas_parede' in locals():
        for y in range(zones_proximas_parede.shape[0]):
            for x in range(zones_proximas_parede.shape[1]):
                if zones_proximas_parede[y, x]:
                    cv2.circle(overlay_margem_col, (x, y), 1, (0, 0, 255), -1)  # Vermelho = margem
        vis_col = cv2.addWeighted(vis_col, 0.7, overlay_margem_col, 0.3, 0)

# Path raw (cinza) - apenas se existir
if path_raw:
    for i in range(len(path_raw) - 1):
        cv2.line(vis_col, path_raw[i], path_raw[i+1], (128, 128, 128), 1)

# Path simplificado (amarelo)
for i in range(len(path_simp) - 1):
    cv2.line(vis_col, path_simp[i], path_simp[i+1], (0, 255, 255), 3)

# Path SEM margem (magenta) - para comparação
if path_simp_sem_margem:
    for i in range(len(path_simp_sem_margem) - 1):
        cv2.line(vis_col, path_simp_sem_margem[i], path_simp_sem_margem[i+1], (255, 0, 255), 2, cv2.LINE_AA)

# Waypoints (verde)
for i, (px, py) in enumerate(path_simp):
    cv2.circle(vis_col, (px, py), 8, (0, 255, 0), -1)
    if i < 10:
        cv2.putText(vis_col, str(i), (px+12, py), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

# Player e destino
cv2.circle(vis_col, (x_player, y_player), 15, (255, 0, 0), -1)
cv2.putText(vis_col, "P", (x_player+20, y_player), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
cv2.circle(vis_col, (x_destino, y_destino), 15, (0, 0, 255), -1)
cv2.putText(vis_col, "D", (x_destino+20, y_destino), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

# Legenda
cv2.putText(vis_col, f"MAPA COLORIDO (Margem: {WALL_MARGIN}px)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.putText(vis_col, "Colorido=Tem chao | Preto=Buraco | Vermelho=Margem", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

crop_col = vis_col[y_min:y_max, x_min:x_max]

# --- VIS 3: Sobreposicao (Blend) ---
blend = cv2.addWeighted(crop_pb, 0.5, crop_col, 0.5, 0)
cv2.putText(blend, "SOBREPOSICAO (50/50)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

# --- VIS 4: Analise de waypoints ---
info_img = np.zeros((crop_pb.shape[0], 400, 3), dtype=np.uint8)
y_text = 30
cv2.putText(info_img, "WAYPOINTS ANALISADOS", (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
y_text += 30

for i, (px, py) in enumerate(path_simp[:10]):
    dist = np.sqrt((px - x_player)**2 + (py - y_player)**2)

    # Verificar walkable no P&B
    is_walkable_pb = pathfinder.is_walkable(px, py)

    # Verificar tem chao no colorido
    pixel_col = mapa_colorido[py, px]
    tem_chao = (pixel_col[0] > 10 or pixel_col[1] > 10 or pixel_col[2] > 10)

    # Pixel P&B
    pixel_pb = mapa_pb[py, px]

    cor = (0, 255, 0) if is_walkable_pb and tem_chao else (0, 0, 255)

    text = f"[{i}] ({px},{py})"
    cv2.putText(info_img, text, (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)
    y_text += 20

    text2 = f"  Dist:{dist:.0f}px Walk:{is_walkable_pb} Chao:{tem_chao}"
    cv2.putText(info_img, text2, (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.35, cor, 1)
    y_text += 20

    text3 = f"  PB:{pixel_pb} RGB:{pixel_col}"
    cv2.putText(info_img, text3, (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
    y_text += 25

# 4. MONTAR IMAGEM FINAL LADO A LADO
print("\n[4] MONTANDO IMAGEM FINAL")

# Linha 1: P&B + Colorido
row1 = np.hstack([crop_pb, crop_col])

# Linha 2: Sobreposicao + Info
# Ajustar tamanho do info para match
info_resized = cv2.resize(info_img, (crop_pb.shape[1] + crop_col.shape[1] - blend.shape[1], blend.shape[0]))
row2 = np.hstack([blend, info_resized])

# Juntar linhas
final = np.vstack([row1, row2])

cv2.imwrite('debug_visual_completo.png', final)

print(f"  OK: debug_visual_completo.png salvo")
print(f"  Dimensoes: {final.shape[1]}x{final.shape[0]}")

# 5. VERIFICAR ALINHAMENTO EM PONTOS CRITICOS
print("\n[5] VERIFICACAO DE ALINHAMENTO")

pontos_teste = [
    (x_player, y_player, "Player"),
    (x_destino, y_destino, "Destino"),
]
if path_simp and len(path_simp) > 0:
    meio_idx = len(path_simp) // 2
    pontos_teste.append((path_simp[meio_idx][0], path_simp[meio_idx][1], "Meio do path"))

for px, py, nome in pontos_teste:
    pixel_pb = mapa_pb[py, px]
    pixel_col = mapa_colorido[py, px]

    print(f"\n  {nome} ({px}, {py}):")
    print(f"    P&B: {pixel_pb} {'(preto=walk)' if pixel_pb < 128 else '(branco=parede)'}")
    print(f"    Colorido: {pixel_col} {'(tem chao)' if (pixel_col[0]>10 or pixel_col[1]>10 or pixel_col[2]>10) else '(buraco)'}")

print("\n" + "="*70)
print("ANALISE COMPLETA!")
print("="*70)
print("\nVeja a imagem: debug_visual_completo.png")
print("\nLayout:")
print("  TOP-LEFT: Mapa P&B com path")
print("  TOP-RIGHT: Mapa Colorido com path")
print("  BOTTOM-LEFT: Sobreposicao 50/50")
print("  BOTTOM-RIGHT: Analise de waypoints")
print("\nCores:")
print("  Cinza = Path raw (pixel-a-pixel)")
print("  Amarelo = Path simplificado COM margem")
print("  Magenta = Path simplificado SEM margem (comparacao)")
print("  Verde = Waypoints numerados")
print("  Vermelho pontilhado = Zonas bloqueadas pela margem de seguranca")
print("  Azul = Player")
print("  Vermelho grande = Destino")
print(f"\nMargem de seguranca: {WALL_MARGIN}px")
print(f"  Isso significa que o path evita caminhos a menos de {WALL_MARGIN}px das paredes")
