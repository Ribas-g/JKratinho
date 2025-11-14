"""
CALIBRADOR DE VELOCIDADE DO PERSONAGEM
Mede a velocidade de movimento do personagem para simulação temporal

Funcionamento:
1. GPS inicial para posição de referência
2. Clica em diferentes distâncias (1-5 tiles)
3. Detecta linha verde (movimento em progresso)
4. Mede tempo até linha verde desaparecer
5. Calcula velocidade média (pixels/segundo e tempo/tile)
6. Salva em FARM/velocidade_personagem.json
"""

import cv2
import numpy as np
import time
import json
from pathlib import Path
import sys
import random
import math

# Importar GPS e A*
sys.path.append('.')
from gps_ncc_realtime import GPSRealtimeNCC
from pathfinding_astar import AStarPathfinder


class CalibradorVelocidade:
    def __init__(self):
        """Inicializa calibrador"""
        self.gps = GPSRealtimeNCC()
        # Usar device do GPS (já conectado)
        self.device = self.gps.device

        # Carregar matriz walkable para validar destinos
        self.carregar_matriz_walkable()

        # Inicializar A* pathfinding com o mapa colorido
        self.inicializar_pathfinding()

        # Carregar configuração de mapa (centro e escala)
        self.carregar_configuracao_mapa()

        # Região onde procurar linha verde (em torno do personagem)
        # O personagem fica no centro da tela (800, 450) em 1600x900
        self.centro_x = 800
        self.centro_y = 450

        # Região de busca da linha verde (caixa em torno do personagem)
        self.verde_x1 = 700
        self.verde_y1 = 350
        self.verde_x2 = 900
        self.verde_y2 = 550

        # Configurações HSV para linha verde
        # Verde em HSV: H=50-70 (tom), S>100 (saturação), V>100 (brilho)
        self.verde_lower = np.array([40, 100, 100])
        self.verde_upper = np.array([80, 255, 255])

        # Distâncias para testar (em tiles)
        # Assumindo 1 tile = ~32 pixels
        self.distancias_tiles = [1, 2, 3, 4, 5]
        self.pixels_por_tile = 32

        # Resultados
        self.medicoes = []

        # Posição do jogador (será setada por GPS)
        self.player_x = None
        self.player_y = None

    def carregar_matriz_walkable(self):
        """Carrega matriz walkable para validar destinos"""
        try:
            dados = np.load('FARM/mapa_mundo_processado.npz')
            self.matriz_walkable = dados['walkable']
            self.mundo_largura = dados['dimensoes'][0]
            self.mundo_altura = dados['dimensoes'][1]
            print("   ✅ Matriz walkable carregada!")
        except FileNotFoundError:
            print("   ⚠️ Matriz walkable não encontrada!")
            print("   Execute: python processar_mapa_mundo.py")
            print("   Calibração continuará sem validação de destinos")
            self.matriz_walkable = None

    def inicializar_pathfinding(self):
        """Inicializa A* pathfinding para calcular distâncias reais"""
        try:
            import cv2
            # Carregar mapa colorido (mesmo usado pelo GPS)
            mapa_colorido = cv2.imread('MINIMAPA CERTOPRETO.png')

            if mapa_colorido is None:
                print("   ⚠️ MINIMAPA CERTOPRETO.png não encontrado!")
                print("   Calibração usará Manhattan sem A*")
                self.pathfinder = None
                return

            # Criar pathfinder A* (sem margem de segurança para calibração)
            print("   🗺️ Inicializando A* pathfinder...")
            self.pathfinder = AStarPathfinder(mapa_colorido, wall_margin=0)
            print("   ✅ A* pathfinder pronto!")

        except Exception as e:
            print(f"   ⚠️ Erro ao inicializar pathfinder: {e}")
            print("   Calibração usará Manhattan sem A*")
            self.pathfinder = None

    def carregar_configuracao_mapa(self):
        """Carrega configuração de transformação mundo → tela (do navegador)"""
        try:
            with open('map_transform_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.centro_mapa_x = config['centro_mapa_tela']['x']
            self.centro_mapa_y = config['centro_mapa_tela']['y']
            self.escala_x = config['escala']['x']
            self.escala_y = config['escala']['y']

            print(f"   ✅ Configuração de mapa carregada")
            print(f"   📍 Centro do mapa na tela: ({self.centro_mapa_x}, {self.centro_mapa_y})")
            print(f"   📏 Escala: X={self.escala_x:.4f}, Y={self.escala_y:.4f}")

        except FileNotFoundError:
            print("   ⚠️ map_transform_config.json não encontrado!")
            print("   Execute calibração do navegador primeiro")
            print("   Usando valores padrão...")

            # Valores padrão (assumindo mapa fullscreen 1600x900)
            self.centro_mapa_x = 800
            self.centro_mapa_y = 450
            self.escala_x = 5.0
            self.escala_y = 5.0

    def mundo_para_tela_mapa(self, x_mundo, y_mundo, x_atual, y_atual):
        """
        Converte coordenadas mundo → tela do mapa (COM MAPA ABERTO)

        IMPORTANTE: Player SEMPRE no centro do mapa.
        Calcula delta e aplica escala.

        Args:
            x_mundo, y_mundo: Destino no mapa mundo
            x_atual, y_atual: Posição atual do player no mapa mundo

        Returns:
            (x_tela, y_tela): Coordenadas para clicar no mapa
        """
        # Delta (quanto precisa andar)
        delta_x = x_mundo - x_atual
        delta_y = y_mundo - y_atual

        # Aplicar escala e somar ao centro
        # Player está SEMPRE no centro do mapa
        x_tela = int(self.centro_mapa_x + delta_x * self.escala_x)
        y_tela = int(self.centro_mapa_y + delta_y * self.escala_y)

        return (x_tela, y_tela)

    def converter_tela_para_mundo(self, tela_x, tela_y):
        """Converte coordenadas da tela para coordenadas do mundo"""
        if self.player_x is None or self.player_y is None:
            return None, None

        offset_x = tela_x - self.centro_x
        offset_y = tela_y - self.centro_y

        mundo_x = self.player_x + offset_x
        mundo_y = self.player_y + offset_y

        return mundo_x, mundo_y

    def validar_destino(self, mundo_x, mundo_y):
        """Valida se destino é walkable"""
        if self.matriz_walkable is None:
            return True  # Se não tem matriz, aceitar qualquer destino

        # Verificar limites
        if mundo_x < 0 or mundo_x >= self.mundo_largura:
            return False
        if mundo_y < 0 or mundo_y >= self.mundo_altura:
            return False

        # Verificar walkability
        return self.matriz_walkable[int(mundo_y), int(mundo_x)] == 1

    def encontrar_destino_valido(self, distancia_tiles, max_tentativas=50):
        """
        Encontra um destino válido usando A* pathfinding

        IMPORTANTE: Usa A* para calcular caminho REAL contornando paredes.
        Não usa Manhattan simples porque pode haver obstáculos no caminho.

        Args:
            distancia_tiles: distância desejada em tiles (aproximada)
            max_tentativas: máximo de tentativas para encontrar destino válido

        Returns:
            (tela_x, tela_y, distancia_astar_px, path) ou None se não encontrar
            - tela_x, tela_y: coordenadas na tela
            - distancia_astar_px: distância REAL do caminho A* em pixels
            - path: lista de pontos do caminho A*
        """
        for _ in range(max_tentativas):
            # PREFERÊNCIA CARDINAL: 80% chance de movimento reto
            # Movimentos cardeais são mais eficientes e precisos
            if random.random() < 0.8:
                # Escolher direção cardinal aleatória
                direcao = random.choice([
                    (1, 0),   # Leste  →
                    (-1, 0),  # Oeste  ←
                    (0, 1),   # Sul    ↓
                    (0, -1),  # Norte  ↑
                ])

                # Calcular offset para movimento cardinal puro
                offset_x = direcao[0] * distancia_tiles * self.pixels_por_tile
                offset_y = direcao[1] * distancia_tiles * self.pixels_por_tile

            else:
                # 20% chance: qualquer ângulo (diagonal)
                # Personagem vai "escadear" para chegar
                angulo = random.uniform(0, 2 * math.pi)
                distancia_px = distancia_tiles * self.pixels_por_tile

                offset_x = int(distancia_px * math.cos(angulo))
                offset_y = int(distancia_px * math.sin(angulo))

            # Coordenadas na tela
            tela_x = self.centro_x + offset_x
            tela_y = self.centro_y + offset_y

            # Garantir que está dentro da tela
            if tela_x < 100 or tela_x > 1500:
                continue
            if tela_y < 100 or tela_y > 800:
                continue

            # Converter para mundo
            mundo_x, mundo_y = self.converter_tela_para_mundo(tela_x, tela_y)

            if mundo_x is None:
                # Sem GPS ainda, fallback para Manhattan
                distancia_manhattan = abs(offset_x) + abs(offset_y)
                return tela_x, tela_y, distancia_manhattan, None

            # Validar que destino é walkable
            if not self.validar_destino(mundo_x, mundo_y):
                continue  # Destino em parede, tentar outro

            # USAR A* para calcular caminho REAL
            if self.pathfinder is not None:
                # Calcular caminho usando A*
                path = self.pathfinder.find_path(
                    int(self.player_x), int(self.player_y),
                    int(mundo_x), int(mundo_y)
                )

                # Se caminho não existe (bloqueado por paredes), descartar
                if path is None:
                    continue

                # Distância REAL = número de tiles no caminho A*
                distancia_astar_tiles = len(path)
                distancia_astar_px = distancia_astar_tiles * self.pixels_por_tile

                # Aceitar esse destino
                return tela_x, tela_y, distancia_astar_px, path

            else:
                # Fallback: sem A*, usar Manhattan
                distancia_manhattan = abs(offset_x) + abs(offset_y)
                return tela_x, tela_y, distancia_manhattan, None

        # Não encontrou destino válido
        return None

    def capturar_tela(self):
        """Captura screenshot do dispositivo"""
        try:
            return self.gps.capture_screen()
        except Exception as e:
            print(f"❌ Erro ao capturar tela: {e}")
            return None

    def detectar_linha_verde(self, img):
        """
        Detecta se linha verde está presente na imagem (TELA DE JOGO)
        Retorna True se linha verde detectada
        """
        if img is None:
            return False

        # Recortar região em torno do personagem
        roi = img[self.verde_y1:self.verde_y2, self.verde_x1:self.verde_x2]

        # Converter para HSV
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Criar máscara para cor verde
        mask = cv2.inRange(hsv, self.verde_lower, self.verde_upper)

        # Contar pixels verdes
        pixels_verdes = cv2.countNonZero(mask)

        # Threshold: precisa de pelo menos 50 pixels verdes para considerar linha presente
        return pixels_verdes > 50

    def detectar_linha_verde_no_mapa(self, img):
        """
        Detecta e conta tiles da linha verde NO MAPA

        A linha verde aparece no mapa quando você clica em um destino,
        mostrando o caminho que o personagem vai percorrer.

        IMPORTANTE: Após processamento de levels, a cor é #00ff00 (verde puro)

        Retorna:
            int: Número de tiles da linha verde (ground truth!)
            None: Se não detectou linha
        """
        if img is None:
            return None

        # Converter para HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Linha verde após levels: #00ff00 (RGB: 0, 255, 0) = verde puro
        # Em HSV: H~60 (verde puro), S alta, V alta
        verde_lower = np.array([50, 150, 150])  # Mais restritivo para verde puro
        verde_upper = np.array([70, 255, 255])

        # Criar máscara
        mask = cv2.inRange(hsv, verde_lower, verde_upper)

        # Contar pixels da linha
        pixels_linha = cv2.countNonZero(mask)

        if pixels_linha < 100:  # Threshold mínimo
            return None

        # Usar morfologia para encontrar o "esqueleto" da linha
        kernel = np.ones((3,3), np.uint8)
        linha_fina = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        linha_fina = cv2.morphologyEx(linha_fina, cv2.MORPH_OPEN, kernel)

        # Encontrar contornos
        contours, _ = cv2.findContours(linha_fina, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Pegar maior contorno (a linha principal)
        maior_contorno = max(contours, key=cv2.contourArea)

        # Calcular comprimento do contorno (aproximação do caminho)
        comprimento_pixels = cv2.arcLength(maior_contorno, closed=False)

        # Converter para tiles
        # pixels no mapa / (pixels_por_tile * escala) = tiles
        tiles = comprimento_pixels / (self.pixels_por_tile * self.escala_x)

        return int(tiles)

    def executar_tap(self, x, y):
        """Executa tap em coordenada específica"""
        try:
            self.device.shell(f"input tap {x} {y}")
            return True
        except Exception as e:
            print(f"❌ Erro ao executar tap: {e}")
            return False

    def calibrar_com_mapa_aberto(self):
        """
        CALIBRAÇÃO COM MAPA ABERTO - Usa linha verde do mapa como ground truth

        Fluxo:
        1. Abre mapa UMA VEZ
        2. Mantém mapa aberto para TODAS as medições
        3. Para cada distância:
           - GPS com mapa já aberto
           - Gera destino walkable válido
           - Converte mundo → tela do mapa
           - Clica no mapa (linha verde aparece)
           - Detecta linha verde NO MAPA (ground truth!)
           - Aguarda movimento completar (mapa ainda aberto)
           - Calcula velocidade = distância / tempo
        4. Fecha mapa apenas no FINAL

        Esta é a CALIBRAÇÃO DEFINITIVA que replica como o mapa do Rucoy funciona!
        """
        print("=" * 70)
        print("⚙️ CALIBRADOR DE VELOCIDADE - BASEADO EM MAPA")
        print("=" * 70)
        print("\n🗺️ Este método usa o MAPA DO JOGO como ground truth")
        print("   A linha verde no mapa mostra o caminho EXATO que o personagem vai percorrer")
        print("   Medições feitas COM MAPA ABERTO para máxima precisão!\n")

        # 1. Abrir mapa UMA VEZ
        print("📖 Abrindo mapa...")
        self.gps.click_button('open')
        time.sleep(1.0)  # Aguardar mapa abrir completamente
        print("   ✅ Mapa aberto!\n")

        try:
            # 2. GPS inicial COM MAPA ABERTO
            print("📡 Obtendo posição inicial via GPS (mapa aberto)...")

            resultado = self.gps.get_current_position(keep_map_open=True, verbose=False)

            if not resultado or 'x' not in resultado:
                print("❌ GPS falhou")
                self.gps.click_button('close')
                return False

            pos_inicial_x = resultado['x']
            pos_inicial_y = resultado['y']

            # Salvar posição do jogador
            self.player_x = pos_inicial_x
            self.player_y = pos_inicial_y

            print(f"   ✅ Posição inicial: ({pos_inicial_x}, {pos_inicial_y})")
            print(f"   🗺️ Zona: {resultado.get('zone', 'Desconhecida')}\n")

            # 3. Loop de medições COM MAPA ABERTO
            print("=" * 70)
            print("🧪 TESTANDO DIFERENTES DISTÂNCIAS (MAPA ABERTO)")
            print("=" * 70)

            for distancia_tiles in self.distancias_tiles:
                medicoes_distancia = []

                for tentativa in range(3):
                    print(f"\n   📏 Distância {distancia_tiles} tiles - Tentativa {tentativa + 1}/3:")

                    # Atualizar GPS antes de cada medição
                    print("      📡 Atualizando posição GPS...")
                    resultado_gps = self.gps.get_current_position(keep_map_open=True, verbose=False)

                    if resultado_gps and 'x' in resultado_gps:
                        self.player_x = resultado_gps['x']
                        self.player_y = resultado_gps['y']
                        print(f"      ✅ Posição atual: ({self.player_x}, {self.player_y})")
                    else:
                        print("      ⚠️ GPS falhou, usando posição anterior")

                    # Gerar destino walkable válido
                    destino = self.encontrar_destino_valido(distancia_tiles)

                    if destino is None:
                        print(f"      ❌ Não encontrou destino válido")
                        continue

                    # Desempacotar: encontrar_destino_valido retorna (tela_x, tela_y, distancia_px, path)
                    destino_tela_x, destino_tela_y, distancia_estimada, path = destino

                    # Converter tela → mundo para obter coordenadas mundo
                    destino_mundo_x, destino_mundo_y = self.converter_tela_para_mundo(destino_tela_x, destino_tela_y)

                    # CONVERTER MUNDO → TELA DO MAPA
                    mapa_x, mapa_y = self.mundo_para_tela_mapa(
                        destino_mundo_x, destino_mundo_y,
                        self.player_x, self.player_y
                    )

                    print(f"      📍 Destino: mundo({destino_mundo_x:.0f}, {destino_mundo_y:.0f}) → mapa({mapa_x}, {mapa_y})")

                    # CLICAR NO MAPA (linha verde vai aparecer)
                    print(f"      🎯 Clicando no mapa...")
                    if not self.executar_tap(mapa_x, mapa_y):
                        print("      ❌ Falha ao clicar")
                        continue

                    time.sleep(0.5)  # Aguardar linha verde aparecer

                    # DETECTAR LINHA VERDE NO MAPA (GROUND TRUTH!)
                    print(f"      🟢 Detectando linha verde no mapa...")
                    img_mapa = self.capturar_tela()
                    tiles_linha_verde = self.detectar_linha_verde_no_mapa(img_mapa)

                    if tiles_linha_verde is None or tiles_linha_verde == 0:
                        print("      ⚠️ Linha verde não detectada no mapa")
                        # Usar distância estimada do A* como fallback
                        tiles_linha_verde = int(distancia_estimada / self.pixels_por_tile)
                        print(f"      📐 Usando distância A* como fallback: {tiles_linha_verde} tiles")
                    else:
                        print(f"      ✅ Linha verde detectada: {tiles_linha_verde} tiles (GROUND TRUTH!)")

                    distancia_real_px = tiles_linha_verde * self.pixels_por_tile

                    # AGUARDAR MOVIMENTO COMPLETAR (MAPA AINDA ABERTO)
                    print(f"      ⏱️ Aguardando movimento completar...")
                    tempo_inicio = time.time()

                    # Timeout baseado em distância (1 segundo por tile + margem)
                    timeout_movimento = tiles_linha_verde * 1.0 + 5.0
                    timeout_final = time.time() + timeout_movimento

                    movimento_completo = False
                    while time.time() < timeout_final:
                        # Verificar se personagem parou (pode usar GPS ou detecção visual)
                        # Por simplicidade, vamos usar tempo estimado + pequena margem
                        time.sleep(0.1)

                        # Verificar se linha verde sumiu (movimento completo)
                        img_check = self.capturar_tela()
                        tiles_check = self.detectar_linha_verde_no_mapa(img_check)

                        if tiles_check is None or tiles_check == 0:
                            tempo_fim = time.time()
                            duracao = tempo_fim - tempo_inicio
                            movimento_completo = True
                            print(f"      ✅ Movimento completo em {duracao:.3f}s")
                            break

                    if not movimento_completo:
                        # Timeout - assumir que chegou
                        tempo_fim = time.time()
                        duracao = tempo_fim - tempo_inicio
                        print(f"      ⚠️ Timeout - assumindo movimento completo em {duracao:.3f}s")

                    # CALCULAR VELOCIDADE
                    velocidade = distancia_real_px / duracao if duracao > 0 else 0

                    medicoes_distancia.append({
                        'duracao': duracao,
                        'distancia_px': distancia_real_px,
                        'tiles_ground_truth': tiles_linha_verde,
                        'velocidade': velocidade
                    })

                    print(f"      🏃 Velocidade: {velocidade:.1f} px/s")

                    # Delay entre medições
                    time.sleep(1.5)

                # Calcular média para esta distância
                if medicoes_distancia:
                    duracoes = [m['duracao'] for m in medicoes_distancia]
                    distancias = [m['distancia_px'] for m in medicoes_distancia]
                    tiles_ground_truth = [m['tiles_ground_truth'] for m in medicoes_distancia]

                    tempo_medio = sum(duracoes) / len(duracoes)
                    distancia_media = sum(distancias) / len(distancias)
                    tiles_medio = sum(tiles_ground_truth) / len(tiles_ground_truth)
                    velocidade_media = distancia_media / tempo_medio if tempo_medio > 0 else 0

                    self.medicoes.append({
                        'distancia_tiles': distancia_tiles,
                        'tiles_ground_truth_medio': tiles_medio,
                        'distancia_media_px': distancia_media,
                        'tempo_medio': tempo_medio,
                        'velocidade_px_s': velocidade_media,
                        'medicoes_individuais': medicoes_distancia
                    })

                    print(f"\n   📊 Média para {distancia_tiles} tiles:")
                    print(f"      🟢 Tiles (ground truth): {tiles_medio:.1f}")
                    print(f"      ⏱️ Tempo médio: {tempo_medio:.3f}s")
                    print(f"      📏 Distância média: {distancia_media:.1f} px")
                    print(f"      🏃 Velocidade média: {velocidade_media:.1f} px/s")

        finally:
            # 4. FECHAR MAPA (apenas no final)
            print("\n📕 Fechando mapa...")
            self.gps.click_button('close')
            time.sleep(0.5)
            print("   ✅ Mapa fechado!\n")

        # 5. Calcular velocidade global
        print("=" * 70)
        print("📊 RESULTADOS FINAIS (BASEADO EM MAPA)")
        print("=" * 70)

        if not self.medicoes:
            print("❌ Nenhuma medição bem-sucedida")
            return False

        # Média ponderada
        total_pixels = sum(m['distancia_media_px'] for m in self.medicoes)
        total_tempo = sum(m['tempo_medio'] for m in self.medicoes)

        velocidade_global = total_pixels / total_tempo if total_tempo > 0 else 0
        tempo_por_tile = self.pixels_por_tile / velocidade_global if velocidade_global > 0 else 0

        print(f"\n🏃 Velocidade média global: {velocidade_global:.1f} pixels/segundo")
        print(f"⏱️ Tempo por tile (32px): {tempo_por_tile:.3f} segundos")
        print(f"\n📋 Detalhamento por distância (com ground truth do mapa):")

        for m in self.medicoes:
            tiles_gt = m.get('tiles_ground_truth_medio', m['distancia_tiles'])
            print(f"   {m['distancia_tiles']} tiles → {tiles_gt:.1f} tiles (mapa): {m['tempo_medio']:.3f}s @ {m['velocidade_px_s']:.1f} px/s")

        # 6. Salvar configuração
        print("\n" + "=" * 70)
        print("💾 SALVANDO CONFIGURAÇÃO")
        print("=" * 70)

        Path("FARM").mkdir(exist_ok=True)

        config = {
            'velocidade_px_s': velocidade_global,
            'tempo_por_tile': tempo_por_tile,
            'pixels_por_tile': self.pixels_por_tile,
            'metodo_calibracao': 'mapa_aberto_ground_truth',
            'medicoes_detalhadas': self.medicoes,
            'data_calibracao': time.strftime('%Y-%m-%d %H:%M:%S'),
            'posicao_inicial': {
                'x': pos_inicial_x,
                'y': pos_inicial_y,
                'zone': resultado.get('zone', 'Desconhecida')
            }
        }

        output_file = 'FARM/velocidade_personagem.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"✅ Configuração salva: {output_file}")
        print(f"\n📝 Método usado: Calibração baseada em MAPA (ground truth)")
        print(f"   A linha verde do mapa forneceu a distância EXATA!")

        print("\n" + "=" * 70)
        print("✅ CALIBRAÇÃO COM MAPA CONCLUÍDA COM SUCESSO!")
        print("=" * 70)

        return True

    def medir_movimento(self, destino_x, destino_y, distancia_tiles):
        """
        Mede tempo de movimento até destino
        Retorna tempo em segundos ou None se falhou
        """
        # 1. Capturar tela antes do movimento (para confirmar que não há linha verde)
        img_antes = self.capturar_tela()
        if img_antes is None:
            print("   ❌ Falha ao capturar tela inicial")
            return None

        linha_antes = self.detectar_linha_verde(img_antes)
        if linha_antes:
            print("   ⚠️ Linha verde já presente, aguardando...")
            # Aguardar movimento anterior terminar
            timeout = time.time() + 10
            while time.time() < timeout:
                img = self.capturar_tela()
                if img is not None and not self.detectar_linha_verde(img):
                    print("   ✅ Movimento anterior finalizado")
                    break
                time.sleep(0.1)
            else:
                print("   ❌ Timeout aguardando movimento anterior")
                return None

            time.sleep(0.5)  # Delay adicional

        # 2. Executar tap
        print(f"   🎯 Executando tap...")
        if not self.executar_tap(destino_x, destino_y):
            return None

        # 3. Aguardar linha verde aparecer (início do movimento)
        tempo_inicio = None
        timeout = time.time() + 3  # 3 segundos para linha verde aparecer

        while time.time() < timeout:
            img = self.capturar_tela()
            if img is not None and self.detectar_linha_verde(img):
                tempo_inicio = time.time()
                print(f"   🟢 Linha verde detectada!")
                break
            time.sleep(0.05)  # 50ms entre verificações

        if tempo_inicio is None:
            print("   ⚠️ Linha verde não apareceu (movimento muito rápido ou destino inválido)")
            # Tentar medir mesmo assim com delay fixo
            time.sleep(0.5)
            return 0.5  # Retornar estimativa para movimentos muito curtos

        # 4. Aguardar linha verde desaparecer (fim do movimento)
        timeout = time.time() + 15  # 15 segundos max para movimento

        while time.time() < timeout:
            img = self.capturar_tela()
            if img is not None and not self.detectar_linha_verde(img):
                tempo_fim = time.time()
                duracao = tempo_fim - tempo_inicio
                print(f"   ✅ Movimento completo em {duracao:.3f}s")
                return duracao
            time.sleep(0.05)  # 50ms entre verificações

        print("   ❌ Timeout aguardando fim do movimento")
        return None

    def calibrar(self):
        """
        Executa calibração completa
        """
        print("=" * 70)
        print("⚙️ CALIBRADOR DE VELOCIDADE DO PERSONAGEM")
        print("=" * 70)

        # 1. GPS inicial
        print("\n📡 Obtendo posição inicial via GPS...")

        # Obter posição GPS
        print("   Obtendo posição GPS...")
        try:
            resultado = self.gps.get_current_position(keep_map_open=False, verbose=False)

            if not resultado or 'x' not in resultado:
                print("❌ GPS falhou")
                return False

            pos_inicial_x = resultado['x']
            pos_inicial_y = resultado['y']

            # Salvar posição do jogador para validação
            self.player_x = pos_inicial_x
            self.player_y = pos_inicial_y

            print(f"   ✅ Posição inicial: ({pos_inicial_x}, {pos_inicial_y})")
            print(f"   🗺️ Zona: {resultado.get('zone', 'Desconhecida')}")
        except Exception as e:
            print(f"❌ Erro ao obter GPS: {e}")
            return False

        # 2. Testar diferentes distâncias
        print("\n" + "=" * 70)
        print("🧪 TESTANDO DIFERENTES DISTÂNCIAS")
        print("=" * 70)

        for i, distancia_tiles in enumerate(self.distancias_tiles):
            # Fazer 3 medições para cada distância
            medicoes_distancia = []

            for tentativa in range(3):
                print(f"\n   Tentativa {tentativa + 1}/3 para {distancia_tiles} tiles:")

                # Encontrar destino válido usando A* pathfinding
                destino = self.encontrar_destino_valido(distancia_tiles)

                if destino is None:
                    print(f"      ❌ Não encontrou destino válido para {distancia_tiles} tiles")
                    continue

                # Desempacotar 4 valores: tela_x, tela_y, distancia_astar_px, path
                destino_x, destino_y, distancia_real_px, path = destino

                # Determinar tipo de movimento (cardinal vs diagonal)
                offset_x = destino_x - self.centro_x
                offset_y = destino_y - self.centro_y

                # Se só um dos offsets é zero, é movimento cardinal (reto)
                if offset_x == 0 or offset_y == 0:
                    movimento_tipo = "cardinal (→←↑↓)"
                else:
                    movimento_tipo = "diagonal (escada)"

                # Converter para mundo para mostrar no log
                mundo_x, mundo_y = self.converter_tela_para_mundo(destino_x, destino_y)
                if mundo_x is not None:
                    print(f"      📍 Destino: tela({destino_x}, {destino_y}) → mundo({mundo_x:.0f}, {mundo_y:.0f})")
                else:
                    print(f"      📍 Destino: ({destino_x}, {destino_y})")

                print(f"      🧭 Movimento: {movimento_tipo}")

                # Mostrar distância A* (caminho real) vs Manhattan (linha reta)
                if path is not None:
                    distancia_manhattan = abs(offset_x) + abs(offset_y)
                    tiles_astar = len(path)
                    diferenca_percent = ((distancia_real_px - distancia_manhattan) / distancia_manhattan * 100) if distancia_manhattan > 0 else 0

                    print(f"      📏 Distância A* (caminho real): {distancia_real_px} px ({tiles_astar} tiles)")
                    print(f"      📐 Distância Manhattan (linha reta): {distancia_manhattan} px")
                    if diferenca_percent > 5:
                        print(f"      🧮 Diferença: +{diferenca_percent:.1f}% (contornou obstáculos!)")
                else:
                    print(f"      📏 Distância: {distancia_real_px} pixels (Manhattan - sem A*)")

                duracao = self.medir_movimento(destino_x, destino_y, distancia_tiles)

                if duracao is not None:
                    # IMPORTANTE: Usar distância MANHATTAN para calcular velocidade
                    # (distância real que personagem percorre, não euclidiana)
                    velocidade = distancia_real_px / duracao if duracao > 0 else 0

                    # Guardar medição com distância real
                    medicoes_distancia.append({
                        'duracao': duracao,
                        'distancia_px': distancia_real_px,
                        'tipo_movimento': movimento_tipo
                    })

                    print(f"      ⏱️ Tempo: {duracao:.3f}s")
                    print(f"      🏃 Velocidade: {velocidade:.1f} px/s (Manhattan)")
                else:
                    print(f"      ❌ Medição falhou")

                # Delay entre medições
                time.sleep(1.5)

            # Calcular média para esta distância
            if medicoes_distancia:
                # Extrair durações e distâncias de cada medição
                duracoes = [m['duracao'] for m in medicoes_distancia]
                distancias = [m['distancia_px'] for m in medicoes_distancia]

                # Média de tempo e distância
                tempo_medio = sum(duracoes) / len(duracoes)
                distancia_media = sum(distancias) / len(distancias)

                # Velocidade média usando distância Manhattan real
                velocidade_media = distancia_media / tempo_medio if tempo_medio > 0 else 0

                # Contar tipos de movimento
                cardinais = sum(1 for m in medicoes_distancia if 'cardinal' in m['tipo_movimento'])
                diagonais = sum(1 for m in medicoes_distancia if 'diagonal' in m['tipo_movimento'])

                self.medicoes.append({
                    'distancia_tiles': distancia_tiles,
                    'distancia_media_px': distancia_media,
                    'tempo_medio': tempo_medio,
                    'velocidade_px_s': velocidade_media,
                    'medicoes_individuais': medicoes_distancia,
                    'cardinais': cardinais,
                    'diagonais': diagonais
                })

                print(f"\n   📊 Média para {distancia_tiles} tiles:")
                print(f"      ⏱️ Tempo médio: {tempo_medio:.3f}s")
                print(f"      📏 Distância média: {distancia_media:.1f} px (Manhattan)")
                print(f"      🏃 Velocidade média: {velocidade_media:.1f} px/s")
                print(f"      🧭 Movimentos: {cardinais} cardinais, {diagonais} diagonais")

        # 3. Calcular velocidade global
        print("\n" + "=" * 70)
        print("📊 RESULTADOS FINAIS")
        print("=" * 70)

        if not self.medicoes:
            print("❌ Nenhuma medição bem-sucedida")
            return False

        # Calcular média ponderada usando distâncias Manhattan reais
        total_pixels = sum(m['distancia_media_px'] for m in self.medicoes)
        total_tempo = sum(m['tempo_medio'] for m in self.medicoes)

        velocidade_global = total_pixels / total_tempo if total_tempo > 0 else 0
        tempo_por_tile = self.pixels_por_tile / velocidade_global if velocidade_global > 0 else 0

        # Estatísticas de tipo de movimento
        total_cardinais = sum(m['cardinais'] for m in self.medicoes)
        total_diagonais = sum(m['diagonais'] for m in self.medicoes)
        total_medicoes = total_cardinais + total_diagonais

        print(f"\n🏃 Velocidade média global: {velocidade_global:.1f} pixels/segundo (Manhattan)")
        print(f"⏱️ Tempo por tile (32px): {tempo_por_tile:.3f} segundos")
        print(f"🧭 Distribuição de movimentos:")
        print(f"   Cardinal (→←↑↓): {total_cardinais}/{total_medicoes} ({100*total_cardinais/total_medicoes:.0f}%)")
        print(f"   Diagonal (escada): {total_diagonais}/{total_medicoes} ({100*total_diagonais/total_medicoes:.0f}%)")
        print(f"\n📋 Detalhamento por distância:")

        for m in self.medicoes:
            print(f"   {m['distancia_tiles']} tiles ({m['distancia_media_px']:.0f}px Manhattan): {m['tempo_medio']:.3f}s @ {m['velocidade_px_s']:.1f} px/s")

        # 4. Salvar configuração
        print("\n" + "=" * 70)
        print("💾 SALVANDO CONFIGURAÇÃO")
        print("=" * 70)

        Path("FARM").mkdir(exist_ok=True)

        config = {
            'velocidade_px_s': velocidade_global,
            'tempo_por_tile': tempo_por_tile,
            'pixels_por_tile': self.pixels_por_tile,
            'medicoes_detalhadas': self.medicoes,
            'data_calibracao': time.strftime('%Y-%m-%d %H:%M:%S'),
            'posicao_inicial': {
                'x': pos_inicial_x,
                'y': pos_inicial_y,
                'zone': resultado.get('zone', 'Desconhecida')
            }
        }

        output_file = 'FARM/velocidade_personagem.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"✅ Configuração salva: {output_file}")
        print(f"\n📝 Para usar no farm bot:")
        print(f"   import json")
        print(f"   with open('{output_file}', 'r') as f:")
        print(f"       config = json.load(f)")
        print(f"   velocidade = config['velocidade_px_s']")
        print(f"   tempo_tile = config['tempo_por_tile']")

        print("\n" + "=" * 70)
        print("✅ CALIBRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 70)

        return True


if __name__ == "__main__":
    try:
        calibrador = CalibradorVelocidade()

        # Usar calibração COM MAPA ABERTO (ground truth do jogo!)
        # Este método usa a linha verde do mapa como referência exata
        sucesso = calibrador.calibrar_com_mapa_aberto()

        if not sucesso:
            print("\n❌ Calibração falhou")
            exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️ Calibração cancelada pelo usuário")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
