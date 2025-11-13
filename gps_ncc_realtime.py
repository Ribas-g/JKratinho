"""
SISTEMA GPS REALTIME COM NCC (NORMALIZED CROSS-CORRELATION)

Integração completa com o jogo:
1. Conecta no BlueStacks via ADB
2. Abre o mapa in-game
3. Captura screenshot
4. Processa com levels
5. Usa NCC (escala 0.2x) para achar posição
6. Retorna (x, y, zona)
7. Fecha o mapa

USO:
    gps = GPSRealtimeNCC()
    posicao = gps.get_current_position()
    print(f"Você está em: {posicao}")
"""

import cv2
import numpy as np
from skimage.feature import match_template
from skimage import img_as_float
from adbutils import adb
import json
import time
import os


# Tabela de cores das zonas
ZONAS_CORES = {
    (0xf4, 0xe1, 0xae): "Praia",
    (0x48, 0x98, 0x48): "Pré-Praia",
    (0x12, 0x2b, 0x12): "Vila Inicial",
    (0x8f, 0xcc, 0x8f): "Floresta dos Corvos",
    (0xe9, 0xbf, 0x99): "Deserto",
    (0x34, 0x5e, 0x35): "Labirinto dos Assassinos",
    (0x64, 0x62, 0x2b): "Área dos Zumbis",
    (0x93, 0x8f, 0x5c): "Covil dos Esqueletos",
    (0x43, 0x3d, 0x29): "Território dos Elfos",
    (0x36, 0x75, 0x35): "Zona dos Lagartos",
    (0xb8, 0x6f, 0x27): "Área Indefinida",
    (0x30, 0xd8, 0x30): "Área dos Goblins",
}


class GPSRealtimeNCC:
    """Sistema GPS em tempo real usando NCC (Template Matching)"""

    def __init__(self):
        """Inicializa GPS: carrega mapas, conecta ADB, carrega configs"""
        print("🚀 Inicializando GPS Realtime...")

        # Diretório do script
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # 1. Conectar ADB
        self.connect_device()

        # 2. Carregar configurações
        self.load_configurations()

        # 3. Carregar mapas de referência
        self.load_maps()

        print("✅ GPS Realtime inicializado com sucesso!\n")

    def connect_device(self):
        """Conecta ao dispositivo ADB (BlueStacks)"""
        print("   📱 Conectando ao BlueStacks...")
        devices = adb.device_list()
        if not devices:
            raise Exception("❌ Nenhum dispositivo encontrado! Abra o BlueStacks.")
        self.device = devices[0]
        print(f"   ✅ Conectado: {self.device.serial}")

    def load_configurations(self):
        """Carrega configurações JSON"""
        print("   📋 Carregando configurações...")

        map_calib_path = os.path.join(self.script_dir, 'map_calibration.json')
        levels_config_path = os.path.join(self.script_dir, 'levels_config.json')

        with open(map_calib_path, 'r') as f:
            self.map_calib = json.load(f)
        with open(levels_config_path, 'r') as f:
            self.levels = json.load(f)

        print(f"   ✅ Configurações carregadas")

    def load_maps(self):
        """Carrega mapas de referência (P&B e colorido)"""
        print("   🗺️ Carregando mapas de referência...")

        # Mapa P&B (para matching)
        mapa_pb_path = os.path.join(self.script_dir, 'MAPA PRETO E BRANCO.png')
        self.mapa_pb = cv2.imread(mapa_pb_path, cv2.IMREAD_GRAYSCALE)
        if self.mapa_pb is None:
            raise Exception(f"❌ MAPA PRETO E BRANCO.png não encontrado!")

        self.mapa_pb_float = img_as_float(self.mapa_pb)

        # Mapa colorido (para zona)
        mapa_colorido_path = os.path.join(self.script_dir, 'MINIMAPA CERTOPRETO.png')
        self.mapa_colorido = cv2.imread(mapa_colorido_path)
        if self.mapa_colorido is None:
            print("   ⚠️ MINIMAPA CERTOPRETO.png não encontrado (zona desabilitada)")
            self.mapa_colorido = None

        print(f"   ✅ Mapa P&B: {self.mapa_pb.shape[1]}x{self.mapa_pb.shape[0]} pixels")
        if self.mapa_colorido is not None:
            print(f"   ✅ Mapa colorido: {self.mapa_colorido.shape[1]}x{self.mapa_colorido.shape[0]} pixels")

    def capture_screen(self):
        """Captura screenshot do BlueStacks via ADB"""
        screenshot_bytes = self.device.shell("screencap -p", encoding=None)
        nparr = np.frombuffer(screenshot_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def click_button(self, button_type):
        """Clica em um botão (open_map ou close_map)"""
        if button_type == 'open':
            x = self.map_calib['buttons']['open_map']['x']
            y = self.map_calib['buttons']['open_map']['y']
        else:
            x = self.map_calib['buttons']['close_map']['x']
            y = self.map_calib['buttons']['close_map']['y']

        self.device.shell(f"input tap {x} {y}")

    def apply_levels(self, img):
        """Aplica levels (ajuste de contraste) na imagem"""
        input_min = self.levels['input_min']
        input_max = self.levels['input_max']
        output_min = self.levels['output_min']
        output_max = self.levels['output_max']

        channels = cv2.split(img)
        processed_channels = []

        for channel in channels:
            channel_float = channel.astype(np.float32) / 255.0
            channel_clipped = np.clip(channel_float, input_min, input_max)

            if (input_max - input_min) > 0:
                channel_normalized = (channel_clipped - input_min) / (input_max - input_min)
            else:
                channel_normalized = channel_clipped

            channel_normalized[channel_float > input_max] = 1.0
            channel_normalized[channel_float < input_min] = 0.0
            channel_output = channel_normalized * (output_max - output_min) + output_min
            channel_result = (channel_output * 255).astype(np.uint8)
            processed_channels.append(channel_result)

        return cv2.merge(processed_channels)

    def extract_map_region(self, screenshot):
        """Extrai região do mapa do screenshot"""
        # Verificar formato do map_calibration.json
        if 'x1' in self.map_calib['map_region']:
            # Formato antigo: x1, y1, x2, y2
            x1 = self.map_calib['map_region']['x1']
            y1 = self.map_calib['map_region']['y1']
            x2 = self.map_calib['map_region']['x2']
            y2 = self.map_calib['map_region']['y2']
        else:
            # Formato novo: x, y, width, height
            x = self.map_calib['map_region']['x']
            y = self.map_calib['map_region']['y']
            width = self.map_calib['map_region']['width']
            height = self.map_calib['map_region']['height']

            x1 = x
            y1 = y
            x2 = x + width
            y2 = y + height

        map_region = screenshot[y1:y2, x1:x2]
        return map_region

    def detect_player(self, processed_map):
        """Detecta posição do player (ponto ciano/azul) na imagem capturada"""
        hsv = cv2.cvtColor(processed_map, cv2.COLOR_BGR2HSV)
        lower_cyan = np.array([80, 100, 100])
        upper_cyan = np.array([100, 255, 255])
        cyan_mask = cv2.inRange(hsv, lower_cyan, upper_cyan)

        contours, _ = cv2.findContours(cyan_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return (cx, cy)

        # Se não detectar, assume centro
        h, w = processed_map.shape[:2]
        return (w // 2, h // 2)

    def find_closest_zone(self, color_rgb):
        """Acha zona mais próxima baseada na cor"""
        min_dist = float('inf')
        closest_zone = "Desconhecida"

        for zone_color, zone_name in ZONAS_CORES.items():
            dist = np.sqrt(sum((int(a) - int(b)) ** 2 for a, b in zip(color_rgb, zone_color)))
            if dist < min_dist:
                min_dist = dist
                closest_zone = zone_name

        return closest_zone, min_dist

    def find_position_ncc(self, captured_map_gray, player_local_x, player_local_y, verbose=False):
        """
        Usa NCC (Template Matching) para achar posição no mapa mundo

        Args:
            captured_map_gray: Mapa capturado em escala de cinza
            player_local_x: Posição X do player na captura
            player_local_y: Posição Y do player na captura
            verbose: Se True, mostra detalhes

        Returns:
            (x, y, confidence, debug_info): Posição no mapa mundo + confiança + info debug
        """
        if verbose:
            print("   🔍 Executando NCC (Template Matching)...")

        # Escala fixa (já sabemos que 0.2x funciona perfeitamente!)
        escala = 0.2

        # Redimensionar captura
        h_original, w_original = captured_map_gray.shape
        nova_w = int(w_original * escala)
        nova_h = int(h_original * escala)

        # Resize
        peca_resized = cv2.resize(captured_map_gray, (nova_w, nova_h), interpolation=cv2.INTER_AREA)
        peca_resized_float = img_as_float(peca_resized)

        # NCC (Template Matching)
        result = match_template(
            self.mapa_pb_float,
            peca_resized_float,
            pad_input=True
        )

        # Melhor match
        max_correlation = np.max(result)
        ij = np.unravel_index(np.argmax(result), result.shape)
        y_match, x_match = ij

        # Ajustar pelo tamanho da peça (match_template retorna centro)
        h_peca, w_peca = peca_resized.shape
        x_match_adjusted = x_match - w_peca // 2
        y_match_adjusted = y_match - h_peca // 2

        # Erro
        error = 1.0 - max_correlation

        if verbose:
            print(f"   📏 Escala: {escala:.3f}x ({nova_w}x{nova_h})")
            print(f"   📊 Erro: {error:.4f}, Correlação: {max_correlation:.4f}")

        # Calcular posição do player no mapa mundo
        player_x_local_scaled = player_local_x * escala
        player_y_local_scaled = player_local_y * escala

        player_x_global = x_match_adjusted + player_x_local_scaled
        player_y_global = y_match_adjusted + player_y_local_scaled

        # Confiança
        if error < 0.1:
            confidence = 95
        elif error < 0.2:
            confidence = 85
        elif error < 0.3:
            confidence = 70
        else:
            confidence = max(50, 100 - int(error * 100))

        # Info para debug
        debug_info = {
            'escala': escala,
            'error': error,
            'correlation': max_correlation,
            'shift': (x_match_adjusted, y_match_adjusted),
            'peca_resized': peca_resized,
            'peca_size': (nova_w, nova_h)
        }

        return (int(round(player_x_global)), int(round(player_y_global)), confidence, debug_info)

    def create_debug_images(self, player_x, player_y, captured_gray, player_local_x, player_local_y, debug_info, zone, confidence):
        """Cria imagens de debug mostrando o matching"""
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        # Extrair info
        shift_x, shift_y = debug_info['shift']
        peca_w, peca_h = debug_info['peca_size']
        escala = debug_info['escala']

        # Criar visualização com 3 painéis
        fig, axes = plt.subplots(1, 3, figsize=(20, 7))

        # Painel 1: Captura com player
        axes[0].imshow(captured_gray, cmap='gray')
        axes[0].plot(player_local_x, player_local_y, 'r*', markersize=20)
        axes[0].set_title(f'Captura\nPlayer: ({player_local_x}, {player_local_y})', fontsize=12)
        axes[0].axis('off')

        # Painel 2: Mapa mundo com posição
        axes[1].imshow(self.mapa_pb, cmap='gray')
        axes[1].plot(player_x, player_y, 'r*', markersize=15, label='Player')

        # Desenhar retângulo onde a peça encaixou
        rect = Rectangle((shift_x, shift_y), peca_w, peca_h,
                         linewidth=2, edgecolor='lime', facecolor='none', label='Área capturada')
        axes[1].add_patch(rect)

        axes[1].set_title(f'Mapa Mundo\nPlayer: ({player_x}, {player_y})', fontsize=12)
        axes[1].legend()
        axes[1].axis('off')

        # Painel 3: Zoom da região
        margin = 150
        y1 = max(0, player_y - margin)
        y2 = min(self.mapa_pb.shape[0], player_y + margin)
        x1 = max(0, player_x - margin)
        x2 = min(self.mapa_pb.shape[1], player_x + margin)

        zoom_region = self.mapa_pb[y1:y2, x1:x2]
        axes[2].imshow(zoom_region, cmap='gray')
        axes[2].plot(player_x - x1, player_y - y1, 'r*', markersize=20)
        axes[2].set_title(f'Zoom\nErro: {debug_info["error"]:.4f}', fontsize=12)
        axes[2].axis('off')

        plt.suptitle(f'GPS Realtime - Escala: {escala:.3f}x | Confiança: {confidence}% | Zona: {zone}',
                     fontsize=14, fontweight='bold')
        plt.tight_layout()

        # Timestamp para nome único
        timestamp = int(time.time())
        filename = f'gps_debug_{timestamp}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"   ✅ Debug salvo: {filename}")
        plt.close()

        # Também salvar mapa com marcação (alta resolução)
        mapa_visual = cv2.cvtColor(self.mapa_pb.copy(), cv2.COLOR_GRAY2BGR)

        # Desenhar retângulo
        cv2.rectangle(mapa_visual, (shift_x, shift_y), (shift_x + peca_w, shift_y + peca_h), (0, 255, 0), 2)

        # Desenhar player
        cv2.circle(mapa_visual, (player_x, player_y), 8, (0, 0, 255), -1)
        cv2.circle(mapa_visual, (player_x, player_y), 15, (0, 0, 255), 2)

        # Label
        cv2.putText(mapa_visual, f"({player_x}, {player_y}) - {zone}",
                    (player_x + 20, player_y - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        filename_map = f'gps_mapa_{timestamp}.png'
        cv2.imwrite(filename_map, mapa_visual)
        print(f"   ✅ Mapa salvo: {filename_map}")

    def get_current_position(self, keep_map_open=False, verbose=True, map_already_open=False):
        """
        FUNÇÃO PRINCIPAL: Obtém posição atual do player

        Args:
            keep_map_open: Se True, mantém mapa aberto após captura
            verbose: Se True, mostra detalhes no console
            map_already_open: Se True, não abre o mapa (assume que já está aberto)

        Returns:
            dict com:
                - x: coordenada X
                - y: coordenada Y
                - zone: nome da zona
                - confidence: confiança (0-100)
        """
        if verbose:
            print("=" * 60)
            print("📍 OBTENDO POSIÇÃO GPS...")
            print("=" * 60)

        # 1. Abrir mapa (só se não estiver aberto)
        if not map_already_open:
            if verbose:
                print("\n1️⃣ Abrindo mapa in-game...")
            self.click_button('open')
            time.sleep(0.3)  # Aguardar animação (otimizado)
        else:
            if verbose:
                print("\n1️⃣ Mapa já está aberto, pulando...")

        # 2. Capturar screenshot
        if verbose:
            print("2️⃣ Capturando screenshot...")
        screenshot = self.capture_screen()

        # 3. Extrair região do mapa
        if verbose:
            print("3️⃣ Extraindo região do mapa...")
        map_region = self.extract_map_region(screenshot)

        # 4. Aplicar levels
        if verbose:
            print("4️⃣ Aplicando processamento (levels)...")
        processed = self.apply_levels(map_region)

        # 5. Converter para P&B
        processed_gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

        # 6. Detectar player
        if verbose:
            print("5️⃣ Detectando posição do player na captura...")
        player_x_local, player_y_local = self.detect_player(processed)
        if verbose:
            print(f"   🎯 Player local: ({player_x_local}, {player_y_local})")

        # 7. NCC - Achar posição no mapa mundo
        if verbose:
            print("6️⃣ Localizando no mapa mundo (NCC)...")
        x, y, confidence, debug_info = self.find_position_ncc(processed_gray, player_x_local, player_y_local, verbose=verbose)

        # 8. Identificar zona
        zone = "Desconhecida"
        if self.mapa_colorido is not None:
            if 0 <= y < self.mapa_colorido.shape[0] and 0 <= x < self.mapa_colorido.shape[1]:
                cor_bgr = self.mapa_colorido[y, x]
                cor_rgb = (int(cor_bgr[2]), int(cor_bgr[1]), int(cor_bgr[0]))
                zone, dist = self.find_closest_zone(cor_rgb)

        # 9. Gerar imagens de debug
        if verbose:
            print("7️⃣ Gerando imagens de debug...")
            self.create_debug_images(x, y, processed_gray, player_x_local, player_y_local, debug_info, zone, confidence)

        # 10. Fechar mapa (se solicitado)
        if not keep_map_open:
            if verbose:
                print("8️⃣ Fechando mapa...")
            self.click_button('close')
            time.sleep(0.4)  # Aumentado para garantir que mapa fechou completamente antes do próximo clique

        # Resultado
        resultado = {
            'x': x,
            'y': y,
            'zone': zone,
            'confidence': confidence
        }

        if verbose:
            print("\n" + "=" * 60)
            print("🎯 POSIÇÃO ATUAL")
            print("=" * 60)
            print(f"📍 Coordenadas: ({x}, {y})")
            print(f"🗺️ Zona: {zone}")
            print(f"📊 Confiança: {confidence}%")
            print("=" * 60 + "\n")

        return resultado


def test_gps_realtime():
    """Teste: Captura posição 5 vezes em intervalos"""
    print("\n🧪 TESTE: GPS REALTIME EM MÚLTIPLAS POSIÇÕES\n")

    # Inicializar GPS
    gps = GPSRealtimeNCC()

    # Loop de teste
    for i in range(5):
        print(f"\n{'='*60}")
        print(f"CAPTURA #{i+1}/5")
        print(f"{'='*60}")

        input("⏸️ Mova o personagem para uma posição diferente e pressione ENTER...")

        # Capturar posição
        pos = gps.get_current_position(verbose=True)

        print(f"✅ Captura #{i+1} concluída: ({pos['x']}, {pos['y']}) - {pos['zone']}")

        time.sleep(1)

    print("\n✅ Teste concluído! GPS funcionando em tempo real! 🎉")


if __name__ == "__main__":
    test_gps_realtime()
