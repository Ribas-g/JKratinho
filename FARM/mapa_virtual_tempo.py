"""
MAPA VIRTUAL COM RASTREAMENTO TEMPORAL
Simula posição do jogador baseado em movimentos conhecidos + tempo

Funcionamento:
1. GPS inicial fornece posição real
2. Bot executa tap -> inicia rastreamento de movimento
3. Calcula tempo estimado baseado em distância + velocidade calibrada
4. Detecta fim do movimento (linha verde desaparece OU timeout)
5. Atualiza posição virtual apenas quando movimento completa
6. GPS periódico (10min) para corrigir drift

Vantagens:
- Overhead quase zero (não abre GPS a cada frame)
- Rastreamento preciso em tempo real
- Validação de clicks (evita clicar em paredes)
- Funciona em labirintos complexos
"""

import cv2
import numpy as np
import time
import json
from pathlib import Path
import math


class MapaVirtualComTempo:
    def __init__(self):
        """Inicializa mapa virtual"""
        print("🗺️ Inicializando Mapa Virtual com Rastreamento Temporal...")

        # 1. Carregar matriz walkable
        self.carregar_matriz()

        # 2. Carregar calibração de velocidade
        self.carregar_velocidade()

        # 3. Inicializar estado do jogador
        self.player_x = None  # Posição mundo X (será setada por GPS)
        self.player_y = None  # Posição mundo Y (será setada por GPS)
        self.ultimo_gps = 0   # Timestamp do último GPS

        # 4. Estado de movimento
        self.movimento_ativo = False
        self.movimento_destino_x = None
        self.movimento_destino_y = None
        self.movimento_inicio = None
        self.movimento_tempo_estimado = None

        # 5. Configurações de detecção de linha verde
        self.verde_lower = np.array([40, 100, 100])
        self.verde_upper = np.array([80, 255, 255])
        self.verde_x1 = 700
        self.verde_y1 = 350
        self.verde_x2 = 900
        self.verde_y2 = 550

        # 6. Dimensões da tela
        self.tela_largura = 1600
        self.tela_altura = 900
        self.centro_x = 800
        self.centro_y = 450

        # 7. Intervalo para GPS recalibração (10 minutos)
        self.intervalo_gps = 600  # segundos

        print(f"   ✅ Matriz walkable carregada: {self.matriz_walkable.shape}")
        print(f"   ✅ Velocidade: {self.velocidade_px_s:.1f} px/s")
        print(f"   ✅ Tempo por tile: {self.tempo_por_tile:.3f}s")

    def carregar_matriz(self):
        """Carrega matriz walkable do arquivo processado"""
        try:
            dados = np.load('FARM/mapa_mundo_processado.npz')
            self.matriz_walkable = dados['walkable']
            self.matriz_biomas = dados['biomas']
            self.dimensoes = dados['dimensoes']

            # Dimensões do mapa mundo
            self.mundo_largura = self.dimensoes[0]
            self.mundo_altura = self.dimensoes[1]

            print(f"   📂 Matriz carregada: {self.mundo_largura}x{self.mundo_altura}")

        except FileNotFoundError:
            print("   ❌ Arquivo mapa_mundo_processado.npz não encontrado!")
            print("   Execute: python processar_mapa_mundo.py")
            raise

    def carregar_velocidade(self):
        """Carrega configuração de velocidade calibrada"""
        try:
            with open('FARM/velocidade_personagem.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.velocidade_px_s = config['velocidade_px_s']
            self.tempo_por_tile = config['tempo_por_tile']
            self.pixels_por_tile = config['pixels_por_tile']

            print(f"   📂 Velocidade carregada: {self.velocidade_px_s:.1f} px/s")

        except FileNotFoundError:
            print("   ⚠️ Arquivo velocidade_personagem.json não encontrado!")
            print("   Usando valores padrão (estimativa)")

            # Valores padrão estimados
            self.velocidade_px_s = 80.0  # ~80 pixels/segundo
            self.tempo_por_tile = 0.4    # ~400ms por tile
            self.pixels_por_tile = 32

    def atualizar_posicao_gps(self, x, y):
        """
        Atualiza posição do jogador via GPS
        Deve ser chamado após obter coordenadas do GPS
        """
        self.player_x = x
        self.player_y = y
        self.ultimo_gps = time.time()

        print(f"📡 Posição GPS atualizada: ({x}, {y})")

        # Se havia movimento ativo, cancelar
        if self.movimento_ativo:
            print("   ⚠️ Movimento ativo cancelado por GPS")
            self.movimento_ativo = False

    def precisa_gps(self):
        """
        Verifica se precisa fazer GPS recalibração
        Retorna True se passou tempo suficiente desde último GPS
        """
        if self.player_x is None:
            return True  # Primeira vez, precisa GPS

        tempo_desde_gps = time.time() - self.ultimo_gps
        return tempo_desde_gps >= self.intervalo_gps

    def converter_tela_para_mundo(self, tela_x, tela_y):
        """
        Converte coordenadas da tela para coordenadas do mundo
        Usa posição virtual atual do jogador

        Args:
            tela_x: coordenada X na tela (0-1600)
            tela_y: coordenada Y na tela (0-900)

        Returns:
            (mundo_x, mundo_y): coordenadas no mapa mundo
        """
        if self.player_x is None or self.player_y is None:
            return None, None

        # Jogador está sempre no centro da tela
        # Offset = quanto o click está do centro
        offset_x = tela_x - self.centro_x
        offset_y = tela_y - self.centro_y

        # Posição mundo = posição jogador + offset
        mundo_x = self.player_x + offset_x
        mundo_y = self.player_y + offset_y

        return mundo_x, mundo_y

    def validar_click(self, mundo_x, mundo_y):
        """
        Valida se click em coordenadas do mundo é walkable

        Args:
            mundo_x: coordenada X no mundo
            mundo_y: coordenada Y no mundo

        Returns:
            True se walkable, False se parede/fora do mapa
        """
        # Verificar limites
        if mundo_x < 0 or mundo_x >= self.mundo_largura:
            return False
        if mundo_y < 0 or mundo_y >= self.mundo_altura:
            return False

        # Verificar walkability
        # Matriz está em [y, x] (linha, coluna)
        return self.matriz_walkable[int(mundo_y), int(mundo_x)] == 1

    def calcular_distancia(self, x1, y1, x2, y2):
        """Calcula distância euclidiana entre dois pontos"""
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def iniciar_movimento(self, destino_mundo_x, destino_mundo_y):
        """
        Inicia rastreamento de movimento para destino

        Args:
            destino_mundo_x: coordenada X de destino no mundo
            destino_mundo_y: coordenada Y de destino no mundo
        """
        if self.player_x is None or self.player_y is None:
            print("⚠️ Não pode iniciar movimento: posição desconhecida")
            return

        # Calcular distância
        distancia = self.calcular_distancia(
            self.player_x, self.player_y,
            destino_mundo_x, destino_mundo_y
        )

        # Calcular tempo estimado baseado em velocidade calibrada
        tempo_estimado = distancia / self.velocidade_px_s if self.velocidade_px_s > 0 else 1.0

        # Adicionar margem de segurança (20%)
        tempo_estimado *= 1.2

        # Marcar movimento como ativo
        self.movimento_ativo = True
        self.movimento_destino_x = destino_mundo_x
        self.movimento_destino_y = destino_mundo_y
        self.movimento_inicio = time.time()
        self.movimento_tempo_estimado = tempo_estimado

        print(f"🏃 Movimento iniciado:")
        print(f"   De: ({self.player_x:.0f}, {self.player_y:.0f})")
        print(f"   Para: ({destino_mundo_x:.0f}, {destino_mundo_y:.0f})")
        print(f"   Distância: {distancia:.1f} px")
        print(f"   Tempo estimado: {tempo_estimado:.3f}s")

    def detectar_linha_verde(self, img):
        """
        Detecta se linha verde está presente na imagem
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

        # Threshold: precisa de pelo menos 50 pixels verdes
        return pixels_verdes > 50

    def verificar_movimento_completo(self, img):
        """
        Verifica se movimento atual foi completado

        Args:
            img: screenshot atual para detectar linha verde

        Returns:
            True se movimento completo, False se ainda em progresso
        """
        if not self.movimento_ativo:
            return True  # Não há movimento ativo

        tempo_decorrido = time.time() - self.movimento_inicio

        # Critério 1: Timeout (tempo estimado + margem passou)
        timeout = self.movimento_tempo_estimado * 1.5  # 50% margem extra
        if tempo_decorrido > timeout:
            print(f"   ⏱️ Movimento completo por timeout ({tempo_decorrido:.3f}s)")
            return True

        # Critério 2: Linha verde desapareceu (e já passou tempo mínimo)
        # Só checar linha verde se já passou pelo menos 30% do tempo estimado
        # (evita falsos positivos no início)
        if tempo_decorrido > self.movimento_tempo_estimado * 0.3:
            linha_verde_presente = self.detectar_linha_verde(img)

            if not linha_verde_presente:
                print(f"   🟢 Movimento completo (linha verde sumiu em {tempo_decorrido:.3f}s)")
                return True

        return False

    def finalizar_movimento(self):
        """
        Finaliza movimento e atualiza posição virtual
        Deve ser chamado quando movimento for confirmado como completo
        """
        if not self.movimento_ativo:
            return

        # Atualizar posição virtual para o destino
        self.player_x = self.movimento_destino_x
        self.player_y = self.movimento_destino_y

        print(f"✅ Posição virtual atualizada: ({self.player_x:.0f}, {self.player_y:.0f})")

        # Resetar estado de movimento
        self.movimento_ativo = False
        self.movimento_destino_x = None
        self.movimento_destino_y = None
        self.movimento_inicio = None
        self.movimento_tempo_estimado = None

    def obter_bioma_atual(self):
        """
        Retorna o bioma da posição atual do jogador
        """
        if self.player_x is None or self.player_y is None:
            return 0  # Desconhecido

        x = int(self.player_x)
        y = int(self.player_y)

        # Verificar limites
        if x < 0 or x >= self.mundo_largura:
            return 0
        if y < 0 or y >= self.mundo_altura:
            return 0

        return self.matriz_biomas[y, x]

    def executar_tap_com_validacao(self, tela_x, tela_y, executar_tap_callback):
        """
        Executa tap com validação e rastreamento temporal

        Args:
            tela_x: coordenada X na tela
            tela_y: coordenada Y na tela
            executar_tap_callback: função para executar o tap real
                                  deve aceitar (x, y) como parâmetros

        Returns:
            True se tap foi executado, False se bloqueado (parede/movimento ativo)
        """
        # 1. Verificar se há movimento ativo
        if self.movimento_ativo:
            print(f"⚠️ Tap bloqueado: movimento em progresso")
            return False

        # 2. Converter coordenadas tela -> mundo
        mundo_x, mundo_y = self.converter_tela_para_mundo(tela_x, tela_y)

        if mundo_x is None or mundo_y is None:
            print(f"⚠️ Tap bloqueado: posição virtual desconhecida (precisa GPS)")
            return False

        # 3. Validar se destino é walkable
        if not self.validar_click(mundo_x, mundo_y):
            print(f"❌ Tap bloqueado: destino não-walkable ({mundo_x:.0f}, {mundo_y:.0f})")
            return False

        # 4. Tudo OK, executar tap
        print(f"✅ Tap validado: ({tela_x}, {tela_y}) -> mundo ({mundo_x:.0f}, {mundo_y:.0f})")

        executar_tap_callback(tela_x, tela_y)

        # 5. Iniciar rastreamento de movimento
        self.iniciar_movimento(mundo_x, mundo_y)

        return True

    def imprimir_status(self):
        """Imprime status atual do mapa virtual"""
        print("\n" + "=" * 70)
        print("🗺️ STATUS DO MAPA VIRTUAL")
        print("=" * 70)

        if self.player_x is None:
            print("❌ Posição desconhecida (precisa GPS inicial)")
        else:
            print(f"📍 Posição virtual: ({self.player_x:.0f}, {self.player_y:.0f})")
            print(f"🗺️ Bioma atual: {self.obter_bioma_atual()}")

            tempo_gps = time.time() - self.ultimo_gps
            print(f"📡 Último GPS: {tempo_gps:.0f}s atrás")

            if self.movimento_ativo:
                tempo_movimento = time.time() - self.movimento_inicio
                print(f"🏃 Movimento ativo:")
                print(f"   Destino: ({self.movimento_destino_x:.0f}, {self.movimento_destino_y:.0f})")
                print(f"   Tempo decorrido: {tempo_movimento:.3f}s / {self.movimento_tempo_estimado:.3f}s")
            else:
                print(f"💤 Sem movimento ativo")

        print("=" * 70)


if __name__ == "__main__":
    """
    Teste básico do mapa virtual
    """
    print("🧪 Testando Mapa Virtual com Tempo...\n")

    try:
        mapa = MapaVirtualComTempo()

        # Simular GPS inicial
        print("\n📡 Simulando GPS inicial (Deserto)...")
        mapa.atualizar_posicao_gps(374, 1342)

        mapa.imprimir_status()

        # Testar validação
        print("\n🧪 Testando validações...")

        # Teste 1: Click walkable
        mundo_x, mundo_y = mapa.converter_tela_para_mundo(900, 450)
        print(f"\nClick em (900, 450) -> mundo ({mundo_x:.0f}, {mundo_y:.0f})")
        print(f"   Walkable? {mapa.validar_click(mundo_x, mundo_y)}")

        # Teste 2: Click em parede (exemplo)
        mundo_x, mundo_y = mapa.converter_tela_para_mundo(1500, 100)
        print(f"\nClick em (1500, 100) -> mundo ({mundo_x:.0f}, {mundo_y:.0f})")
        print(f"   Walkable? {mapa.validar_click(mundo_x, mundo_y)}")

        print("\n✅ Teste concluído!")

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
