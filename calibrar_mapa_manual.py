"""
CALIBRADOR MANUAL DE ESCALA DO MAPA

Permite ajustar manualmente o fator de escala para conversão mundo → mapa
até os clicks ficarem certinhos e a linha verde aparecer.

Uso:
1. Escolhe direção (↑↓←→)
2. Escolhe quantidade de tiles (1, 2, 3...)
3. Ajusta fator de escala
4. Clica no mapa e vê se linha verde aparece correta
"""

import cv2
import numpy as np
import time
import sys

sys.path.append('.')
from gps_ncc_realtime import GPSRealtimeNCC


class CalibradorManual:
    def __init__(self):
        """Inicializa calibrador manual"""
        print("🚀 Inicializando GPS...")
        self.gps = GPSRealtimeNCC()
        self.device = self.gps.device

        # Centro do mapa (player sempre aqui)
        self.centro_mapa_x = 800
        self.centro_mapa_y = 450

        # Fator de escala inicial (ajustável)
        self.fator_escala = 5.0

        # Tamanho do tile em pixels no mundo
        self.pixels_por_tile = 32

        # Posição do player
        self.player_x = None
        self.player_y = None

        print("✅ Inicialização completa!\n")

    def executar_tap(self, x, y):
        """Executa tap em coordenada específica"""
        try:
            self.device.shell(f"input tap {x} {y}")
            return True
        except Exception as e:
            print(f"❌ Erro ao executar tap: {e}")
            return False

    def capturar_tela(self):
        """Captura screenshot do dispositivo"""
        try:
            return self.gps.capture_screen()
        except Exception as e:
            print(f"❌ Erro ao capturar tela: {e}")
            return None

    def calcular_click_mapa(self, direcao, tiles):
        """
        Calcula onde clicar no mapa baseado em direção e quantidade de tiles

        Args:
            direcao: 'cima', 'baixo', 'esquerda', 'direita'
            tiles: quantidade de tiles para mover

        Returns:
            (x, y): coordenadas para clicar no mapa
        """
        # Delta em tiles
        if direcao == 'cima':
            delta_tiles_x = 0
            delta_tiles_y = -tiles
        elif direcao == 'baixo':
            delta_tiles_x = 0
            delta_tiles_y = tiles
        elif direcao == 'esquerda':
            delta_tiles_x = -tiles
            delta_tiles_y = 0
        elif direcao == 'direita':
            delta_tiles_x = tiles
            delta_tiles_y = 0
        else:
            return None

        # Converter tiles → pixels no mapa
        # Fórmula: delta_tiles * fator_escala = pixels no mapa
        delta_mapa_x = delta_tiles_x * self.fator_escala
        delta_mapa_y = delta_tiles_y * self.fator_escala

        # Posição final no mapa (player sempre no centro)
        mapa_x = int(self.centro_mapa_x + delta_mapa_x)
        mapa_y = int(self.centro_mapa_y + delta_mapa_y)

        return (mapa_x, mapa_y)

    def detectar_linha_verde(self, img):
        """
        Detecta se há linha verde no mapa

        Returns:
            bool: True se detectou linha verde
        """
        if img is None:
            return False

        # Converter para HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Linha verde: #00ff00 (verde puro)
        verde_lower = np.array([50, 150, 150])
        verde_upper = np.array([70, 255, 255])

        # Criar máscara
        mask = cv2.inRange(hsv, verde_lower, verde_upper)

        # Contar pixels verdes
        pixels_verdes = cv2.countNonZero(mask)

        # Se encontrou pelo menos 100 pixels verdes, tem linha
        return pixels_verdes > 100

    def menu_principal(self):
        """Menu principal interativo"""
        print("=" * 70)
        print("🗺️ CALIBRADOR MANUAL DE ESCALA DO MAPA")
        print("=" * 70)

        # Abrir mapa
        print("\n📖 Abrindo mapa...")
        self.gps.click_button('open')
        time.sleep(1.0)
        print("   ✅ Mapa aberto!")

        # GPS inicial
        print("\n📡 Obtendo posição GPS...")
        resultado = self.gps.get_current_position(keep_map_open=True, verbose=False)

        if not resultado or 'x' not in resultado:
            print("❌ GPS falhou")
            self.gps.click_button('close')
            return

        self.player_x = resultado['x']
        self.player_y = resultado['y']
        print(f"   ✅ Posição: ({self.player_x}, {self.player_y})")
        print(f"   🗺️ Zona: {resultado.get('zone', 'Desconhecida')}")

        try:
            while True:
                print("\n" + "=" * 70)
                print(f"📏 FATOR DE ESCALA ATUAL: {self.fator_escala:.2f}")
                print("=" * 70)
                print("\n🎯 ESCOLHA A DIREÇÃO:")
                print("   1 - ↑ CIMA (Norte)")
                print("   2 - ↓ BAIXO (Sul)")
                print("   3 - ← ESQUERDA (Oeste)")
                print("   4 - → DIREITA (Leste)")
                print("\n⚙️ AJUSTES:")
                print("   + - Aumentar fator de escala (+0.1)")
                print("   - - Diminuir fator de escala (-0.1)")
                print("   ++ - Aumentar muito (+1.0)")
                print("   -- - Diminuir muito (-1.0)")
                print("\n   q - Sair e fechar mapa")

                escolha = input("\nSua escolha: ").strip().lower()

                if escolha == 'q':
                    print("\n👋 Saindo...")
                    break

                # Ajustar fator de escala
                if escolha == '+':
                    self.fator_escala += 0.1
                    print(f"   📏 Novo fator: {self.fator_escala:.2f}")
                    continue
                elif escolha == '-':
                    self.fator_escala -= 0.1
                    print(f"   📏 Novo fator: {self.fator_escala:.2f}")
                    continue
                elif escolha == '++':
                    self.fator_escala += 1.0
                    print(f"   📏 Novo fator: {self.fator_escala:.2f}")
                    continue
                elif escolha == '--':
                    self.fator_escala -= 1.0
                    print(f"   📏 Novo fator: {self.fator_escala:.2f}")
                    continue

                # Mapear escolha → direção
                direcoes = {
                    '1': 'cima',
                    '2': 'baixo',
                    '3': 'esquerda',
                    '4': 'direita'
                }

                if escolha not in direcoes:
                    print("   ❌ Opção inválida!")
                    continue

                direcao = direcoes[escolha]

                # Pedir quantidade de tiles
                try:
                    tiles = int(input("   📏 Quantos tiles? (1-10): "))
                    if tiles < 1 or tiles > 10:
                        print("   ❌ Valor inválido! Use 1-10")
                        continue
                except ValueError:
                    print("   ❌ Digite um número válido!")
                    continue

                # Calcular onde clicar
                coords = self.calcular_click_mapa(direcao, tiles)
                if coords is None:
                    print("   ❌ Erro ao calcular coordenadas")
                    continue

                mapa_x, mapa_y = coords

                # Mostrar informações
                print(f"\n   🎯 TESTE: {tiles} tiles para {direcao.upper()}")
                print(f"   📐 Fator de escala: {self.fator_escala:.2f}")
                print(f"   📍 Centro do mapa: ({self.centro_mapa_x}, {self.centro_mapa_y})")
                print(f"   📍 Click no mapa: ({mapa_x}, {mapa_y})")
                print(f"   📏 Delta: ({mapa_x - self.centro_mapa_x}, {mapa_y - self.centro_mapa_y}) pixels")

                # Executar click
                print(f"\n   👆 Clicando...")
                if not self.executar_tap(mapa_x, mapa_y):
                    print("   ❌ Falha ao clicar")
                    continue

                time.sleep(0.8)

                # Capturar tela e verificar linha verde
                print("   🟢 Verificando linha verde...")
                img = self.capturar_tela()

                # Salvar screenshot
                filename = f'DEBUG_manual_{direcao}_{tiles}tiles_fator{self.fator_escala:.1f}.png'
                try:
                    cv2.imwrite(filename, img)
                    print(f"   💾 Screenshot salvo: {filename}")
                except:
                    pass

                tem_linha = self.detectar_linha_verde(img)

                if tem_linha:
                    print("   ✅ LINHA VERDE DETECTADA!")
                    print(f"   🎉 Fator de escala {self.fator_escala:.2f} parece estar CORRETO!")
                else:
                    print("   ⚠️ Linha verde NÃO detectada")
                    print("   💡 Dica: Ajuste o fator de escala (+/-) ou tente outra direção")

                # Perguntar se quer aguardar movimento
                aguardar = input("\n   ⏱️ Aguardar movimento completar? (s/n): ").strip().lower()
                if aguardar == 's':
                    print("   ⏳ Aguardando 3 segundos...")
                    time.sleep(3)

                    # GPS de verificação
                    print("   📡 Verificando posição após movimento...")
                    resultado_final = self.gps.get_current_position(keep_map_open=True, verbose=False)

                    if resultado_final and 'x' in resultado_final:
                        delta_x = resultado_final['x'] - self.player_x
                        delta_y = resultado_final['y'] - self.player_y

                        print(f"   📍 Posição inicial: ({self.player_x}, {self.player_y})")
                        print(f"   📍 Posição final: ({resultado_final['x']}, {resultado_final['y']})")
                        print(f"   📏 Movimento real: ({delta_x}, {delta_y}) pixels")

                        tiles_reais = (abs(delta_x) + abs(delta_y)) / self.pixels_por_tile
                        print(f"   📏 Distância real: {tiles_reais:.1f} tiles")

                        # Atualizar posição
                        self.player_x = resultado_final['x']
                        self.player_y = resultado_final['y']

        finally:
            # Fechar mapa
            print("\n📕 Fechando mapa...")
            self.gps.click_button('close')
            time.sleep(0.5)
            print("   ✅ Mapa fechado!")

            print(f"\n📊 RESULTADO FINAL:")
            print(f"   📏 Fator de escala calibrado: {self.fator_escala:.2f}")
            print(f"\n💡 Use esse valor em map_transform_config.json:")
            print(f'   "escala": {{"x": {self.fator_escala:.2f}, "y": {self.fator_escala:.2f}}}')


if __name__ == "__main__":
    try:
        calibrador = CalibradorManual()
        calibrador.menu_principal()

    except KeyboardInterrupt:
        print("\n\n⚠️ Calibração cancelada pelo usuário")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
