"""
CÂMERA VIRTUAL - Navegação sem abrir o mapa!

Este sistema simula o minimapa do jogo como uma "câmera top-view" virtual.
A câmera segue o personagem e converte coordenadas mundo → tela do jogo.

IDEIA:
- Pegar GPS UMA vez no início
- Simular posição do personagem virtualmente
- Quando quiser ir para um ponto, calcular onde esse ponto apareceria NA TELA DO JOGO
- Clicar direto no chão (sem abrir mapa!)
- GPS periódico só para correção de erros

VANTAGENS:
- ⚡ MUITO mais rápido (sem abrir/fechar mapa)
- 🎯 Cliques diretos no chão do jogo
- 🗺️ Navegação fluida

LIMITES:
- Campo de visão limitado (~6 tiles ou 192 pixels do centro)
- Precisa GPS periódico para evitar erro acumulado
"""

import cv2
import numpy as np
import time
import json
from pathlib import Path


class CameraVirtual:
    """
    Simula o minimapa como uma câmera virtual que segue o personagem
    """

    def __init__(self, gps, device):
        """
        Inicializa câmera virtual

        Args:
            gps: GPSRealtimeNCC instance
            device: ADB device
        """
        self.gps = gps
        self.device = device

        # Configurações da tela do jogo
        self.tela_largura = 1600
        self.tela_altura = 900
        self.centro_x = 800  # Personagem sempre no centro
        self.centro_y = 450

        # Escalas (pixels por tile)
        self.pixels_por_tile_mundo = 32  # No mundo (coordenadas absolutas)
        self.pixels_por_tile_tela = 32   # Na tela do jogo (mesma escala!)

        # Posição virtual do personagem (coordenadas mundo)
        self.pos_x = None
        self.pos_y = None

        # Contador de movimentos desde último GPS
        self.movimentos_desde_gps = 0
        self.max_movimentos_sem_gps = 5  # Corrigir a cada 5 movimentos

        # Limite de clique (campo de visão)
        # Não podemos clicar muito longe do personagem!
        self.max_clique_tiles = 6  # 6 tiles = 192 pixels
        self.max_clique_pixels = self.max_clique_tiles * self.pixels_por_tile_tela

        # Histórico de erros (para debug)
        self.historico_erros = []

        print("🎥 Câmera Virtual inicializada!")
        print(f"   Campo de visão: {self.max_clique_tiles} tiles ({self.max_clique_pixels}px)")
        print(f"   GPS a cada {self.max_movimentos_sem_gps} movimentos")

    def inicializar_posicao(self):
        """
        Obtém posição inicial via GPS (UMA VEZ)

        Returns:
            bool: True se sucesso, False se falhou
        """
        print("\n📡 Obtendo posição inicial via GPS...")

        resultado = self.gps.get_current_position(keep_map_open=False, verbose=True)

        if not resultado or 'x' not in resultado:
            print("❌ GPS falhou!")
            return False

        self.pos_x = resultado['x']
        self.pos_y = resultado['y']
        self.movimentos_desde_gps = 0

        print(f"   ✅ Posição inicial: ({self.pos_x}, {self.pos_y})")
        print(f"   🗺️ Zona: {resultado.get('zone', 'Desconhecida')}\n")

        return True

    def mundo_para_tela_jogo(self, x_mundo, y_mundo):
        """
        Converte coordenadas MUNDO → TELA DO JOGO (SEM MAPA ABERTO!)

        Esta é a CHAVE do sistema! Ao invés de:
        1. Abrir mapa
        2. Converter mundo → tela do mapa
        3. Clicar no mapa
        4. Fechar mapa

        Fazemos:
        1. Converter mundo → tela do jogo DIRETO
        2. Clicar no chão

        Args:
            x_mundo, y_mundo: Coordenadas absolutas no mundo

        Returns:
            (x_tela, y_tela, alcancavel):
                - Coordenadas na tela do jogo
                - Bool se está dentro do campo de visão
        """
        if self.pos_x is None or self.pos_y is None:
            return None, None, False

        # 1. Calcular delta em pixels do mundo
        delta_x = x_mundo - self.pos_x
        delta_y = y_mundo - self.pos_y

        # 2. Na TELA DO JOGO, a escala é a MESMA do mundo (1:1)
        #    Não há compressão como no minimap!
        #    32 pixels no mundo = 32 pixels na tela

        # 3. Personagem está SEMPRE no centro da tela (800, 450)
        #    Então basta adicionar o delta!
        x_tela = self.centro_x + delta_x
        y_tela = self.centro_y + delta_y

        # 4. Verificar se está dentro do campo de visão
        distancia = np.sqrt(delta_x**2 + delta_y**2)
        alcancavel = distancia <= self.max_clique_pixels

        return int(x_tela), int(y_tela), alcancavel

    def tela_para_mundo(self, x_tela, y_tela):
        """
        Converte coordenadas TELA DO JOGO → MUNDO

        Útil para quando você quer clicar em um ponto da tela
        e saber qual coordenada mundo aquilo representa.

        Args:
            x_tela, y_tela: Coordenadas na tela do jogo

        Returns:
            (x_mundo, y_mundo): Coordenadas absolutas no mundo
        """
        if self.pos_x is None or self.pos_y is None:
            return None, None

        # Delta em pixels da tela
        delta_x = x_tela - self.centro_x
        delta_y = y_tela - self.centro_y

        # Escala 1:1, então delta na tela = delta no mundo
        x_mundo = self.pos_x + delta_x
        y_mundo = self.pos_y + delta_y

        return int(x_mundo), int(y_mundo)

    def navegar_para(self, x_mundo_destino, y_mundo_destino, forcar_gps=False):
        """
        Navega para um ponto no mundo usando a câmera virtual

        Args:
            x_mundo_destino, y_mundo_destino: Coordenadas mundo do destino
            forcar_gps: Se True, força GPS antes de navegar

        Returns:
            dict: Informações sobre a navegação
        """
        # Verificar se precisa GPS
        if forcar_gps or self.movimentos_desde_gps >= self.max_movimentos_sem_gps:
            self._corrigir_posicao_gps()

        # Converter destino para tela do jogo
        x_tela, y_tela, alcancavel = self.mundo_para_tela_jogo(
            x_mundo_destino, y_mundo_destino
        )

        if x_tela is None:
            return {
                'sucesso': False,
                'erro': 'Posição da câmera não inicializada'
            }

        # Calcular distância
        delta_x = x_mundo_destino - self.pos_x
        delta_y = y_mundo_destino - self.pos_y
        distancia_px = np.sqrt(delta_x**2 + delta_y**2)
        distancia_tiles = distancia_px / self.pixels_por_tile_mundo

        print(f"\n🎯 Navegando via câmera virtual:")
        print(f"   De:   ({self.pos_x}, {self.pos_y})")
        print(f"   Para: ({x_mundo_destino}, {y_mundo_destino})")
        print(f"   Distância: {distancia_px:.0f}px ({distancia_tiles:.1f} tiles)")
        print(f"   Clique tela: ({x_tela}, {y_tela})")
        print(f"   Alcançável: {'✅ SIM' if alcancavel else '❌ NÃO (muito longe!)'}")

        if not alcancavel:
            return {
                'sucesso': False,
                'erro': f'Destino fora do campo de visão ({distancia_tiles:.1f} > {self.max_clique_tiles} tiles)',
                'distancia_tiles': distancia_tiles,
                'max_tiles': self.max_clique_tiles
            }

        # Executar clique DIRETO no chão do jogo (SEM ABRIR MAPA!)
        print(f"   🖱️ Clicando em ({x_tela}, {y_tela})...")
        self.device.shell(f"input tap {x_tela} {y_tela}")

        # Atualizar posição virtual (dead reckoning)
        # Assumimos que o personagem VAI chegar no destino
        self.pos_x = x_mundo_destino
        self.pos_y = y_mundo_destino
        self.movimentos_desde_gps += 1

        print(f"   ✅ Clique executado!")
        print(f"   📍 Posição virtual atualizada: ({self.pos_x}, {self.pos_y})")
        print(f"   🔄 Movimentos desde GPS: {self.movimentos_desde_gps}/{self.max_movimentos_sem_gps}")

        return {
            'sucesso': True,
            'x_tela': x_tela,
            'y_tela': y_tela,
            'distancia_px': distancia_px,
            'distancia_tiles': distancia_tiles,
            'movimentos_desde_gps': self.movimentos_desde_gps
        }

    def navegar_path(self, path_mundo, auto_gps=True):
        """
        Navega por um caminho (lista de pontos mundo)

        Args:
            path_mundo: Lista de (x, y) em coordenadas mundo
            auto_gps: Se True, faz GPS automático a cada N movimentos

        Returns:
            list: Resultados de cada navegação
        """
        resultados = []

        print(f"\n🗺️ Navegando path com {len(path_mundo)} waypoints...")

        for i, (x, y) in enumerate(path_mundo):
            print(f"\n--- Waypoint {i+1}/{len(path_mundo)} ---")

            # Navegar para próximo ponto
            resultado = self.navegar_para(x, y, forcar_gps=False)
            resultados.append(resultado)

            if not resultado['sucesso']:
                print(f"⚠️ Navegação falhou: {resultado['erro']}")
                # Se falhou por estar longe, fazer GPS e tentar de novo
                if 'campo de visão' in resultado.get('erro', ''):
                    print("   🔄 Tentando com GPS...")
                    self._corrigir_posicao_gps()
                    resultado = self.navegar_para(x, y, forcar_gps=False)
                    resultados[-1] = resultado

            # Aguardar movimento completar
            time.sleep(0.5)

        return resultados

    def _corrigir_posicao_gps(self):
        """
        Corrige posição virtual usando GPS

        Isso previne erro acumulado no dead reckoning
        """
        print("\n🔄 Corrigindo posição via GPS...")

        # Guardar posição virtual anterior
        pos_virtual_anterior_x = self.pos_x
        pos_virtual_anterior_y = self.pos_y

        # Obter posição real via GPS
        resultado = self.gps.get_current_position(keep_map_open=False, verbose=False)

        if not resultado or 'x' not in resultado:
            print("   ⚠️ GPS falhou, mantendo posição virtual")
            return

        pos_real_x = resultado['x']
        pos_real_y = resultado['y']

        # Calcular erro acumulado
        erro_x = pos_real_x - pos_virtual_anterior_x
        erro_y = pos_real_y - pos_virtual_anterior_y
        erro_total = np.sqrt(erro_x**2 + erro_y**2)

        # Atualizar posição
        self.pos_x = pos_real_x
        self.pos_y = pos_real_y
        self.movimentos_desde_gps = 0

        # Salvar no histórico
        self.historico_erros.append({
            'timestamp': time.time(),
            'erro_px': erro_total,
            'erro_tiles': erro_total / self.pixels_por_tile_mundo
        })

        print(f"   ✅ Posição corrigida!")
        print(f"   Virtual: ({pos_virtual_anterior_x}, {pos_virtual_anterior_y})")
        print(f"   Real:    ({pos_real_x}, {pos_real_y})")
        print(f"   Erro:    {erro_total:.1f}px ({erro_total/self.pixels_por_tile_mundo:.2f} tiles)")

    def obter_estatisticas_erro(self):
        """
        Retorna estatísticas de erro acumulado

        Returns:
            dict: Estatísticas (média, máximo, etc)
        """
        if not self.historico_erros:
            return None

        erros_px = [e['erro_px'] for e in self.historico_erros]
        erros_tiles = [e['erro_tiles'] for e in self.historico_erros]

        return {
            'num_correcoes': len(self.historico_erros),
            'erro_medio_px': np.mean(erros_px),
            'erro_max_px': np.max(erros_px),
            'erro_medio_tiles': np.mean(erros_tiles),
            'erro_max_tiles': np.max(erros_tiles),
            'historico': self.historico_erros
        }

    def desenhar_campo_visao(self, img_mundo, cor=(0, 255, 255), thickness=2):
        """
        Desenha campo de visão no mapa mundo (para debug)

        Args:
            img_mundo: Imagem do mapa mundo
            cor: Cor BGR do círculo
            thickness: Espessura da linha

        Returns:
            img: Imagem com campo de visão desenhado
        """
        if self.pos_x is None or self.pos_y is None:
            return img_mundo

        img = img_mundo.copy()

        # Desenhar círculo do campo de visão
        cv2.circle(
            img,
            (int(self.pos_x), int(self.pos_y)),
            int(self.max_clique_pixels),
            cor,
            thickness
        )

        # Desenhar posição do personagem
        cv2.circle(
            img,
            (int(self.pos_x), int(self.pos_y)),
            5,
            (255, 0, 255),  # Magenta
            -1  # Preenchido
        )

        # Texto
        cv2.putText(
            img,
            f"Campo de visao: {self.max_clique_tiles} tiles",
            (int(self.pos_x) - 100, int(self.pos_y) - self.max_clique_pixels - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            cor,
            2
        )

        return img


class VisualizadorCameraVirtual:
    """
    Visualizador em tempo real da câmera virtual

    Mostra uma janela com o mapa mundo e a câmera se movendo ao vivo!
    """

    def __init__(self, camera, mapa_path='MINIMAPA CERTOPRETO.png'):
        """
        Inicializa visualizador

        Args:
            camera: CameraVirtual instance
            mapa_path: Path para imagem do mapa mundo
        """
        self.camera = camera

        # Carregar mapa mundo
        print(f"📖 Carregando mapa: {mapa_path}")
        self.mapa_original = cv2.imread(mapa_path)

        if self.mapa_original is None:
            raise FileNotFoundError(f"Mapa não encontrado: {mapa_path}")

        self.mapa_altura, self.mapa_largura = self.mapa_original.shape[:2]
        print(f"   ✅ Mapa carregado: {self.mapa_largura}x{self.mapa_altura}")

        # Configurações de visualização
        self.janela_nome = "Camera Virtual - Debug ao Vivo"
        self.zoom_level = 1.0
        self.mostrar_historico = True
        self.historico_posicoes = []  # Lista de posições anteriores

        # Cores
        self.cor_campo_visao = (0, 255, 255)      # Amarelo (campo de visão)
        self.cor_posicao = (255, 0, 255)          # Magenta (posição atual)
        self.cor_historico = (128, 128, 128)      # Cinza (histórico)
        self.cor_destino = (0, 255, 0)            # Verde (próximo destino)

        # Estado
        self.rodando = False
        self.proximo_destino = None

    def iniciar(self):
        """Inicia visualização"""
        self.rodando = True
        cv2.namedWindow(self.janela_nome, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.janela_nome, 1400, 900)
        print("\n🎥 Visualizador iniciado!")
        print("   Teclas:")
        print("   - ESC: Fechar")
        print("   - H: Toggle histórico")
        print("   - +/-: Zoom in/out")
        print("   - R: Reset zoom")

    def parar(self):
        """Para visualização"""
        self.rodando = False
        cv2.destroyWindow(self.janela_nome)

    def atualizar(self, destino=None):
        """
        Atualiza visualização

        Args:
            destino: Tuple (x, y) do próximo destino (opcional)
        """
        if not self.rodando:
            return

        self.proximo_destino = destino

        # Criar imagem de visualização
        img = self.mapa_original.copy()

        # 1. Desenhar histórico de posições
        if self.mostrar_historico and len(self.historico_posicoes) > 1:
            for i in range(len(self.historico_posicoes) - 1):
                p1 = self.historico_posicoes[i]
                p2 = self.historico_posicoes[i + 1]
                cv2.line(img, p1, p2, self.cor_historico, 2)

        # 2. Desenhar campo de visão (círculo amarelo)
        if self.camera.pos_x is not None:
            cv2.circle(
                img,
                (int(self.camera.pos_x), int(self.camera.pos_y)),
                int(self.camera.max_clique_pixels),
                self.cor_campo_visao,
                3
            )

            # 3. Desenhar posição atual (círculo magenta)
            cv2.circle(
                img,
                (int(self.camera.pos_x), int(self.camera.pos_y)),
                8,
                self.cor_posicao,
                -1
            )

            # Adicionar ao histórico
            pos_atual = (int(self.camera.pos_x), int(self.camera.pos_y))
            if not self.historico_posicoes or self.historico_posicoes[-1] != pos_atual:
                self.historico_posicoes.append(pos_atual)

        # 4. Desenhar próximo destino (se houver)
        if self.proximo_destino:
            dest_x, dest_y = self.proximo_destino

            # Verificar se destino está dentro do campo de visão
            x_tela, y_tela, alcancavel = self.camera.mundo_para_tela_jogo(dest_x, dest_y)

            # Linha do player ao destino
            if self.camera.pos_x is not None:
                cor_linha = self.cor_destino if alcancavel else (0, 0, 255)  # Verde se OK, vermelho se longe
                cv2.line(
                    img,
                    (int(self.camera.pos_x), int(self.camera.pos_y)),
                    (int(dest_x), int(dest_y)),
                    cor_linha,
                    2,
                    cv2.LINE_AA
                )

            # Círculo no destino
            cv2.circle(img, (int(dest_x), int(dest_y)), 6, self.cor_destino, -1)

            # Texto da distância
            if self.camera.pos_x is not None:
                dist_px = np.sqrt((dest_x - self.camera.pos_x)**2 + (dest_y - self.camera.pos_y)**2)
                dist_tiles = dist_px / self.camera.pixels_por_tile_mundo

                texto = f"{dist_tiles:.1f} tiles"
                cv2.putText(
                    img,
                    texto,
                    (int(dest_x) + 10, int(dest_y) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    self.cor_destino,
                    2
                )

        # 5. Adicionar HUD (informações)
        self._desenhar_hud(img)

        # 6. Aplicar zoom
        if self.zoom_level != 1.0:
            # Centralizar zoom na posição da câmera
            if self.camera.pos_x is not None:
                img = self._aplicar_zoom(img)

        # 7. Mostrar imagem
        cv2.imshow(self.janela_nome, img)

        # 8. Processar teclas
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            self.parar()
        elif key == ord('h') or key == ord('H'):
            self.mostrar_historico = not self.mostrar_historico
            print(f"   Histórico: {'ON' if self.mostrar_historico else 'OFF'}")
        elif key == ord('+') or key == ord('='):
            self.zoom_level = min(self.zoom_level + 0.1, 3.0)
            print(f"   Zoom: {self.zoom_level:.1f}x")
        elif key == ord('-') or key == ord('_'):
            self.zoom_level = max(self.zoom_level - 0.1, 0.5)
            print(f"   Zoom: {self.zoom_level:.1f}x")
        elif key == ord('r') or key == ord('R'):
            self.zoom_level = 1.0
            print(f"   Zoom resetado: {self.zoom_level:.1f}x")

    def _desenhar_hud(self, img):
        """Desenha HUD com informações"""
        y_offset = 30

        # Fundo semi-transparente para HUD
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (400, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        # Informações
        info_lines = [
            f"Camera Virtual - Debug ao Vivo",
            f"Posicao: ({int(self.camera.pos_x) if self.camera.pos_x else '?'}, {int(self.camera.pos_y) if self.camera.pos_y else '?'})",
            f"Campo de visao: {self.camera.max_clique_tiles} tiles ({self.camera.max_clique_pixels}px)",
            f"Movimentos desde GPS: {self.camera.movimentos_desde_gps}/{self.camera.max_movimentos_sem_gps}",
            f"Historico: {len(self.historico_posicoes)} posicoes",
            f"Zoom: {self.zoom_level:.1f}x"
        ]

        for i, line in enumerate(info_lines):
            cv2.putText(
                img,
                line,
                (20, y_offset + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

    def _aplicar_zoom(self, img):
        """Aplica zoom centralizado na câmera"""
        if self.camera.pos_x is None:
            return img

        # Centro do zoom = posição da câmera
        cx = int(self.camera.pos_x)
        cy = int(self.camera.pos_y)

        # Tamanho da janela após zoom
        h, w = img.shape[:2]
        new_w = int(w / self.zoom_level)
        new_h = int(h / self.zoom_level)

        # Calcular região para recortar (centralizada na câmera)
        x1 = max(0, cx - new_w // 2)
        y1 = max(0, cy - new_h // 2)
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)

        # Ajustar se bateu nas bordas
        if x2 - x1 < new_w:
            x1 = max(0, x2 - new_w)
        if y2 - y1 < new_h:
            y1 = max(0, y2 - new_h)

        # Recortar e redimensionar
        cropped = img[y1:y2, x1:x2]
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        return zoomed


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    import sys
    import os
    # Adicionar diretório pai ao path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from gps_ncc_realtime import GPSRealtimeNCC

    print("=" * 70)
    print("🎥 TESTE DA CÂMERA VIRTUAL COM VISUALIZAÇÃO AO VIVO")
    print("=" * 70)

    # 1. Inicializar GPS
    gps = GPSRealtimeNCC()

    # 2. Criar câmera virtual
    camera = CameraVirtual(gps, gps.device)

    # 3. Inicializar posição
    if not camera.inicializar_posicao():
        print("❌ Falha ao inicializar posição")
        exit(1)

    # 4. Criar visualizador
    try:
        # Procurar mapa no diretório pai
        mapa_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'MINIMAPA CERTOPRETO.png')
        visualizador = VisualizadorCameraVirtual(camera, mapa_path)
        visualizador.iniciar()
        print("\n✅ Visualizador ao vivo ativado!")
        print("   Você verá a câmera se mover no mapa em tempo real!\n")
    except FileNotFoundError as e:
        print(f"⚠️ Visualizador não disponível: {e}")
        print("   Continuando sem visualização...\n")
        visualizador = None

    # 5. Atualizar visualizador inicial
    if visualizador:
        visualizador.atualizar()
        time.sleep(2)

    # 6. Teste 1: Navegar para um ponto próximo (2 tiles)
    print("\n" + "=" * 70)
    print("TESTE 1: Navegar 2 tiles para a direita")
    print("=" * 70)

    destino_x = camera.pos_x + (2 * 32)  # 2 tiles = 64 pixels
    destino_y = camera.pos_y

    # Mostrar destino no visualizador
    if visualizador:
        visualizador.atualizar(destino=(destino_x, destino_y))
        time.sleep(1)

    resultado = camera.navegar_para(destino_x, destino_y)
    print(f"\nResultado: {resultado}")

    # Atualizar visualizador com nova posição
    if visualizador:
        for _ in range(30):  # Loop para ver animação
            visualizador.atualizar()
            time.sleep(0.1)
            if not visualizador.rodando:
                break

    time.sleep(2)

    # 7. Teste 2: Navegar para um ponto mais longe (4 tiles)
    if visualizador and visualizador.rodando:
        print("\n" + "=" * 70)
        print("TESTE 2: Navegar 4 tiles para cima")
        print("=" * 70)

        destino_x = camera.pos_x
        destino_y = camera.pos_y - (4 * 32)  # 4 tiles = 128 pixels (cima = negativo)

        # Mostrar destino no visualizador
        visualizador.atualizar(destino=(destino_x, destino_y))
        time.sleep(1)

        resultado = camera.navegar_para(destino_x, destino_y)
        print(f"\nResultado: {resultado}")

        # Atualizar visualizador
        for _ in range(30):
            visualizador.atualizar()
            time.sleep(0.1)
            if not visualizador.rodando:
                break

        time.sleep(2)

    # 8. Teste 3: Movimento em quadrado (para ver histórico)
    if visualizador and visualizador.rodando:
        print("\n" + "=" * 70)
        print("TESTE 3: Movimento em quadrado (3x3 tiles)")
        print("=" * 70)

        # Criar path em quadrado
        lado = 3 * 32  # 3 tiles
        pos_inicial_x = camera.pos_x
        pos_inicial_y = camera.pos_y

        path_quadrado = [
            (pos_inicial_x + lado, pos_inicial_y),        # Direita
            (pos_inicial_x + lado, pos_inicial_y + lado), # Baixo
            (pos_inicial_x, pos_inicial_y + lado),        # Esquerda
            (pos_inicial_x, pos_inicial_y),               # Cima (volta ao início)
        ]

        for i, (dest_x, dest_y) in enumerate(path_quadrado):
            print(f"\n   Waypoint {i+1}/4...")

            # Mostrar destino
            visualizador.atualizar(destino=(dest_x, dest_y))
            time.sleep(0.5)

            # Navegar
            resultado = camera.navegar_para(dest_x, dest_y)

            # Atualizar visualizador
            for _ in range(20):
                visualizador.atualizar()
                time.sleep(0.1)
                if not visualizador.rodando:
                    break

            if not visualizador.rodando:
                break

            time.sleep(1)

    # 9. Teste 4: Tentar navegar MUITO longe (deve falhar)
    if visualizador and visualizador.rodando:
        print("\n" + "=" * 70)
        print("TESTE 4: Tentar navegar 10 tiles (MUITO LONGE - deve falhar!)")
        print("=" * 70)

        destino_x = camera.pos_x + (10 * 32)  # 10 tiles = 320 pixels (muito longe!)
        destino_y = camera.pos_y

        # Mostrar destino (linha vermelha = fora do alcance)
        visualizador.atualizar(destino=(destino_x, destino_y))
        time.sleep(2)

        resultado = camera.navegar_para(destino_x, destino_y)
        print(f"\nResultado: {resultado}")

        # Atualizar visualizador
        for _ in range(20):
            visualizador.atualizar()
            time.sleep(0.1)
            if not visualizador.rodando:
                break

    # 10. Estatísticas
    print("\n" + "=" * 70)
    print("📊 ESTATÍSTICAS DE ERRO")
    print("=" * 70)

    stats = camera.obter_estatisticas_erro()
    if stats:
        print(f"Correções GPS: {stats['num_correcoes']}")
        print(f"Erro médio: {stats['erro_medio_px']:.1f}px ({stats['erro_medio_tiles']:.2f} tiles)")
        print(f"Erro máximo: {stats['erro_max_px']:.1f}px ({stats['erro_max_tiles']:.2f} tiles)")
    else:
        print("Nenhuma correção GPS realizada ainda")

    # 11. Manter visualizador aberto
    if visualizador and visualizador.rodando:
        print("\n" + "=" * 70)
        print("✅ Teste concluído! Visualizador permanece aberto.")
        print("   Pressione ESC na janela para fechar.")
        print("=" * 70)

        # Loop até usuário fechar
        while visualizador.rodando:
            visualizador.atualizar()
            time.sleep(0.05)
    else:
        print("\n✅ Teste concluído!")
