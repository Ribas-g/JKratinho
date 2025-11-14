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

# Importar GPS
sys.path.append('.')
from gps_ncc_realtime import GPSRealtimeNCC


class CalibradorVelocidade:
    def __init__(self):
        """Inicializa calibrador"""
        self.gps = GPSRealtimeNCC()
        # Usar device do GPS (já conectado)
        self.device = self.gps.device

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

    def capturar_tela(self):
        """Captura screenshot do dispositivo"""
        try:
            return self.gps.capture_screen()
        except Exception as e:
            print(f"❌ Erro ao capturar tela: {e}")
            return None

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

        # Threshold: precisa de pelo menos 50 pixels verdes para considerar linha presente
        return pixels_verdes > 50

    def executar_tap(self, x, y):
        """Executa tap em coordenada específica"""
        try:
            self.device.shell(f"input tap {x} {y}")
            return True
        except Exception as e:
            print(f"❌ Erro ao executar tap: {e}")
            return False

    def medir_movimento(self, destino_x, destino_y, distancia_tiles):
        """
        Mede tempo de movimento até destino
        Retorna tempo em segundos ou None se falhou
        """
        print(f"\n📍 Testando movimento de {distancia_tiles} tiles...")
        print(f"   Destino: ({destino_x}, {destino_y})")

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
            # Calcular destino em pixels (ir para direita)
            offset_pixels = distancia_tiles * self.pixels_por_tile
            destino_x = self.centro_x + offset_pixels
            destino_y = self.centro_y

            # Garantir que destino está dentro da tela
            if destino_x > 1500:
                destino_x = 1500

            # Fazer 3 medições para cada distância
            medicoes_distancia = []

            for tentativa in range(3):
                print(f"\n   Tentativa {tentativa + 1}/3:")
                duracao = self.medir_movimento(destino_x, destino_y, distancia_tiles)

                if duracao is not None:
                    medicoes_distancia.append(duracao)

                    # Calcular pixels percorridos
                    pixels = distancia_tiles * self.pixels_por_tile
                    velocidade = pixels / duracao if duracao > 0 else 0

                    print(f"      ⏱️ Tempo: {duracao:.3f}s")
                    print(f"      📏 Pixels: {pixels}")
                    print(f"      🏃 Velocidade: {velocidade:.1f} px/s")
                else:
                    print(f"      ❌ Medição falhou")

                # Delay entre medições
                time.sleep(1)

            # Calcular média para esta distância
            if medicoes_distancia:
                media = sum(medicoes_distancia) / len(medicoes_distancia)
                pixels = distancia_tiles * self.pixels_por_tile
                velocidade_media = pixels / media if media > 0 else 0

                self.medicoes.append({
                    'distancia_tiles': distancia_tiles,
                    'pixels': pixels,
                    'tempo_medio': media,
                    'velocidade_px_s': velocidade_media,
                    'medicoes_individuais': medicoes_distancia
                })

                print(f"\n   📊 Média para {distancia_tiles} tiles:")
                print(f"      ⏱️ Tempo: {media:.3f}s")
                print(f"      🏃 Velocidade: {velocidade_media:.1f} px/s")

        # 3. Calcular velocidade global
        print("\n" + "=" * 70)
        print("📊 RESULTADOS FINAIS")
        print("=" * 70)

        if not self.medicoes:
            print("❌ Nenhuma medição bem-sucedida")
            return False

        # Calcular média ponderada (dar mais peso para distâncias maiores)
        total_pixels = sum(m['pixels'] for m in self.medicoes)
        total_tempo = sum(m['tempo_medio'] for m in self.medicoes)

        velocidade_global = total_pixels / total_tempo if total_tempo > 0 else 0
        tempo_por_tile = self.pixels_por_tile / velocidade_global if velocidade_global > 0 else 0

        print(f"\n🏃 Velocidade média global: {velocidade_global:.1f} pixels/segundo")
        print(f"⏱️ Tempo por tile (32px): {tempo_por_tile:.3f} segundos")
        print(f"\n📋 Detalhamento por distância:")

        for m in self.medicoes:
            print(f"   {m['distancia_tiles']} tiles ({m['pixels']}px): {m['tempo_medio']:.3f}s @ {m['velocidade_px_s']:.1f} px/s")

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
        sucesso = calibrador.calibrar()

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
