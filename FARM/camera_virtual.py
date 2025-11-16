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
- Campo de visão limitado (16×9 tiles = 64×36px no mapa mundo)
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

        # Carregar escala do mapa (igual ao navegador)
        self._carregar_escala_mapa()

        # Posição virtual do personagem (coordenadas mundo)
        self.pos_x = None
        self.pos_y = None

        # Contador de movimentos desde último GPS
        self.movimentos_desde_gps = 0
        self.max_movimentos_sem_gps = 5  # Corrigir a cada 5 movimentos

        # Campo de visão (RETÂNGULO da tela do jogo no mapa mundo)
        # Tentar carregar configuração salva, senão usar padrão
        self._carregar_config_fov()

        # Histórico de erros (para debug)
        self.historico_erros = []

        # Carregar matriz walkable para validação de paredes
        self._carregar_matriz_walkable()
        self.validacao_parede_ativa = True  # Pode ser desabilitada no modo interativo

        # Imprimir informações de inicialização
        print("🎥 Câmera Virtual inicializada!")
        print(f"   Tela do jogo: {self.tela_largura}x{self.tela_altura}px (1 tile = {self.pixels_por_tile_jogo}px)")
        print(f"   Tiles visíveis: {int(self.tiles_visiveis_x)}x{int(self.tiles_visiveis_y)} tiles")
        print(f"   Escala mapa: {self.escala_x:.1f}px/tile")
        print(f"   FOV no mapa: {self.fov_largura_mapa:.0f}x{self.fov_altura_mapa:.0f}px")
        print(f"   GPS a cada {self.max_movimentos_sem_gps} movimentos")

    def _carregar_escala_mapa(self):
        """
        Carrega escala do mapa (igual ao navegador)

        A escala converte pixels do mapa mundo para pixels da tela:
        x_tela = centro + (delta_mundo * escala)
        """
        try:
            with open('map_transform_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.escala_x = config['escala']['x']
            self.escala_y = config['escala']['y']

        except FileNotFoundError:
            # Fallback: usar escala padrão calibrada
            # Escala 25.0 = FOV de 64×36px (16×9 tiles)
            # (1 pixel mundo × 25.0 = 25 pixels tela)
            print("   ⚠️ map_transform_config.json não encontrado")
            print("   Usando escala padrão: 25.0 (FOV 64×36px)")
            self.escala_x = 25.0
            self.escala_y = 25.0

    def _carregar_config_fov(self):
        """
        Calcula FOV baseado na escala do mapa

        LÓGICA CORRETA (calibrada via testes manuais):
        - Tela do jogo: 1600x900px
        - Escala: 25.0 (1px mundo → 25px tela)
        - FOV no mundo = Tela / Escala = 1600/25.0 = 64×36px
        - 1 tile no mundo = 4px (DESCOBERTO VIA TESTES!)
        - Tiles visíveis = 64/4 = 16 tiles (horizontal) × 36/4 = 9 tiles (vertical)
        """
        # Calcular FOV no mapa mundo (INVERSO da escala!)
        # fov_mundo = tela_jogo / escala
        self.fov_largura_mapa = self.tela_largura / self.escala_x  # 1600 / 25.0 = 64px
        self.fov_altura_mapa = self.tela_altura / self.escala_y    # 900 / 25.0 = 36px

        # Calcular tiles visíveis (1 tile no mundo = 4px - CALIBRADO!)
        self.pixels_por_tile_mundo = 4.0  # 1 tile = 4px no mapa mundo
        self.tiles_visiveis_x = self.fov_largura_mapa / self.pixels_por_tile_mundo  # 64/4 = 16 tiles
        self.tiles_visiveis_y = self.fov_altura_mapa / self.pixels_por_tile_mundo   # 36/4 = 9 tiles

        # 1 tile na tela do jogo (para exibição)
        self.pixels_por_tile_jogo = 100  # 1 tile = 100px na tela do jogo

        # Escala do FOV é igual à escala do mapa
        self.escala_fov_x = self.escala_x
        self.escala_fov_y = self.escala_y

        print(f"   📐 FOV calculado: {int(self.tiles_visiveis_x)}x{int(self.tiles_visiveis_y)} tiles = {self.fov_largura_mapa:.0f}x{self.fov_altura_mapa:.0f}px")

    def _carregar_matriz_walkable(self):
        """
        Carrega matriz walkable para validação de paredes

        FORMATO DA MATRIZ V2.0:
        - Shape: (largura, altura) = (X, Y)
        - Acesso: matriz[x, y]
        - 1 = andável (chão)
        - 0 = parede/obstáculo
        """
        try:
            dados = np.load('FARM/mapa_mundo_processado.npz')
            self.matriz_walkable = dados['walkable']
            self.mundo_largura = dados['dimensoes'][0]  # X (largura)
            self.mundo_altura = dados['dimensoes'][1]   # Y (altura)

            formato = dados.get('formato', 'desconhecido')
            versao = dados.get('versao', 'desconhecido')

            print(f"   ✅ Matriz walkable carregada: {self.mundo_largura}x{self.mundo_altura}")
            print(f"      Versão: {versao}, Formato: {formato}")
            print(f"      Shape real: {self.matriz_walkable.shape}")
        except FileNotFoundError:
            print("   ⚠️ FARM/mapa_mundo_processado.npz não encontrado - validação de paredes desabilitada")
            self.matriz_walkable = None
            self.mundo_largura = None
            self.mundo_altura = None

    def validar_posicao(self, x_mundo, y_mundo, debug=False):
        """
        Valida se posição no mundo é andável (não é parede)

        IMPORTANTE: Valida uma ÁREA 3x3 ao redor do ponto para compensar
        possíveis erros de alinhamento da matriz ou drift do GPS

        Args:
            x_mundo: coordenada X no mundo
            y_mundo: coordenada Y no mundo
            debug: Se True, mostra informações detalhadas

        Returns:
            bool: True se andável, False se parede ou fora do mapa
        """
        if self.matriz_walkable is None or not self.validacao_parede_ativa:
            return True  # Sem validação, aceitar tudo

        # Arredondar para centro do pixel
        x = int(round(x_mundo))
        y = int(round(y_mundo))

        if debug:
            print(f"\n   🔍 DEBUG VALIDAÇÃO:")
            print(f"      Player: ({self.pos_x:.1f}, {self.pos_y:.1f})")
            print(f"      Target mundo: ({x_mundo:.1f}, {y_mundo:.1f})")
            print(f"      Target int: ({x}, {y})")
            print(f"      Limites matriz: [0-{self.mundo_largura}] x [0-{self.mundo_altura}]")

        # Verificar limites
        if x < 1 or x >= self.mundo_largura - 1:
            if debug:
                print(f"      ❌ FORA DOS LIMITES X: {x} (limites: 1-{self.mundo_largura-1})")
            return False
        if y < 1 or y >= self.mundo_altura - 1:
            if debug:
                print(f"      ❌ FORA DOS LIMITES Y: {y} (limites: 1-{self.mundo_altura-1})")
            return False

        # Verificar área 3x3 ao redor do ponto (compensar drift/alinhamento)
        # Se QUALQUER pixel na área for andável, considerar OK
        #
        # IMPORTANTE: Matriz está em formato [X, Y] não [Y, X]!
        # Descoberto via debug - coluna direita tinha ✓, esquerda tinha ✗
        if debug:
            print(f"      Verificando área 3x3:")
            print(f"      Shape da matriz: {self.matriz_walkable.shape}")
            print(f"      ✅ USANDO matriz[x, y] (inversão corrigida)")

        andavel_encontrado = False
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                # CORREÇÃO APLICADA: matriz[x, y] ao invés de matriz[y, x]
                try:
                    valor = self.matriz_walkable[x + dx, y + dy]
                except:
                    valor = -1

                if debug:
                    simbolo = "✓" if valor == 1 else "✗"
                    print(f"         matriz[{x+dx:4d}, {y+dy:4d}] = {valor} {simbolo}")

                if valor == 1:
                    andavel_encontrado = True

        if debug:
            if andavel_encontrado:
                print(f"      ✅ ANDÁVEL (pelo menos 1 pixel livre)")
            else:
                print(f"      🚫 PAREDE (toda área bloqueada)")

        return andavel_encontrado

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

        ESCALA CORRETA (calibrada via testes manuais):
        - Tela do jogo: 1600×900px
        - Mapa mundo: FOV = 64×36px
        - Escala = 1600 ÷ 64 = 25.0 (1px mundo = 25px tela)
        - 1 tile = 4px no mapa mundo

        Args:
            x_mundo, y_mundo: Coordenadas absolutas no mundo

        Returns:
            (x_tela, y_tela, alcancavel, eh_parede):
                - Coordenadas na tela do jogo
                - Bool se está dentro do campo de visão
                - Bool se é parede (True = parede, False = andável)
        """
        if self.pos_x is None or self.pos_y is None:
            return None, None, False, False

        # 1. Calcular delta em pixels do mundo
        delta_x = x_mundo - self.pos_x
        delta_y = y_mundo - self.pos_y

        # 2. Aplicar escala correta: 25.0 (64px mundo → 1600px tela)
        #    x_tela = centro + (delta_mundo * escala)
        #    Com escala 25.0: 1px mundo = 25px tela
        x_tela = self.centro_x + (delta_x * self.escala_x)
        y_tela = self.centro_y + (delta_y * self.escala_y)

        # 3. Verificar se está dentro do campo de visão (retângulo FOV)
        half_fov_x = self.fov_largura_mapa / 2
        half_fov_y = self.fov_altura_mapa / 2

        dentro_fov = (abs(delta_x) <= half_fov_x and abs(delta_y) <= half_fov_y)

        # 4. Verificar se é parede
        eh_parede = not self.validar_posicao(x_mundo, y_mundo)

        # Alcançável = dentro do FOV E não é parede
        alcancavel = dentro_fov and not eh_parede

        return int(x_tela), int(y_tela), alcancavel, eh_parede

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
        delta_tela_x = x_tela - self.centro_x
        delta_tela_y = y_tela - self.centro_y

        # Converter de volta para mundo (dividir pela escala)
        delta_mundo_x = delta_tela_x / self.escala_x
        delta_mundo_y = delta_tela_y / self.escala_y

        x_mundo = self.pos_x + delta_mundo_x
        y_mundo = self.pos_y + delta_mundo_y

        return int(x_mundo), int(y_mundo)

    def navegar_para(self, x_mundo_destino, y_mundo_destino, forcar_gps=False, verificar_gps_apos=False):
        """
        Navega para um ponto no mundo usando a câmera virtual

        Args:
            x_mundo_destino, y_mundo_destino: Coordenadas mundo do destino
            forcar_gps: Se True, força GPS antes de navegar
            verificar_gps_apos: Se True, faz GPS após movimento para calibração

        Returns:
            dict: Informações sobre a navegação
        """
        # Verificar se precisa GPS
        if forcar_gps or self.movimentos_desde_gps >= self.max_movimentos_sem_gps:
            self._corrigir_posicao_gps()

        # Salvar posição virtual ANTES do movimento
        pos_virtual_antes_x = self.pos_x
        pos_virtual_antes_y = self.pos_y

        # Converter destino para tela do jogo
        x_tela, y_tela, alcancavel, eh_parede = self.mundo_para_tela_jogo(
            x_mundo_destino, y_mundo_destino
        )

        if x_tela is None:
            return {
                'sucesso': False,
                'erro': 'Posição da câmera não inicializada'
            }

        # Calcular distância esperada
        delta_x_esperado = x_mundo_destino - self.pos_x
        delta_y_esperado = y_mundo_destino - self.pos_y
        distancia_px = np.sqrt(delta_x_esperado**2 + delta_y_esperado**2)

        print(f"\n🎯 Navegando via câmera virtual:")
        print(f"   De:   ({self.pos_x}, {self.pos_y})")
        print(f"   Para: ({x_mundo_destino}, {y_mundo_destino})")
        print(f"   Distância: {distancia_px:.0f}px")
        print(f"   Clique tela: ({x_tela}, {y_tela})")

        if eh_parede:
            print(f"   Alcançável: ❌ NÃO (PAREDE!)")
        elif not alcancavel:
            print(f"   Alcançável: ❌ NÃO (fora do FOV!)")
        else:
            print(f"   Alcançável: ✅ SIM")

        if not alcancavel:
            erro_msg = 'Destino é uma PAREDE!' if eh_parede else f'Destino fora do campo de visão (FOV: {self.fov_largura_mapa:.0f}x{self.fov_altura_mapa:.0f}px)'
            return {
                'sucesso': False,
                'erro': erro_msg,
                'eh_parede': eh_parede,
                'distancia_px': distancia_px,
                'fov_largura': self.fov_largura_mapa,
                'fov_altura': self.fov_altura_mapa
            }

        # Executar clique DIRETO no chão do jogo (SEM ABRIR MAPA!)
        print(f"   🖱️ Clicando em ({x_tela}, {y_tela})...")
        self.device.shell(f"input tap {x_tela} {y_tela}")

        # Aguardar movimento completar
        time.sleep(1.0)  # Dar tempo pro personagem andar

        # Atualizar posição virtual (dead reckoning)
        # Assumimos que o personagem VAI chegar no destino
        self.pos_x = x_mundo_destino
        self.pos_y = y_mundo_destino
        self.movimentos_desde_gps += 1

        print(f"   ✅ Clique executado!")
        print(f"   📍 Posição virtual atualizada: ({self.pos_x}, {self.pos_y})")
        print(f"   🔄 Movimentos desde GPS: {self.movimentos_desde_gps}/{self.max_movimentos_sem_gps}")

        # VERIFICAÇÃO GPS PÓS-MOVIMENTO (para calibração)
        delta_real_x = None
        delta_real_y = None
        erro_calibracao = None

        if verificar_gps_apos:
            print(f"\n📡 Verificando posição REAL via GPS...")
            resultado_gps = self.gps.get_current_position(keep_map_open=False, verbose=False)

            if resultado_gps and 'x' in resultado_gps:
                pos_real_x = resultado_gps['x']
                pos_real_y = resultado_gps['y']

                # Calcular quanto realmente andou
                delta_real_x = pos_real_x - pos_virtual_antes_x
                delta_real_y = pos_real_y - pos_virtual_antes_y
                distancia_real = np.sqrt(delta_real_x**2 + delta_real_y**2)

                # Calcular erro de calibração
                erro_calibracao_x = delta_real_x - delta_x_esperado
                erro_calibracao_y = delta_real_y - delta_y_esperado
                erro_calibracao = np.sqrt(erro_calibracao_x**2 + erro_calibracao_y**2)

                # Atualizar posição virtual com a REAL
                self.pos_x = pos_real_x
                self.pos_y = pos_real_y
                self.movimentos_desde_gps = 0

                print(f"\n📊 COMPARAÇÃO VIRTUAL vs REAL:")
                print(f"   📍 Posição ANTES: ({pos_virtual_antes_x}, {pos_virtual_antes_y})")
                print(f"   🎯 ESPERADO andar: ({delta_x_esperado:+.1f}, {delta_y_esperado:+.1f}) = {distancia_px:.1f}px")
                print(f"   ✅ REAL andou:     ({delta_real_x:+.1f}, {delta_real_y:+.1f}) = {distancia_real:.1f}px")
                print(f"   📍 Posição REAL:   ({pos_real_x}, {pos_real_y})")
                print(f"   ⚠️ ERRO calibração: {erro_calibracao:.1f}px")

                # Calcular escala sugerida
                if abs(delta_x_esperado) > 0.5:
                    escala_sugerida_x = abs(delta_real_x / delta_x_esperado)
                    print(f"   💡 Escala sugerida X: {escala_sugerida_x:.3f} (atual: {self.escala_x:.1f})")
                if abs(delta_y_esperado) > 0.5:
                    escala_sugerida_y = abs(delta_real_y / delta_y_esperado)
                    print(f"   💡 Escala sugerida Y: {escala_sugerida_y:.3f} (atual: {self.escala_y:.1f})")
            else:
                print(f"   ⚠️ GPS falhou, mantendo posição virtual")

        return {
            'sucesso': True,
            'x_tela': x_tela,
            'y_tela': y_tela,
            'distancia_px': distancia_px,
            'movimentos_desde_gps': self.movimentos_desde_gps,
            'delta_real_x': delta_real_x,
            'delta_real_y': delta_real_y,
            'erro_calibracao': erro_calibracao
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
            'erro_px': erro_total
        })

        print(f"   ✅ Posição corrigida!")
        print(f"   Virtual: ({pos_virtual_anterior_x}, {pos_virtual_anterior_y})")
        print(f"   Real:    ({pos_real_x}, {pos_real_y})")
        print(f"   Erro:    {erro_total:.1f}px")

    def obter_estatisticas_erro(self):
        """
        Retorna estatísticas de erro acumulado

        Returns:
            dict: Estatísticas (média, máximo, etc)
        """
        if not self.historico_erros:
            return None

        erros_px = [e['erro_px'] for e in self.historico_erros]

        return {
            'num_correcoes': len(self.historico_erros),
            'erro_medio_px': np.mean(erros_px),
            'erro_max_px': np.max(erros_px),
            'historico': self.historico_erros
        }

    def desenhar_campo_visao(self, img_mundo, cor=(0, 255, 255), thickness=2):
        """
        Desenha campo de visão no mapa mundo (RETÂNGULO da tela do jogo)

        Args:
            img_mundo: Imagem do mapa mundo
            cor: Cor BGR do retângulo
            thickness: Espessura da linha

        Returns:
            img: Imagem com campo de visão desenhado
        """
        if self.pos_x is None or self.pos_y is None:
            return img_mundo

        img = img_mundo.copy()

        # Calcular cantos do retângulo FOV (centralizado no personagem)
        # Dimensões no mapa mundo
        half_width = self.fov_largura_mapa / 2
        half_height = self.fov_altura_mapa / 2

        x1 = int(self.pos_x - half_width)
        y1 = int(self.pos_y - half_height)
        x2 = int(self.pos_x + half_width)
        y2 = int(self.pos_y + half_height)

        # Desenhar retângulo do campo de visão
        cv2.rectangle(
            img,
            (x1, y1),
            (x2, y2),
            cor,
            thickness
        )

        # Desenhar posição do personagem (centro do retângulo)
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
            f"FOV: {int(self.tiles_visiveis_x)}x{int(self.tiles_visiveis_y)} tiles = {int(self.fov_largura_mapa)}x{int(self.fov_altura_mapa)}px",
            (x1, y1 - 10),
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
        self.cor_campo_visao = (0, 255, 255)      # Amarelo (FOV - retângulo da tela)
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

        # 2. Desenhar campo de visão (RETÂNGULO amarelo - tela do jogo)
        if self.camera.pos_x is not None:
            # Calcular cantos do retângulo FOV
            half_width = self.camera.fov_largura_mapa / 2
            half_height = self.camera.fov_altura_mapa / 2

            x1 = int(self.camera.pos_x - half_width)
            y1 = int(self.camera.pos_y - half_height)
            x2 = int(self.camera.pos_x + half_width)
            y2 = int(self.camera.pos_y + half_height)

            # Desenhar retângulo
            cv2.rectangle(
                img,
                (x1, y1),
                (x2, y2),
                self.cor_campo_visao,
                3
            )

            # 3. Desenhar posição atual (círculo magenta no centro)
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

            # Verificar se destino está dentro do campo de visão E se é parede
            x_tela, y_tela, alcancavel, eh_parede = self.camera.mundo_para_tela_jogo(dest_x, dest_y)

            # Linha do player ao destino
            if self.camera.pos_x is not None:
                # Vermelho se parede OU fora do FOV, verde se OK
                cor_linha = self.cor_destino if alcancavel else (0, 0, 255)
                cv2.line(
                    img,
                    (int(self.camera.pos_x), int(self.camera.pos_y)),
                    (int(dest_x), int(dest_y)),
                    cor_linha,
                    2,
                    cv2.LINE_AA
                )

            # Círculo no destino (vermelho se parede, verde se OK)
            cor_circulo = (0, 0, 255) if eh_parede else self.cor_destino
            cv2.circle(img, (int(dest_x), int(dest_y)), 6, cor_circulo, -1)

            # Texto da distância e status
            if self.camera.pos_x is not None:
                dist_px = np.sqrt((dest_x - self.camera.pos_x)**2 + (dest_y - self.camera.pos_y)**2)

                # Texto com status
                if eh_parede:
                    texto = f"{dist_px:.0f}px (PAREDE)"
                    cor_texto = (0, 0, 255)
                elif not alcancavel:
                    texto = f"{dist_px:.0f}px (FOV)"
                    cor_texto = (0, 0, 255)
                else:
                    texto = f"{dist_px:.0f}px (OK)"
                    cor_texto = self.cor_destino

                cv2.putText(
                    img,
                    texto,
                    (int(dest_x) + 10, int(dest_y) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    cor_texto,
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
        cv2.rectangle(overlay, (10, 10), (400, 230), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        # Informações
        validacao_status = "ON" if self.camera.validacao_parede_ativa else "OFF"
        info_lines = [
            f"Camera Virtual - Debug ao Vivo",
            f"Posicao: ({int(self.camera.pos_x) if self.camera.pos_x else '?'}, {int(self.camera.pos_y) if self.camera.pos_y else '?'})",
            f"Tela: {self.camera.tela_largura}x{self.camera.tela_altura}px (1 tile = {self.camera.pixels_por_tile_jogo}px)",
            f"FOV: {int(self.camera.tiles_visiveis_x)}x{int(self.camera.tiles_visiveis_y)} tiles = {int(self.camera.fov_largura_mapa)}x{int(self.camera.fov_altura_mapa)}px",
            f"Escala mapa: {self.camera.escala_x:.1f}px/tile",
            f"Validacao Parede: {validacao_status}",
            f"GPS: {self.camera.movimentos_desde_gps}/{self.camera.max_movimentos_sem_gps}",
            f"Historico: {len(self.historico_posicoes)} pos",
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

    # 6. Teste 1: Navegar para um ponto próximo (10 pixels mundo)
    print("\n" + "=" * 70)
    print("TESTE 1: Navegar 10px para a direita (mapa mundo)")
    print("=" * 70)

    destino_x = camera.pos_x + 10  # 10 pixels no mapa mundo
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

    # 7. Teste 2: Navegar para um ponto mais longe (20 pixels mundo)
    if visualizador and visualizador.rodando:
        print("\n" + "=" * 70)
        print("TESTE 2: Navegar 20px para cima (mapa mundo)")
        print("=" * 70)

        destino_x = camera.pos_x
        destino_y = camera.pos_y - 20  # 20 pixels no mapa mundo (cima = negativo)

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
        print("TESTE 3: Movimento em quadrado (15x15 pixels mundo)")
        print("=" * 70)

        # Criar path em quadrado
        lado = 15  # 15 pixels no mapa mundo
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
        print("TESTE 4: Tentar navegar 100px (MUITO LONGE - deve falhar!)")
        print("=" * 70)

        destino_x = camera.pos_x + 100  # 100 pixels mundo (muito longe!)
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
        print(f"Erro médio: {stats['erro_medio_px']:.1f}px")
        print(f"Erro máximo: {stats['erro_max_px']:.1f}px")
    else:
        print("Nenhuma correção GPS realizada ainda")

    # 11. Modo Interativo de Teste Manual
    if visualizador and visualizador.rodando:
        print("\n" + "=" * 70)
        print("🎮 MODO INTERATIVO - TESTE MANUAL DE CLIQUES")
        print("=" * 70)
        print("\nControles:")
        print("  [W] [A] [S] [D] - Direções (cima, esq, baixo, dir)")
        print("  [P] [O] - Aumentar/diminuir PIXELS do clique (±1px)")
        print("  [+] [-] - Aumentar/diminuir FOV (largura)")
        print("  [9] [0] - Aumentar/diminuir FOV (altura)")
        print("  [M] [N] - Aumentar/diminuir ESCALA (±0.1)")
        print("  [V] - Toggle validação de parede")
        print("  [SPACE] - Executar movimento no jogo")
        print("  [X] - Salvar configurações (FOV + ESCALA)")
        print("  [G] - Forçar correção GPS")
        print("  [R] - Reset zoom")
        print("  [H] - Toggle histórico")
        print("  [ESC] - Sair")
        print("=" * 70)
        print("\n📐 ESCALA CALIBRADA (via testes manuais):")
        print("   - Tela do jogo: 1600×900px")
        print("   - Mapa mundo: 1 tile = 4px")
        print("   - Escala: 25.0 (1px mundo = 25px tela)")
        print("   - FOV: 16×9 tiles = 64×36px no mapa")
        print("=" * 70)

        # Estado do controle interativo
        direcao = 'direita'  # 'direita', 'esquerda', 'cima', 'baixo'
        pixels_clique = 20  # Quantidade de PIXELS do clique (distância no mundo = 1 tile no mapa)

        while visualizador.rodando:
            # Mostrar estado atual
            setas = {
                'direita': '→',
                'esquerda': '←',
                'cima': '↑',
                'baixo': '↓'
            }

            # Calcular em tiles para referência (1 tile = 32px)
            tiles_equiv = pixels_clique / 32.0

            print(f"\r[Direção: {setas[direcao]} {direcao.upper()}] [Pixels: {pixels_clique}px = {tiles_equiv:.2f} tiles] [FOV: {camera.fov_largura_mapa:.0f}x{camera.fov_altura_mapa:.0f}px]", end='', flush=True)

            # Calcular destino baseado na direção e pixels
            destino_x = camera.pos_x
            destino_y = camera.pos_y

            if direcao == 'direita':
                destino_x = camera.pos_x + pixels_clique
            elif direcao == 'esquerda':
                destino_x = camera.pos_x - pixels_clique
            elif direcao == 'cima':
                destino_y = camera.pos_y - pixels_clique
            elif direcao == 'baixo':
                destino_y = camera.pos_y + pixels_clique

            # Atualizar visualizador com destino proposto
            visualizador.atualizar(destino=(destino_x, destino_y))

            # Processar tecla
            key = cv2.waitKey(50) & 0xFF

            if key == 27:  # ESC
                break
            elif key == ord('w') or key == ord('W'):
                direcao = 'cima'
                print(f"\n   → Direção: CIMA ↑")
            elif key == ord('s') or key == ord('S'):
                direcao = 'baixo'
                print(f"\n   → Direção: BAIXO ↓")
            elif key == ord('a') or key == ord('A'):
                direcao = 'esquerda'
                print(f"\n   → Direção: ESQUERDA ←")
            elif key == ord('d') or key == ord('D'):
                direcao = 'direita'
                print(f"\n   → Direção: DIREITA →")
            elif key == ord('p') or key == ord('P'):  # P = Aumentar pixels
                pixels_clique = min(pixels_clique + 1, 500)
                print(f"\n   → Pixels: {pixels_clique}px ({pixels_clique/32:.2f} tiles)")
            elif key == ord('o') or key == ord('O'):  # O = Diminuir pixels
                pixels_clique = max(pixels_clique - 1, 1)
                print(f"\n   → Pixels: {pixels_clique}px ({pixels_clique/32:.2f} tiles)")
            elif key == ord('+') or key == ord('='):
                camera.fov_largura_mapa = min(camera.fov_largura_mapa + 2, 200)
                camera.escala_fov_x = camera.tela_largura / camera.fov_largura_mapa
                print(f"\n   → FOV Largura: {camera.fov_largura_mapa:.0f}px (escala: {camera.escala_fov_x:.2f})")
            elif key == ord('-') or key == ord('_'):
                camera.fov_largura_mapa = max(camera.fov_largura_mapa - 2, 20)
                camera.escala_fov_x = camera.tela_largura / camera.fov_largura_mapa
                print(f"\n   → FOV Largura: {camera.fov_largura_mapa:.0f}px (escala: {camera.escala_fov_x:.2f})")
            elif key == ord('9'):
                camera.fov_altura_mapa = min(camera.fov_altura_mapa + 2, 200)
                camera.escala_fov_y = camera.tela_altura / camera.fov_altura_mapa
                print(f"\n   → FOV Altura: {camera.fov_altura_mapa:.0f}px (escala: {camera.escala_fov_y:.2f})")
            elif key == ord('0'):
                camera.fov_altura_mapa = max(camera.fov_altura_mapa - 2, 20)
                camera.escala_fov_y = camera.tela_altura / camera.fov_altura_mapa
                print(f"\n   → FOV Altura: {camera.fov_altura_mapa:.0f}px (escala: {camera.escala_fov_y:.2f})")
            elif key == ord('m') or key == ord('M'):  # M = Aumentar escala
                camera.escala_x = min(camera.escala_x + 0.1, 50.0)
                camera.escala_y = camera.escala_x
                print(f"\n   → ESCALA: {camera.escala_x:.2f} (1 tile = {32/camera.escala_x:.1f}px mundo)")
            elif key == ord('n') or key == ord('N'):  # N = Diminuir escala
                camera.escala_x = max(camera.escala_x - 0.1, 0.5)
                camera.escala_y = camera.escala_x
                print(f"\n   → ESCALA: {camera.escala_x:.2f} (1 tile = {32/camera.escala_x:.1f}px mundo)")
            elif key == ord(' '):  # SPACE - Executar movimento
                print(f"\n\n🎯 EXECUTANDO MOVIMENTO:")
                print(f"   Direção: {direcao.upper()} {setas[direcao]}")
                print(f"   Distância: {pixels_clique}px mundo ({pixels_clique/32:.2f} tiles)")
                resultado = camera.navegar_para(destino_x, destino_y, verificar_gps_apos=True)
                print(f"   Resultado: {'✅ SUCESSO' if resultado['sucesso'] else '❌ FALHOU'}")
                if not resultado['sucesso']:
                    print(f"   Erro: {resultado['erro']}")
                else:
                    print(f"   🖱️ Clicou em: ({resultado['x_tela']}, {resultado['y_tela']})")
                print()
            elif key == ord('x') or key == ord('X'):  # X - Salvar configurações
                print(f"\n\n💾 SALVANDO CONFIGURAÇÕES:")
                print(f"   FOV: {camera.fov_largura_mapa:.0f}x{camera.fov_altura_mapa:.0f}px")
                print(f"   Escala FOV: {camera.escala_fov_x:.2f}x{camera.escala_fov_y:.2f}")
                print(f"   Escala MAPA: {camera.escala_x:.2f}x{camera.escala_y:.2f}")
                print(f"   1 tile (32px tela) = {32/camera.escala_x:.1f}px mundo")

                # Salvar em arquivo JSON
                config_fov = {
                    'fov_largura_mapa': camera.fov_largura_mapa,
                    'fov_altura_mapa': camera.fov_altura_mapa,
                    'escala_fov_x': camera.escala_fov_x,
                    'escala_fov_y': camera.escala_fov_y,
                    'observacoes': 'FOV calibrado manualmente no modo interativo'
                }

                # Salvar escala do mapa também
                config_escala = {
                    'centro_mapa_tela': {'x': 800, 'y': 450},
                    'escala': {'x': camera.escala_x, 'y': camera.escala_y},
                    'observacoes': f'Escala calibrada manualmente - 1 tile = {32/camera.escala_x:.1f}px mundo'
                }

                with open('camera_virtual_config.json', 'w', encoding='utf-8') as f:
                    json.dump(config_fov, f, indent=2, ensure_ascii=False)

                with open('map_transform_config.json', 'w', encoding='utf-8') as f:
                    json.dump(config_escala, f, indent=2, ensure_ascii=False)

                print(f"   ✅ Salvo em: camera_virtual_config.json")
                print(f"   ✅ Salvo em: map_transform_config.json")
                print()
            elif key == ord('g') or key == ord('G'):
                print("\n\n🔄 Forçando correção GPS...")
                camera._corrigir_posicao_gps()
                print()
            elif key == ord('r') or key == ord('R'):
                visualizador.zoom_level = 1.0
                print(f"\n   → Zoom resetado: 1.0x")
            elif key == ord('h') or key == ord('H'):
                visualizador.mostrar_historico = not visualizador.mostrar_historico
                print(f"\n   → Histórico: {'ON' if visualizador.mostrar_historico else 'OFF'}")
            elif key == ord('v') or key == ord('V'):
                camera.validacao_parede_ativa = not camera.validacao_parede_ativa
                print(f"\n   → Validação de Parede: {'ON' if camera.validacao_parede_ativa else 'OFF (DESABILITADA)'}")

        print("\n\n✅ Modo interativo encerrado!")
    else:
        print("\n✅ Teste concluído!")