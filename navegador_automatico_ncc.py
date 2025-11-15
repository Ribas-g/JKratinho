"""
NAVEGADOR AUTOMÁTICO COM NCC

Sistema completo de navegação automática:
1. Obtém posição atual (GPS com NCC)
2. Escolhe destino (por zona/coordenadas)
3. Navega clicando no mapa
4. Detecta linha verde (player em movimento)
5. Aguarda chegada
6. Repete até chegar no destino final

USO:
    nav = NavegadorAutomaticoNCC()
    nav.navegar_para_zona('Deserto')
    # ou
    nav.navegar_para_coordenadas(500, 300)
"""

import cv2
import numpy as np
import time
import json
import os
import threading
from gps_ncc_realtime import GPSRealtimeNCC
from pathfinding_astar import AStarPathfinder


# Zonas disponíveis (coordenadas corrigidas baseadas nas cores)
ZONAS_DISPONIVEIS = {
    'Praia': {'spawn': (34, 1058), 'color': (0xf4, 0xe1, 0xae)},
    'Pré-Praia': {'spawn': (177, 1139), 'color': (0x48, 0x98, 0x48)},
    'Vila Inicial': {'spawn': (379, 1147), 'color': (0x12, 0x2b, 0x12)},
    'Floresta dos Corvos': {'spawn': (548, 1135), 'color': (0x8f, 0xcc, 0x8f)},
    'Deserto': {'spawn': (374, 1342), 'color': (0xe9, 0xbf, 0x99)},
    'Labirinto dos Assassinos': {'spawn': (377, 931), 'color': (0x34, 0x5e, 0x35)},
    'Área dos Zumbis': {'spawn': (369, 727), 'color': (0x64, 0x62, 0x2b)},
    'Covil dos Esqueletos': {'spawn': (564, 727), 'color': (0x93, 0x8f, 0x5c)},
    'Território dos Elfos': {'spawn': (690, 933), 'color': (0x43, 0x3d, 0x29)},
    'Zona dos Lagartos': {'spawn': (886, 632), 'color': (0x36, 0x75, 0x35)},
    'Área Indefinida': {'spawn': (476, 430), 'color': (0xb8, 0x6f, 0x27)},
    'Área dos Goblins': {'spawn': (787, 1228), 'color': (0x30, 0xd8, 0x30)},
}


class NavegadorAutomaticoNCC:
    """Navegador automático usando NCC para GPS"""

    def __init__(self):
        """Inicializa navegador"""
        print("🚀 Inicializando Navegador Automático com NCC...")

        # GPS com NCC
        self.gps = GPSRealtimeNCC()

        # Usar mapa colorido do GPS (MINIMAPA CERTOPRETO.png) para referência
        self.mapa_colorido = self.gps.mapa_colorido
        if self.mapa_colorido is None:
            raise FileNotFoundError("❌ Mapa colorido não encontrado! Verifique MINIMAPA CERTOPRETO.png")
        print(f"   ✅ Mapa colorido carregado: {self.mapa_colorido.shape[1]}x{self.mapa_colorido.shape[0]}")

        # IMPORTANTE: Usar mapa COLORIDO para pathfinding
        # No mapa colorido (MINIMAPA CERTOPRETO.png):
        # - COLORIDO = walkable (chão do jogo, biomas)
        # - PRETO = não walkable (paredes, fora do mapa)
        # O pathfinder verifica se o pixel é colorido (não preto) para determinar se é walkable
        wall_margin = 5
        print(f"   🗺️ Inicializando pathfinder A* com mapa COLORIDO...")
        print(f"   🛡️ Margem de seguranca das paredes: {wall_margin}px")
        print(f"   📝 Regra: COLORIDO = walkable, PRETO = parede")
        self.pathfinder = AStarPathfinder(self.mapa_colorido, wall_margin=wall_margin)

        # Carregar calibração
        self.load_calibration()

        # Configurações de navegação
        # O mapa visível tem ~1600x900 pixels na tela
        # Mas isso representa uma área menor no mapa mundo (devido à escala)
        # Raio clicável = metade da largura visível no mapa mundo
        map_region = self.gps.map_calib['map_region']
        self.click_distance = int((map_region['width'] / self.escala_x) * 0.35)  # 35% do raio visível

        print(f"   📏 Distância de clique: {self.click_distance} pixels (no mapa mundo)")

        self.wait_after_click = 0.3  # Tempo de espera após clique para garantir que comando foi processado
        self.max_steps = 100  # Máximo de passos para evitar loop infinito
        self.tolerance_pixels = 30  # Tolerância para considerar "chegou" (em pixels)
        
        # Visualização em tempo real
        self.show_visualization = True
        self.visualization_window = "Navegação ao Vivo"
        if self.show_visualization:
            cv2.namedWindow(self.visualization_window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.visualization_window, 1200, 800)

        print("✅ Navegador inicializado!\n")

    def load_calibration(self):
        """Carrega configuração de transformação"""
        config_file = 'map_transform_config.json'

        if not os.path.exists(config_file):
            print("   ⚠️ Configuração não encontrada!")
            print("   💡 Execute: python calcular_escala_mapa.py")

            # Calcular automaticamente
            print("   🔧 Calculando escala automaticamente...")
            map_region = self.gps.map_calib['map_region']

            self.centro_x = map_region['x'] + map_region['width'] // 2
            self.centro_y = map_region['y'] + map_region['height'] // 2

            # CORREÇÃO CRÍTICA: Entender o processo completo do GPS!
            # 
            # PROCESSO DO GPS (MATCHING):
            # 1. GPS captura 1600x899 pixels da TELA ORIGINAL (mapa visível no jogo)
            # 2. GPS detecta player na TELA ORIGINAL (ex: player_x_local = 800, player_y_local = 450)
            # 3. GPS reduz captura para 320x180 pixels (0.2x) apenas para MATCHING RÁPIDO
            # 4. GPS faz matching: encontra onde a área de 320x180 (reduzida) está no mapa mundo completo
            # 5. GPS calcula: player_x_global = x_match_adjusted + (player_x_local * 0.2)
            #    - player_x_local * 0.2 = posição do player na captura REDUZIDA (ex: 800 * 0.2 = 160)
            #    - x_match_adjusted = posição do CANTO SUPERIOR ESQUERDO da área reduzida no mapa mundo
            #    - player_x_global = posição do player no mapa mundo completo
            #
            # IMPORTANTE: O GPS calcula a posição do player no mapa mundo usando a ESCALA REDUZIDA (0.2x)
            # Isso significa que a relação entre a TELA ORIGINAL e o MAPA MUNDO é:
            # - 1 pixel da TELA ORIGINAL = 1 pixel do MAPA MUNDO (aproximadamente)
            # - Porque: player_x_local (800) → player_x_local * 0.2 (160) → player_x_global (x_match_adjusted + 160)
            # - E x_match_adjusted é calculado baseado na área REDUZIDA, então a conversão final é 1:1
            #
            # PROCESSO PARA CLICAR (OPOSTO DO MATCHING):
            # 1. Temos coordenadas do mapa mundo (ex: player em 220, 1153; destino em 378, 1343)
            # 2. Precisamos converter para coordenadas da TELA ORIGINAL (1600x899)
            # 3. A conversão é DIRETA: delta_mundo = delta_tela (escala 1:1)
            #    - Player está no CENTRO da tela original (800, 450)
            #    - Delta do destino: delta_x = destino_x - player_x_global
            #    - Clique na tela: x_clique = 800 + delta_x (sem escala adicional)
            #
            # SOLUÇÃO FINAL: Usar escala 1.0 (1:1) porque:
            # - O GPS já faz a conversão correta usando a escala reduzida internamente
            # - A relação final entre TELA ORIGINAL e MAPA MUNDO é 1:1
            # - O player está sempre no centro, então delta_mundo = delta_tela
            
            # Tamanho do mapa capturado (TELA ORIGINAL - não reduzida)
            # Esta é a tela onde vamos CLICAR!
            map_capturado_width = map_region['width']   # 1600 pixels (TELA ORIGINAL)
            map_capturado_height = map_region['height'] # 899 pixels (TELA ORIGINAL)
            
            # ESCALA PARA CLICAR: 5.0 (1 pixel mundo = 5 pixels tela)
            # CORREÇÃO: O GPS reduz captura para 0.2x (1600px → 320px)
            # As coordenadas retornadas pelo GPS estão na escala do matching (320px)
            # Para converter de volta para a TELA ORIGINAL (1600px), precisamos:
            # escala = tamanho_tela / tamanho_reduzido = 1600 / 320 = 5.0
            # Ou: escala = 1 / escala_GPS = 1 / 0.2 = 5.0
            self.escala_x = 5.0
            self.escala_y = 5.0

            print(f"   ✅ Escala REAL calculada (para cliques na TELA ORIGINAL):")
            print(f"      Tela original (captura): {map_capturado_width}x{map_capturado_height} pixels")
            print(f"      Captura reduzida (GPS): {int(map_capturado_width * 0.2)}x{int(map_capturado_height * 0.2)} pixels (0.2x)")
            print(f"      Escala cliques: X={self.escala_x:.4f}, Y={self.escala_y:.4f} (5:1)")
            print(f"      💡 1 pixel do mapa mundo = 5 pixels na TELA ORIGINAL")
            print(f"      ⚠️ Fórmula: escala = 1 / escala_GPS = 1 / 0.2 = 5.0")
            return

        # Carregar do arquivo
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self.centro_x = config['centro_mapa_tela']['x']
        self.centro_y = config['centro_mapa_tela']['y']
        self.escala_x = config['escala']['x']
        self.escala_y = config['escala']['y']

        print(f"   ✅ Configuração carregada")
        print(f"   📍 Centro: ({self.centro_x}, {self.centro_y})")
        print(f"   📏 Escala: X={self.escala_x:.4f}, Y={self.escala_y:.4f}")

    def mundo_to_tela(self, x_mundo, y_mundo, x_atual, y_atual):
        """
        Converte coordenadas do mundo para coordenadas de clique na tela

        O player SEMPRE fica no centro do mapa visível.
        Para clicar em um destino, calculamos o delta e aplicamos a escala.

        IMPORTANTE: Limita cliques para dentro da região do mapa visível!

        Args:
            x_mundo, y_mundo: Coordenadas destino no mapa mundo
            x_atual, y_atual: Coordenadas atuais do player no mapa mundo

        Returns:
            (x, y): Coordenadas para clicar na tela (limitadas à região do mapa)
        """
        # Delta (quanto precisa andar)
        delta_x = x_mundo - x_atual
        delta_y = y_mundo - y_atual

        # Aplicar escala e somar ao centro
        x_tela = int(self.centro_x + delta_x * self.escala_x)
        y_tela = int(self.centro_y + delta_y * self.escala_y)

        # LIMITAR cliques à região clicável do mapa (evitar clicar em UI/paredes)
        # IMPORTANTE: Usar margens maiores para garantir que o clique seja válido e não clique em UI
        map_region = self.gps.map_calib['map_region']
        margem_x = 120  # Margem para UI/bordas na largura (aumentada)
        margem_y = 100  # Margem para UI/bordas na altura (aumentada)

        # Limites da região clicável do mapa (considerando UI e bordas)
        x_min = map_region['x'] + margem_x
        x_max = map_region['x'] + map_region['width'] - margem_x
        y_min = map_region['y'] + margem_y
        y_max = map_region['y'] + map_region['height'] - margem_y

        # Clampar coordenadas
        x_tela_limitado = max(x_min, min(x_max, x_tela))
        y_tela_limitado = max(y_min, min(y_max, y_tela))

        # Avisar se houve limitação
        if x_tela != x_tela_limitado or y_tela != y_tela_limitado:
            print(f"         ⚠️ Clique ajustado: ({x_tela}, {y_tela}) → ({x_tela_limitado}, {y_tela_limitado})")
            print(f"         Motivo: Clique original estava fora da região do mapa")
        else:
            # Debug: mostrar coordenadas calculadas
            print(f"         📍 Clique calculado: mundo=({x_mundo:.0f},{y_mundo:.0f}), delta=({delta_x:+.0f},{delta_y:+.0f}), tela=({x_tela},{y_tela})")

        return (x_tela_limitado, y_tela_limitado)

    def is_walkable(self, x_mundo, y_mundo):
        """
        Verifica se uma coordenada é walkável usando o pathfinder (que tem a lógica correta)

        Args:
            x_mundo, y_mundo: Coordenadas no mapa mundo

        Returns:
            True se é área walkável, False caso contrário
        """
        # Verificar bounds primeiro
        if not (0 <= int(x_mundo) < self.mapa_colorido.shape[1] and
                0 <= int(y_mundo) < self.mapa_colorido.shape[0]):
            return False

        # Pegar cor do pixel no mapa colorido (para debug)
        pixel = self.mapa_colorido[int(y_mundo), int(x_mundo)]

        # Usar a lógica do pathfinder que já está validada
        result = self.pathfinder.is_walkable(int(x_mundo), int(y_mundo))

        # Debug: mostrar cor do pixel quando NÃO é walkável
        if not result:
            print(f"      ⚠️ Pixel ({int(x_mundo)}, {int(y_mundo)}) NÃO walkável! Cor BGR: {pixel}")

        return result

    def clicar_no_mapa(self, destino_x_mundo, destino_y_mundo, x_atual, y_atual):
        """
        Clica no mapa na direção do destino

        Args:
            destino_x_mundo: Coordenada X do destino no mapa mundo
            destino_y_mundo: Coordenada Y do destino no mapa mundo
            x_atual, y_atual: Posição atual do player
        """
        # Converter para coordenadas de clique
        x_clique, y_clique = self.mundo_to_tela(destino_x_mundo, destino_y_mundo, x_atual, y_atual)

        # Debug: mostrar cálculo detalhado
        delta_x_mundo = destino_x_mundo - x_atual
        delta_y_mundo = destino_y_mundo - y_atual
        dist_mundo = self.calcular_distancia(x_atual, y_atual, destino_x_mundo, destino_y_mundo)
        
        # Clicar
        print(f"      🖱️ Clicando em ({x_clique}, {y_clique})")
        print(f"         Mundo: ({destino_x_mundo:.0f}, {destino_y_mundo:.0f})")
        print(f"         Delta: ({delta_x_mundo:+.0f}, {delta_y_mundo:+.0f}) = {dist_mundo:.1f}px")
        print(f"         Escala: X={self.escala_x:.4f}, Y={self.escala_y:.4f}")
        
        # Enviar clique via ADB
        self.gps.device.shell(f"input tap {x_clique} {y_clique}")
        
        # Pequeno delay para garantir que o clique foi processado
        time.sleep(0.1)

    def detectar_linha_verde(self, return_ratio=False):
        """
        Detecta linha verde no mapa (indica que player está em movimento)

        Player é CIANO (#00ffff) após levels → HSV: H=90, S=255, V=255
        Linha verde é VERDE PURO (#00ff00) → HSV: H=60, S=255, V=255

        Args:
            return_ratio: Se True, retorna (bool, ratio) ao invés de apenas bool

        Returns:
            Se return_ratio=False: True se detectou linha verde
            Se return_ratio=True: (True/False, green_ratio_percentage)
        """
        # Capturar screenshot
        screenshot = self.gps.capture_screen()

        # Extrair região do mapa
        map_region = self.gps.extract_map_region(screenshot)

        # Aplicar levels (mesma transformação do GPS)
        map_processed = self.gps.apply_levels(map_region)

        # Converter para HSV
        hsv = cv2.cvtColor(map_processed, cv2.COLOR_BGR2HSV)

        # Range de verde PURO (#00ff00)
        # Verde puro em HSV: H=60 (±10 para tolerância)
        # CIANO é H=90, então range 50-70 evita pegar ciano
        lower_green = np.array([50, 180, 180])  # Verde puro, saturação e valor altos
        upper_green = np.array([70, 255, 255])  # Não pega ciano (H=90)

        # Máscara de verde
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        # IMPORTANTE: Remover região central (onde fica o player ciano)
        # Player está sempre no centro do mapa
        height, width = green_mask.shape
        centro_x = width // 2
        centro_y = height // 2
        raio_exclusao = 40  # Pixels ao redor do centro (aumentado)

        # Criar máscara para excluir centro
        y_indices, x_indices = np.ogrid[:height, :width]
        distancia_centro = np.sqrt((x_indices - centro_x)**2 + (y_indices - centro_y)**2)
        mascara_centro = distancia_centro > raio_exclusao

        # Aplicar exclusão do centro
        green_mask = green_mask & mascara_centro.astype(np.uint8) * 255

        # Contar pixels verdes (excluindo centro)
        green_pixels = np.sum(green_mask > 0)
        total_pixels = green_mask.shape[0] * green_mask.shape[1]

        if total_pixels == 0:
            return (False, 0.0) if return_ratio else False

        green_ratio = green_pixels / total_pixels
        green_percentage = green_ratio * 100  # Converter para porcentagem

        # SISTEMA DE THRESHOLD ESCALONADO (ideia do usuário):
        # 0-0.5% = Parado/ruído (falso positivo)
        # 0.5-2% = Começando a andar (transição)
        # 2%+ = Realmente andando (confirmado)

        # Threshold ajustado: 0.5% (5x mais alto que antes)
        # Reduz drasticamente falsos positivos
        is_moving = green_ratio > 0.005  # 0.5% ao invés de 0.02%

        if return_ratio:
            return (is_moving, green_percentage)
        return is_moving

    def aguardar_chegada(self, destino_x, destino_y, x_antes, y_antes, max_wait=10.0, use_gps_confirm=True):
        """
        Aguarda player chegar no destino clicado

        Fluxo:
        1. Aguarda linha verde APARECER (começou a andar)
        2. Aguarda linha verde SUMIR (parou de andar)
        3. Confirma com GPS (realmente chegou)

        Args:
            destino_x, destino_y: Coordenadas do destino
            x_antes, y_antes: Posição ANTES do clique (para comparar)
            max_wait: Tempo máximo de espera (segundos)
            use_gps_confirm: Se True, usa GPS para confirmar chegada

        Returns:
            True se player chegou, False se timeout
        """
        start_time = time.time()
        check_interval = 0.15  # Reduzido para checks mais rápidos
        last_print_time = 0

        print(f"      ⏳ Aguardando movimento (de {x_antes},{y_antes} para {destino_x},{destino_y})...")

        # FASE 1: Aguardar linha verde APARECER (player começou a andar)
        # MELHORIA: Verificar 2 frames consecutivos para evitar falsos positivos
        movimento_detectado = False
        fase1_timeout = 0.8  # Timeout reduzido (mais rápido)
        frames_consecutivos_movimento = 0  # Contador de frames com movimento
        frames_necessarios = 2  # Precisa de 2 frames consecutivos

        while (time.time() - start_time) < fase1_timeout:
            has_green, green_pct = self.detectar_linha_verde(return_ratio=True)

            if has_green:
                frames_consecutivos_movimento += 1

                # Mostrar porcentagem (barra de loading)
                if green_pct >= 2.0:
                    status = "andando forte"
                elif green_pct >= 0.5:
                    status = "começando"
                else:
                    status = "detectado"

                print(f"         Verde: {green_pct:.2f}% ({status})")

                # Confirmar movimento após frames consecutivos
                if frames_consecutivos_movimento >= frames_necessarios:
                    print(f"      ✅ Movimento confirmado ({frames_consecutivos_movimento} frames, {green_pct:.2f}%)!")
                    movimento_detectado = True
                    break
            else:
                # Resetar contador se perdeu movimento
                frames_consecutivos_movimento = 0

            time.sleep(check_interval)

        if not movimento_detectado:
            print(f"      ⚠️ Linha verde não detectada (movimento curto?)")

            # Esperar um pouco mais e verificar se posição mudou
            time.sleep(0.5)

            # Verificar com GPS se player andou
            if use_gps_confirm:
                print(f"      🔍 Verificando se player andou (GPS)...")
                pos_depois = self.gps.get_current_position(keep_map_open=True, verbose=False, map_already_open=True)
                x_depois, y_depois = pos_depois['x'], pos_depois['y']

                # Calcular movimento (delta X e Y)
                delta_x = x_depois - x_antes
                delta_y = y_depois - y_antes
                distancia_andada = self.calcular_distancia(x_antes, y_antes, x_depois, y_depois)

                # Calcular direção esperada (em relação ao destino)
                direcao_esperada_x = destino_x - x_antes  # Positivo = ir pra direita
                direcao_esperada_y = destino_y - y_antes  # Positivo = ir pra baixo

                print(f"         Antes: ({x_antes}, {y_antes})")
                print(f"         Depois: ({x_depois}, {y_depois})")
                print(f"         Movimento: Δx={delta_x:+.0f}, Δy={delta_y:+.0f} ({distancia_andada:.1f}px)")
                print(f"         Direção esperada: Δx={direcao_esperada_x:+.0f}, Δy={direcao_esperada_y:+.0f}")

                # Verificar se andou na direção certa
                # Considera correto se pelo menos um dos eixos está indo na direção certa
                andou_x_correto = (delta_x * direcao_esperada_x) > 0 if direcao_esperada_x != 0 else True
                andou_y_correto = (delta_y * direcao_esperada_y) > 0 if direcao_esperada_y != 0 else True

                # Se andou pelo menos 3 pixels E na direção certa
                if distancia_andada >= 3 and (andou_x_correto or andou_y_correto):
                    direcao_str = []
                    if delta_x > 0:
                        direcao_str.append("Leste")
                    elif delta_x < 0:
                        direcao_str.append("Oeste")
                    if delta_y > 0:
                        direcao_str.append("Sul")
                    elif delta_y < 0:
                        direcao_str.append("Norte")

                    print(f"      ✅ Player andou! ({' + '.join(direcao_str) if direcao_str else 'Parado'})")

                    # Verificar se chegou no destino
                    dist_destino = self.calcular_distancia(x_depois, y_depois, destino_x, destino_y)
                    print(f"         Distância ao destino: {dist_destino:.1f} pixels")

                    if dist_destino <= self.tolerance_pixels:  # 30px
                        print(f"      ✅ GPS confirma - Chegou no destino!")
                        return True
                    else:
                        # Andou mas não chegou, CONTINUAR TENTANDO
                        print(f"      ↻ Ainda não chegou (precisa clicar de novo)")
                        return False
                elif distancia_andada >= 3:
                    print(f"      ⚠️ Player andou mas na DIREÇÃO ERRADA!")
                    print(f"         (isso pode indicar obstáculo)")
                    return False
                else:
                    print(f"      ⚠️ Player não andou (parado)")
                    dist_destino = self.calcular_distancia(x_depois, y_depois, destino_x, destino_y)

                    if dist_destino <= self.tolerance_pixels:
                        print(f"      ✅ Já está no destino!")
                        return True
                    else:
                        print(f"      ❌ Não chegou (dist={dist_destino:.1f})")
                        return False
            else:
                return False

        # FASE 2: Aguardar linha verde SUMIR (player parou)
        print(f"      ⏳ Aguardando parar...")
        consecutive_no_green = 0
        required_no_green = 2  # Reduzido para ser mais rápido (2 frames)
        last_green_pct = 0

        while (time.time() - start_time) < max_wait:
            has_green, green_pct = self.detectar_linha_verde(return_ratio=True)

            if has_green:
                consecutive_no_green = 0
                last_green_pct = green_pct

                # Print periódico com porcentagem
                current_time = time.time()
                if current_time - last_print_time >= 2.0:
                    print(f"         Ainda em movimento... ({int(current_time - start_time)}s, verde: {green_pct:.2f}%)")
                    last_print_time = current_time
            else:
                consecutive_no_green += 1

                # Linha verde sumiu consistentemente
                if consecutive_no_green >= required_no_green:
                    print(f"      ✅ Player parou (verde: {last_green_pct:.2f}% → 0%)")

                    # FASE 3: CONFIRMAÇÃO POR GPS
                    if use_gps_confirm:
                        print(f"      🔍 Confirmando com GPS...")
                        pos_atual = self.gps.get_current_position(keep_map_open=True, verbose=False, map_already_open=True)
                        x_atual, y_atual = pos_atual['x'], pos_atual['y']
                        dist = self.calcular_distancia(x_atual, y_atual, destino_x, destino_y)

                        print(f"         Posição GPS: ({x_atual}, {y_atual})")
                        print(f"         Distância ao destino: {dist:.1f} pixels")

                        if dist <= self.tolerance_pixels:  # 30px
                            print(f"      ✅ GPS confirma - Chegou!")
                            return True
                        else:
                            print(f"      ↻ Ainda longe (dist={dist:.1f}px) - clicar de novo")
                            return False
                    else:
                        return True

            time.sleep(check_interval)

        # Timeout
        print(f"      ⏱️ Timeout após {max_wait}s")

        # Verificação final por GPS
        if use_gps_confirm:
            print(f"      🔍 Verificação final com GPS...")
            pos_atual = self.gps.get_current_position(keep_map_open=True, verbose=False, map_already_open=True)
            x_atual, y_atual = pos_atual['x'], pos_atual['y']
            dist = self.calcular_distancia(x_atual, y_atual, destino_x, destino_y)

            print(f"         Posição: ({x_atual}, {y_atual})")
            print(f"         Distância: {dist:.1f} pixels")

            if dist <= self.tolerance_pixels:
                print(f"      ✅ GPS confirma chegada!")
                return True

        return False

    def calcular_distancia(self, x1, y1, x2, y2):
        """Calcula distância euclidiana entre dois pontos"""
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def _atualizar_visualizacao(self, vis_state):
        """
        Atualiza janela de visualização em tempo real
        
        Mostra:
        - Screenshot atual do mapa
        - Posição do player (azul)
        - Path completo (linha amarela)
        - Waypoint atual (verde)
        - Onde está clicando (vermelho)
        - Área visível (retângulo)
        - Informações de debug
        """
        try:
            # Capturar screenshot atual
            screenshot = self.gps.capture_screen()
            if screenshot is None:
                return
            
            # Extrair região do mapa
            map_region = self.gps.map_calib['map_region']
            map_img = self.gps.extract_map_region(screenshot)
            
            if map_img is None:
                return
            
            # Criar cópia para desenhar
            vis_img = map_img.copy()
            
            # Converter coordenadas mundo para coordenadas na imagem do mapa
            def mundo_to_img(x_mundo, y_mundo):
                """Converte coordenadas mundo para coordenadas na imagem capturada"""
                # Player está no centro da imagem
                img_center_x = map_img.shape[1] // 2
                img_center_y = map_img.shape[0] // 2
                
                # Delta do player atual
                if vis_state['x_atual'] is not None:
                    delta_x = x_mundo - vis_state['x_atual']
                    delta_y = y_mundo - vis_state['y_atual']
                    
                    # Aplicar escala
                    x_img = int(img_center_x + delta_x * self.escala_x)
                    y_img = int(img_center_y + delta_y * self.escala_y)
                    
                    return (x_img, y_img)
                return None
            
            # 1. Desenhar path RESTANTE VISÍVEL (do player até o destino) - linha amarela
            # IMPORTANTE: Mostrar apenas a parte do path que está VISÍVEL na tela atual
            # Isso evita confusão visual e mostra claramente o caminho futuro visível
            if vis_state['path_completo'] and vis_state['x_atual'] is not None:
                # Encontrar qual ponto do path está mais próximo da posição atual
                indice_atual = 0
                dist_minima = float('inf')
                for i, (px, py) in enumerate(vis_state['path_completo']):
                    dist = self.calcular_distancia(vis_state['x_atual'], vis_state['y_atual'], px, py)
                    if dist < dist_minima:
                        dist_minima = dist
                        indice_atual = i
                
                # Desenhar apenas a parte do path que ainda falta percorrer E está VISÍVEL
                # Calcular área visível para filtrar pontos
                map_region = self.gps.map_calib['map_region']
                raio_visivel_x = int((map_region['width'] / 2) / self.escala_x)
                raio_visivel_y = int((map_region['height'] / 2) / self.escala_y)
                
                x_min_visivel = vis_state['x_atual'] - raio_visivel_x
                x_max_visivel = vis_state['x_atual'] + raio_visivel_x
                y_min_visivel = vis_state['y_atual'] - raio_visivel_y
                y_max_visivel = vis_state['y_atual'] + raio_visivel_y
                
                # Filtrar pontos do path que estão VISÍVEIS na tela
                path_restante = vis_state['path_completo'][indice_atual:]
                path_points_visiveis = []
                
                for px, py in path_restante:
                    # Verificar se está visível na tela
                    if (x_min_visivel <= px <= x_max_visivel and
                        y_min_visivel <= py <= y_max_visivel):
                        pt = mundo_to_img(px, py)
                        if pt and 0 <= pt[0] < vis_img.shape[1] and 0 <= pt[1] < vis_img.shape[0]:
                            path_points_visiveis.append(pt)
                    # Se saiu da área visível, parar de desenhar
                    elif len(path_points_visiveis) > 0:
                        break
                
                # Desenhar apenas path VISÍVEL restante (linha amarela)
                if len(path_points_visiveis) > 1:
                    pts = np.array(path_points_visiveis, np.int32)
                    cv2.polylines(vis_img, [pts], False, (0, 255, 255), 2)  # Amarelo - path restante visível
            
            # 2. Desenhar destino final (círculo rosa)
            if vis_state['destino_x'] is not None:
                dest_pt = mundo_to_img(vis_state['destino_x'], vis_state['destino_y'])
                if dest_pt:
                    cv2.circle(vis_img, dest_pt, 15, (255, 0, 255), 3)  # Rosa
                    cv2.putText(vis_img, "DESTINO", (dest_pt[0] + 20, dest_pt[1]), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
            
            # 3. Desenhar player (círculo azul)
            if vis_state['x_atual'] is not None:
                player_pt = (map_img.shape[1] // 2, map_img.shape[0] // 2)
                cv2.circle(vis_img, player_pt, 10, (255, 0, 0), -1)  # Azul sólido
                cv2.putText(vis_img, "P", (player_pt[0] - 5, player_pt[1] + 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # 4. Desenhar waypoint atual (círculo verde)
            if vis_state['wp_x'] is not None:
                wp_pt = mundo_to_img(vis_state['wp_x'], vis_state['wp_y'])
                if wp_pt:
                    cv2.circle(vis_img, wp_pt, 8, (0, 255, 0), 2)  # Verde
                    cv2.putText(vis_img, "WP", (wp_pt[0] + 15, wp_pt[1]), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            # 5. Desenhar onde está clicando (DESTACADO - próximo clique)
            if vis_state['x_clique'] is not None and vis_state['y_clique'] is not None:
                # Converter coordenadas de tela para coordenadas na imagem do mapa
                map_region = self.gps.map_calib['map_region']
                clique_rel_x = vis_state['x_clique'] - map_region['x']
                clique_rel_y = vis_state['y_clique'] - map_region['y']
                
                # Escalar para tamanho da imagem
                scale_x = map_img.shape[1] / map_region['width']
                scale_y = map_img.shape[0] / map_region['height']
                
                clique_img_x = int(clique_rel_x * scale_x)
                clique_img_y = int(clique_rel_y * scale_y)
                
                if 0 <= clique_img_x < vis_img.shape[1] and 0 <= clique_img_y < vis_img.shape[0]:
                    # Desenhar círculo grande pulsante (vermelho brilhante)
                    cv2.circle(vis_img, (clique_img_x, clique_img_y), 25, (0, 0, 255), 4)  # Círculo externo
                    cv2.circle(vis_img, (clique_img_x, clique_img_y), 15, (0, 100, 255), 3)  # Círculo médio
                    cv2.circle(vis_img, (clique_img_x, clique_img_y), 8, (0, 0, 255), -1)  # Círculo interno sólido
                    
                    # Desenhar cruz vermelha grande
                    cv2.line(vis_img, 
                            (clique_img_x - 20, clique_img_y), 
                            (clique_img_x + 20, clique_img_y), 
                            (0, 0, 255), 4)
                    cv2.line(vis_img, 
                            (clique_img_x, clique_img_y - 20), 
                            (clique_img_x, clique_img_y + 20), 
                            (0, 0, 255), 4)
                    
                    # Texto destacado
                    cv2.putText(vis_img, ">>> PROXIMO CLIQUE <<<", 
                               (clique_img_x - 80, clique_img_y - 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 3)
                    
                    # NÃO desenhar linha do player ao clique aqui
                    # O path já mostra o caminho completo, e o clique destacado já é suficiente
                    # Isso evita desenhar duas linhas diferentes (path + linha direta)
            
            # 6. Desenhar área visível (retângulo)
            if vis_state['x_atual'] is not None:
                map_region = self.gps.map_calib['map_region']
                raio_visivel_x = int((map_region['width'] / 2) / self.escala_x)
                raio_visivel_y = int((map_region['height'] / 2) / self.escala_y)
                
                # Canto superior esquerdo
                pt1 = mundo_to_img(vis_state['x_atual'] - raio_visivel_x, 
                                  vis_state['y_atual'] - raio_visivel_y)
                # Canto inferior direito
                pt2 = mundo_to_img(vis_state['x_atual'] + raio_visivel_x, 
                                  vis_state['y_atual'] + raio_visivel_y)
                
                if pt1 and pt2:
                    cv2.rectangle(vis_img, pt1, pt2, (255, 255, 0), 2)  # Ciano
            
            # 7. Adicionar informações de debug (texto)
            info_y = 30
            cv2.putText(vis_img, f"Status: {vis_state['status']}", (10, info_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            info_y += 30
            
            if vis_state['x_atual'] is not None:
                cv2.putText(vis_img, f"Player: ({vis_state['x_atual']}, {vis_state['y_atual']})", 
                           (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                info_y += 25
            
            if vis_state['wp_x'] is not None:
                cv2.putText(vis_img, f"Waypoint: ({vis_state['wp_x']}, {vis_state['wp_y']})", 
                           (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                info_y += 25
            
            if vis_state['x_clique'] is not None:
                cv2.putText(vis_img, f"Clique: ({vis_state['x_clique']}, {vis_state['y_clique']})", 
                           (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                info_y += 25
            
            # Legenda
            legend_y = vis_img.shape[0] - 120
            cv2.putText(vis_img, "Legenda:", (10, legend_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            legend_y += 25
            cv2.putText(vis_img, "Azul (P) = Player | Amarelo = Path restante | Vermelho (X) = Proximo clique | Rosa = Destino", 
                       (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Mostrar imagem
            cv2.imshow(self.visualization_window, vis_img)
            cv2.waitKey(1)  # Atualizar janela
            
        except Exception as e:
            print(f"      ⚠️ Erro na visualização: {e}")

    def _tem_chao(self, x_mundo, y_mundo):
        """
        Verifica se coordenada tem chão (não é buraco/fora do mapa)

        Usa mapa colorido (MINIMAPA CERTOPRETO.png):
        - Área COLORIDA = tem chão (dentro do mapa)
        - Área PRETA = buraco/fora do mapa

        Args:
            x_mundo, y_mundo: Coordenadas no mapa mundo

        Returns:
            True se tem chão (colorido), False se é buraco (preto)
        """
        # Verificar bounds
        if not (0 <= int(x_mundo) < self.mapa_colorido.shape[1] and
                0 <= int(y_mundo) < self.mapa_colorido.shape[0]):
            return False

        # Pegar pixel do mapa colorido
        pixel = self.mapa_colorido[int(y_mundo), int(x_mundo)]
        b, g, r = pixel

        # Tem chão se NÃO é preto (algum canal > 10)
        tem_cor = (b > 10 or g > 10 or r > 10)

        return tem_cor

    def calcular_area_visivel(self, x_player, y_player):
        """
        Calcula a área do mapa mundo que está VISÍVEL na tela atual
        
        O player sempre está no centro do mapa visível.
        Área visível = player_pos ± (tamanho_tela / 2 / escala)
        
        Args:
            x_player, y_player: Posição atual do player no mapa mundo
            
        Returns:
            (x_min, x_max, y_min, y_max): Limites da área visível em coordenadas mundo
        """
        map_region = self.gps.map_calib['map_region']
        
        # Raio visível = metade do tamanho da tela em coordenadas mundo
        raio_visivel_x = int((map_region['width'] / 2) / self.escala_x)
        raio_visivel_y = int((map_region['height'] / 2) / self.escala_y)
        
        x_min = x_player - raio_visivel_x
        x_max = x_player + raio_visivel_x
        y_min = y_player - raio_visivel_y
        y_max = y_player + raio_visivel_y
        
        return (x_min, x_max, y_min, y_max)
    
    def encontrar_ponto_visivel_no_path(self, path_completo, x_atual, y_atual):
        """
        Encontra o ponto mais distante no caminho A* SEGUINDO A ORDEM DO PATH

        IMPORTANTE: Percorre o path NA ORDEM (do início ao fim) e pega o ponto
        mais distante que ainda está visível. Isso garante que seguimos o path
        que contorna obstáculos, ao invés de tentar ir reto.

        Args:
            path_completo: Caminho pixel-a-pixel do A* (ORDENADO)
            x_atual, y_atual: Posição atual do player

        Returns:
            (x, y): Coordenadas do ponto mais distante NA ORDEM do path
        """
        map_region = self.gps.map_calib['map_region']

        # Raio da área visível no mapa - REDUZIDO para forçar pontos intermediários
        raio_visivel_x = int((map_region['width'] / self.escala_x) * 0.25)  # 25% do raio
        raio_visivel_y = int((map_region['height'] / self.escala_y) * 0.25)  # 25% do raio

        # Limites de coordenadas mundo visíveis
        x_min_visivel = x_atual - raio_visivel_x
        x_max_visivel = x_atual + raio_visivel_x
        y_min_visivel = y_atual - raio_visivel_y
        y_max_visivel = y_atual + raio_visivel_y

        # Distâncias - REDUZIDAS para clicar mais perto
        dist_minima_obrigatoria = 50   # pixels (não clicar muito perto)
        dist_maxima_permitida = 200    # pixels (não clicar muito longe)

        # Percorrer path NA ORDEM (do início ao fim)
        # Pegar pontos válidos, mas PARAR se próximo ponto estiver muito perto
        ponto_escolhido = None
        dist_escolhida = 0
        dist_anterior = 0

        for i, (px, py) in enumerate(path_completo):
            dist_ao_ponto = self.calcular_distancia(x_atual, y_atual, px, py)

            # Ignorar se muito perto (já passou)
            if dist_ao_ponto < dist_minima_obrigatoria:
                continue

            # Parar se muito longe (saiu da área clicável)
            if dist_ao_ponto > dist_maxima_permitida:
                break

            # NOVO: Parar se este waypoint está muito perto do anterior (< 20px)
            # Isso evita pegar waypoints finais que estão colados
            if ponto_escolhido and (dist_ao_ponto - dist_anterior) < 20:
                print(f"      ⏹️ Parando - waypoints ficaram próximos demais")
                break

            # Verificar se está visível no mapa
            if (x_min_visivel <= px <= x_max_visivel and
                y_min_visivel <= py <= y_max_visivel):

                # VALIDAÇÃO EXTRA: Verificar se tem chão (não é buraco preto fora do mapa)
                # Usar mapa colorido - área colorida = tem chão
                if self._tem_chao(px, py):
                    # Este ponto é válido! Guardar e continuar
                    ponto_escolhido = (px, py)
                    dist_anterior = dist_escolhida
                    dist_escolhida = dist_ao_ponto
                else:
                    # Buraco/fora do mapa - parar aqui
                    print(f"      ⚠️ Ponto ({px}, {py}) está fora do mapa (preto)!")
                    break
            else:
                # Saiu da área visível - parar aqui
                break

        if ponto_escolhido:
            print(f"      🎯 Ponto no path a {dist_escolhida:.0f}px (seguindo ordem do A*)")
            return ponto_escolhido
        else:
            print(f"      ⚠️ Nenhum ponto encontrado! Usando fallback...")
            # Fallback: pegar primeiro ponto >= 50px
            for px, py in path_completo:
                dist = self.calcular_distancia(x_atual, y_atual, px, py)
                if dist >= 50:
                    print(f"      🎯 Fallback: ponto a {dist:.0f}px")
                    return (px, py)

            # Último recurso
            if len(path_completo) > 5:
                return path_completo[5]
            else:
                return path_completo[-1]

    def navegar_para_coordenadas(self, destino_x, destino_y, verbose=True, use_pathfinding=True):
        """
        Navega para coordenadas específicas usando pathfinding A*

        Args:
            destino_x, destino_y: Coordenadas do destino no mapa mundo
            verbose: Se True, mostra detalhes
            use_pathfinding: Se True, usa A* para calcular rota

        Returns:
            True se chegou, False se falhou
        """
        if verbose:
            print("=" * 60)
            print(f"🧭 NAVEGANDO PARA ({destino_x}, {destino_y})")
            if use_pathfinding:
                print("   🗺️ Usando pathfinding A*")
            print("=" * 60)

        # Obter posição inicial (ABRE o mapa e MANTÉM ABERTO)
        print("\n📍 Obtendo posição inicial...")
        print("   🗺️ Abrindo mapa (será mantido aberto durante navegação)...")
        pos = self.gps.get_current_position(keep_map_open=True, verbose=False)
        x_inicial, y_inicial = pos['x'], pos['y']
        print(f"   Posição inicial: ({x_inicial}, {y_inicial}) - {pos['zone']}")
        print(f"   ✅ Mapa aberto e será mantido durante toda navegação")

        # Calcular rota com pathfinding
        path_completo = None
        if use_pathfinding:
            print(f"\n🔍 Calculando rota com A*...")
            path_raw = self.pathfinder.find_path(x_inicial, y_inicial, destino_x, destino_y)

            if path_raw is None:
                print("   ⚠️ Pathfinding falhou com margem de parede!")
                print("   🔧 Tentando pathfinding SEM margem de parede...")
                
                # Tentar criar pathfinder sem margem usando o mapa colorido
                if self.mapa_colorido is not None:
                    pathfinder_sem_margem = AStarPathfinder(self.mapa_colorido, wall_margin=0)
                    path_raw = pathfinder_sem_margem.find_path(x_inicial, y_inicial, destino_x, destino_y)
                    
                    if path_raw is None:
                        print("   ❌ Pathfinding falhou mesmo sem margem!")
                        print("   🔍 Verificando se posições são válidas...")
                        print(f"      Início walkável: {self.pathfinder.is_walkable(x_inicial, y_inicial)}")
                        print(f"      Destino walkável: {self.pathfinder.is_walkable(destino_x, destino_y)}")
                        print("   ↻ Continuando com navegação direta...")
                        use_pathfinding = False
                    else:
                        print(f"   ✅ Caminho A* calculado SEM margem: {len(path_raw)} pontos")
                        # Atualizar pathfinder para usar o sem margem
                        self.pathfinder = pathfinder_sem_margem
                else:
                    print("   ❌ Mapa colorido não encontrado! Tentando navegação direta...")
                    use_pathfinding = False
            else:
                print(f"   ✅ Caminho A* calculado: {len(path_raw)} pontos")

            if path_raw is not None:
                # IMPORTANTE: Usar path COMPLETO (não simplificar muito)
                # Vamos usar todos os pontos do A* para ter mais opções de clique
                path_completo = path_raw
                print(f"   ✅ Path completo: {len(path_completo)} pontos")
                
                # Opcional: Simplificar apenas para visualização (mas não para navegação)
                # path_simplificado = self.pathfinder.simplify_path(path_raw, max_distance=150)
                # print(f"   📊 Path simplificado: {len(path_simplificado)} waypoints (apenas para visualização)")

        # NAVEGAÇÃO INCREMENTAL: calcular cliques baseado na tela ATUAL
        step = 0
        max_steps = 200
        
        # IMPORTANTE: Inicializar índice baseado na posição atual do player
        # Encontrar qual ponto do path está mais próximo da posição inicial
        indice_waypoint_atual = 0
        if path_completo:
            dist_minima_encontrada = float('inf')
            indice_mais_proximo = 0
            
            # Procurar ponto do path mais próximo da posição inicial
            for i, (px, py) in enumerate(path_completo):
                dist = self.calcular_distancia(x_inicial, y_inicial, px, py)
                if dist < dist_minima_encontrada:
                    dist_minima_encontrada = dist
                    indice_mais_proximo = i
            
            # Começar do ponto mais próximo + 1 (para estar à frente)
            indice_waypoint_atual = min(indice_mais_proximo + 1, len(path_completo) - 1)
            print(f"   📍 Índice inicial do path: {indice_waypoint_atual+1}/{len(path_completo)} (ponto mais próximo: {indice_mais_proximo+1})")
        
        posicao_anterior = None  # Para detectar se está preso
        cliques_sem_movimento = 0  # Contador de cliques sem movimento
        MAX_CLIQUES_SEM_MOVIMENTO = 3  # Máximo de cliques sem movimento antes de pular waypoint
        
        # Estado para visualização
        vis_state = {
            'x_atual': None,
            'y_atual': None,
            'wp_x': None,
            'wp_y': None,
            'x_clique': None,
            'y_clique': None,
            'path_completo': path_completo,
            'destino_x': destino_x,
            'destino_y': destino_y,
            'step': 0,
            'status': 'Iniciando...'
        }

        while step < max_steps:
            step += 1

            if verbose:
                print(f"\n▶️ Passo {step}/{max_steps}")

            # 1. CAPTURAR TELA ATUAL e obter posição atual (mapa JÁ está aberto)
            print("   1️⃣ Capturando tela atual e obtendo posição...")
            pos = self.gps.get_current_position(keep_map_open=True, verbose=False, map_already_open=True)
            x_atual, y_atual = pos['x'], pos['y']
            print(f"      📍 Posição atual: ({x_atual}, {y_atual}) - {pos['zone']}")
            
            # Atualizar estado para visualização
            vis_state['x_atual'] = x_atual
            vis_state['y_atual'] = y_atual
            vis_state['step'] = step
            vis_state['status'] = f'Passo {step}/{max_steps}'
            
            # Detectar se player está preso (não se moveu)
            if posicao_anterior is not None:
                if posicao_anterior == (x_atual, y_atual):
                    cliques_sem_movimento += 1
                    print(f"      ⚠️ Player não se moveu! Cliques sem movimento: {cliques_sem_movimento}/{MAX_CLIQUES_SEM_MOVIMENTO}")
                    vis_state['status'] = f'Preso! ({cliques_sem_movimento}/{MAX_CLIQUES_SEM_MOVIMENTO})'
                else:
                    cliques_sem_movimento = 0  # Reset contador se moveu
            posicao_anterior = (x_atual, y_atual)

            # 2. Verificar se chegou no destino final
            distancia_final = self.calcular_distancia(x_atual, y_atual, destino_x, destino_y)
            print(f"      📏 Distância ao destino: {distancia_final:.1f} pixels")

            if distancia_final <= self.tolerance_pixels:
                print(f"\n{'=' * 60}")
                print(f"🎯 CHEGOU NO DESTINO!")
                print(f"   Posição final: ({x_atual}, {y_atual})")
                print(f"{'=' * 60}\n")
                print("   🗺️ Fechando mapa...")
                self.gps.click_button('close')
                time.sleep(0.3)  # Aguardar mapa fechar
                return True
            
            # 2.5. Verificar se player está preso (não se moveu nos últimos passos)
            if step > 3:
                # Verificar posições anteriores (podemos implementar cache se necessário)
                pass

            # 3. Calcular área VISÍVEL do mapa mundo na tela atual
            # IMPORTANTE: A área visível é calculada baseada no tamanho da CAPTURA ORIGINAL
            # Como a escala é 1:1 (GPS já faz conversão interna), a área visível = tamanho da captura
            # O player está SEMPRE no centro da tela, então:
            # - Raio visível = metade do tamanho da captura
            # - Área visível = player_pos ± raio_visivel
            map_region = self.gps.map_calib['map_region']
            
            # Tamanho da captura ORIGINAL (tela onde vamos clicar)
            captura_width = map_region['width']   # 1600 pixels (TELA ORIGINAL)
            captura_height = map_region['height'] # 899 pixels (TELA ORIGINAL)
            
            # Raio visível (metade da captura) - em pixels do mapa mundo
            # CORREÇÃO: Com escala 5.0, precisamos dividir pelo fator de escala!
            # Tela captura 1600px, mas com escala 5.0 isso representa 1600/5 = 320px no mundo
            # Raio = (tamanho_tela / 2) / escala = área visível no mapa mundo
            raio_visivel_x = int((captura_width / 2) / self.escala_x)   # (1600 / 2) / 5.0 = 160 pixels
            raio_visivel_y = int((captura_height / 2) / self.escala_y)  # (899 / 2) / 5.0 = 90 pixels
            
            # Área visível do mapa mundo (em pixels do mapa mundo)
            # Área visível = player_pos ± raio_visivel
            # Isso define quais coordenadas do mapa mundo estão VISÍVEIS na tela atual
            
            # Limites da área visível (em coordenadas do mapa mundo)
            x_min_visivel = x_atual - raio_visivel_x
            x_max_visivel = x_atual + raio_visivel_x
            y_min_visivel = y_atual - raio_visivel_y
            y_max_visivel = y_atual + raio_visivel_y
            
            # Verificar se destino final está visível
            destino_visivel = (x_min_visivel <= destino_x <= x_max_visivel and
                             y_min_visivel <= destino_y <= y_max_visivel)
            
            dist_destino = self.calcular_distancia(x_atual, y_atual, destino_x, destino_y)
            
            # IMPORTANTE: Se destino está visível, clicar DIRETO nele (prioridade máxima)
            # MAS: Verificar se destino é walkable e se o clique será válido
            usar_destino_direto = (destino_visivel and 
                                  dist_destino >= 30 and  # Mínimo 30px para evitar cliques muito próximos
                                  cliques_sem_movimento == 0 and  # Player não está preso
                                  path_completo is not None and  # Path existe (garantia de caminho)
                                  self.is_walkable(destino_x, destino_y))  # Destino é walkable
            
            if usar_destino_direto:
                # Verificar se o clique será válido (dentro da região clicável do mapa)
                x_clique_test, y_clique_test = self.mundo_to_tela(destino_x, destino_y, x_atual, y_atual)
                map_region = self.gps.map_calib['map_region']
                
                # Verificar se clique está dentro dos limites (com margens maiores para UI/bordas)
                margem_x = 120  # Margem para UI/bordas na largura
                margem_y = 100  # Margem para UI/bordas na altura
                clique_valido = (map_region['x'] + margem_x <= x_clique_test <= map_region['x'] + map_region['width'] - margem_x and
                                map_region['y'] + margem_y <= y_clique_test <= map_region['y'] + map_region['height'] - margem_y)
                
                if clique_valido:
                    print(f"   2️⃣ DESTINO FINAL está visível na tela!")
                    print(f"      🎯 Clicando DIRETO no destino: ({destino_x}, {destino_y})")
                    print(f"      📏 Distância: {dist_destino:.1f} pixels")
                    print(f"      ✅ Prioridade: destino visível > waypoints intermediários")
                    wp_x, wp_y = destino_x, destino_y
                else:
                    print(f"   2️⃣ Destino visível mas clique seria inválido ({x_clique_test}, {y_clique_test})")
                    print(f"      ↻ Usando path intermediário...")
                    usar_destino_direto = False  # Forçar uso do path
            # 3.1. Se não, encontrar o ponto MAIS LONGE do path A* que está visível na tela
            elif path_completo:
                print(f"   2️⃣ Procurando ponto MAIS LONGE do path A* visível na tela...")
                print(f"      📐 Área visível: ({x_min_visivel}, {y_min_visivel}) a ({x_max_visivel}, {y_max_visivel})")
                
                # IMPORTANTE: Atualizar índice baseado na posição atual do player
                # Encontrar qual ponto do path está mais próximo da posição atual
                # (player pode ter andado além do índice atual)
                dist_minima_para_atualizar = 50  # Se player está muito longe do índice atual, atualizar
                
                # Verificar se precisa atualizar índice do path
                if indice_waypoint_atual < len(path_completo):
                    px_atual, py_atual = path_completo[indice_waypoint_atual]
                    dist_ao_indice_atual = self.calcular_distancia(x_atual, y_atual, px_atual, py_atual)
                    
                    # Se player passou muito além do índice atual, atualizar índice
                    if dist_ao_indice_atual > dist_minima_para_atualizar:
                        # Encontrar índice mais próximo da posição atual do player
                        dist_minima_encontrada = float('inf')
                        indice_mais_proximo = indice_waypoint_atual
                        
                        # Procurar do índice atual até o final do path
                        for i in range(indice_waypoint_atual, len(path_completo)):
                            px, py = path_completo[i]
                            dist = self.calcular_distancia(x_atual, y_atual, px, py)
                            
                            # Se encontrou ponto mais próximo E está à frente (índice maior)
                            if dist < dist_minima_encontrada:
                                dist_minima_encontrada = dist
                                indice_mais_proximo = i
                        
                        # Se encontrou ponto mais próximo, atualizar índice
                        if dist_minima_encontrada < dist_minima_para_atualizar:
                            indice_waypoint_atual = indice_mais_proximo + 1  # +1 para estar à frente
                            if indice_waypoint_atual >= len(path_completo):
                                indice_waypoint_atual = len(path_completo) - 1
                            print(f"      🔄 Índice atualizado para {indice_waypoint_atual+1}/{len(path_completo)} (player andou)")
                
                # Filtrar pontos do path que estão:
                # 1. À frente do player (índice >= indice_waypoint_atual)
                # 2. Visíveis na tela atual
                # 3. Com distância adequada (mínima e máxima)
                # 4. NA ORDEM do path (seguir sequência)
                
                pontos_visiveis = []
                dist_minima_clique = 30  # Mínimo 30px para clicar
                
                # IMPORTANTE: dist_maxima_clique precisa considerar as MARGENS de clique
                # A área clicável é menor que a área visível devido às margens (UI, bordas, etc.)
                # Margens usadas em mundo_to_tela: 120px (X) e 100px (Y)
                # Área clicável = captura - margens
                # Raio clicável = (captura - margens) / 2
                margem_clique_x = 120  # Margem para UI/bordas na largura
                margem_clique_y = 100  # Margem para UI/bordas na altura

                # CORREÇÃO: Com escala 5.0, precisamos dividir pelo fator de escala!
                # Área clicável na tela → convertida para pixels do mundo
                raio_clicavel_x = int(((captura_width - margem_clique_x * 2) / 2) / self.escala_x)   # (1360 / 2) / 5.0 = 136
                raio_clicavel_y = int(((captura_height - margem_clique_y * 2) / 2) / self.escala_y)  # (699 / 2) / 5.0 = 70

                # Distância máxima para clique = raio clicável no mapa mundo
                dist_maxima_clique = min(raio_clicavel_x, raio_clicavel_y)  # min(136, 70) = 70 pixels mundo
                
                # IMPORTANTE: Limitar distância máxima para garantir que o clique seja válido
                # O clique precisa estar dentro da área visível e dentro da região do mapa
                # Vamos usar o raio visível como limite máximo
                
                # IMPORTANTE: Percorrer path NA ORDEM (do índice atual até o final)
                # Pegar pontos visíveis que estejam dentro da distância máxima
                # Escolher o MAIS DISTANTE visível (mas dentro do limite) para maximizar progresso
                for i in range(indice_waypoint_atual, len(path_completo)):
                    px, py = path_completo[i]
                    dist = self.calcular_distancia(x_atual, y_atual, px, py)
                    
                    # Verificar se está visível E com distância adequada (mínima e máxima)
                    if (x_min_visivel <= px <= x_max_visivel and
                        y_min_visivel <= py <= y_max_visivel and
                        dist >= dist_minima_clique and
                        dist <= dist_maxima_clique):
                        
                        # Verificar se é walkable usando mapa colorido
                        if self._tem_chao(px, py):
                            pontos_visiveis.append((i, px, py, dist))
                
                # Se encontrou pontos visíveis, pegar o MAIS DISTANTE visível
                # IMPORTANTE: Ordenar por distância (maior primeiro) e pegar o mais distante
                # MAS: Verificar se o clique será válido antes de escolher
                if pontos_visiveis:
                    # Ordenar por distância (maior primeiro) - MAIS DISTANTE primeiro
                    pontos_visiveis.sort(key=lambda x: x[3], reverse=True)
                    
                    # Tentar encontrar um ponto que gere um clique válido
                    wp_x, wp_y = None, None
                    i_escolhido = None
                    map_region = self.gps.map_calib['map_region']
                    
                    for i, px, py, dist in pontos_visiveis:
                        # Verificar se o clique será válido (dentro da região do mapa)
                        x_clique_test, y_clique_test = self.mundo_to_tela(px, py, x_atual, y_atual)
                        
                        # Verificar se clique está dentro dos limites (com as mesmas margens usadas em mundo_to_tela)
                        clique_valido = (map_region['x'] + margem_clique_x <= x_clique_test <= map_region['x'] + map_region['width'] - margem_clique_x and
                                        map_region['y'] + margem_clique_y <= y_clique_test <= map_region['y'] + map_region['height'] - margem_clique_y)
                        
                        if clique_valido:
                            wp_x, wp_y = px, py
                            i_escolhido = i
                            dist_escolhida = dist
                            break
                    
                    if wp_x is not None:
                        # Atualizar índice para o ponto escolhido
                        indice_waypoint_atual = i_escolhido
                        
                        print(f"      🎯 Ponto MAIS DISTANTE visível na tela: ({wp_x}, {wp_y})")
                        print(f"      📏 Distância: {dist_escolhida:.1f} pixels (máxima visível)")
                        print(f"      📍 Índice no path: {i_escolhido+1}/{len(path_completo)}")
                        print(f"      ✅ Total de pontos visíveis: {len(pontos_visiveis)}")
                        print(f"      📊 Estratégia: Clicar no ponto mais distante para máximo progresso")
                    else:
                        # Nenhum ponto visível gera clique válido, usar fallback
                        print(f"      ⚠️ Nenhum ponto visível gera clique válido na região do mapa")
                        wp_x, wp_y = None, None
                else:
                    # Nenhum ponto visível, tentar avançar índice
                    print(f"      ⚠️ Nenhum ponto do path visível na tela atual")
                    
                    # Avançar para próximo ponto no path que esteja suficientemente longe
                    wp_x, wp_y = None, None
                    for i in range(indice_waypoint_atual + 1, len(path_completo)):
                        px, py = path_completo[i]
                        dist_proximo = self.calcular_distancia(x_atual, y_atual, px, py)
                        
                        if dist_proximo >= dist_minima_clique:
                            indice_waypoint_atual = i
                            wp_x, wp_y = px, py
                            print(f"      ↻ Avançando para próximo ponto no path...")
                            print(f"      🎯 Ponto {i+1}/{len(path_completo)}: ({wp_x}, {wp_y})")
                            print(f"      📏 Distância: {dist_proximo:.1f} pixels")
                            break
                    
                    # Se não encontrou ponto adequado, usar destino final
                    if wp_x is None:
                        print(f"      ⚠️ Todos os pontos próximos demais, usando destino final")
                        wp_x, wp_y = destino_x, destino_y
            else:
                # Sem pathfinding, verificar se destino está MUITO PERTO
                if destino_visivel and dist_destino <= 150 and dist_destino >= 30:
                    print(f"      🎯 Destino visível e muito perto, clicando direto!")
                    wp_x, wp_y = destino_x, destino_y
                else:
                    # Sem pathfinding, ir direto (último recurso)
                    wp_x, wp_y = destino_x, destino_y

            # 4. Verificar se temos um waypoint válido
            if wp_x is None or wp_y is None:
                print(f"   3️⃣ ⚠️ Nenhum waypoint válido encontrado!")
                print(f"      ↻ Tentando encontrar ponto mais próximo no path...")
                
                # Fallback: encontrar próximo ponto válido no path
                if path_completo:
                    for i in range(indice_waypoint_atual, min(indice_waypoint_atual + 50, len(path_completo))):
                        px, py = path_completo[i]
                        dist = self.calcular_distancia(x_atual, y_atual, px, py)
                        
                        if dist >= 30 and self._tem_chao(px, py):
                            # Verificar se clique será válido (dentro da região clicável do mapa)
                            x_clique_test, y_clique_test = self.mundo_to_tela(px, py, x_atual, y_atual)
                            map_region = self.gps.map_calib['map_region']
                            margem_x = 120  # Margem para UI/bordas na largura
                            margem_y = 100  # Margem para UI/bordas na altura
                            clique_valido = (map_region['x'] + margem_x <= x_clique_test <= map_region['x'] + map_region['width'] - margem_x and
                                            map_region['y'] + margem_y <= y_clique_test <= map_region['y'] + map_region['height'] - margem_y)
                            
                            if clique_valido:
                                wp_x, wp_y = px, py
                                indice_waypoint_atual = i
                                print(f"      ✅ Ponto válido encontrado: ({wp_x}, {wp_y})")
                                break
                
                if wp_x is None:
                    print(f"      ❌ Não foi possível encontrar ponto válido!")
                    print(f"      ↻ Avançando índice e tentando novamente no próximo passo...")
                    indice_waypoint_atual = min(indice_waypoint_atual + 10, len(path_completo) - 1)
                    continue  # Pular este passo
            
            # 5. Calcular clique baseado na TELA ATUAL usando a função correta
            print(f"   3️⃣ Calculando clique para tela ATUAL...")
            print(f"      → Destino mundo: ({wp_x}, {wp_y})")
            print(f"      → Walkável: {'✅' if self.is_walkable(wp_x, wp_y) else '❌'}")
            
            # IMPORTANTE: Usar função mundo_to_tela que já faz todo o cálculo corretamente
            # Ela usa a posição ATUAL do player e converte para coordenadas de clique
            x_clique, y_clique = self.mundo_to_tela(wp_x, wp_y, x_atual, y_atual)
            
            # VALIDAÇÃO FINAL: Verificar se clique está dentro dos limites válidos
            map_region = self.gps.map_calib['map_region']
            margem_x = 120  # Margem para UI/bordas na largura
            margem_y = 100  # Margem para UI/bordas na altura
            clique_dentro_limites = (map_region['x'] + margem_x <= x_clique <= map_region['x'] + map_region['width'] - margem_x and
                                    map_region['y'] + margem_y <= y_clique <= map_region['y'] + map_region['height'] - margem_y)
            
            if not clique_dentro_limites:
                print(f"      ❌ Clique ({x_clique}, {y_clique}) está FORA da região clicável do mapa!")
                print(f"      ↻ Região clicável: X=[{map_region['x'] + margem_x}, {map_region['x'] + map_region['width'] - margem_x}], Y=[{map_region['y'] + margem_y}, {map_region['y'] + map_region['height'] - margem_y}]")
                print(f"      ↻ Avançando para próximo ponto no path...")
                indice_waypoint_atual = min(indice_waypoint_atual + 10, len(path_completo) - 1)
                continue  # Pular este passo
            
            # Atualizar estado para visualização
            vis_state['wp_x'] = wp_x
            vis_state['wp_y'] = wp_y
            vis_state['x_clique'] = x_clique
            vis_state['y_clique'] = y_clique
            
            print(f"      🖱️ Clique calculado: ({x_clique}, {y_clique})")
            print(f"      ✅ Clique dentro dos limites válidos")
            
            # Atualizar visualização ANTES de clicar
            if self.show_visualization:
                self._atualizar_visualizacao(vis_state)
            
            # Clicar usando a função que já existe
            self.clicar_no_mapa(wp_x, wp_y, x_atual, y_atual)

            time.sleep(self.wait_after_click)

            # 5. Aguardar chegada e CONFIRMAR com novo scan do mapa
            print(f"   4️⃣ Aguardando chegada...")
            chegou = self.aguardar_chegada(wp_x, wp_y, x_atual, y_atual, max_wait=10.0, use_gps_confirm=True)
            
            # 5.5. CONFIRMAÇÃO: Após movimento, fazer novo scan para confirmar posição
            if chegou:
                print(f"      ✅ Chegou no waypoint!")
                print(f"      🔍 Confirmando posição com novo scan do mapa...")
                # Novo scan já será feito no próximo passo (4.1)
                # O índice será atualizado automaticamente baseado na nova posição
            else:
                # Não chegou, mas continua tentando
                print(f"      ↻ Ainda não chegou no waypoint, continuando navegação...")
                
                # Se player está preso tentando ir direto ao destino, usar path
                if wp_x == destino_x and wp_y == destino_y and cliques_sem_movimento >= 2:
                    print(f"      ⚠️ Player ficou preso tentando ir direto ao destino!")
                    print(f"      🔄 Próxima iteração usará waypoints do path para contornar obstáculos...")
                    # Resetar índice para encontrar próximo waypoint no path
                    if path_completo:
                        # Encontrar próximo waypoint no path que esteja à frente do player
                        for i, (px, py) in enumerate(path_completo):
                            dist = self.calcular_distancia(x_atual, y_atual, px, py)
                            if dist > 50:  # Waypoint que está suficientemente à frente
                                indice_waypoint_atual = i
                                break

        # Máximo de passos atingido
        print(f"\n⚠️ Máximo de passos ({max_steps}) atingido!")
        print("   🗺️ Fechando mapa...")
        self.gps.click_button('close')
        time.sleep(0.3)  # Aguardar mapa fechar
        return False

    def navegar_para_zona(self, nome_zona, verbose=True):
        """
        Navega para spawn de uma zona

        Args:
            nome_zona: Nome da zona (ex: 'Deserto', 'Praia')
            verbose: Se True, mostra detalhes

        Returns:
            True se chegou, False se falhou
        """
        if nome_zona not in ZONAS_DISPONIVEIS:
            print(f"❌ Zona '{nome_zona}' não encontrada!")
            print(f"Zonas disponíveis: {list(ZONAS_DISPONIVEIS.keys())}")
            return False

        spawn_x, spawn_y = ZONAS_DISPONIVEIS[nome_zona]['spawn']

        if verbose:
            print(f"\n🗺️ Navegando para zona: {nome_zona}")
            print(f"   Spawn: ({spawn_x}, {spawn_y})")

        return self.navegar_para_coordenadas(spawn_x, spawn_y, verbose=verbose)


def menu_interativo():
    """Menu interativo para testar navegação"""
    print("\n" + "=" * 60)
    print("🧭 NAVEGADOR AUTOMÁTICO COM NCC")
    print("=" * 60 + "\n")

    # Inicializar navegador
    nav = NavegadorAutomaticoNCC()

    while True:
        print("\n" + "=" * 60)
        print("MENU:")
        print("=" * 60)
        print("  1. Navegar para zona")
        print("  2. Navegar para coordenadas")
        print("  3. Ver posição atual")
        print("  4. Listar zonas")
        print("  5. Sair")
        print("=" * 60)

        escolha = input("\nEscolha (1-5): ").strip()

        if escolha == '1':
            # Navegar para zona
            print("\nZonas disponíveis:")
            for i, zona in enumerate(ZONAS_DISPONIVEIS.keys(), 1):
                print(f"  [{i:2d}] {zona}")

            zona_id = input("\nDigite o número da zona: ").strip()

            try:
                zona_id = int(zona_id)
                zonas_list = list(ZONAS_DISPONIVEIS.keys())
                if 1 <= zona_id <= len(zonas_list):
                    zona_nome = zonas_list[zona_id - 1]
                    nav.navegar_para_zona(zona_nome)
                else:
                    print(f"❌ Número inválido! Escolha entre 1 e {len(zonas_list)}")
            except ValueError:
                print("❌ Número inválido! Digite apenas números.")
            except IndexError:
                print(f"❌ Zona não encontrada! Escolha entre 1 e {len(ZONAS_DISPONIVEIS)}")
            except Exception as e:
                print(f"❌ Erro durante navegação: {e}")
                import traceback
                traceback.print_exc()

        elif escolha == '2':
            # Navegar para coordenadas
            try:
                x = int(input("Digite X: ").strip())
                y = int(input("Digite Y: ").strip())
                nav.navegar_para_coordenadas(x, y)
            except:
                print("❌ Coordenadas inválidas!")

        elif escolha == '3':
            # Ver posição atual
            pos = nav.gps.get_current_position()
            print(f"\n📍 Posição atual: ({pos['x']}, {pos['y']})")
            print(f"🗺️ Zona: {pos['zone']}")
            print(f"📊 Confiança: {pos['confidence']}%")

        elif escolha == '4':
            # Listar zonas
            print("\n🗺️ Zonas disponíveis:")
            for zona, info in ZONAS_DISPONIVEIS.items():
                print(f"   • {zona:30s} - Spawn: {info['spawn']}")

        elif escolha == '5':
            print("\n👋 Até logo!")
            break

        else:
            print("❌ Opção inválida!")


if __name__ == "__main__":
    menu_interativo()
