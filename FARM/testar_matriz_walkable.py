"""
TESTE DE MATRIZ WALKABLE - Verificação de Desalinhamento

Permite mover o player com W/A/S/D e ver em tempo real:
- Posição atual (GPS virtual)
- Área 5x5 sendo validada
- Status walkable/parede
- Coordenadas mundo vs tela
- Feedback visual ao vivo

Controles:
- W: Mover 1 tile para cima (norte)
- S: Mover 1 tile para baixo (sul)
- A: Mover 1 tile para esquerda (oeste)
- D: Mover 1 tile para direita (leste)
- ESPAÇO: Validar posição atual (mostrar área 5x5)
- R: Resetar posição (GPS real)
- ESC: Sair
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

from gps_ncc_realtime import GPSRealtimeNCC
from FARM.camera_virtual import CameraVirtual
from adbutils import adb


class TestadorMatrizWalkable:
    """Testador visual da matriz walkable"""
    
    def __init__(self):
        print("=" * 70)
        print("🧪 TESTE DE MATRIZ WALKABLE")
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
        
        # Carregar mapa para visualização
        print("🗺️ Carregando mapa para visualização...")
        mapa_path = Path(__file__).parent.parent / 'MINIMAPA CERTOPRETO.png'
        self.mapa_original = cv2.imread(str(mapa_path))
        
        if self.mapa_original is None:
            print(f"⚠️ Mapa não encontrado: {mapa_path}")
            self.mapa_original = np.zeros((1000, 1000, 3), dtype=np.uint8)
        else:
            print(f"✅ Mapa carregado: {self.mapa_original.shape[1]}x{self.mapa_original.shape[0]}")
        print()
        
        # Configurações
        self.tile_size_mundo = 4.0  # 1 tile = 4px no mundo
        self.janela_nome = "🧪 Teste Matriz Walkable"
        self.rodando = True
        
        # Estatísticas de drift
        self.drift_total = 0.0
        self.drift_max = 0.0
        self.movimentos_com_drift = 0
        self.total_movimentos = 0
        
        # Estado
        self.ultima_validacao = None
        self.movimentos_realizados = []
        self.debug_teclas = False  # Ativar para ver códigos das teclas
        
        print("✅ Sistema pronto!")
        print()
        print("=" * 70)
        print("🎮 CONTROLES:")
        print("=" * 70)
        print("  ↑ (Seta Cima) ou W - Mover 1 tile para CIMA (norte)")
        print("  ↓ (Seta Baixo) ou S - Mover 1 tile para BAIXO (sul)")
        print("  ← (Seta Esquerda) ou A - Mover 1 tile para ESQUERDA (oeste)")
        print("  → (Seta Direita) ou D - Mover 1 tile para DIREITA (leste)")
        print("  ESPAÇO - Validar posição atual (mostrar área 5x5)")
        print("  R - Resetar posição (GPS real)")
        print("  T - Toggle debug de teclas (ver códigos)")
        print("  ESC - Sair")
        print()
        print("  ⚠️ IMPORTANTE: A janela do OpenCV precisa estar em FOCO para detectar setas!")
        print("     Se as setas não funcionarem, use W/A/S/D como alternativa")
        print("=" * 70)
        print()
    
    def inicializar(self):
        """Inicializa GPS"""
        if not self.camera.inicializar_posicao():
            print("❌ Falha ao inicializar GPS!")
            return False
        return True
    
    def mover_tile(self, direcao):
        """
        Move 1 tile na direção especificada E executa clique no jogo
        
        Args:
            direcao: 'norte', 'sul', 'leste', 'oeste'
        """
        if self.camera.pos_x is None or self.camera.pos_y is None:
            print("⚠️ Posição não inicializada! Pressione R para resetar.")
            return
        
        # Calcular delta (1 tile = 4px no mundo)
        delta_x = 0
        delta_y = 0
        
        if direcao == 'norte':
            delta_y = -self.tile_size_mundo  # Y diminui para cima
        elif direcao == 'sul':
            delta_y = self.tile_size_mundo   # Y aumenta para baixo
        elif direcao == 'leste':
            delta_x = self.tile_size_mundo   # X aumenta para direita
        elif direcao == 'oeste':
            delta_x = -self.tile_size_mundo  # X diminui para esquerda
        
        # Calcular destino no mundo
        destino_x_mundo = self.camera.pos_x + delta_x
        destino_y_mundo = self.camera.pos_y + delta_y
        
        # Converter destino para tela do jogo
        resultado = self.camera.mundo_para_tela_jogo(destino_x_mundo, destino_y_mundo)
        
        if resultado[0] is None:
            print(f"   ❌ Destino fora do campo de visão!")
            return
        
        x_tela, y_tela = resultado[0], resultado[1]
        alcancavel, eh_parede = resultado[2], resultado[3]
        
        # Mostrar status
        pos_antes = (self.camera.pos_x, self.camera.pos_y)
        print(f"\n   🎯 MOVENDO {direcao.upper()}:")
        print(f"      De: ({pos_antes[0]:.1f}, {pos_antes[1]:.1f})")
        print(f"      Para: ({destino_x_mundo:.1f}, {destino_y_mundo:.1f})")
        print(f"      Clique tela: ({x_tela}, {y_tela})")
        
        # Validar se é walkable ANTES de clicar (COM DEBUG para ver o que está acontecendo)
        # Para navegação, NÃO permitir expansão (centro deve ser walkable)
        print(f"\n   🔍 VALIDANDO DESTINO ANTES DE CLICAR:")
        eh_walkable = self.camera.validar_posicao(destino_x_mundo, destino_y_mundo, debug=True, permitir_expansao=False)
        
        # Status da validação
        if eh_walkable:
            print(f"      ✅ CHÃO (walkable)")
        else:
            print(f"      🚫 PAREDE (não walkable)")
            print(f"      ⚠️ Mas clicando mesmo assim para testar...")
        
        # Executar clique no jogo
        try:
            self.device.shell(f"input tap {x_tela} {y_tela}")
            print(f"      🖱️ Clique executado no jogo!")
        except Exception as e:
            print(f"      ❌ Erro ao clicar: {e}")
            return
        
        # Aguardar movimento completar
        time.sleep(0.3)  # Tempo mínimo para movimento (otimizado para velocidade)
        
        # DEAD RECKONING: Assumir que chegou no destino (sem GPS a cada movimento)
        # O GPS será usado apenas para correção periódica (a cada 5 movimentos)
        self.camera.pos_x = destino_x_mundo
        self.camera.pos_y = destino_y_mundo
        self.camera.movimentos_desde_gps += 1
        
        # Atualizar estatísticas
        self.total_movimentos += 1
        
        # Verificar se precisa corrigir com GPS (correção periódica)
        if self.camera.movimentos_desde_gps >= self.camera.max_movimentos_sem_gps:
            print(f"\n   📡 Correção GPS periódica ({self.camera.movimentos_desde_gps} movimentos)...")
            try:
                posicao_real = self.gps.get_current_position(verbose=False, keep_map_open=False)
                if posicao_real and 'x' in posicao_real and 'y' in posicao_real:
                    pos_real_x = posicao_real['x']
                    pos_real_y = posicao_real['y']
                    
                    # Calcular drift acumulado
                    drift_x = abs(pos_real_x - self.camera.pos_x)
                    drift_y = abs(pos_real_y - self.camera.pos_y)
                    drift_total = math.sqrt(drift_x**2 + drift_y**2)
                    
                    # Atualizar posição com GPS real
                    pos_antes = (self.camera.pos_x, self.camera.pos_y)
                    self.camera.pos_x = pos_real_x
                    self.camera.pos_y = pos_real_y
                    self.camera.movimentos_desde_gps = 0
                    
                    print(f"      📍 GPS Real: ({pos_real_x:.1f}, {pos_real_y:.1f})")
                    print(f"      📍 Virtual: ({pos_antes[0]:.1f}, {pos_antes[1]:.1f})")
                    if drift_total > 1.0:
                        print(f"      ⚠️ DRIFT acumulado: {drift_total:.2f}px (dx={drift_x:.1f}, dy={drift_y:.1f})")
                        self.movimentos_com_drift += 1
                        self.drift_total += drift_total
                        if drift_total > self.drift_max:
                            self.drift_max = drift_total
                    else:
                        print(f"      ✅ Drift mínimo ({drift_total:.2f}px)")
                    
                    # Estatísticas
                    if self.total_movimentos > 0:
                        drift_medio = self.drift_total / self.movimentos_com_drift if self.movimentos_com_drift > 0 else 0.0
                        percentual_drift = (self.movimentos_com_drift / self.total_movimentos) * 100
                        print(f"      📊 Estatísticas: {self.total_movimentos} movimentos, {self.movimentos_com_drift} com drift ({percentual_drift:.1f}%), drift médio: {drift_medio:.2f}px, máximo: {self.drift_max:.2f}px")
                else:
                    print(f"      ⚠️ GPS não retornou posição válida, mantendo posição virtual")
            except Exception as e:
                print(f"      ⚠️ Erro ao atualizar GPS: {e}, mantendo posição virtual")
        else:
            # Mostrar contador de movimentos até próxima correção GPS
            movimentos_restantes = self.camera.max_movimentos_sem_gps - self.camera.movimentos_desde_gps
            print(f"      📍 Posição virtual: ({destino_x_mundo:.1f}, {destino_y_mundo:.1f})")
            print(f"      🔄 GPS em {movimentos_restantes} movimento(s)")
        
        # Registrar movimento
        self.movimentos_realizados.append({
            'antes': pos_antes,
            'depois': (self.camera.pos_x, self.camera.pos_y),  # Posição virtual (dead reckoning)
            'direcao': direcao,
            'eh_walkable': eh_walkable
        })
        
        # Validar posição final (com debug)
        print(f"\n   🔍 VALIDANDO POSIÇÃO FINAL:")
        self.validar_posicao_atual()
    
    def validar_posicao_atual(self):
        """Valida posição atual e mostra área 5x5"""
        if self.camera.pos_x is None or self.camera.pos_y is None:
            return
        
        x_mundo = self.camera.pos_x
        y_mundo = self.camera.pos_y
        
        print(f"\n🔍 VALIDANDO POSIÇÃO:")
        print(f"   Mundo: ({x_mundo:.1f}, {y_mundo:.1f})")
        
        # Validar com debug (sem expansão - queremos saber se o centro é walkable)
        eh_walkable = self.camera.validar_posicao(x_mundo, y_mundo, debug=True, permitir_expansao=False)
        
        # Converter para tela
        resultado = self.camera.mundo_para_tela_jogo(x_mundo, y_mundo)
        if resultado[0] is not None:
            x_tela, y_tela = resultado[0], resultado[1]
            print(f"   Tela: ({x_tela}, {y_tela})")
        
        # Guardar resultado
        self.ultima_validacao = {
            'x_mundo': x_mundo,
            'y_mundo': y_mundo,
            'eh_walkable': eh_walkable,
            'x_tela': resultado[0] if resultado[0] is not None else None,
            'y_tela': resultado[1] if resultado[1] is not None else None
        }
        
        status = "✅ WALKABLE" if eh_walkable else "🚫 PAREDE"
        print(f"   Status: {status}")
        print()
    
    def resetar_posicao(self):
        """Reseta posição usando GPS real"""
        print("\n🔄 Resetando posição via GPS...")
        if self.camera.inicializar_posicao():
            self.movimentos_realizados = []
            self.validar_posicao_atual()
            print("✅ Posição resetada!")
        else:
            print("❌ Falha ao resetar posição!")
        print()
    
    def desenhar_visualizacao(self):
        """Desenha visualização completa"""
        if self.camera.pos_x is None or self.camera.pos_y is None:
            return
        
        # Criar cópia do mapa
        img = self.mapa_original.copy()
        
        # 1. Desenhar histórico de movimentos
        if len(self.movimentos_realizados) > 0:
            for i, mov in enumerate(self.movimentos_realizados):
                x1, y1 = int(mov['antes'][0]), int(mov['antes'][1])
                # Usar posição após movimento
                if 'depois' in mov:
                    x2, y2 = int(mov['depois'][0]), int(mov['depois'][1])
                elif 'real' in mov:
                    x2, y2 = int(mov['real'][0]), int(mov['real'][1])
                elif 'esperado' in mov:
                    x2, y2 = int(mov['esperado'][0]), int(mov['esperado'][1])
                else:
                    # Fallback
                    x2, y2 = x1, y1
                
                # Linha do movimento (cinza padrão)
                cv2.line(img, (x1, y1), (x2, y2), (128, 128, 128), 2)
                
                # Ponto inicial
                cv2.circle(img, (x1, y1), 3, (200, 200, 200), -1)
        
        # 2. Desenhar área 5x5 da última validação
        if self.ultima_validacao:
            x = int(self.ultima_validacao['x_mundo'])
            y = int(self.ultima_validacao['y_mundo'])
            eh_walkable = self.ultima_validacao['eh_walkable']
            
            # Cor baseada no status
            cor_area = (0, 255, 0) if eh_walkable else (0, 0, 255)  # Verde ou Vermelho
            
            # Desenhar área 5x5
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    px = x + dx
                    py = y + dy
                    
                    if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                        # Verificar valor na matriz
                        if self.camera.matriz_walkable is not None:
                            try:
                                valor = self.camera.matriz_walkable[px, py]
                                if valor == 1:
                                    cv2.circle(img, (px, py), 2, (0, 255, 0), -1)  # Verde = walkable
                                else:
                                    cv2.circle(img, (px, py), 2, (0, 0, 255), -1)  # Vermelho = parede
                            except:
                                pass
                        
                        # Desenhar borda da área 5x5
                        if abs(dx) == 2 or abs(dy) == 2:
                            cv2.rectangle(img, (px-1, py-1), (px+1, py+1), cor_area, 1)
        
        # 3. Desenhar posição atual (círculo grande)
        x_atual = int(self.camera.pos_x)
        y_atual = int(self.camera.pos_y)
        
        # Círculo externo (posição atual)
        cv2.circle(img, (x_atual, y_atual), 8, (255, 0, 255), 2)  # Magenta
        cv2.circle(img, (x_atual, y_atual), 3, (255, 0, 255), -1)
        
        # 4. Desenhar FOV (campo de visão)
        half_w = self.camera.fov_largura_mapa / 2
        half_h = self.camera.fov_altura_mapa / 2
        
        x1 = int(self.camera.pos_x - half_w)
        y1 = int(self.camera.pos_y - half_h)
        x2 = int(self.camera.pos_x + half_w)
        y2 = int(self.camera.pos_y + half_h)
        
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 2)  # Amarelo
        
        # 5. Adicionar informações de texto
        y_texto = 30
        info_lines = [
            f"🧪 TESTE DE MATRIZ WALKABLE",
            f"Posição Mundo: ({self.camera.pos_x:.1f}, {self.camera.pos_y:.1f})",
            f"Movimentos: {len(self.movimentos_realizados)}",
        ]
        
        if self.ultima_validacao:
            status = "✅ WALKABLE" if self.ultima_validacao['eh_walkable'] else "🚫 PAREDE"
            info_lines.append(f"Última Validação: {status}")
            if self.ultima_validacao['x_tela'] is not None:
                info_lines.append(f"Tela: ({self.ultima_validacao['x_tela']}, {self.ultima_validacao['y_tela']})")
        
        info_lines.extend([
            "",
            "↑↓←→ (Setas) | ESPAÇO=Validar | R=Reset | ESC=Sair"
        ])
        
        # Fundo semi-transparente
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (600, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        
        # Texto
        for i, line in enumerate(info_lines):
            cv2.putText(
                img,
                line,
                (20, y_texto + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
        
        # 6. Mostrar imagem
        cv2.namedWindow(self.janela_nome, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.janela_nome, 1400, 900)
        cv2.imshow(self.janela_nome, img)
    
    def executar_clique_teste(self, x_tela, y_tela):
        """
        Executa clique de teste na tela (simula movimento)
        
        Args:
            x_tela, y_tela: Coordenadas na tela
        """
        # Converter para mundo
        x_mundo, y_mundo = self.camera.tela_para_mundo(x_tela, y_tela)
        
        if x_mundo is None:
            return
        
        # Atualizar posição virtual
        pos_antes = (self.camera.pos_x, self.camera.pos_y)
        self.camera.pos_x = x_mundo
        self.camera.pos_y = y_mundo
        pos_depois = (self.camera.pos_x, self.camera.pos_y)
        
        # Calcular distância
        dist = math.sqrt((pos_depois[0] - pos_antes[0])**2 + (pos_depois[1] - pos_antes[1])**2)
        tiles = dist / self.tile_size_mundo
        
        print(f"   🖱️ Clique teste: Tela=({x_tela}, {y_tela}) → Mundo=({x_mundo:.1f}, {y_mundo:.1f})")
        print(f"      Distância: {dist:.1f}px = {tiles:.1f} tiles")
        
        # Validar
        self.validar_posicao_atual()
    
    def run(self):
        """Loop principal"""
        if not self.inicializar():
            return
        
        print("\n🎮 Iniciando teste visual...")
        print("   Use as teclas para mover e verificar a matriz!\n")
        
        # Validar posição inicial
        self.validar_posicao_atual()
        
        while self.rodando:
            # Desenhar visualização
            self.desenhar_visualizacao()
            
            # Processar teclas - usar waitKeyEx para detectar setas
            # Timeout maior (100ms) para melhor detecção e garantir que janela está em foco
            key = cv2.waitKeyEx(100)
            
            # ESC (sempre verificar primeiro)
            if key == 27 or key == -1:  # ESC ou nenhuma tecla
                if key == 27:
                    print("\n👋 Encerrando teste...")
                    break
                continue
            
            # Ignorar key=0 (pode ser ruído)
            if key == 0:
                continue
            
            # Debug: mostrar código da tecla se ativado
            if self.debug_teclas:
                key_ascii = key & 0xFF
                print(f"   🔍 Tecla pressionada: key={key} (0x{key:08X}), key_ascii={key_ascii}")
            
            # Teclas normais (ASCII)
            key_ascii = key & 0xFF
            if key_ascii == ord(' '):  # ESPAÇO
                self.validar_posicao_atual()
            elif key_ascii == ord('r') or key_ascii == ord('R'):
                self.resetar_posicao()
            elif key_ascii == ord('t') or key_ascii == ord('T'):
                # Toggle debug de teclas (mudei para T para não conflitar com D)
                self.debug_teclas = not self.debug_teclas
                print(f"   🔍 Debug teclas: {'ON' if self.debug_teclas else 'OFF'}")
            # Fallback: usar W/A/S/D também
            elif key_ascii == ord('w') or key_ascii == ord('W'):
                self.mover_tile('norte')
            elif key_ascii == ord('s') or key_ascii == ord('S'):
                self.mover_tile('sul')
            elif key_ascii == ord('a') or key_ascii == ord('A'):
                self.mover_tile('oeste')
            elif key_ascii == ord('d') or key_ascii == ord('D'):
                self.mover_tile('leste')
            
            # Setas do teclado - waitKeyEx retorna códigos especiais
            # Códigos comuns no Windows: 2490368=↑, 2621440=↓, 2424832=←, 2555904=→
            # Também verificar códigos alternativos
            seta_detectada = False
            if key == 2490368 or key == 0x260000 or key == 63232:  # Seta para cima (↑)
                self.mover_tile('norte')
                seta_detectada = True
            elif key == 2621440 or key == 0x280000 or key == 63233:  # Seta para baixo (↓)
                self.mover_tile('sul')
                seta_detectada = True
            elif key == 2424832 or key == 0x250000 or key == 63234:  # Seta para esquerda (←)
                self.mover_tile('oeste')
                seta_detectada = True
            elif key == 2555904 or key == 0x270000 or key == 63235:  # Seta para direita (→)
                self.mover_tile('leste')
                seta_detectada = True
            
            # Se não detectou seta mas key > 255, pode ser uma seta com código diferente
            if not seta_detectada and key > 255 and self.debug_teclas:
                print(f"   ⚠️ Tecla especial não reconhecida: {key} (0x{key:08X}) - pode ser uma seta")
                print(f"      💡 Tente usar W/A/S/D como alternativa")
        
        cv2.destroyAllWindows()
        print("\n✅ Teste finalizado!")


if __name__ == "__main__":
    try:
        testador = TestadorMatrizWalkable()
        testador.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()

