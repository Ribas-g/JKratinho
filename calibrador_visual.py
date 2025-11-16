"""
CALIBRADOR VISUAL DE MAPA - Ajuste fino de escala e offset

Sistema visual interativo para calibrar a sincronização perfeita entre
o jogo e o mapa virtual.

OBJETIVO:
- Replicar o mapa de Rucoy como "modo navegação"
- Sincronizar 100% movimento do jogo com o mapa virtual
- Sistema de tracking perfeito sem abrir mapa

FUNCIONAMENTO:
1. Mostra jogo (screenshot) + mapa virtual lado a lado
2. Você ajusta escala/offset até alinharem perfeitamente
3. Testa andando - se mapa seguir corretamente, salva!

CONTROLES:
  [Q/E] Escala X ±0.1
  [W/S] Escala Y ±0.1
  [A/D] Offset X ±1px
  [Z/X] Offset Y ±1px

  [+/-] Zoom in/out (mapa virtual)
  [SCROLL] Zoom in/out
  [R] Reset valores
  [G] Atualizar GPS
  [ESPAÇO] Salvar configuração
  [ESC] Sair

ZOOM:
  - Centralizado na posição do player
  - Níveis: 0.25x → 0.5x → 1x → 2x → 4x → 8x
  - Permite ver detalhes do alinhamento
"""

import cv2
import numpy as np
import sys
import os
import json
import time
from pathlib import Path
from adbutils import adb

# Adicionar path para imports
sys.path.insert(0, str(Path(__file__).parent))

from gps_ncc_realtime import GPSRealtimeNCC


class CalibradorVisual:
    """Sistema visual interativo para calibração de mapa"""

    def __init__(self):
        """Inicializa calibrador"""
        print("=" * 80)
        print("🎯 CALIBRADOR VISUAL DE MAPA")
        print("=" * 80)

        # Conectar dispositivo
        print("\n📱 Conectando ao dispositivo...")
        devices = adb.device_list()
        if not devices:
            raise Exception("❌ Nenhum dispositivo encontrado!")
        self.device = devices[0]
        print(f"   ✅ Conectado: {self.device.serial}")

        # Inicializar GPS
        print("\n📡 Inicializando GPS...")
        self.gps = GPSRealtimeNCC()

        # Carregar mapa
        print("\n🗺️ Carregando mapa...")
        self._carregar_mapa()

        # Configurações da tela do jogo
        self.tela_largura = 1600
        self.tela_altura = 900
        self.centro_x = 800
        self.centro_y = 450

        # Parâmetros ajustáveis
        self.escala_x = 25.0  # Valor inicial
        self.escala_y = 25.0
        self.offset_x = 0
        self.offset_y = 0

        # Zoom do mapa virtual
        self.zoom_level = 1.0
        self.zoom_levels = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
        self.zoom_index = 2  # Começa em 1.0x

        # Posição atual (GPS)
        self.pos_x = None
        self.pos_y = None
        self.zona = "Desconhecida"

        # FOV (Field of View)
        self.fov_largura_mundo = 64  # pixels no mapa mundo
        self.fov_altura_mundo = 36

        # Controle de atualização
        self.ultimo_screenshot = None
        self.ultimo_gps_tempo = 0
        self.gps_intervalo = 2.0  # Atualizar GPS a cada 2s

        # Tamanho das janelas
        self.janela_largura = 800
        self.janela_altura = 600

        print("\n✅ Calibrador inicializado!")
        print("\n" + "=" * 80)
        print("🎮 CONTROLES:")
        print("=" * 80)
        print("  Q/E : Ajustar Escala X")
        print("  W/S : Ajustar Escala Y")
        print("  A/D : Ajustar Offset X")
        print("  Z/X : Ajustar Offset Y")
        print("  +/- : Zoom in/out")
        print("  R   : Reset valores")
        print("  G   : Atualizar GPS")
        print("  SPC : Salvar configuração")
        print("  ESC : Sair")
        print("=" * 80)

    def _carregar_mapa(self):
        """Carrega mapa de referência"""
        mapa_path = Path(__file__).parent / 'MINIMAPA CERTOPRETO.png'

        if not mapa_path.exists():
            raise FileNotFoundError(f"Mapa não encontrado: {mapa_path}")

        self.mapa_original = cv2.imread(str(mapa_path))

        if self.mapa_original is None:
            raise ValueError("Erro ao carregar mapa!")

        self.mapa_altura, self.mapa_largura = self.mapa_original.shape[:2]

        print(f"   ✅ Mapa carregado: {self.mapa_largura}x{self.mapa_altura}px")

    def atualizar_gps(self):
        """Atualiza posição via GPS"""
        print("\n📡 Atualizando GPS...")
        resultado = self.gps.get_current_position(verbose=False)

        if resultado:
            self.pos_x = float(resultado['x'])
            self.pos_y = float(resultado['y'])
            self.zona = resultado.get('zone', 'Desconhecida')
            self.ultimo_gps_tempo = time.time()

            print(f"   ✅ Posição: ({self.pos_x:.0f}, {self.pos_y:.0f})")
            print(f"   🗺️ Zona: {self.zona}")
            return True
        else:
            print("   ❌ Falha ao obter GPS")
            return False

    def capturar_screenshot(self):
        """Captura screenshot do jogo"""
        try:
            screenshot_bytes = self.device.shell("screencap", encoding=None)

            if not screenshot_bytes or len(screenshot_bytes) < 1000:
                return None

            # Decodificar formato raw
            width = int.from_bytes(screenshot_bytes[0:4], byteorder='little')
            height = int.from_bytes(screenshot_bytes[4:8], byteorder='little')
            pixels = screenshot_bytes[12:]

            # Converter para imagem
            img_array = np.frombuffer(pixels, dtype=np.uint8)

            # Reshape
            try:
                img = img_array.reshape((height, width, 4))
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                self.ultimo_screenshot = img
                return img
            except:
                return self.ultimo_screenshot

        except Exception as e:
            print(f"   ⚠️ Erro ao capturar: {e}")
            return self.ultimo_screenshot

    def renderizar_mapa_virtual(self):
        """Renderiza mapa virtual centrado no player com zoom"""
        if self.pos_x is None or self.pos_y is None:
            # Retornar imagem preta com mensagem
            img = np.zeros((self.janela_altura, self.janela_largura, 3), dtype=np.uint8)
            cv2.putText(img, "Aguardando GPS...", (250, 300),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return img

        # Calcular FOV no mapa baseado na escala e zoom
        fov_mundo_x = (self.tela_largura / self.escala_x) * self.zoom_level
        fov_mundo_y = (self.tela_altura / self.escala_y) * self.zoom_level

        # Calcular região do mapa a extrair (centrado no player)
        x1 = int(self.pos_x + self.offset_x - fov_mundo_x / 2)
        y1 = int(self.pos_y + self.offset_y - fov_mundo_y / 2)
        x2 = int(self.pos_x + self.offset_x + fov_mundo_x / 2)
        y2 = int(self.pos_y + self.offset_y + fov_mundo_y / 2)

        # Limitar aos bounds do mapa
        x1 = max(0, min(x1, self.mapa_largura - 1))
        y1 = max(0, min(y1, self.mapa_altura - 1))
        x2 = max(0, min(x2, self.mapa_largura - 1))
        y2 = max(0, min(y2, self.mapa_altura - 1))

        # Extrair região
        if x2 > x1 and y2 > y1:
            regiao = self.mapa_original[y1:y2, x1:x2].copy()
        else:
            regiao = np.zeros((100, 100, 3), dtype=np.uint8)

        # Redimensionar para tamanho da janela
        mapa_renderizado = cv2.resize(regiao, (self.janela_largura, self.janela_altura))

        # Desenhar marcação do player (centro)
        centro_janela_x = self.janela_largura // 2
        centro_janela_y = self.janela_altura // 2

        # Cruz vermelha no player
        cv2.drawMarker(mapa_renderizado, (centro_janela_x, centro_janela_y),
                      (0, 0, 255), cv2.MARKER_CROSS, 40, 3)

        # Círculo azul ao redor
        cv2.circle(mapa_renderizado, (centro_janela_x, centro_janela_y),
                  20, (255, 0, 0), 2)

        # Desenhar FOV (campo de visão) do jogo
        fov_px_x = int((self.tela_largura / self.escala_x) * (self.janela_largura / fov_mundo_x))
        fov_px_y = int((self.tela_altura / self.escala_y) * (self.janela_altura / fov_mundo_y))

        fov_x1 = centro_janela_x - fov_px_x // 2
        fov_y1 = centro_janela_y - fov_px_y // 2
        fov_x2 = centro_janela_x + fov_px_x // 2
        fov_y2 = centro_janela_y + fov_px_y // 2

        # Retângulo verde mostrando FOV do jogo
        cv2.rectangle(mapa_renderizado, (fov_x1, fov_y1), (fov_x2, fov_y2),
                     (0, 255, 0), 2)

        # Grid de tiles (opcional, a cada 4px no mundo = 1 tile)
        if self.zoom_level >= 2.0:  # Só mostrar grid quando zoom >= 2x
            tile_size_mundo = 4  # 1 tile = 4px no mapa mundo
            tile_size_px = int(tile_size_mundo * (self.janela_largura / fov_mundo_x))

            # Linhas verticais
            for i in range(0, self.janela_largura, tile_size_px):
                cv2.line(mapa_renderizado, (i, 0), (i, self.janela_altura),
                        (100, 100, 100), 1)

            # Linhas horizontais
            for i in range(0, self.janela_altura, tile_size_px):
                cv2.line(mapa_renderizado, (0, i), (self.janela_largura, i),
                        (100, 100, 100), 1)

        return mapa_renderizado

    def adicionar_overlay_info(self, img, lado="esquerda"):
        """Adiciona overlay com informações"""
        overlay = img.copy()

        # Fundo semi-transparente
        cv2.rectangle(overlay, (10, 10), (400, 180), (0, 0, 0), -1)
        img_com_overlay = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)

        y_offset = 30

        if lado == "esquerda":
            cv2.putText(img_com_overlay, "JOGO (Screenshot)", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        else:
            cv2.putText(img_com_overlay, f"MAPA VIRTUAL (Zoom: {self.zoom_level:.2f}x)", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 25
            cv2.putText(img_com_overlay, f"Escala: X={self.escala_x:.1f}, Y={self.escala_y:.1f}", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            y_offset += 20
            cv2.putText(img_com_overlay, f"Offset: X={self.offset_x:+d}, Y={self.offset_y:+d}", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        y_offset += 25
        cv2.putText(img_com_overlay, f"Pos: ({self.pos_x:.0f}, {self.pos_y:.0f})" if self.pos_x else "GPS: aguardando...",
                   (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        y_offset += 20
        cv2.putText(img_com_overlay, f"Zona: {self.zona}", (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        return img_com_overlay

    def salvar_configuracao(self):
        """Salva configuração calibrada"""
        pasta_farm = Path(__file__).parent / 'FARM'

        # Configuração da escala
        config_escala = {
            'centro_mapa_tela': {'x': self.centro_x, 'y': self.centro_y},
            'escala': {'x': self.escala_x, 'y': self.escala_y},
            'offset': {'x': self.offset_x, 'y': self.offset_y},
            'observacoes': f'Calibrado visualmente - {time.strftime("%Y-%m-%d %H:%M:%S")}'
        }

        config_path = pasta_farm / 'map_transform_config.json'

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_escala, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Configuração salva: {config_path}")
        print(f"   Escala: X={self.escala_x:.1f}, Y={self.escala_y:.1f}")
        print(f"   Offset: X={self.offset_x:+d}, Y={self.offset_y:+d}")

    def run(self):
        """Loop principal"""
        # Obter posição inicial
        if not self.atualizar_gps():
            print("\n❌ Não foi possível obter GPS inicial!")
            return

        # Criar janela
        cv2.namedWindow('Calibrador Visual', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Calibrador Visual', 1600, 600)

        print("\n🚀 Iniciando calibrador...")
        print("   Aguardando interação...\n")

        while True:
            # Atualizar GPS periodicamente
            if time.time() - self.ultimo_gps_tempo > self.gps_intervalo:
                self.atualizar_gps()

            # Capturar screenshot do jogo
            screenshot = self.capturar_screenshot()

            if screenshot is not None:
                # Redimensionar screenshot para caber na janela
                screenshot_resized = cv2.resize(screenshot, (self.janela_largura, self.janela_altura))
                screenshot_com_info = self.adicionar_overlay_info(screenshot_resized, "esquerda")
            else:
                screenshot_com_info = np.zeros((self.janela_altura, self.janela_largura, 3), dtype=np.uint8)
                cv2.putText(screenshot_com_info, "Erro ao capturar jogo", (200, 300),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Renderizar mapa virtual
            mapa_virtual = self.renderizar_mapa_virtual()
            mapa_com_info = self.adicionar_overlay_info(mapa_virtual, "direita")

            # Combinar lado a lado
            frame_combinado = np.hstack([screenshot_com_info, mapa_com_info])

            # Mostrar
            cv2.imshow('Calibrador Visual', frame_combinado)

            # Processar teclas
            key = cv2.waitKey(50) & 0xFF

            if key == 27:  # ESC
                print("\n👋 Encerrando...")
                break

            elif key == ord('q') or key == ord('Q'):
                self.escala_x += 0.1
                print(f"   Escala X: {self.escala_x:.1f}")

            elif key == ord('e') or key == ord('E'):
                self.escala_x -= 0.1
                print(f"   Escala X: {self.escala_x:.1f}")

            elif key == ord('w') or key == ord('W'):
                self.escala_y += 0.1
                print(f"   Escala Y: {self.escala_y:.1f}")

            elif key == ord('s') or key == ord('S'):
                self.escala_y -= 0.1
                print(f"   Escala Y: {self.escala_y:.1f}")

            elif key == ord('a') or key == ord('A'):
                self.offset_x -= 1
                print(f"   Offset X: {self.offset_x:+d}")

            elif key == ord('d') or key == ord('D'):
                self.offset_x += 1
                print(f"   Offset X: {self.offset_x:+d}")

            elif key == ord('z') or key == ord('Z'):
                self.offset_y -= 1
                print(f"   Offset Y: {self.offset_y:+d}")

            elif key == ord('x') or key == ord('X'):
                self.offset_y += 1
                print(f"   Offset Y: {self.offset_y:+d}")

            elif key == ord('+') or key == ord('='):
                if self.zoom_index < len(self.zoom_levels) - 1:
                    self.zoom_index += 1
                    self.zoom_level = self.zoom_levels[self.zoom_index]
                    print(f"   Zoom: {self.zoom_level:.2f}x")

            elif key == ord('-') or key == ord('_'):
                if self.zoom_index > 0:
                    self.zoom_index -= 1
                    self.zoom_level = self.zoom_levels[self.zoom_index]
                    print(f"   Zoom: {self.zoom_level:.2f}x")

            elif key == ord('r') or key == ord('R'):
                self.escala_x = 25.0
                self.escala_y = 25.0
                self.offset_x = 0
                self.offset_y = 0
                self.zoom_index = 2
                self.zoom_level = 1.0
                print("   ↺ Valores resetados")

            elif key == ord('g') or key == ord('G'):
                self.atualizar_gps()

            elif key == ord(' '):  # ESPAÇO
                self.salvar_configuracao()

        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        calibrador = CalibradorVisual()
        calibrador.run()
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
