"""
SISTEMA INTEGRADO: NAVEGAÇÃO + FARM
Navega automaticamente para zonas e farma mobs com kiting

Features:
- Seleção de classe (Arqueiro/Guerreiro/Mago)
- Navegação automática para zona de farm
- Farm com kiting específico da classe
- Movimento ativo (procura mobs na área)
- Loop contínuo até usuário parar

Execute: python farm_integrado.py
"""

import sys
import os
import json
import time
import math
from pathlib import Path

# Adicionar diretório pai ao path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from navegador_automatico_ncc import NavegadorAutomaticoNCC
from gps_ncc_realtime import GPSRealtimeNCC
from FARM.farm_bot import ArcherFarmBot
from adbutils import adb
import cv2
import numpy as np


class FarmIntegrado:
    """Sistema integrado de navegação e farm"""

    def __init__(self):
        print("=" * 70)
        print("🎮 SISTEMA INTEGRADO: NAVEGAÇÃO + FARM")
        print("=" * 70)

        # Carregar configurações de zonas
        self.load_farm_zones()

        # Navegador (será inicializado depois)
        self.navegador = None

        # GPS (compartilhado)
        self.gps = None

        # Farm bot (será inicializado depois)
        self.farm_bot = None

        # Configurações
        self.selected_class = None
        self.selected_zone = None
        self.running = False

    def load_farm_zones(self):
        """Carrega configurações de zonas de farm"""
        try:
            zones_path = Path(__file__).parent / "farm_zones.json"
            with open(zones_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.zones = data['zones']
            self.class_configs = data['class_configs']
            print("✅ Configurações de zonas carregadas!")

        except FileNotFoundError:
            print("❌ farm_zones.json não encontrado!")
            sys.exit(1)

    def selecionar_classe(self):
        """Menu de seleção de classe"""
        print("\n" + "=" * 70)
        print("⚔️ SELEÇÃO DE CLASSE")
        print("=" * 70)

        classes = list(self.class_configs.keys())

        for i, class_key in enumerate(classes, 1):
            config = self.class_configs[class_key]
            print(f"  [{i}] {config['name']}")
            print(f"      Estilo: {config['kiting_style']}")
            print(f"      Distância ideal: {config['ideal_distance']} tiles")
            print(f"      Padrão: {config['movement_pattern']}")
            print()

        while True:
            try:
                escolha = input("Escolha sua classe (1-3): ").strip()
                idx = int(escolha) - 1

                if 0 <= idx < len(classes):
                    self.selected_class = classes[idx]
                    print(f"\n✅ Classe selecionada: {self.class_configs[self.selected_class]['name']}")
                    return
                else:
                    print("❌ Opção inválida!")

            except (ValueError, KeyError):
                print("❌ Opção inválida!")

    def selecionar_zona(self):
        """Menu de seleção de zona de farm"""
        print("\n" + "=" * 70)
        print("🗺️ SELEÇÃO DE ZONA DE FARM")
        print("=" * 70)

        zone_names = list(self.zones.keys())

        for i, zone_name in enumerate(zone_names, 1):
            zone = self.zones[zone_name]
            mobs_str = ", ".join(zone['mobs'])
            print(f"  [{i:2d}] {zone_name}")
            print(f"       Mobs: {mobs_str}")
            print(f"       Level: {zone['level_range']}")
            print(f"       {zone['description']}")
            print()

        while True:
            try:
                escolha = input("Escolha a zona de farm (número): ").strip()
                idx = int(escolha) - 1

                if 0 <= idx < len(zone_names):
                    self.selected_zone = zone_names[idx]
                    print(f"\n✅ Zona selecionada: {self.selected_zone}")
                    return
                else:
                    print("❌ Opção inválida!")

            except (ValueError, KeyError):
                print("❌ Opção inválida!")

    def inicializar_sistemas(self):
        """Inicializa navegador e farm bot"""
        print("\n" + "=" * 70)
        print("🚀 INICIALIZANDO SISTEMAS...")
        print("=" * 70)

        # Inicializar navegador
        print("\n📍 Inicializando Navegador...")
        self.navegador = NavegadorAutomaticoNCC()
        self.gps = self.navegador.gps
        print("✅ Navegador pronto!")

        # Inicializar farm bot
        print("\n🤖 Inicializando Farm Bot...")

        # Caminho absoluto do modelo (resolve corretamente no Windows e Linux)
        model_path = Path(__file__).parent / "rucoy_model_final.pt"
        print(f"   📦 Caminho do modelo: {model_path}")

        self.farm_bot = ArcherFarmBot(model_path=str(model_path))

        if not self.farm_bot.conectar_bluestacks():
            print("❌ Falha ao conectar BlueStacks!")
            return False

        if not self.farm_bot.carregar_modelo():
            print("❌ Falha ao carregar modelo YOLO!")
            print(f"   ⚠️ Verifique se o arquivo existe: {model_path}")
            return False

        # Compartilhar dispositivo ADB
        self.farm_bot.device = self.gps.device

        # Configurar kiting baseado na classe
        self.configurar_kiting_classe()

        print("✅ Farm Bot pronto!")
        return True

    def configurar_kiting_classe(self):
        """Configura kiting baseado na classe selecionada"""
        config = self.class_configs[self.selected_class]

        # Atualizar configurações do farm bot
        self.farm_bot.config.ideal_distance = config['ideal_distance']
        self.farm_bot.config.min_safe_distance = config['min_distance']
        self.farm_bot.config.max_attack_range = config['max_distance']
        self.farm_bot.action_cooldown = config['attack_cooldown']

        # Configurar combat style (melee vs ranged)
        if self.selected_class == 'warrior':
            self.farm_bot.combat_style = "melee"
        else:
            self.farm_bot.combat_style = "ranged"

        print(f"\n⚙️ Configurações de {config['name']}:")
        print(f"   Estilo de combate: {self.farm_bot.combat_style.upper()}")
        print(f"   Distância ideal: {config['ideal_distance']} tiles")
        print(f"   Distância mínima: {config['min_distance']} tiles")
        print(f"   Alcance máximo: {config['max_distance']} tiles")
        print(f"   Padrão de movimento: {config['movement_pattern']}")

    def navegar_para_zona(self):
        """Navega para a zona de farm selecionada"""
        print("\n" + "=" * 70)
        print(f"🧭 NAVEGANDO PARA: {self.selected_zone}")
        print("=" * 70)

        zone_data = self.zones[self.selected_zone]
        spawn_x = zone_data['spawn_point']['x']
        spawn_y = zone_data['spawn_point']['y']

        print(f"📍 Destino: ({spawn_x}, {spawn_y})")
        print(f"🎯 Área de farm: Raio {zone_data['farm_area']['radius']} pixels")

        # Navegar usando o sistema de navegação
        sucesso = self.navegador.navegar_para_coordenadas(
            spawn_x, spawn_y,
            use_pathfinding=True,
            verbose=True
        )

        if sucesso:
            print(f"\n✅ Chegou na zona: {self.selected_zone}!")
            return True
        else:
            print(f"\n❌ Falha ao navegar para {self.selected_zone}")
            return False

    def esta_na_area_farm(self):
        """Verifica se player está na área de farm"""
        # Obter posição atual via GPS
        pos = self.gps.get_current_position(keep_map_open=False, verbose=False)
        x_atual, y_atual = pos['x'], pos['y']

        # Área de farm
        zone_data = self.zones[self.selected_zone]
        center_x = zone_data['farm_area']['center']['x']
        center_y = zone_data['farm_area']['center']['y']
        radius = zone_data['farm_area']['radius']

        # Calcular distância ao centro
        dist = math.sqrt((x_atual - center_x)**2 + (y_atual - center_y)**2)

        return dist <= radius, dist, radius

    def procurar_mobs_ativamente(self, atualizar_gps=False):
        """
        Movimento ativo: Se não houver mobs visíveis, move-se pela área
        para encontrar mais mobs (SEM SAIR DO BIOMA)

        GPS INTELIGENTE:
        - Atualiza GPS antes de procurar mobs (evita desorientação)
        - Usa GPS a cada 5-10 movimentos para manter precisão
        - GPS rápido: ~0.3-0.5s (abre/fecha mapa rapidamente)

        NAVEGAÇÃO PARA CENTRO:
        - Se na borda (>70% do raio), navega PARA o centro usando A*
        - Monitora mobs durante navegação (cancela se encontrar)
        - Usa pathfinding para evitar paredes
        """
        print("   🔍 Procurando mobs na área...")

        # GPS INTELIGENTE: Atualizar posição se solicitado
        na_borda = False
        pos_atual = None

        if atualizar_gps:
            print("   📡 Atualizando GPS antes de procurar...")
            try:
                pos = self.gps.get_current_position(keep_map_open=False, verbose=False)
                if pos and 'x' in pos and 'y' in pos:
                    pos_atual = pos
                    print(f"   ✅ Posição atual: ({pos['x']:.0f}, {pos['y']:.0f})")

                    # Verificar se ainda está na área de farm
                    zone_data = self.zones[self.selected_zone]
                    center_x = zone_data['farm_area']['center']['x']
                    center_y = zone_data['farm_area']['center']['y']
                    radius = zone_data['farm_area']['radius']

                    dist = math.sqrt((pos['x'] - center_x)**2 + (pos['y'] - center_y)**2)

                    if dist > radius:
                        print(f"   ⚠️ FORA DA ÁREA DE FARM! Distância: {dist:.0f}/{radius} pixels")
                        print("   🔙 Voltando para zona de farm...")
                        # Voltar para zona
                        self.navegar_para_zona()
                        return
                    elif dist > radius * 0.7:  # borda_threshold
                        print(f"   ⚠️ NA BORDA da área ({dist:.0f}/{radius}px, >70%)")
                        na_borda = True
                    else:
                        print(f"   ✅ Dentro da área (distância: {dist:.0f}/{radius}px)")

            except Exception as e:
                print(f"   ⚠️ Erro ao atualizar GPS: {e}")

        # Capturar frame para detecção
        img = self.farm_bot.capturar_frame()
        if img is None:
            return

        deteccoes = self.farm_bot.detectar_objetos(img)

        # Verificar se há mobs visíveis
        mobs = [d for d in deteccoes if d['class'] in self.zones[self.selected_zone]['mobs']]

        if len(mobs) == 0:
            # Nenhum mob visível - mover para explorar área
            print("   ➡️ Nenhum mob visível, explorando área...")

            # SE NA BORDA: Navegar para centro usando A*
            if na_borda and pos_atual:
                print("   🎯 NA BORDA - Navegando para CENTRO com A*...")
                self.navegar_para_centro_inteligente(pos_atual)
                return

            # SENÃO: Movimento aleatório normal
            # Movimento em coordenadas de TELA (não usar GPS)
            # Calcular ponto aleatório a 2-3 tiles de distância (MENOS AGRESSIVO)

            import random

            # Distância aleatória: 2-3 tiles (era 3-4, agora menor)
            tile_size = self.farm_bot.config.tile_size
            distance = random.uniform(tile_size * 2, tile_size * 3)

            # Ângulo aleatório
            angle = random.uniform(0, 2 * math.pi)

            # Calcular ponto relativo ao personagem (centro da tela)
            center_x = self.farm_bot.config.center_x
            center_y = self.farm_bot.config.center_y

            offset_x = int(distance * math.cos(angle))
            offset_y = int(distance * math.sin(angle))

            move_x = center_x + offset_x
            move_y = center_y + offset_y

            # Limitar à tela (não clicar fora)
            move_x = max(100, min(self.farm_bot.config.screen_width - 100, move_x))
            move_y = max(100, min(self.farm_bot.config.screen_height - 100, move_y))

            print(f"   📍 Explorando: ({move_x}, {move_y}) - {distance/tile_size:.1f} tiles")

            # Executar movimento
            self.farm_bot.executar_tap(move_x, move_y, "🔍 Explorar área")

            time.sleep(1.2)  # Esperar movimento (era 1.5s, agora 1.2s)

    def navegar_para_centro_inteligente(self, pos_atual):
        """
        Navega PARA o centro do bioma usando A* pathfinding

        ESTRATÉGIA INTELIGENTE:
        - Calcula path A* até o centro
        - Pega próximo waypoint visível no mapa
        - Abre mapa, clica no waypoint, fecha mapa
        - Personagem continua andando automaticamente
        - Main loop monitora mobs (cancela se encontrar)

        Args:
            pos_atual: Posição atual do GPS {'x': ..., 'y': ...}
        """
        try:
            print("   🧭 Calculando rota para CENTRO com A*...")

            # Dados da zona
            zone_data = self.zones[self.selected_zone]
            center_x = zone_data['farm_area']['center']['x']
            center_y = zone_data['farm_area']['center']['y']

            x_atual = int(pos_atual['x'])
            y_atual = int(pos_atual['y'])

            print(f"      Posição atual: ({x_atual}, {y_atual})")
            print(f"      Centro bioma: ({center_x}, {center_y})")

            # Usar pathfinder do navegador para calcular caminho
            if not self.navegador or not hasattr(self.navegador, 'pathfinder'):
                print("   ⚠️ Pathfinder não disponível, usando movimento direto")
                self._navegar_direto_para_centro(center_x, center_y)
                return

            # Calcular path A*
            path = self.navegador.pathfinder.find_path(x_atual, y_atual, center_x, center_y)

            if not path or len(path) < 2:
                print("   ⚠️ Pathfinding falhou, tentando movimento direto...")
                self._navegar_direto_para_centro(center_x, center_y)
                return

            print(f"   ✅ Path calculado: {len(path)} waypoints")

            # ESTRATÉGIA: Pegar waypoint intermediário (não ir direto ao centro)
            # Queremos apenas nos APROXIMAR do centro, não ir exatamente até lá
            # Pegar waypoint a 30-50% do caminho

            import random
            progresso = random.uniform(0.3, 0.5)  # 30-50% do caminho
            indice_waypoint = min(int(len(path) * progresso), len(path) - 1)
            indice_waypoint = max(1, indice_waypoint)  # No mínimo waypoint 1

            wp_x, wp_y = path[indice_waypoint]

            print(f"   🎯 Waypoint escolhido: ({wp_x}, {wp_y}) - {indice_waypoint+1}/{len(path)} ({progresso*100:.0f}% do caminho)")

            # Abrir mapa, clicar no waypoint, fechar mapa
            print("   🗺️ Abrindo mapa para clicar waypoint...")

            # Abrir mapa
            self.farm_bot.executar_tap(
                self.farm_bot.config.map_button_x,
                self.farm_bot.config.map_button_y,
                "📍 Abrir mapa"
            )
            time.sleep(0.4)  # Esperar mapa abrir

            # Converter coordenadas mundo → tela do mapa
            # Usar função do GPS para isso
            if hasattr(self.gps, 'converter_mundo_para_mapa'):
                map_x, map_y = self.gps.converter_mundo_para_mapa(wp_x, wp_y, pos_atual['x'], pos_atual['y'])
            else:
                # Fallback: converter manualmente (simplificado)
                # O mapa no jogo geralmente tem escala ~1px por tile
                escala_mapa = 1.0
                centro_mapa_x = 800  # Centro do minimapa (ajustar conforme jogo)
                centro_mapa_y = 450

                delta_x = (wp_x - pos_atual['x']) * escala_mapa
                delta_y = (wp_y - pos_atual['y']) * escala_mapa

                map_x = int(centro_mapa_x + delta_x)
                map_y = int(centro_mapa_y + delta_y)

            print(f"   📍 Clicando waypoint no mapa: tela ({map_x}, {map_y}) = mundo ({wp_x}, {wp_y})")

            # Clicar no waypoint
            self.farm_bot.executar_tap(map_x, map_y, "🎯 Clicar waypoint")
            time.sleep(0.3)

            # Fechar mapa (personagem continua andando automaticamente)
            self.farm_bot.executar_tap(
                self.farm_bot.config.map_button_x,
                self.farm_bot.config.map_button_y,
                "🗺️ Fechar mapa"
            )

            print("   ✅ Navegação iniciada! Personagem andando para centro...")
            print("   👀 Main loop monitorará mobs (cancela se encontrar)")

            time.sleep(2.0)  # Esperar um pouco para personagem começar a andar

        except Exception as e:
            print(f"   ❌ Erro ao navegar para centro: {e}")
            import traceback
            traceback.print_exc()

    def _navegar_direto_para_centro(self, center_x, center_y):
        """
        Fallback: navegação direta para centro (sem pathfinding)
        Usado quando A* não está disponível
        """
        print("   📍 Navegação direta para centro (sem A*)...")

        # Abrir mapa
        self.farm_bot.executar_tap(
            self.farm_bot.config.map_button_x,
            self.farm_bot.config.map_button_y,
            "📍 Abrir mapa"
        )
        time.sleep(0.4)

        # Clicar no centro (simplificado - assumir centro do mapa)
        centro_mapa_x = 800
        centro_mapa_y = 450

        self.farm_bot.executar_tap(centro_mapa_x, centro_mapa_y, "🎯 Clicar centro")
        time.sleep(0.3)

        # Fechar mapa
        self.farm_bot.executar_tap(
            self.farm_bot.config.map_button_x,
            self.farm_bot.config.map_button_y,
            "🗺️ Fechar mapa"
        )

        print("   ✅ Navegação iniciada (direta)!")
        time.sleep(2.0)

    def executar_farm_loop(self):
        """Loop principal de farm"""
        print("\n" + "=" * 70)
        print(f"⚔️ INICIANDO FARM EM: {self.selected_zone}")
        print("=" * 70)
        print("📌 Controles:")
        print("   P: Pausar/Retomar")
        print("   Q: Sair e voltar para menu")
        print("=" * 70)

        # GPS INICIAL: Atualizar mapa virtual com posição atual
        if self.farm_bot.usar_mapa_virtual:
            print("\n📡 Obtendo posição GPS inicial para mapa virtual...")
            try:
                pos = self.gps.get_current_position(keep_map_open=False, verbose=False)
                if pos and 'x' in pos and 'y' in pos:
                    self.farm_bot.atualizar_posicao_gps(pos['x'], pos['y'])
                    print(f"   ✅ Posição inicial: ({pos['x']}, {pos['y']})")
                else:
                    print("   ⚠️ GPS inicial falhou, mapa virtual sem posição")
            except Exception as e:
                print(f"   ⚠️ Erro ao obter GPS inicial: {e}")

        self.running = True
        self.farm_bot.bot_active = True

        frame_count = 0
        last_mob_check = time.time()
        last_heartbeat = time.time()
        last_gps_check = time.time()  # Controle de recalibração GPS
        last_mob_found_time = time.time()  # Última vez que encontrou mob
        movimentos_sem_gps = 0  # Contador de movimentos sem atualizar GPS
        check_interval = 5.0  # Verificar área a cada 5 segundos
        heartbeat_interval = 30.0  # Log de status a cada 30 segundos
        gps_check_interval = 60.0  # Verificar GPS a cada 60 segundos (background)
        gps_sem_mob_timeout = 5.0  # GPS se não achar mob por 5 segundos (REDUZIDO!)
        max_movimentos_sem_gps = 8  # GPS a cada 8 movimentos de procura
        borda_threshold = 0.7  # Considera "borda" se >70% do raio
        failed_captures = 0
        max_failed_captures = 10  # Parar após 10 falhas consecutivas

        while self.running:
            try:
                # Heartbeat: Log periódico de status
                current_time = time.time()
                if (current_time - last_heartbeat) >= heartbeat_interval:
                    print(f"\n💚 [Heartbeat] Frame {frame_count}, Bot ativo: {self.farm_bot.bot_active}")
                    last_heartbeat = current_time

                # GPS RECALIBRAÇÃO: Verificar se precisa atualizar posição virtual
                if self.farm_bot.usar_mapa_virtual and (current_time - last_gps_check) >= gps_check_interval:
                    if self.farm_bot.precisa_gps_recalibracao():
                        print("\n🔄 GPS recalibração necessária...")
                        try:
                            pos = self.gps.get_current_position(keep_map_open=False, verbose=False)
                            if pos and 'x' in pos and 'y' in pos:
                                self.farm_bot.atualizar_posicao_gps(pos['x'], pos['y'])
                                print(f"   ✅ Posição atualizada: ({pos['x']}, {pos['y']})")
                            else:
                                print("   ⚠️ GPS recalibração falhou")
                        except Exception as e:
                            print(f"   ⚠️ Erro na recalibração GPS: {e}")
                    last_gps_check = current_time

                # Processar frame de farm
                try:
                    self.farm_bot.processar_frame()
                    failed_captures = 0  # Reset contador de falhas
                except Exception as e:
                    failed_captures += 1
                    print(f"⚠️ Erro ao processar frame ({failed_captures}/{max_failed_captures}): {e}")
                    if failed_captures >= max_failed_captures:
                        print(f"\n❌ Muitas falhas consecutivas! Parando farm...")
                        break
                    time.sleep(0.5)  # Esperar antes de tentar novamente
                    continue

                # GPS INTELIGENTE: Atualizar quando não encontrar mobs por muito tempo
                tempo_sem_mob = current_time - last_mob_found_time
                precisa_gps_inteligente = False

                # Verificar se tem mob atualmente
                if self.farm_bot.current_target is not None:
                    last_mob_found_time = current_time  # Reset timer
                    movimentos_sem_gps = 0  # Reset contador

                # Condições para GPS inteligente:
                # 1. Não encontrou mob por mais de 15 segundos
                # 2. Já fez 8 movimentos de procura sem GPS
                if tempo_sem_mob >= gps_sem_mob_timeout:
                    print(f"\n⚠️ Sem mobs por {tempo_sem_mob:.0f}s - GPS inteligente!")
                    precisa_gps_inteligente = True
                elif movimentos_sem_gps >= max_movimentos_sem_gps:
                    print(f"\n⚠️ {movimentos_sem_gps} movimentos sem GPS - atualizando!")
                    precisa_gps_inteligente = True

                # Procurar mobs ativamente se não houver alvo
                if (current_time - last_mob_check) >= check_interval:
                    if self.farm_bot.current_target is None:
                        self.procurar_mobs_ativamente(atualizar_gps=precisa_gps_inteligente)
                        movimentos_sem_gps += 1

                        # Reset após GPS inteligente
                        if precisa_gps_inteligente:
                            movimentos_sem_gps = 0
                            last_mob_found_time = current_time

                    last_mob_check = current_time

                frame_count += 1

                # DELAY ENTRE FRAMES: Evitar sobrecarga de CPU e flood de comandos
                time.sleep(0.15)  # 150ms entre frames (~6-7 FPS)

            except KeyboardInterrupt:
                print("\n\n⏹️ Farm interrompido pelo usuário!")
                break
            except Exception as e:
                print(f"\n❌ Erro no farm: {e}")
                import traceback
                traceback.print_exc()
                break

        self.farm_bot.bot_active = False
        print("\n✅ Farm finalizado!")
        print(f"📊 Total de frames processados: {frame_count}")

    def menu_principal(self):
        """Menu principal do sistema integrado"""
        print("\n" + "=" * 70)
        print("🎮 SISTEMA INTEGRADO - MENU PRINCIPAL")
        print("=" * 70)
        print("  [1] Iniciar Farm (Navegar + Farmar)")
        print("  [2] Apenas Navegar para Zona")
        print("  [3] Apenas Farm (sem navegação)")
        print("  [4] Configurações")
        print("  [5] Sair")
        print("=" * 70)

        escolha = input("\nEscolha uma opção (1-5): ").strip()
        return escolha

    def executar(self):
        """Execução principal"""
        # Seleção de classe
        self.selecionar_classe()

        # Seleção de zona
        self.selecionar_zona()

        # Inicializar sistemas
        if not self.inicializar_sistemas():
            print("\n❌ Falha na inicialização!")
            return

        # Menu principal
        while True:
            escolha = self.menu_principal()

            if escolha == '1':
                # Navegar + Farm
                if self.navegar_para_zona():
                    self.executar_farm_loop()

            elif escolha == '2':
                # Apenas navegar
                self.navegar_para_zona()

            elif escolha == '3':
                # Apenas farm
                print("\n⚠️ Farm sem navegação - certifique-se de estar na zona correta!")
                input("Pressione ENTER para continuar...")
                self.executar_farm_loop()

            elif escolha == '4':
                # Configurações
                print("\n⚙️ Configurações:")
                print(f"   Classe: {self.class_configs[self.selected_class]['name']}")
                print(f"   Zona: {self.selected_zone}")
                input("\nPressione ENTER para voltar...")

            elif escolha == '5':
                # Sair
                print("\n👋 Até logo!")
                break

            else:
                print("❌ Opção inválida!")


def main():
    """Função principal"""
    try:
        farm_system = FarmIntegrado()
        farm_system.executar()

    except KeyboardInterrupt:
        print("\n\n⏹️ Sistema encerrado pelo usuário!")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
