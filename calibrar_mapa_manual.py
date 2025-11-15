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
import json
from pathlib import Path

sys.path.append('.')
from gps_ncc_realtime import GPSRealtimeNCC
from fast_capture import FastCapture


class CalibradorManual:
    def __init__(self):
        """Inicializa calibrador manual"""
        print("🚀 Inicializando GPS...")
        self.gps = GPSRealtimeNCC()
        self.device = self.gps.device

        # Inicializar captura rápida (scrcpy ou ADB)
        print("🚀 Inicializando captura rápida...")
        self.fast_capture = FastCapture(device=self.device, preferred_method='auto')
        self.fast_capture.start()

        # Centro do mapa (player sempre aqui)
        self.centro_mapa_x = 800
        self.centro_mapa_y = 450

        # Fator de escala inicial (ajustável)
        # Já calibrado manualmente como 20.0
        self.fator_escala = 20.0

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
        """Captura screenshot do dispositivo via FastCapture"""
        try:
            return self.fast_capture.get_frame(timeout=1.0)
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

    def detectar_linha_verde(self, img, retornar_contagem=False):
        """
        Detecta se há linha verde no mapa

        Args:
            img: imagem capturada
            retornar_contagem: se True, retorna (bool, pixels_verdes)

        Returns:
            bool ou (bool, int): True se detectou linha verde, opcionalmente com contagem
        """
        if img is None:
            return (False, 0) if retornar_contagem else False

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
        tem_linha = pixels_verdes > 100

        if retornar_contagem:
            return tem_linha, pixels_verdes
        return tem_linha

    def medir_velocidade(self, direcao, tiles):
        """
        Mede velocidade de movimento com timing preciso

        Args:
            direcao: 'cima', 'baixo', 'esquerda', 'direita'
            tiles: quantidade de tiles

        Returns:
            dict com resultados da medição ou None se falhou
        """
        # Calcular onde clicar
        coords = self.calcular_click_mapa(direcao, tiles)
        if coords is None:
            return None

        mapa_x, mapa_y = coords

        print(f"\n   📏 MEDIÇÃO: {tiles} tiles para {direcao.upper()}")
        print(f"   📍 Posição inicial: ({self.player_x}, {self.player_y})")
        print(f"   📍 Click no mapa: ({mapa_x}, {mapa_y})")

        # IMPORTANTE: Capturar tempo ANTES do click
        tempo_click = time.time()

        # Executar click
        print(f"   👆 Clicando...")
        self.executar_tap(mapa_x, mapa_y)

        # USAR TEMPO DO CLICK como início (linha verde aparece instantaneamente!)
        tempo_inicio = tempo_click
        print(f"   ⚡ Usando tempo do click como início (linha verde é instantânea)")

        # Pequeno delay para garantir que movimento iniciou
        time.sleep(0.1)

        # Aguardar linha verde sumir (fim do movimento)
        tempo_fim = None
        timeout = time.time() + 15.0
        ultima_contagem = 0

        print(f"   ⏱️ Aguardando movimento completar...")
        while time.time() < timeout:
            img = self.capturar_tela()
            tem_linha, pixels_verdes = self.detectar_linha_verde(img, retornar_contagem=True)
            ultima_contagem = pixels_verdes

            # CRITÉRIO MAIS RIGOROSO: linha verde sumiu = MENOS de 10 pixels verdes
            # (antes era <100, agora é <10 para ser mais preciso)
            if pixels_verdes < 10:
                tempo_fim = time.time()
                duracao = tempo_fim - tempo_inicio

                # SALVAR SCREENSHOT DO FIM (linha verde sumiu!)
                timestamp = time.strftime('%H%M%S')
                filename_fim = f'DEBUG_FIM_{tiles}tiles_{direcao}_{timestamp}.png'

                # Adicionar texto na imagem para debug
                img_debug = img.copy()
                velocidade_temp = (tiles * self.pixels_por_tile) / duracao
                cv2.putText(img_debug, f'FIM - {tiles} tiles {direcao}', (50, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(img_debug, f'Duracao: {duracao:.3f}s', (50, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(img_debug, f'Velocidade: {velocidade_temp:.1f} px/s', (50, 150),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(img_debug, f'Pixels verdes: {pixels_verdes}', (50, 200),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(img_debug, f'Tempo: {timestamp}', (50, 250),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                cv2.imwrite(filename_fim, img_debug)

                print(f"   ✅ Movimento completo em {duracao:.3f}s")
                print(f"   📊 Pixels verdes no fim: {pixels_verdes}")
                print(f"   📸 Screenshot fim: {filename_fim}")
                break
            time.sleep(0.01)  # 10ms polling = 100 FPS!

        if tempo_fim is None:
            print(f"   ⚠️ Timeout aguardando fim do movimento")
            return None

        # Calcular velocidade (usando distância solicitada, sem GPS de verificação)
        distancia_px = tiles * self.pixels_por_tile
        velocidade = distancia_px / duracao
        tempo_por_tile = self.pixels_por_tile / velocidade

        print(f"   🏃 Velocidade: {velocidade:.1f} px/s")
        print(f"   ⏱️ Tempo por tile: {tempo_por_tile:.3f}s")

        return {
            'direcao': direcao,
            'tiles_solicitados': tiles,
            'tiles_reais': tiles,
            'distancia_px': distancia_px,
            'duracao': duracao,
            'velocidade_px_s': velocidade,
            'tempo_por_tile': tempo_por_tile
        }

    def menu_principal(self):
        """Menu principal interativo"""
        print("=" * 70)
        print("🗺️ CALIBRADOR MANUAL DE ESCALA DO MAPA")
        print("=" * 70)

        # Mostrar método de captura ativo
        metodo = self.fast_capture.active_method
        latencia = self.fast_capture.get_latency_estimate() * 1000
        print(f"\n📸 CAPTURA ATIVA: {metodo.upper()}")
        print(f"   ⚡ Latência estimada: ~{latencia:.0f}ms")
        if metodo == 'scrcpy':
            print(f"   ✅ Usando captura ultra-rápida!")
        else:
            print(f"   ⚠️  Para captura 10x mais rápida, instale scrcpy")
            print(f"   💡 Veja: INSTALL_SCRCPY_WINDOWS.md")

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

        # Lista para armazenar medições
        medicoes = []

        try:
            while True:
                print("\n" + "=" * 70)
                print(f"📏 FATOR DE ESCALA ATUAL: {self.fator_escala:.2f}")
                print("=" * 70)
                print("\n🎯 MODO DE OPERAÇÃO:")
                print("   e - Testar ESCALA (ver se linha verde aparece)")
                print("   v - Calibrar VELOCIDADE (medir timing preciso)")
                print("\n⚙️ AJUSTES:")
                print("   + - Aumentar fator de escala (+0.1)")
                print("   - - Diminuir fator de escala (-0.1)")
                print("   ++ - Aumentar muito (+1.0)")
                print("   -- - Diminuir muito (-1.0)")
                print("\n   r - Ver resultados das medições")
                print("   s - Salvar resultados em arquivo")
                print("   q - Sair e fechar mapa")

                escolha = input("\nSua escolha: ").strip().lower()

                if escolha == 'q':
                    print("\n👋 Saindo...")
                    break

                # Ver resultados
                elif escolha == 'r':
                    if not medicoes:
                        print("\n   ⚠️ Nenhuma medição realizada ainda")
                        continue

                    print("\n" + "=" * 70)
                    print(f"📊 RESULTADOS DAS MEDIÇÕES ({len(medicoes)} medições)")
                    print("=" * 70)

                    for i, m in enumerate(medicoes, 1):
                        print(f"\n   {i}. {m['tiles_solicitados']} tiles → {m['direcao'].upper()}")
                        print(f"      📏 Real: {m['tiles_reais']:.1f} tiles ({m['distancia_px']}px)")
                        print(f"      ⏱️ Duração: {m['duracao']:.3f}s")
                        print(f"      🏃 Velocidade: {m['velocidade_px_s']:.1f} px/s")
                        print(f"      ⏱️ Tempo/tile: {m['tempo_por_tile']:.3f}s")

                    # Calcular média
                    vel_media = sum(m['velocidade_px_s'] for m in medicoes) / len(medicoes)
                    tempo_medio = sum(m['tempo_por_tile'] for m in medicoes) / len(medicoes)

                    print(f"\n   📊 MÉDIAS:")
                    print(f"      🏃 Velocidade média: {vel_media:.1f} px/s")
                    print(f"      ⏱️ Tempo médio por tile: {tempo_medio:.3f}s")

                    # REGRESSÃO LINEAR: distância vs tempo
                    # Isso elimina o overhead fixo!
                    if len(medicoes) >= 3:
                        import numpy as np

                        distancias = np.array([m['distancia_px'] for m in medicoes])
                        tempos = np.array([m['duracao'] for m in medicoes])

                        # Regressão linear: tempo = a * distancia + b
                        # a = 1/velocidade, b = overhead
                        coef = np.polyfit(distancias, tempos, 1)
                        velocidade_real = 1.0 / coef[0]
                        overhead = coef[1]

                        print(f"\n   📈 REGRESSÃO LINEAR (elimina overhead!):")
                        print(f"      🏃 Velocidade REAL: {velocidade_real:.1f} px/s")
                        print(f"      ⏱️ Tempo/tile REAL: {32.0/velocidade_real:.3f}s")
                        print(f"      ⚠️ Overhead fixo: {overhead:.3f}s")

                    continue

                # Salvar resultados
                elif escolha == 's':
                    if not medicoes:
                        print("\n   ⚠️ Nenhuma medição para salvar")
                        continue

                    Path("FARM").mkdir(exist_ok=True)

                    # Calcular estatísticas
                    vel_media = sum(m['velocidade_px_s'] for m in medicoes) / len(medicoes)
                    tempo_medio = sum(m['tempo_por_tile'] for m in medicoes) / len(medicoes)

                    # REGRESSÃO LINEAR para velocidade real
                    velocidade_real = vel_media
                    overhead = 0.0
                    tempo_real = tempo_medio

                    if len(medicoes) >= 3:
                        import numpy as np

                        distancias = np.array([m['distancia_px'] for m in medicoes])
                        tempos = np.array([m['duracao'] for m in medicoes])

                        # Regressão linear
                        coef = np.polyfit(distancias, tempos, 1)
                        velocidade_real = 1.0 / coef[0]
                        overhead = coef[1]
                        tempo_real = self.pixels_por_tile / velocidade_real

                        print(f"\n   📈 Regressão linear aplicada:")
                        print(f"      Overhead eliminado: {overhead:.3f}s")

                    resultado = {
                        'velocidade_px_s': velocidade_real,
                        'tempo_por_tile': tempo_real,
                        'pixels_por_tile': self.pixels_por_tile,
                        'fator_escala': self.fator_escala,
                        'overhead_fixo': overhead,
                        'metodo': 'calibracao_manual_regressao_linear',
                        'medicoes': medicoes,
                        'data': time.strftime('%Y-%m-%d %H:%M:%S')
                    }

                    filename = 'FARM/velocidade_personagem.json'
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(resultado, f, indent=2, ensure_ascii=False)

                    print(f"\n   ✅ Resultados salvos: {filename}")
                    print(f"   🏃 Velocidade REAL: {velocidade_real:.1f} px/s")
                    print(f"   ⏱️ Tempo/tile REAL: {tempo_real:.3f}s")
                    continue

                # Ajustar fator de escala
                elif escolha == '+':
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

                # Modo de teste de escala ou calibração de velocidade
                elif escolha in ['e', 'v']:
                    modo_velocidade = (escolha == 'v')

                    # Escolher direção
                    print("\n   🎯 ESCOLHA A DIREÇÃO:")
                    print("      1 - ↑ CIMA (Norte)")
                    print("      2 - ↓ BAIXO (Sul)")
                    print("      3 - ← ESQUERDA (Oeste)")
                    print("      4 - → DIREITA (Leste)")

                    dir_escolha = input("   Direção: ").strip()

                    direcoes = {
                        '1': 'cima',
                        '2': 'baixo',
                        '3': 'esquerda',
                        '4': 'direita'
                    }

                    if dir_escolha not in direcoes:
                        print("   ❌ Opção inválida!")
                        continue

                    direcao = direcoes[dir_escolha]

                    # Pedir quantidade de tiles
                    try:
                        tiles = int(input("   📏 Quantos tiles? (1-10): "))
                        if tiles < 1 or tiles > 10:
                            print("   ❌ Valor inválido! Use 1-10")
                            continue
                    except ValueError:
                        print("   ❌ Digite um número válido!")
                        continue

                    # Modo VELOCIDADE: medição completa com timing preciso
                    if modo_velocidade:
                        resultado = self.medir_velocidade(direcao, tiles)
                        if resultado:
                            medicoes.append(resultado)
                            print(f"\n   ✅ Medição {len(medicoes)} salva!")

                    # Modo ESCALA: apenas teste de linha verde
                    else:
                        coords = self.calcular_click_mapa(direcao, tiles)
                        if coords is None:
                            print("   ❌ Erro ao calcular coordenadas")
                            continue

                        mapa_x, mapa_y = coords

                        print(f"\n   🎯 TESTE: {tiles} tiles para {direcao.upper()}")
                        print(f"   📐 Fator de escala: {self.fator_escala:.2f}")
                        print(f"   📍 Click no mapa: ({mapa_x}, {mapa_y})")

                        # Executar click
                        print(f"   👆 Clicando...")
                        self.executar_tap(mapa_x, mapa_y)

                        # IMEDIATAMENTE verificar linha verde (sem delay!)
                        print("   🟢 Verificando linha verde...")
                        time.sleep(0.05)  # Mínimo delay para linha aparecer
                        img = self.capturar_tela()

                        tem_linha = self.detectar_linha_verde(img)

                        if tem_linha:
                            print("   ✅ LINHA VERDE DETECTADA!")
                            print(f"   🎉 Fator {self.fator_escala:.2f} está CORRETO!")
                        else:
                            print("   ⚠️ Linha verde NÃO detectada")
                            print("   💡 Ajuste o fator de escala (+/-)")

                else:
                    print("   ❌ Opção inválida!")
                    continue

        finally:
            # Fechar mapa
            print("\n📕 Fechando mapa...")
            self.gps.click_button('close')
            time.sleep(0.5)
            print("   ✅ Mapa fechado!")

            # Mostrar resumo
            print(f"\n" + "=" * 70)
            print(f"📊 RESUMO DA SESSÃO")
            print("=" * 70)
            print(f"   📏 Fator de escala: {self.fator_escala:.2f}")
            print(f"   📊 Medições realizadas: {len(medicoes)}")

            if medicoes:
                vel_media = sum(m['velocidade_px_s'] for m in medicoes) / len(medicoes)
                tempo_medio = sum(m['tempo_por_tile'] for m in medicoes) / len(medicoes)

                print(f"\n   🏃 Velocidade média: {vel_media:.1f} px/s")
                print(f"   ⏱️ Tempo médio por tile: {tempo_medio:.3f}s")
                print(f"\n   💡 Use 's' para salvar ou 'r' para ver detalhes!")

            print(f"\n   💾 Config para map_transform_config.json:")
            print(f'   "escala": {{"x": {self.fator_escala:.2f}, "y": {self.fator_escala:.2f}}}')


if __name__ == "__main__":
    calibrador = None
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
    finally:
        # Limpar fast_capture
        if calibrador is not None and hasattr(calibrador, 'fast_capture'):
            calibrador.fast_capture.stop()
