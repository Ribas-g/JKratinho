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

    def procurar_mobs_ativamente(self):
        """
        Movimento ativo: Se não houver mobs visíveis, move-se pela área
        para encontrar mais mobs (SEM SAIR DO BIOMA)
        """
        print("   🔍 Procurando mobs na área...")

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

            # Movimento em coordenadas de TELA (não usar GPS)
            # Calcular ponto aleatório a 3-4 tiles de distância

            import random

            # Distância aleatória: 3-4 tiles
            tile_size = self.farm_bot.config.tile_size
            distance = random.uniform(tile_size * 3, tile_size * 4)

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

            time.sleep(1.5)  # Esperar movimento

    def executar_farm_loop(self):
        """Loop principal de farm"""
        print("\n" + "=" * 70)
        print(f"⚔️ INICIANDO FARM EM: {self.selected_zone}")
        print("=" * 70)
        print("📌 Controles:")
        print("   P: Pausar/Retomar")
        print("   Q: Sair e voltar para menu")
        print("=" * 70)

        self.running = True
        self.farm_bot.bot_active = True

        frame_count = 0
        last_mob_check = time.time()
        check_interval = 5.0  # Verificar área a cada 5 segundos

        while self.running:
            try:
                # DESABILITADO: Verificação de área com GPS (abre mapa desnecessariamente)
                # Se necessário no futuro, implementar com sistema de tracking alternativo
                # if frame_count % 30 == 0:
                #     na_area, dist, radius = self.esta_na_area_farm()
                #     if not na_area:
                #         print(f"\n⚠️ Fora da área de farm! (dist={dist:.1f}, max={radius})")
                #         print("🔄 Retornando para área de farm...")
                #         if not self.navegar_para_zona():
                #             print("❌ Falha ao retornar! Parando farm...")
                #             break

                # Processar frame de farm
                self.farm_bot.processar_frame()

                # Procurar mobs ativamente se não houver alvo
                current_time = time.time()
                if (current_time - last_mob_check) >= check_interval:
                    if self.farm_bot.current_target is None:
                        self.procurar_mobs_ativamente()
                    last_mob_check = current_time

                frame_count += 1

                # TODO: Adicionar verificação de teclas (P para pausar, Q para sair)

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
