"""
DEBUG: Transformação de Coordenadas Mundo → Tela
Mostra onde o sistema está clicando vs onde deveria clicar

Visualiza:
1. Path calculado (pontos verdes onde deveria clicar)
2. Tela REAL do emulador com cliques sobrepostos (onde realmente vai clicar)
3. Comparação lado a lado

USO:
    python debug_clique_coordenadas.py [destino_x destino_y]
    
    Se destino não fornecido, usa destino padrão (374, 1342) - Deserto
"""
import cv2
import numpy as np
import json
import os
import sys
import io
import time
from pathfinding_astar import AStarPathfinder
from gps_ncc_realtime import GPSRealtimeNCC

print("="*70)
print("DEBUG: TRANSFORMACAO COORDENADAS MUNDO -> TELA")
print("="*70)

# MARGEM DE SEGURANCA
WALL_MARGIN = 20

# 0. OBTER POSIÇÃO ATUAL DO GPS E CAPTURAR TELA REAL
print("\n[0] Inicializando GPS e capturando tela real...")
gps = None
screenshot_real = None
map_region_real = None
map_processed_real = None

try:
    # Inicializar GPS
    print("  [1/6] Inicializando GPS...")
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        gps = GPSRealtimeNCC()
        sys.stdout = old_stdout
        print("  [OK] GPS inicializado com sucesso")
    except Exception as e_init:
        sys.stdout = old_stdout
        error_msg = str(e_init)
        emojis = ['\U0001f680', '\U0001f4f1', '\U0001f4cb', '\U0001f5fa', '\u2705', '\u26a0', '\u274c', '\U0001f3af', '\U0001f4cd']
        for emoji in emojis:
            error_msg = error_msg.replace(emoji, '')
        raise Exception(f"Erro ao inicializar GPS: {error_msg}")
    
    # Verificar se dispositivo está conectado
    print("  [2/6] Verificando dispositivo ADB...")
    try:
        # Verificar se dispositivo está conectado (gps.device já é o dispositivo conectado)
        if gps.device is None:
            raise Exception("Nenhum dispositivo ADB encontrado! Abra o BlueStacks e verifique a conexao ADB.")
        print(f"  [OK] Dispositivo encontrado: {gps.device.serial}")
    except Exception as e:
        raise Exception(f"Erro ao verificar dispositivo: {e}")
    
    # IMPORTANTE: Abrir mapa ANTES de capturar para ter o mapa visível
    print("  [3/6] Abrindo mapa no jogo...")
    try:
        gps.click_button('open')
        print("  [OK] Comando para abrir mapa enviado")
        
        # Aguardar mapa abrir completamente
        print("  [INFO] Aguardando mapa abrir (1.5s)...")
        time.sleep(1.5)  # Aumentar tempo de espera
        print("  [OK] Mapa deve estar aberto agora")
    except Exception as e:
        raise Exception(f"Erro ao abrir mapa: {e}")
    
    # Capturar screenshot REAL do emulador (AGORA com mapa aberto)
    print("  [4/6] Capturando screenshot do emulador...")
    try:
        screenshot_real = gps.capture_screen()
        
        if screenshot_real is None:
            raise Exception("Screenshot retornou None!")
        
        print(f"  [OK] Screenshot capturado: {screenshot_real.shape[1]}x{screenshot_real.shape[0]}")
        
        # Extrair região do mapa
        print("  [5/6] Extraindo regiao do mapa...")
        map_region_real = gps.extract_map_region(screenshot_real)
        print(f"  [OK] Regiao do mapa extraida: {map_region_real.shape[1]}x{map_region_real.shape[0]}")
        
        # Aplicar levels (mesma transformação do GPS)
        print("  [6/6] Aplicando levels...")
        map_processed_real = gps.apply_levels(map_region_real)
        print(f"  [OK] Levels aplicados - Mapa processado: {map_processed_real.shape[1]}x{map_processed_real.shape[0]}")
        
    except Exception as e:
        raise Exception(f"Erro ao capturar/processar screenshot: {e}")
    
    # Pegar posição atual (já com mapa aberto)
    print("  [INFO] Obtendo posicao atual do player...")
    try:
        pos_atual = gps.get_current_position(keep_map_open=True, verbose=False)
        x_player = pos_atual['x']
        y_player = pos_atual['y']
        print(f"  [OK] Posicao atual: ({x_player}, {y_player}) - {pos_atual['zone']}")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel obter posicao: {e}")
        print(f"  [FALLBACK] Usando valores padrao para posicao...")
        x_player = 253
        y_player = 1207
    
except Exception as e:
    # Restaurar stdout em caso de erro
    if 'old_stdout' in locals():
        sys.stdout = old_stdout
    
    # Remover todos os emojis da mensagem de erro
    error_msg = str(e)
    emojis = ['\U0001f680', '\U0001f4f1', '\U0001f4cb', '\U0001f5fa', '\u2705', '\u26a0', '\u274c', '\U0001f3af', '\U0001f4cd']
    for emoji in emojis:
        error_msg = error_msg.replace(emoji, '')
    
    print(f"  [ERRO] Nao foi possivel inicializar GPS: {error_msg}")
    
    # Verificar se é erro de arquivo faltando
    if 'No such file' in error_msg or 'map_calibration.json' in error_msg:
        print(f"\n  [PROBLEMA DETECTADO] Arquivo map_calibration.json nao encontrado!")
        print(f"  [SOLUCAO] Crie o arquivo map_calibration.json na pasta:")
        print(f"     {os.path.dirname(os.path.abspath(__file__))}")
        print(f"\n  [ESTRUTURA ESPERADA DO JSON]:")
        print(f'     {{')
        print(f'       "map_region": {{')
        print(f'         "x": 0,')
        print(f'         "y": 0,')
        print(f'         "width": 1600,')
        print(f'         "height": 900')
        print(f'       }},')
        print(f'       "buttons": {{')
        print(f'         "open_map": {{"x": 100, "y": 100}},')
        print(f'         "close_map": {{"x": 1500, "y": 100}}')
        print(f'       }},')
        print(f'       "map_scale": 20.0')
        print(f'     }}')
    
    print(f"\n  [FALLBACK] Usando valores padrao...")
    x_player = 253
    y_player = 1207
    gps = None  # GPS não disponível
    screenshot_real = None
    map_region_real = None
    map_processed_real = None

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
    print(f"  [DICA] Para usar outro destino: python debug_clique_coordenadas.py X Y")

print(f"\nPlayer mundo: ({x_player}, {y_player})")
print(f"Destino mundo: ({x_destino}, {y_destino})")
print(f"Margem de seguranca: {WALL_MARGIN}px")

# 1. CARREGAR MAPAS E PATHFINDING
print("\n[1] Carregando mapas e calculando path...")
mapa_pb = cv2.imread('MAPA PRETO E BRANCO.png', 0)
mapa_colorido = cv2.imread('MINIMAPA CERTOPRETO.png')

if mapa_pb is None:
    print("  [ERRO] MAPA PRETO E BRANCO.png nao encontrado!")
    exit(1)
if mapa_colorido is None:
    print("  [ERRO] MINIMAPA CERTOPRETO.png nao encontrado!")
    exit(1)

pathfinder = AStarPathfinder(mapa_pb, wall_margin=WALL_MARGIN)
path_raw = pathfinder.find_path(x_player, y_player, x_destino, y_destino)

if path_raw is None:
    print(f"  [ERRO] Path nao encontrado! Destino muito proximo da parede?")
    print(f"  [SUGESTAO] Reduza WALL_MARGIN ou ajuste destino")
    # Tentar sem margem
    print(f"  [TENTATIVA] Tentando sem margem...")
    pathfinder_sem = AStarPathfinder(mapa_pb, wall_margin=0)
    path_raw = pathfinder_sem.find_path(x_player, y_player, x_destino, y_destino)
    if path_raw:
        pathfinder = pathfinder_sem
        print(f"  [OK] Path encontrado sem margem")
    else:
        print(f"  [ERRO] Path nao encontrado mesmo sem margem!")
        exit(1)

path_simp = pathfinder.simplify_path(path_raw, 150)

print(f"  [OK] Path simplificado: {len(path_raw)} pontos -> {len(path_simp)} waypoints")

# 2. CARREGAR CONFIGURACAO DE TRANSFORMACAO
print("\n[2] Carregando configuracao de transformacao...")

# IMPORTANTE: A conversão precisa usar o TAMANHO ORIGINAL do mapa capturado
# O GPS reduz o mapa para 0.2x para fazer matching, mas os cliques devem ser
# calculados em relação ao tamanho ORIGINAL (antes do resize)

map_width_original = None
map_height_original = None

if map_region_real is not None:
    # Usar tamanho REAL do mapa capturado (antes do resize)
    map_height_original, map_width_original = map_region_real.shape[:2]
    print(f"  [OK] Tamanho original do mapa capturado: {map_width_original}x{map_height_original}")
elif gps is not None and hasattr(gps, 'map_calib'):
    # Fallback: usar do map_calib
    map_region_data = gps.map_calib.get('map_region', {})
    map_width_original = map_region_data.get('width', 1600)
    map_height_original = map_region_data.get('height', 900)
    print(f"  [OK] Tamanho do mapa do GPS: {map_width_original}x{map_height_original}")

# Calcular centro e escala REAL (sempre calcular baseado no tamanho do mapa)
mapa_mundo_width = mapa_pb.shape[1]  # Largura do mapa mundo completo
mapa_mundo_height = mapa_pb.shape[0]  # Altura do mapa mundo completo

if gps is not None and hasattr(gps, 'map_calib'):
    try:
        map_region_data = gps.map_calib.get('map_region', {})
        
        # IMPORTANTE: Centro é o centro da REGIÃO DO MAPA na tela completa
        # Isso é usado para calcular cliques na tela completa
        map_x_offset = map_region_data.get('x', 0)
        map_y_offset = map_region_data.get('y', 0)
        map_w = map_region_data.get('width', 1600)
        map_h = map_region_data.get('height', 900)
        
        centro_x = map_x_offset + map_w // 2  # Centro X na tela completa
        centro_y = map_y_offset + map_h // 2  # Centro Y na tela completa
        
        # SEMPRE calcular escala REAL baseada no tamanho do mapa
        if map_width_original and map_height_original:
            # Escala REAL = tamanho_capturado / tamanho_mundo
            escala_x = map_width_original / mapa_mundo_width
            escala_y = map_height_original / mapa_mundo_height
            print(f"  [INFO] Escala REAL calculada:")
            print(f"     Mapa mundo: {mapa_mundo_width}x{mapa_mundo_height}")
            print(f"     Mapa capturado: {map_width_original}x{map_height_original}")
            print(f"     Escala REAL: X={escala_x:.6f}, Y={escala_y:.6f}")
        else:
            # Usar tamanho do map_region se não tiver capturado
            escala_x = map_w / mapa_mundo_width
            escala_y = map_h / mapa_mundo_height
            print(f"  [INFO] Escala REAL calculada (do map_region):")
            print(f"     Mapa mundo: {mapa_mundo_width}x{mapa_mundo_height}")
            print(f"     Mapa capturado: {map_w}x{map_h}")
            print(f"     Escala REAL: X={escala_x:.6f}, Y={escala_y:.6f}")
        
        map_region = gps.map_calib.get('map_region', {})
        
        print(f"  [OK] Config do GPS:")
        print(f"     Map region na tela: x={map_x_offset}, y={map_y_offset}, w={map_w}, h={map_h}")
        print(f"     Centro tela (tela completa): ({centro_x}, {centro_y})")
        print(f"     Centro mapa (dentro da regiao): ({map_w//2}, {map_h//2})")
        print(f"     Escala FINAL: X={escala_x:.6f}, Y={escala_y:.6f}")
    except Exception as e:
        print(f"  [ERRO] Erro ao calcular do GPS: {e}")
        # Fallback: calcular escala REAL mesmo sem GPS
        map_w = 1600  # Tamanho comum do mapa no emulador
        map_h = 900
        centro_x = 800
        centro_y = 450
        escala_x = map_w / mapa_mundo_width
        escala_y = map_h / mapa_mundo_height
        map_region = {'x': 0, 'y': 0, 'width': map_w, 'height': map_h}
        print(f"     [FALLBACK] Calculando escala REAL:")
        print(f"     Mapa mundo: {mapa_mundo_width}x{mapa_mundo_height}")
        print(f"     Mapa assumido: {map_w}x{map_h}")
        print(f"     Escala REAL: X={escala_x:.6f}, Y={escala_y:.6f}")
else:
    # Fallback: calcular escala REAL mesmo sem GPS
    map_w = 1600  # Tamanho comum do mapa no emulador
    map_h = 900
    centro_x = 800
    centro_y = 450
    escala_x = map_w / mapa_mundo_width  # Escala REAL, não 0.2!
    escala_y = map_h / mapa_mundo_height
    map_region = {'x': 0, 'y': 0, 'width': map_w, 'height': map_h}
    print(f"  [AVISO] GPS nao disponivel, calculando escala REAL:")
    print(f"     Mapa mundo: {mapa_mundo_width}x{mapa_mundo_height}")
    print(f"     Mapa assumido: {map_w}x{map_h}")
    print(f"     Escala REAL: X={escala_x:.6f}, Y={escala_y:.6f}")

# 3. CONVERTER COORDENADAS MUNDO -> TELA
print("\n[3] Convertendo coordenadas mundo -> tela...")

def mundo_to_tela(x_mundo, y_mundo, x_atual, y_atual, centro_x, centro_y, escala_x, escala_y, map_region):
    """Converte coordenadas mundo -> tela (igual no navegador)"""
    # Delta
    delta_x = x_mundo - x_atual
    delta_y = y_mundo - y_atual
    
    # Aplicar escala
    x_tela = int(centro_x + delta_x * escala_x)
    y_tela = int(centro_y + delta_y * escala_y)
    
    # Limitar à região do mapa
    margem = 20
    x_min = map_region.get('x', 0) + margem
    x_max = map_region.get('x', 0) + map_region.get('width', 1600) - margem
    y_min = map_region.get('y', 0) + margem
    y_max = map_region.get('y', 0) + map_region.get('height', 900) - margem
    
    x_tela_limitado = max(x_min, min(x_max, x_tela))
    y_tela_limitado = max(y_min, min(y_max, y_tela))
    
    return (x_tela, y_tela), (x_tela_limitado, y_tela_limitado)

# Converter waypoints
waypoints_tela = []
waypoints_tela_limitados = []

for wp_x, wp_y in path_simp[:10]:  # Primeiros 10 waypoints
    tela, tela_limitado = mundo_to_tela(wp_x, wp_y, x_player, y_player, 
                                         centro_x, centro_y, escala_x, escala_y, map_region)
    waypoints_tela.append(tela)
    waypoints_tela_limitados.append(tela_limitado)
    
    if len(waypoints_tela) <= 5:  # Mostrar primeiros 5
        print(f"  WP[{len(waypoints_tela)-1}] Mundo: ({wp_x}, {wp_y}) -> Tela: {tela} [Limitado: {tela_limitado}]")

# 4. GERAR VISUALIZACOES
print("\n[4] Gerando visualizacoes...")

# Crop area do mapa mundo
margin = 200
x_min = max(0, min(x_player, x_destino) - margin)
x_max = min(mapa_pb.shape[1], max(x_player, x_destino) + margin)
y_min = max(0, min(y_player, y_destino) - margin)
y_max = min(mapa_pb.shape[0], max(y_player, y_destino) + margin)

# --- VIS 1: Mapa mundo com path e waypoints ---
vis_mundo = cv2.cvtColor(mapa_pb, cv2.COLOR_GRAY2BGR)

# Path simplificado (amarelo)
for i in range(len(path_simp) - 1):
    cv2.line(vis_mundo, path_simp[i], path_simp[i+1], (0, 255, 255), 3)

# Waypoints (verde)
for i, (px, py) in enumerate(path_simp[:10]):
    cv2.circle(vis_mundo, (px, py), 8, (0, 255, 0), -1)
    if i < 10:
        cv2.putText(vis_mundo, str(i), (px+12, py), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

# Player e destino
cv2.circle(vis_mundo, (x_player, y_player), 15, (255, 0, 0), -1)
cv2.putText(vis_mundo, "P", (x_player+20, y_player), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
cv2.circle(vis_mundo, (x_destino, y_destino), 15, (0, 0, 255), -1)
cv2.putText(vis_mundo, "D", (x_destino+20, y_destino), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

cv2.putText(vis_mundo, "MAPA MUNDO (Path calculado)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.putText(vis_mundo, "Verde = Waypoints onde deveria clicar", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

crop_mundo = vis_mundo[y_min:y_max, x_min:x_max]

# --- VIS 2: Tela REAL do emulador com cliques sobrepostos ---
if map_processed_real is not None:
    # Usar o mapa processado REAL
    vis_tela = map_processed_real.copy()
    print(f"  [OK] Usando tela real do emulador: {vis_tela.shape[1]}x{vis_tela.shape[0]}")
else:
    # Fallback: tentar carregar do GPS se ainda não tentou
    print(f"  [AVISO] Tela real nao capturada, tentando capturar agora...")
    if gps is not None:
        try:
            # Tentar capturar screenshot agora
            screenshot_temp = gps.capture_screen()
            if screenshot_temp is not None:
                map_region_temp = gps.extract_map_region(screenshot_temp)
                map_processed_temp = gps.apply_levels(map_region_temp)
                vis_tela = map_processed_temp.copy()
                print(f"  [OK] Tela capturada agora: {vis_tela.shape[1]}x{vis_tela.shape[0]}")
            else:
                raise Exception("Nao foi possivel capturar screenshot")
        except Exception as e:
            print(f"  [ERRO] Nao foi possivel capturar: {e}")
            # Fallback: criar imagem simulada com tamanho correto
            if gps is not None and hasattr(gps, 'map_calib'):
                map_region_data = gps.map_calib.get('map_region', {})
                map_w = map_region_data.get('width', 1600)
                map_h = map_region_data.get('height', 900)
            else:
                map_w = 1600
                map_h = 900
            
            vis_tela = np.zeros((map_h, map_w, 3), dtype=np.uint8)
            cv2.rectangle(vis_tela, (0, 0), (map_w, map_h), (50, 50, 50), -1)
            cv2.putText(vis_tela, "MAPa NAO DISPONIVEL", (map_w//2 - 200, map_h//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            print(f"  [AVISO] Usando simulacao: {map_w}x{map_h}")
    else:
        # Sem GPS, criar imagem simulada
        print(f"  [AVISO] GPS nao disponivel, usando simulacao...")
        vis_tela = np.zeros((900, 1600, 3), dtype=np.uint8)
        cv2.rectangle(vis_tela, (0, 0), (1600, 900), (50, 50, 50), -1)
        cv2.putText(vis_tela, "MAPa NAO DISPONIVEL", (600, 450), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

# IMPORTANTE: O player está sempre no CENTRO do mapa visível
# O centro do mapa é onde o player está visualmente
map_x = map_region.get('x', 0)
map_y = map_region.get('y', 0)

# Centro do mapa (onde o player está visualmente) - coordenadas dentro da região do mapa
centro_x_map = vis_tela.shape[1] // 2  # Centro X da região do mapa
centro_y_map = vis_tela.shape[0] // 2  # Centro Y da região do mapa

# Desenhar centro do mapa (ciano) - onde o player está
cv2.circle(vis_tela, (centro_x_map, centro_y_map), 15, (255, 255, 0), -1)
cv2.circle(vis_tela, (centro_x_map, centro_y_map), 20, (255, 255, 0), 2)
cv2.putText(vis_tela, "P", (centro_x_map + 20, centro_y_map), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

# Desenhar waypoints convertidos (onde vai clicar)
# IMPORTANTE: Cada waypoint é calculado em relação ao player (centro)
for i, (wp_mundo_x, wp_mundo_y) in enumerate(path_simp[:10]):
    # Calcular delta do player atual para o waypoint
    delta_x_mundo = wp_mundo_x - x_player
    delta_y_mundo = wp_mundo_y - y_player
    
    # Aplicar escala para converter delta mundo -> delta tela
    delta_x_tela = delta_x_mundo * escala_x
    delta_y_tela = delta_y_mundo * escala_y
    
    # Posição do clique na região do mapa (centro + delta)
    tx_map = int(centro_x_map + delta_x_tela)
    ty_map = int(centro_y_map + delta_y_tela)
    
    # Limitar à região visível
    margem = 20
    tx_map = max(margem, min(vis_tela.shape[1] - margem, tx_map))
    ty_map = max(margem, min(vis_tela.shape[0] - margem, ty_map))
    
    # Verificar se está dentro da região visível
    if 0 <= tx_map < vis_tela.shape[1] and 0 <= ty_map < vis_tela.shape[0]:
        # Ponto onde vai clicar (verde) - MAIOR para ficar visível
        cv2.circle(vis_tela, (tx_map, ty_map), 15, (0, 255, 0), -1)
        cv2.circle(vis_tela, (tx_map, ty_map), 22, (0, 255, 0), 3)
        
        # Linha do centro (player) até o clique
        cv2.line(vis_tela, (centro_x_map, centro_y_map), (tx_map, ty_map), (0, 255, 255), 3)
        
        # Número do waypoint - MAIOR
        cv2.putText(vis_tela, str(i), (tx_map + 25, ty_map), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        
        # Mostrar coordenadas mundo e tela
        coord_text = f"M:({wp_mundo_x},{wp_mundo_y})"
        cv2.putText(vis_tela, coord_text, (tx_map + 50, ty_map - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        
        coord_tela_text = f"T:({tx_map},{ty_map})"
        cv2.putText(vis_tela, coord_tela_text, (tx_map + 50, ty_map + 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 2)

# Desenhar path completo (linha amarela conectando todos os waypoints)
for i in range(len(path_simp[:10]) - 1):
    wp1_mundo = path_simp[i]
    wp2_mundo = path_simp[i + 1]
    
    # Converter ambos para coordenadas da tela
    delta1_x = (wp1_mundo[0] - x_player) * escala_x
    delta1_y = (wp1_mundo[1] - y_player) * escala_y
    delta2_x = (wp2_mundo[0] - x_player) * escala_x
    delta2_y = (wp2_mundo[1] - y_player) * escala_y
    
    pt1 = (int(centro_x_map + delta1_x), int(centro_y_map + delta1_y))
    pt2 = (int(centro_x_map + delta2_x), int(centro_y_map + delta2_y))
    
    # Limitar pontos
    margem = 20
    pt1 = (max(margem, min(vis_tela.shape[1] - margem, pt1[0])), 
           max(margem, min(vis_tela.shape[0] - margem, pt1[1])))
    pt2 = (max(margem, min(vis_tela.shape[1] - margem, pt2[0])), 
           max(margem, min(vis_tela.shape[0] - margem, pt2[1])))
    
    # Desenhar linha do path
    cv2.line(vis_tela, pt1, pt2, (0, 255, 255), 2)

cv2.putText(vis_tela, "TELA REAL DO EMULADOR (Onde vai clicar)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
cv2.putText(vis_tela, "Verde = Cliques | Ciano(P) = Player/Centro | Amarelo = Path", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

# IMPORTANTE: Redimensionar para MUITO MAIOR para visualização
# Aumentar significativamente o tamanho para ficar visível
target_height = 1200  # Altura MUITO maior para melhor visualização
scale_factor = target_height / vis_tela.shape[0]
new_width = int(vis_tela.shape[1] * scale_factor)

# Redimensionar usando INTER_LINEAR para melhor qualidade
vis_tela_resized = cv2.resize(vis_tela, (new_width, target_height), interpolation=cv2.INTER_LINEAR)

# Aumentar tamanho dos círculos e texto na imagem redimensionada (escalar proporcionalmente)
scale_ratio = scale_factor
circle_size = int(12 * scale_ratio)
circle_thickness = int(18 * scale_ratio)
line_thickness = int(2 * scale_ratio)
font_scale = 0.7 * scale_ratio
font_thickness = int(2 * scale_ratio)

# Redesenhar pontos na imagem redimensionada (maiores e mais visíveis)
vis_tela_final = vis_tela_resized.copy()

# Recalcular centro na imagem redimensionada
centro_x_resized = int(centro_x_map * scale_factor)
centro_y_resized = int(centro_y_map * scale_factor)

# Redesenhar centro (player)
cv2.circle(vis_tela_final, (centro_x_resized, centro_y_resized), circle_size, (255, 255, 0), -1)
cv2.circle(vis_tela_final, (centro_x_resized, centro_y_resized), circle_thickness, (255, 255, 0), line_thickness)
cv2.putText(vis_tela_final, "P", (centro_x_resized + int(20 * scale_ratio), centro_y_resized), 
            cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2, (255, 255, 255), font_thickness * 2)

# Redesenhar waypoints na imagem redimensionada
for i, (wp_mundo_x, wp_mundo_y) in enumerate(path_simp[:10]):
    # Calcular delta e posição (mesma lógica de antes)
    delta_x_mundo = wp_mundo_x - x_player
    delta_y_mundo = wp_mundo_y - y_player
    delta_x_tela = delta_x_mundo * escala_x
    delta_y_tela = delta_y_mundo * escala_y
    
    tx_map = int(centro_x_map + delta_x_tela)
    ty_map = int(centro_y_map + delta_y_tela)
    
    margem = 20
    tx_map = max(margem, min(vis_tela.shape[1] - margem, tx_map))
    ty_map = max(margem, min(vis_tela.shape[0] - margem, ty_map))
    
    # Converter para coordenadas redimensionadas
    tx_resized = int(tx_map * scale_factor)
    ty_resized = int(ty_map * scale_factor)
    
    # Verificar se está dentro da região visível
    if 0 <= tx_resized < vis_tela_final.shape[1] and 0 <= ty_resized < vis_tela_final.shape[0]:
        # Ponto onde vai clicar (verde) - MUITO MAIOR
        cv2.circle(vis_tela_final, (tx_resized, ty_resized), circle_size, (0, 255, 0), -1)
        cv2.circle(vis_tela_final, (tx_resized, ty_resized), circle_thickness, (0, 255, 0), line_thickness)
        
        # Linha do centro até o clique - MAIS GROSSA
        cv2.line(vis_tela_final, (centro_x_resized, centro_y_resized), (tx_resized, ty_resized), (0, 255, 255), line_thickness * 2)
        
        # Número do waypoint - MAIOR
        cv2.putText(vis_tela_final, str(i), (tx_resized + int(25 * scale_ratio), ty_resized), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), font_thickness)
        
        # Mostrar coordenadas mundo
        coord_text = f"M:({wp_mundo_x},{wp_mundo_y})"
        cv2.putText(vis_tela_final, coord_text, 
                   (tx_resized + int(50 * scale_ratio), ty_resized - int(20 * scale_ratio)), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.7, (200, 200, 200), font_thickness)
        
        # Mostrar coordenadas tela
        coord_tela_text = f"T:({tx_map},{ty_map})"
        cv2.putText(vis_tela_final, coord_tela_text, 
                   (tx_resized + int(50 * scale_ratio), ty_resized + int(5 * scale_ratio)), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.7, (200, 255, 200), font_thickness)

# Redesenhar path completo na imagem redimensionada
for i in range(len(path_simp[:10]) - 1):
    wp1_mundo = path_simp[i]
    wp2_mundo = path_simp[i + 1]
    
    delta1_x = (wp1_mundo[0] - x_player) * escala_x
    delta1_y = (wp1_mundo[1] - y_player) * escala_y
    delta2_x = (wp2_mundo[0] - x_player) * escala_x
    delta2_y = (wp2_mundo[1] - y_player) * escala_y
    
    pt1_map = (int(centro_x_map + delta1_x), int(centro_y_map + delta1_y))
    pt2_map = (int(centro_x_map + delta2_x), int(centro_y_map + delta2_y))
    
    margem = 20
    pt1_map = (max(margem, min(vis_tela.shape[1] - margem, pt1_map[0])), 
               max(margem, min(vis_tela.shape[0] - margem, pt1_map[1])))
    pt2_map = (max(margem, min(vis_tela.shape[1] - margem, pt2_map[0])), 
               max(margem, min(vis_tela.shape[0] - margem, pt2_map[1])))
    
    pt1_resized = (int(pt1_map[0] * scale_factor), int(pt1_map[1] * scale_factor))
    pt2_resized = (int(pt2_map[0] * scale_factor), int(pt2_map[1] * scale_factor))
    
    cv2.line(vis_tela_final, pt1_resized, pt2_resized, (0, 255, 255), line_thickness * 2)

# Redesenhar textos na imagem redimensionada
cv2.putText(vis_tela_final, "TELA REAL DO EMULADOR (Onde vai clicar)", 
           (int(10 * scale_ratio), int(30 * scale_ratio)), 
           cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2, (255, 255, 255), font_thickness * 2)
cv2.putText(vis_tela_final, "Verde = Cliques | Ciano = Centro | Amarelo = Ajustado", 
           (int(10 * scale_ratio), int(55 * scale_ratio)), 
           cv2.FONT_HERSHEY_SIMPLEX, font_scale, (200, 200, 200), font_thickness)

vis_tela_resized = vis_tela_final

# Redimensionar mapa mundo para mesma altura (usar INTER_LINEAR para melhor qualidade)
mundo_scale = target_height / crop_mundo.shape[0]
mundo_new_width = int(crop_mundo.shape[1] * mundo_scale)
crop_mundo_resized = cv2.resize(crop_mundo, (mundo_new_width, target_height), interpolation=cv2.INTER_LINEAR)

# --- VIS 3: Informações ---
info_img = np.zeros((target_height, 700, 3), dtype=np.uint8)  # Mais largura para texto maior
y_text = 40
font_scale_info = 1.0  # Fonte maior
font_thickness_info = 2

cv2.putText(info_img, "INFORMACOES", (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info * 1.2, (255, 255, 255), font_thickness_info * 2)
y_text += 60

cv2.putText(info_img, f"Centro tela: ({centro_x}, {centro_y})", (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info, (255, 255, 255), font_thickness_info)
y_text += 45

cv2.putText(info_img, f"Escala X: {escala_x:.6f}", (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info, (255, 255, 255), font_thickness_info)
y_text += 45

cv2.putText(info_img, f"Escala Y: {escala_y:.6f}", (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info, (255, 255, 255), font_thickness_info)
y_text += 60

cv2.putText(info_img, "Waypoints:", (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info * 1.1, (255, 255, 0), font_thickness_info * 2)
y_text += 50

for i, (wp_mundo, (tx_orig, ty_orig), (tx_lim, ty_lim)) in enumerate(zip(path_simp[:8], waypoints_tela, waypoints_tela_limitados)):
    texto = f"WP[{i}] Mundo: {wp_mundo}"
    cv2.putText(info_img, texto, (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info * 0.9, (255, 255, 255), font_thickness_info)
    y_text += 35
    
    texto = f"  Tela: ({tx_orig}, {ty_orig})"
    cv2.putText(info_img, texto, (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info * 0.9, (0, 255, 255), font_thickness_info)
    y_text += 35
    
    if tx_orig != tx_lim or ty_orig != ty_lim:
        texto = f"  LIMITADO: ({tx_lim}, {ty_lim})"
        cv2.putText(info_img, texto, (10, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale_info * 0.9, (0, 165, 255), font_thickness_info)
        y_text += 35
    y_text += 15

# 5. MONTAR IMAGEM FINAL
print("\n[5] Montando imagem final...")

# Linha 1: Mapa mundo + Tela REAL (redimensionada)
row1 = np.hstack([crop_mundo_resized, vis_tela_resized, info_img])

# Se ainda houver espaço, pode adicionar mais info
final = row1

cv2.imwrite('debug_clique_coordenadas.png', final)

print(f"  [OK] debug_clique_coordenadas.png salvo")
print(f"  Dimensoes: {final.shape[1]}x{final.shape[0]}")

print("\n" + "="*70)
print("ANALISE DE COORDENADAS COMPLETA!")
print("="*70)
print("\nVeja a imagem: debug_clique_coordenadas.png")
print("\nLayout:")
print("  LEFT: Mapa mundo com path (onde deveria clicar)")
print("  CENTER: Tela REAL do emulador (onde realmente vai clicar)")
print("  RIGHT: Informacoes de conversao")
print("\nCores:")
print("  Verde (Mundo) = Waypoints calculados pelo A*")
print("  Verde (Tela) = Onde vai clicar no emulador")
print("  Amarelo (Tela) = Clique original (antes de limitar)")
print("  Ciano = Centro do mapa na tela")
print("\nSe os pontos verdes na TELA nao correspondem aos pontos")
print("verdes no MUNDO, ha um problema na conversao de coordenadas!")
