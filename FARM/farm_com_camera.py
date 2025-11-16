"""
FARM BOT COM CÂMERA VIRTUAL + VISUALIZADOR

Sistema de farm integrado com:
- GPS em tempo real
- Câmera virtual (FOV 64×36px, escala 25.0)
- Validação de parede ANTES de cada clique
- Visualizador ao vivo mostrando mapa + FOV + inimigos

Execute: python farm_com_camera.py
"""

import cv2
import numpy as np
import sys
import os
from pathlib import Path
import time
import math

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adbutils import adb
from ultralytics import YOLO

# Importar sistemas
from gps_ncc_realtime import GPSRealtimeNCC
from FARM.camera_virtual import CameraVirtual

# Importar adbnativeblitz (captura rápida)
try:
    from adbnativeblitz import AdbFastScreenshots
    ADBNATIVEBLITZ_DISPONIVEL = True
except ImportError:
    ADBNATIVEBLITZ_DISPONIVEL = False
    print("⚠️ adbnativeblitz não instalado. Usando screencap padrão.")


class VisualizadorFarm:
    """
    Visualizador customizado para o farm
    Mostra mapa virtual + FOV + inimigos detectados
    """

    def __init__(self, camera, mapa_path='MINIMAPA CERTOPRETO.png'):
        self.camera = camera

        # Carregar mapa mundo
        print(f"📖 Carregando mapa: {mapa_path}")
        self.mapa_original = cv2.imread(mapa_path)

        if self.mapa_original is None:
            raise FileNotFoundError(f"Mapa não encontrado: {mapa_path}")

        self.mapa_altura, self.mapa_largura = self.mapa_original.shape[:2]
        print(f"   ✅ Mapa carregado: {self.mapa_largura}x{self.mapa_altura}")

        # Configurações
        self.janela_nome = "🎮 FARM BOT - Mapa Virtual"
        self.mostrar_fov = True
        self.mostrar_inimigos = True

        # Cores
        self.cor_fov = (0, 255, 255)  # Amarelo
        self.cor_player = (255, 0, 255)  # Magenta
        self.cor_inimigo = (0, 0, 255)  # Vermelho
        self.cor_coin = (255, 255, 0)  # Amarelo

        # Inimigos atuais
        self.inimigos = []

        self.rodando = False

    def iniciar(self):
        """Inicia visualizador"""
        self.rodando = True
        cv2.namedWindow(self.janela_nome, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.janela_nome, 1400, 900)
        print("🎥 Visualizador Farm iniciado!")

    def parar(self):
        """Para visualizador"""
        self.rodando = False
        cv2.destroyWindow(self.janela_nome)

    def atualizar_inimigos(self, lista_inimigos):
        """
        Atualiza lista de inimigos

        Args:
            lista_inimigos: Lista de dicts com {'x_mundo', 'y_mundo', 'class'}
        """
        self.inimigos = lista_inimigos

    def atualizar(self):
        """Atualiza visualização"""
        if not self.rodando:
            return

        img = self.mapa_original.copy()

        # 1. Desenhar FOV (retângulo amarelo)
        if self.camera.pos_x is not None and self.mostrar_fov:
            half_w = self.camera.fov_largura_mapa / 2
            half_h = self.camera.fov_altura_mapa / 2

            x1 = int(self.camera.pos_x - half_w)
            y1 = int(self.camera.pos_y - half_h)
            x2 = int(self.camera.pos_x + half_w)
            y2 = int(self.camera.pos_y + half_h)

            cv2.rectangle(img, (x1, y1), (x2, y2), self.cor_fov, 2)

        # 2. Desenhar posição do player (círculo magenta)
        if self.camera.pos_x is not None:
            cv2.circle(
                img,
                (int(self.camera.pos_x), int(self.camera.pos_y)),
                6,
                self.cor_player,
                -1
            )

        # 3. Desenhar inimigos
        if self.mostrar_inimigos:
            for inimigo in self.inimigos:
                x = int(inimigo['x_mundo'])
                y = int(inimigo['y_mundo'])

                # Círculo do inimigo
                cor = self.cor_coin if inimigo['class'] == 'coin' else self.cor_inimigo
                cv2.circle(img, (x, y), 4, cor, -1)

                # Nome da classe
                cv2.putText(
                    img,
                    inimigo['class'],
                    (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    cor,
                    1
                )

        # 4. HUD
        self._desenhar_hud(img)

        # 5. Mostrar
        cv2.imshow(self.janela_nome, img)

        # 6. Processar teclas
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            self.parar()
        elif key == ord('f') or key == ord('F'):
            self.mostrar_fov = not self.mostrar_fov
        elif key == ord('i') or key == ord('I'):
            self.mostrar_inimigos = not self.mostrar_inimigos

    def _desenhar_hud(self, img):
        """Desenha informações"""
        y_offset = 30

        # Fundo semi-transparente
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (450, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        # Informações
        info_lines = [
            "🎮 FARM BOT - Mapa Virtual",
            f"Player: ({int(self.camera.pos_x) if self.camera.pos_x else '?'}, {int(self.camera.pos_y) if self.camera.pos_y else '?'})",
            f"FOV: {int(self.camera.fov_largura_mapa)}x{int(self.camera.fov_altura_mapa)}px",
            f"Escala: {self.camera.escala_x:.1f}",
            f"Inimigos: {len(self.inimigos)}",
            "",
            "[F] Toggle FOV  [I] Toggle Inimigos",
            "[ESC] Fechar"
        ]

        for i, line in enumerate(info_lines):
            cv2.putText(
                img,
                line,
                (20, y_offset + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )


class FarmComCamera:
    """Farm bot com câmera virtual integrada"""

    def __init__(self, model_path="rucoy_model_final.pt"):
        print("=" * 70)
        print("🤖 FARM BOT - Sistema de Câmera Virtual")
        print("=" * 70)
        print()

        # GPS e Câmera
        print("📡 Inicializando GPS...")
        self.gps = GPSRealtimeNCC()

        # Dispositivo
        devices = adb.device_list()
        if not devices:
            print("❌ Dispositivo não encontrado!")
            exit(1)
        self.device = devices[0]
        print(f"✅ Dispositivo: {self.device.serial}")
        print()

        # Câmera Virtual
        print("🎥 Inicializando Câmera Virtual...")
        self.camera = CameraVirtual(self.gps, self.device)
        print()

        # Visualizador
        print("🗺️ Inicializando Visualizador...")
        try:
            mapa_path = Path(__file__).parent.parent / 'MINIMAPA CERTOPRETO.png'
            self.visualizador = VisualizadorFarm(self.camera, str(mapa_path))
            self.visualizador.iniciar()
            print("✅ Visualizador ativo!")
        except Exception as e:
            print(f"⚠️ Visualizador desabilitado: {e}")
            self.visualizador = None
        print()

        # Modelo YOLO
        print("📦 Carregando modelo YOLO...")
        model_full_path = Path(__file__).parent / model_path
        if not model_full_path.exists():
            print(f"⚠️ Modelo não encontrado: {model_full_path}")
            print("   Farm funcionará sem detecção")
            self.model = None
        else:
            self.model = YOLO(str(model_full_path))
            print("✅ Modelo carregado!")
        print()

        # Configurações
        self.tile_size = 100  # 1 tile = 100px na tela
        self.center_x = 800
        self.center_y = 450

        # Estado do farm
        self.running = False
        self.deteccoes_atuais = []
        self.last_action = "IDLE"
        self.last_action_time = 0
        self.action_cooldown = 0.4  # 400ms entre ações

        # Rastreamento de cliques (para visualização)
        self.ultimo_clique_x = None
        self.ultimo_clique_y = None
        self.ultimo_clique_tempo = 0
        self.tempo_exibir_clique = 1.0  # Mostrar clique por 1 segundo

        # Janela de visualização do jogo (frame)
        self.mostrar_deteccoes = True

        # Medidor de FPS
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.fps_atual = 0

        # Sistema de captura (adbnativeblitz vs screencap)
        self.usar_adbnativeblitz = ADBNATIVEBLITZ_DISPONIVEL  # Usar se disponível
        self.adb_stream = None  # Stream do adbnativeblitz
        self.metodo_captura = "DESCONHECIDO"

        print("🎥 Sistema de captura:")
        if self.usar_adbnativeblitz:
            print("   ✅ ADBNATIVEBLITZ ativado (30+ FPS esperado)")
            self.metodo_captura = "ADBNATIVEBLITZ"
        else:
            print("   ⚠️ SCREENCAP RAW (10-15 FPS esperado)")
            self.metodo_captura = "SCREENCAP_RAW"
        print()

    def inicializar(self):
        """Inicializa GPS"""
        print("🚀 Inicializando sistema...")

        if not self.camera.inicializar_posicao():
            print("❌ Falha ao inicializar GPS!")
            return False

        print("✅ Sistema pronto!")
        print()
        return True

    def tela_para_mundo(self, x_tela, y_tela):
        """Converte tela → mundo"""
        return self.camera.tela_para_mundo(x_tela, y_tela)

    def validar_clique(self, x_tela, y_tela):
        """Valida se clique é seguro (não é parede)"""
        x_mundo, y_mundo = self.tela_para_mundo(x_tela, y_tela)

        if x_mundo is None:
            return False

        return self.camera.validar_posicao(x_mundo, y_mundo)

    def executar_clique_seguro(self, x_tela, y_tela, description="", ajustar_zona_morta=True):
        """
        Executa clique COM validação de parede

        Args:
            x_tela, y_tela: Coordenadas do clique
            description: Descrição da ação
            ajustar_zona_morta: Se True, ajusta cliques muito próximos do centro

        Returns:
            bool: True se clique foi executado
        """
        x_original = x_tela
        y_original = y_tela

        # Zona morta (reduzida para evitar kiting excessivo)
        if ajustar_zona_morta:
            dx = x_tela - self.center_x
            dy = y_tela - self.center_y
            dist = math.sqrt(dx**2 + dy**2)

            # ZONA MORTA REDUZIDA: 30px (era 80px)
            # Isso permite atacar mais próximo sem tanto kiting
            DEAD_ZONE = 30
            if dist < DEAD_ZONE:
                if dist > 0:
                    scale = DEAD_ZONE / dist
                    x_tela = self.center_x + int(dx * scale)
                    y_tela = self.center_y + int(dy * scale)
                else:
                    return False

        # Validar parede
        if not self.validar_clique(x_tela, y_tela):
            print(f"   🚫 PAREDE! Original: ({x_original}, {y_original}) → Ajustado: ({x_tela}, {y_tela})")
            return False

        # Executar
        try:
            self.device.shell(f"input tap {x_tela} {y_tela}")

            # Registrar clique para visualização
            self.ultimo_clique_x = x_tela
            self.ultimo_clique_y = y_tela
            self.ultimo_clique_tempo = time.time()

            if description:
                ajuste_info = ""
                if ajustar_zona_morta and (x_tela != x_original or y_tela != y_original):
                    ajuste_info = f" [Ajustado: {x_original},{y_original} → {x_tela},{y_tela}]"
                print(f"   ✅ {description} ({x_tela}, {y_tela}){ajuste_info}")
            return True
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            return False

    def capturar_frame(self):
        """
        Captura screenshot usando SCREENCAP RAW

        Usado apenas quando adbnativeblitz não está disponível
        ou como fallback.
        """
        # SCREENCAP RAW
        try:
            # screencap sem compressão PNG
            screenshot_bytes = self.device.shell("screencap", encoding=None)

            if not screenshot_bytes or len(screenshot_bytes) < 1000:
                return None

            # Decodificar formato raw do screencap
            # Formato: header (12 bytes) + pixels RGBA
            # Header: width (4 bytes), height (4 bytes), format (4 bytes)

            # Pular header (12 bytes)
            width = int.from_bytes(screenshot_bytes[0:4], byteorder='little')
            height = int.from_bytes(screenshot_bytes[4:8], byteorder='little')

            # Dados dos pixels começam no byte 12
            pixels = screenshot_bytes[12:]

            # Converter para numpy array (RGBA)
            img = np.frombuffer(pixels, dtype=np.uint8)

            # Verificar tamanho esperado
            expected_size = width * height * 4  # RGBA = 4 bytes por pixel
            if len(img) < expected_size:
                # Fallback para método antigo
                return self.capturar_frame_fallback()

            # Reshape para imagem (height, width, 4)
            img = img.reshape((height, width, 4))

            # Converter RGBA -> BGR (OpenCV usa BGR)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

            return img_bgr

        except Exception as e:
            # Se método otimizado falhar, usar fallback
            return self.capturar_frame_fallback()

    def capturar_frame_fallback(self):
        """Captura screenshot MÉTODO ANTIGO (fallback)"""
        try:
            screenshot_bytes = self.device.shell("screencap -p", encoding=None)
            nparr = np.frombuffer(screenshot_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except:
            return None

    def detectar_objetos(self, frame):
        """Detecta objetos com YOLO"""
        if self.model is None:
            return []

        try:
            results = self.model(frame, conf=0.3, verbose=False)
            deteccoes = []

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    class_name = r.names[cls]

                    deteccoes.append({
                        'class': class_name,
                        'conf': conf,
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'center': [(int(x1) + int(x2)) // 2, (int(y1) + int(y2)) // 2]
                    })

            return deteccoes
        except:
            return []

    def calcular_distancia_tiles(self, bbox):
        """
        Calcula distância em tiles do centro da tela até o objeto

        Args:
            bbox: [x1, y1, x2, y2]

        Returns:
            float: distância em tiles
        """
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        dx = center_x - self.center_x
        dy = center_y - self.center_y

        dist_px = math.sqrt(dx**2 + dy**2)
        dist_tiles = dist_px / self.tile_size

        return dist_tiles

    def desenhar_deteccoes(self, frame):
        """
        Desenha detecções YOLO no frame do jogo

        Args:
            frame: Imagem BGR do jogo

        Returns:
            frame com detecções desenhadas
        """
        if frame is None or len(self.deteccoes_atuais) == 0:
            return frame

        img = frame.copy()

        # Cores por classe
        cores = {
            'coin': (0, 255, 255),  # Amarelo
            'crab': (0, 255, 0),    # Verde
            'rat': (0, 0, 255),     # Vermelho
            'crow': (211, 0, 148),  # Roxo
            'spider': (0, 165, 255), # Laranja
        }

        for det in self.deteccoes_atuais:
            x1, y1, x2, y2 = det['bbox']
            cx, cy = det['center']
            classe = det['class']
            conf = det['conf']

            # Cor
            cor = cores.get(classe, (255, 255, 255))

            # Retângulo
            cv2.rectangle(img, (x1, y1), (x2, y2), cor, 2)

            # Label
            label = f"{classe} {conf:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (x1, y1 - h - 4), (x1 + w, y1), cor, -1)
            cv2.putText(img, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Distância
            dist_tiles = self.calcular_distancia_tiles(det['bbox'])
            cv2.putText(img, f"{dist_tiles:.1f}t", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 2)

        # Desenhar último clique (se recente)
        tempo_atual = time.time()
        if self.ultimo_clique_x is not None:
            tempo_desde_clique = tempo_atual - self.ultimo_clique_tempo
            if tempo_desde_clique < self.tempo_exibir_clique:
                # Calcular opacidade baseada no tempo (fade out)
                alpha = 1.0 - (tempo_desde_clique / self.tempo_exibir_clique)

                # Cor vibrante: Magenta brilhante
                cor_clique = (255, 0, 255)  # Magenta

                # Desenhar círculos concêntricos pulsantes
                raio_base = 40
                raio_pulso = int(raio_base * (1 + 0.3 * (tempo_desde_clique / self.tempo_exibir_clique)))

                # Círculo externo (mais transparente)
                cv2.circle(img, (self.ultimo_clique_x, self.ultimo_clique_y), raio_pulso, cor_clique, 3)

                # Círculo médio
                cv2.circle(img, (self.ultimo_clique_x, self.ultimo_clique_y), int(raio_pulso * 0.6), cor_clique, 2)

                # Círculo interno (sólido)
                cv2.circle(img, (self.ultimo_clique_x, self.ultimo_clique_y), 8, cor_clique, -1)

                # Cruz de mira
                tam_cruz = 25
                cv2.line(img,
                        (self.ultimo_clique_x - tam_cruz, self.ultimo_clique_y),
                        (self.ultimo_clique_x + tam_cruz, self.ultimo_clique_y),
                        cor_clique, 3)
                cv2.line(img,
                        (self.ultimo_clique_x, self.ultimo_clique_y - tam_cruz),
                        (self.ultimo_clique_x, self.ultimo_clique_y + tam_cruz),
                        cor_clique, 3)

                # Texto "CLIQUE!"
                cv2.putText(img, ">>> CLIQUE <<<",
                           (self.ultimo_clique_x - 80, self.ultimo_clique_y - raio_pulso - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_clique, 2)

        # Desenhar zona morta (área mínima de clique)
        cv2.circle(img, (self.center_x, self.center_y), 30, (128, 128, 128), 1)  # Cinza
        cv2.putText(img, "DEAD ZONE", (self.center_x - 45, self.center_y + 45),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)

        # HUD
        cv2.putText(img, f"FPS: {self.fps_atual:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(img, f"Captura: {self.metodo_captura}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(img, f"Deteccoes: {len(self.deteccoes_atuais)}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img, f"Ultima acao: {self.last_action}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return img

    def atualizar_visualizador(self, frame=None):
        """Atualiza visualizador com detecções"""
        # 1. Atualizar mapa virtual
        if self.visualizador and self.visualizador.rodando:
            # Converter detecções para coordenadas mundo
            inimigos_mundo = []

            for det in self.deteccoes_atuais:
                x_tela, y_tela = det['center']
                x_mundo, y_mundo = self.tela_para_mundo(x_tela, y_tela)

                if x_mundo is not None:
                    inimigos_mundo.append({
                        'x_mundo': x_mundo,
                        'y_mundo': y_mundo,
                        'class': det['class']
                    })

            # Atualizar
            self.visualizador.atualizar_inimigos(inimigos_mundo)
            self.visualizador.atualizar()

        # 2. Mostrar tela do jogo com detecções
        if frame is not None and self.mostrar_deteccoes:
            img_deteccoes = self.desenhar_deteccoes(frame)

            # Redimensionar para caber na tela
            h, w = img_deteccoes.shape[:2]
            scale = 0.8  # 80% do tamanho
            new_w = int(w * scale)
            new_h = int(h * scale)
            img_resized = cv2.resize(img_deteccoes, (new_w, new_h))

            cv2.imshow("🎮 Farm Bot - Deteccoes YOLO", img_resized)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('d') or key == ord('D'):
                self.mostrar_deteccoes = not self.mostrar_deteccoes
                if not self.mostrar_deteccoes:
                    cv2.destroyWindow("🎮 Farm Bot - Deteccoes YOLO")

    def processar_farm(self):
        """
        Lógica principal de farm (MELHORADA - menos kiting):
        1. Coletar coins primeiro (prioridade)
        2. Atacar mobs mais próximos (SEM kiting excessivo)
        3. Validar cada clique (parede)
        4. Respeitar cooldown
        """
        # Verificar cooldown
        tempo_atual = time.time()
        if (tempo_atual - self.last_action_time) < self.action_cooldown:
            return  # Ainda em cooldown

        # Separar detecções
        coins = [d for d in self.deteccoes_atuais if d['class'] == 'coin']
        mobs = [d for d in self.deteccoes_atuais if d['class'] != 'coin']

        # PRIORIDADE 1: Coletar coins
        if len(coins) > 0:
            # Pegar coin mais próximo
            coin_mais_proximo = min(coins, key=lambda c: self.calcular_distancia_tiles(c['bbox']))
            dist_tiles = self.calcular_distancia_tiles(coin_mais_proximo['bbox'])

            # Se coin está perto (< 5 tiles), coletar
            if dist_tiles < 5.0:
                x, y = coin_mais_proximo['center']

                # Coins não precisam de zona morta (queremos clicar direto)
                if self.executar_clique_seguro(x, y, f"💰 Coin ({dist_tiles:.1f}t)", ajustar_zona_morta=False):
                    self.last_action_time = tempo_atual
                    self.last_action = "COIN"
                return  # Não atacar se coletou coin

        # PRIORIDADE 2: Atacar mobs
        if len(mobs) > 0:
            # Pegar mob mais próximo
            mob_mais_proximo = min(mobs, key=lambda m: self.calcular_distancia_tiles(m['bbox']))
            dist_tiles = self.calcular_distancia_tiles(mob_mais_proximo['bbox'])

            # ALCANCE AUMENTADO: 1-6 tiles (era 0-5)
            # Isso permite atacar de longe sem precisar se aproximar tanto
            if 1.0 < dist_tiles < 6.5:
                x, y = mob_mais_proximo['center']
                mob_class = mob_mais_proximo['class']

                # Se mob está MUITO perto (< 1 tile), NÃO atacar direto no mob
                # Isso evita clicar em cima e bugar
                if dist_tiles < 1.0:
                    # Não fazer nada se mob está muito perto
                    # Deixar ele atacar por auto-attack
                    self.last_action = "AUTO_ATTACK"
                    return

                # Atacar SEM ajuste de zona morta se dist > 2 tiles
                # Isso reduz kiting desnecessário
                ajustar = dist_tiles < 2.0

                if self.executar_clique_seguro(x, y, f"⚔️ {mob_class} ({dist_tiles:.1f}t)", ajustar_zona_morta=ajustar):
                    self.last_action_time = tempo_atual
                    self.last_action = f"ATTACK_{mob_class}"
                return

        # Nenhuma ação executada
        if (tempo_atual - self.last_action_time) > 2.0:  # Log a cada 2s
            self.last_action = "IDLE"
            self.last_action_time = tempo_atual

    def _loop_principal_screencap(self):
        """Loop principal usando screencap raw"""
        while self.running:
            try:
                # Capturar frame
                frame = self.capturar_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                # Calcular FPS
                self.fps_counter += 1
                tempo_decorrido = time.time() - self.fps_start_time
                if tempo_decorrido >= 1.0:  # Atualizar FPS a cada 1 segundo
                    self.fps_atual = self.fps_counter / tempo_decorrido
                    self.fps_counter = 0
                    self.fps_start_time = time.time()

                # Detectar objetos
                self.deteccoes_atuais = self.detectar_objetos(frame)

                # 🎯 LÓGICA DE FARM
                self.processar_farm()

                # Atualizar visualizadores (mapa + tela do jogo)
                self.atualizar_visualizador(frame)

                # Aguardar (reduzido para aproveitar FPS maior)
                time.sleep(0.05)  # 50ms = ~20 FPS teórico máximo

                # Verificar se visualizador fechou
                if self.visualizador and not self.visualizador.rodando:
                    self.running = False

            except KeyboardInterrupt:
                print("\n\n⚠️ Interrompido")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Erro: {e}")
                time.sleep(1)

    def _loop_principal_adbnativeblitz(self):
        """Loop principal usando adbnativeblitz (com context manager)"""
        import shutil
        adb_path = shutil.which("adb")
        if adb_path is None:
            # Tentar caminho padrão Windows
            import os
            possible_paths = [
                r"C:\Android\android-sdk\platform-tools\adb.exe",
                r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe",
                r"C:\Users\{}\AppData\Local\Android\Sdk\platform-tools\adb.exe".format(os.getenv('USERNAME', 'user')),
                "adb"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    adb_path = path
                    break
            if adb_path is None:
                adb_path = "adb"

        print(f"   🔧 ADB path: {adb_path}")
        print(f"   📱 Device: {self.device.serial}")
        print("   🎬 Iniciando stream H.264...")

        try:
            # USAR WITH STATEMENT CORRETAMENTE
            with AdbFastScreenshots(
                adb_path=adb_path,
                device_serial=self.device.serial,
                time_interval=179,
                width=1600,
                height=900,
                bitrate="20M",
                use_busybox=False,
                connect_to_device=True,
                screenshotbuffer=10,
                go_idle=0.001
            ) as adb_stream:
                print("   ✅ Stream ativo!")

                # Loop dentro do context manager
                for frame in adb_stream:
                    if frame is None:
                        continue

                    if not self.running:
                        break

                    # Calcular FPS
                    self.fps_counter += 1
                    tempo_decorrido = time.time() - self.fps_start_time
                    if tempo_decorrido >= 1.0:
                        self.fps_atual = self.fps_counter / tempo_decorrido
                        self.fps_counter = 0
                        self.fps_start_time = time.time()

                    # Detectar objetos
                    self.deteccoes_atuais = self.detectar_objetos(frame)

                    # 🎯 LÓGICA DE FARM
                    self.processar_farm()

                    # Atualizar visualizadores
                    self.atualizar_visualizador(frame)

                    # Aguardar
                    time.sleep(0.001)  # Mínimo, deixar stream controlar velocidade

                    # Verificar se visualizador fechou
                    if self.visualizador and not self.visualizador.rodando:
                        self.running = False
                        break

        except KeyboardInterrupt:
            print("\n\n⚠️ Interrompido")
            self.running = False
        except Exception as e:
            print(f"\n❌ Erro no stream adbnativeblitz: {e}")
            print(f"   Tipo: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise

    def run(self):
        """Loop principal"""
        if not self.inicializar():
            return

        print("\n" + "=" * 70)
        print("🎮 FARM BOT ATIVO!")
        print("=" * 70)
        print("Controles:")
        print("  ESC - Fechar visualizador (para farm)")
        print("  Ctrl+C - Parar farm")
        print("=" * 70)
        print()

        self.running = True

        # Escolher loop baseado no método de captura
        if self.usar_adbnativeblitz and ADBNATIVEBLITZ_DISPONIVEL:
            print("🚀 Usando ADBNATIVEBLITZ (H.264 stream)...")
            try:
                self._loop_principal_adbnativeblitz()
            except Exception as e:
                print(f"\n⚠️ adbnativeblitz falhou: {e}")
                print("   ↪️ Voltando para screencap raw...")
                self.usar_adbnativeblitz = False
                self.metodo_captura = "SCREENCAP_RAW"
                self.running = True
                self._loop_principal_screencap()
        else:
            print("🔧 Usando SCREENCAP RAW...")
            self._loop_principal_screencap()

        print("\n✅ Farm finalizado!")


if __name__ == "__main__":
    bot = FarmComCamera()
    bot.run()
