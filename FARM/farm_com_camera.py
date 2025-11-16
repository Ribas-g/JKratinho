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

        # Janela de visualização do jogo (frame)
        self.mostrar_deteccoes = True

    def inicializar(self):
        """Inicializa GPS"""
        print("🚀 Inicializando sistema...")

        if not self.camera.inicializar_posicao():
            print("❌ Falha ao inicializar GPS!")
            return False

        print("✅ Sistema pronto!")
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

    def executar_clique_seguro(self, x_tela, y_tela, description=""):
        """Executa clique COM validação de parede"""
        # Zona morta
        dx = x_tela - self.center_x
        dy = y_tela - self.center_y
        dist = math.sqrt(dx**2 + dy**2)

        DEAD_ZONE = 80
        if dist < DEAD_ZONE:
            if dist > 0:
                scale = DEAD_ZONE / dist
                x_tela = self.center_x + int(dx * scale)
                y_tela = self.center_y + int(dy * scale)
            else:
                return False

        # Validar parede
        if not self.validar_clique(x_tela, y_tela):
            print(f"   🚫 PAREDE! ({x_tela}, {y_tela})")
            return False

        # Executar
        try:
            self.device.shell(f"input tap {x_tela} {y_tela}")
            if description:
                print(f"   ✅ {description} ({x_tela}, {y_tela})")
            return True
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            return False

    def capturar_frame(self):
        """Captura screenshot"""
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

        # HUD
        cv2.putText(img, f"Deteccoes: {len(self.deteccoes_atuais)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img, f"Ultima acao: {self.last_action}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

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
        Lógica principal de farm:
        1. Coletar coins primeiro (prioridade)
        2. Atacar mobs mais próximos
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

            # Se coin está perto (< 4 tiles), coletar
            if dist_tiles < 4.0:
                x, y = coin_mais_proximo['center']

                if self.executar_clique_seguro(x, y, f"💰 Coin ({dist_tiles:.1f}t)"):
                    self.last_action_time = tempo_atual
                    self.last_action = "COIN"
                return  # Não atacar se coletou coin

        # PRIORIDADE 2: Atacar mobs
        if len(mobs) > 0:
            # Pegar mob mais próximo
            mob_mais_proximo = min(mobs, key=lambda m: self.calcular_distancia_tiles(m['bbox']))
            dist_tiles = self.calcular_distancia_tiles(mob_mais_proximo['bbox'])

            # Se mob está no alcance (< 5 tiles), atacar
            if dist_tiles < 5.0:
                x, y = mob_mais_proximo['center']
                mob_class = mob_mais_proximo['class']

                if self.executar_clique_seguro(x, y, f"⚔️ {mob_class} ({dist_tiles:.1f}t)"):
                    self.last_action_time = tempo_atual
                    self.last_action = f"ATTACK_{mob_class}"
                return

        # Nenhuma ação executada
        if (tempo_atual - self.last_action_time) > 2.0:  # Log a cada 2s
            # print("   💤 Aguardando targets...")
            self.last_action_time = tempo_atual

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

        while self.running:
            try:
                # Capturar frame
                frame = self.capturar_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                # Detectar objetos
                self.deteccoes_atuais = self.detectar_objetos(frame)

                # 🎯 LÓGICA DE FARM
                self.processar_farm()

                # Atualizar visualizadores (mapa + tela do jogo)
                self.atualizar_visualizador(frame)

                # Aguardar
                time.sleep(0.15)

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

        print("\n✅ Farm finalizado!")


if __name__ == "__main__":
    bot = FarmComCamera()
    bot.run()
