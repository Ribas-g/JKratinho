"""
Farm Bot - Rucoy Online (Arqueiro)
Bot automático de farm com sistema de kiting

Features:
- Detecção de mobs via YOLO
- Cálculo de distâncias em tiles
- Kiting automático (manter distância)
- Coleta de coins
- Visualização em tempo real

Controles:
- P: Pausar/Retomar bot
- Q: Sair
- ESPAÇO: Toggle visualização

Execute: python farm_bot.py
"""

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
from adbutils import adb
from ultralytics import YOLO
import time
import os
import json
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class FarmConfig:
    """Configurações do farm (carregadas de farm_config.json)"""
    tile_size: int
    screen_width: int
    screen_height: int
    center_x: int
    center_y: int
    min_safe_distance: float  # tiles
    ideal_distance: float     # tiles
    max_attack_range: float   # tiles
    aggro_range: float        # tiles

    @classmethod
    def load(cls, filename='farm_config.json'):
        """Carrega configuração do JSON"""
        with open(filename, 'r') as f:
            data = json.load(f)

        return cls(
            tile_size=data['tile_size'],
            screen_width=data['screen_width'],
            screen_height=data['screen_height'],
            center_x=data['center_x'],
            center_y=data['center_y'],
            min_safe_distance=data['ranges']['min_safe_distance'],
            ideal_distance=data['ranges']['ideal_distance'],
            max_attack_range=data['ranges']['max_attack_range'],
            aggro_range=data['ranges']['aggro_range']
        )


class ArcherFarmBot:
    """Bot de farm para Arqueiro com kiting"""

    def __init__(self, model_path="models/rucoy_model_final.pt"):
        # Carregar configurações
        try:
            self.config = FarmConfig.load()
            print(f"✅ Configuração carregada!")
            print(f"   Tile Size: {self.config.tile_size}px")
            print(f"   Range Ideal: {self.config.ideal_distance} tiles")
        except FileNotFoundError:
            print("❌ farm_config.json não encontrado!")
            print("   Execute: python calibrate_tile.py")
            exit(1)

        # Dispositivo e modelo
        self.model_path = model_path
        self.device = None
        self.model = None

        # Estado do bot
        self.running = False
        self.paused = False
        self.bot_active = False
        self.show_visualization = True
        self.debug_mode = False  # Mostra TODAS detecções com confiança

        # Alvo atual
        self.current_target = None
        self.target_lock_time = 0  # Timestamp de quando travou no alvo
        self.target_lock_duration = 2.0  # Manter alvo por 2 segundos antes de trocar
        self.last_action = "IDLE"
        self.last_action_time = 0
        self.action_cooldown = 0.4  # segundos entre ações

        # Sistema de kiting ativo
        self.kite_state = "ATTACK"  # Alterna entre ATTACK e MOVE
        self.kite_angle = 0  # Ângulo para movimento circular
        self.last_kite_move = 0
        self.combat_style = "ranged"  # "ranged" (arqueiro/mago) ou "melee" (guerreiro)

        # Área de farm (limites para não sair do bioma)
        self.farm_area_center = None  # (x, y) em coordenadas de tela
        self.farm_area_radius = None  # raio em pixels

        # Estatísticas
        self.frame_count = 0
        self.kills_count = 0
        self.coins_collected = 0
        self.actions_history = deque(maxlen=50)
        self.fps_buffer = deque(maxlen=30)
        self.last_frame_time = time.time()

        # Cores
        self.class_colors = {
            'coin': (255, 255, 0),
            'crab': (0, 255, 0),
            'rat': (255, 0, 0),
            'crow': (148, 0, 211),
            'spider': (255, 165, 0),
            'skeleton': (255, 255, 255),
            'cobra': (255, 100, 100),
            'worm': (150, 75, 0),
            'scorpion': (255, 200, 0),
        }

        # UI
        self.root = None
        self.canvas = None

    def configurar_area_farm(self, center_screen_x, center_screen_y, radius_px):
        """
        Configura área de farm em coordenadas de tela
        Args:
            center_screen_x, center_screen_y: Centro em pixels da tela
            radius_px: Raio em pixels
        """
        self.farm_area_center = (center_screen_x, center_screen_y)
        self.farm_area_radius = radius_px
        print(f"   📍 Área de farm configurada: centro=({center_screen_x}, {center_screen_y}), raio={radius_px}px")

    def conectar_bluestacks(self):
        """Conecta ao BlueStacks"""
        try:
            devices = adb.device_list()
            if not devices:
                print("❌ BlueStacks não detectado!")
                return False

            self.device = devices[0]
            print(f"✅ Conectado: {self.device.serial}")
            return True
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False

    def carregar_modelo(self):
        """Carrega modelo YOLO"""
        try:
            if not os.path.exists(self.model_path):
                print(f"❌ Modelo não encontrado: {self.model_path}")
                return False

            print(f"📦 Carregando modelo...")
            self.model = YOLO(self.model_path)
            print(f"✅ Modelo carregado!")
            return True
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False

    def capturar_frame(self):
        """Captura screenshot"""
        try:
            screenshot_bytes = self.device.shell("screencap -p", encoding=None)
            if not screenshot_bytes or len(screenshot_bytes) < 100:
                print(f"⚠️ Screenshot vazio ou muito pequeno")
                return None

            nparr = np.frombuffer(screenshot_bytes, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img_bgr is None or img_bgr.size == 0:
                print(f"⚠️ Falha ao decodificar screenshot")
                return None

            # IMPORTANTE: YOLO espera BGR, não converter!
            return img_bgr
        except Exception as e:
            print(f"❌ Erro ao capturar: {e}")
            return None

    def detectar_objetos(self, img):
        """Detecta objetos na imagem"""
        try:
            if img is None or img.size == 0:
                return []

            # Threshold mais baixo para detectar mais (ajustável)
            results = self.model(img, conf=0.25, verbose=False)

            deteccoes = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = self.model.names[class_id]

                    deteccoes.append({
                        'class': class_name,
                        'conf': conf,
                        'bbox': (int(x1), int(y1), int(x2), int(y2))
                    })

            return deteccoes
        except Exception as e:
            print(f"❌ Erro na detecção: {e}")
            return []

    def detectar_cerco(self, deteccoes):
        """
        Detecta se está sendo cercado por mobs (PERIGOSO!)
        Retorna (cercado, num_mobs_proximos, direcao_fuga)
        """
        mobs = [d for d in deteccoes if d['class'] in ['crab', 'rat', 'crow', 'spider', 'skeleton', 'cobra', 'worm', 'scorpion']]

        # Contar mobs a 1 tile de distância
        mobs_muito_proximos = []
        for mob in mobs:
            dist_px, dist_tiles = self.calcular_distancia(mob['bbox'])
            if dist_tiles <= 1.0:
                x1, y1, x2, y2 = mob['bbox']
                mob_center_x = (x1 + x2) // 2
                mob_center_y = (y1 + y2) // 2
                mobs_muito_proximos.append({
                    'bbox': mob['bbox'],
                    'center': (mob_center_x, mob_center_y),
                    'dist': dist_tiles
                })

        num_proximos = len(mobs_muito_proximos)

        # 3+ mobs a 1 tile = CERCO PERIGOSO!
        if num_proximos >= 3:
            # Calcular direção média dos mobs (para fugir na direção oposta)
            avg_dx = 0
            avg_dy = 0
            for mob in mobs_muito_proximos:
                dx = mob['center'][0] - self.config.center_x
                dy = mob['center'][1] - self.config.center_y
                avg_dx += dx
                avg_dy += dy

            avg_dx /= num_proximos
            avg_dy /= num_proximos

            # Direção de fuga: oposta aos mobs
            fuga_dx = -avg_dx
            fuga_dy = -avg_dy

            # Normalizar
            dist = math.sqrt(fuga_dx**2 + fuga_dy**2)
            if dist > 0:
                fuga_dx /= dist
                fuga_dy /= dist

            # Ponto de fuga: 3 tiles na direção oposta
            fuga_distance = self.config.tile_size * 3.0
            fuga_x = int(self.config.center_x + fuga_dx * fuga_distance)
            fuga_y = int(self.config.center_y + fuga_dy * fuga_distance)

            return True, num_proximos, (fuga_x, fuga_y)

        return False, num_proximos, None

    def calcular_distancia(self, bbox):
        """Calcula distância do mob ao player (centro) em pixels"""
        x1, y1, x2, y2 = bbox
        mob_center_x = (x1 + x2) // 2
        mob_center_y = (y1 + y2) // 2

        # Distância euclidiana até o centro da tela (player)
        dist_px = math.sqrt(
            (mob_center_x - self.config.center_x) ** 2 +
            (mob_center_y - self.config.center_y) ** 2
        )

        # Converter para tiles
        dist_tiles = dist_px / self.config.tile_size

        return dist_px, dist_tiles

    def classificar_zona(self, dist_tiles):
        """Classifica em qual zona o mob está"""
        if dist_tiles < self.config.min_safe_distance:
            return "MUITO_PERTO"  # Recuar
        elif dist_tiles <= self.config.ideal_distance:
            return "IDEAL"  # Atacar
        elif dist_tiles <= self.config.max_attack_range:
            return "ATACAVEL"  # Aproximar um pouco
        elif dist_tiles <= self.config.aggro_range:
            return "AGGRO"  # Ir até o mob
        else:
            return "MUITO_LONGE"  # Ignorar

    def selecionar_alvo(self, deteccoes):
        """
        Seleciona melhor alvo para atacar com PERSISTÊNCIA
        Mantém alvo atual por target_lock_duration segundos antes de trocar
        """
        current_time = time.time()

        # Filtrar apenas mobs (não coins)
        mobs = [d for d in deteccoes if d['class'] in ['crab', 'rat', 'crow', 'spider', 'skeleton', 'cobra', 'worm', 'scorpion']]

        if not mobs:
            self.current_target = None
            return None

        # Calcular distâncias
        mobs_com_info = []
        for mob in mobs:
            dist_px, dist_tiles = self.calcular_distancia(mob['bbox'])
            zona = self.classificar_zona(dist_tiles)

            mobs_com_info.append({
                'mob': mob,
                'dist_px': dist_px,
                'dist_tiles': dist_tiles,
                'zona': zona
            })

        # PERSISTÊNCIA: Se tem alvo atual e ainda está visível, manter por um tempo
        if self.current_target is not None:
            time_locked = current_time - self.target_lock_time

            # Se ainda não passou o tempo de lock, verificar se alvo atual ainda existe
            if time_locked < self.target_lock_duration:
                # Procurar alvo atual nas detecções
                for mob_info in mobs_com_info:
                    if mob_info['mob']['class'] == self.current_target['mob']['class']:
                        # Verificar se é aproximadamente a mesma posição (dentro de 50px)
                        if mob_info['dist_px'] - self.current_target['dist_px'] < 50:
                            # Manter alvo atual
                            return mob_info

        # Trocar de alvo ou selecionar novo
        self.target_lock_time = current_time

        # Prioridade: mobs na zona IDEAL, depois mais próximos
        ideal = [m for m in mobs_com_info if m['zona'] == 'IDEAL']
        if ideal:
            return min(ideal, key=lambda m: m['dist_px'])

        # Se nenhum ideal, pegar zona ATACAVEL
        atacavel = [m for m in mobs_com_info if m['zona'] == 'ATACAVEL']
        if atacavel:
            return min(atacavel, key=lambda m: m['dist_px'])

        # Se nenhum atacável, pegar AGGRO (ir até ele)
        aggro = [m for m in mobs_com_info if m['zona'] == 'AGGRO']
        if aggro:
            return min(aggro, key=lambda m: m['dist_px'])

        # Se nenhum, pegar o mais próximo (mesmo que MUITO_PERTO)
        if mobs_com_info:
            return min(mobs_com_info, key=lambda m: m['dist_px'])

        return None

    def calcular_ponto_kite(self, mob_bbox, kite_type="strafe", combat_style="ranged"):
        """
        Calcula ponto para kiting (movimento evasivo mantendo distância)

        Args:
            mob_bbox: Bounding box do mob
            kite_type: "strafe" (lateral), "back" (recuar), "circle" (circular melee)
            combat_style: "ranged" (arqueiro/mago) ou "melee" (guerreiro)
        """
        x1, y1, x2, y2 = mob_bbox
        mob_center_x = (x1 + x2) // 2
        mob_center_y = (y1 + y2) // 2

        # Vetor do mob para o player
        dx = self.config.center_x - mob_center_x
        dy = self.config.center_y - mob_center_y

        # Distância atual
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0:
            dist = 1

        # Normalizar
        dx_norm = dx / dist
        dy_norm = dy / dist

        if combat_style == "melee":
            # GUERREIRO (MELEE): Movimento circular curto ao redor do mob
            # Mantém distância de ~1 tile para poder atacar

            if kite_type == "back":
                # Emergência: recuar um pouco
                kite_distance = self.config.tile_size * 1.5
                kite_x = self.config.center_x + int(dx_norm * kite_distance)
                kite_y = self.config.center_y + int(dy_norm * kite_distance)
            else:
                # Movimento circular: orbitar ao redor do mob
                # Distância fixa de 1 tile (alcance melee)
                ideal_distance = self.config.tile_size * 1.0

                # Incrementar ângulo para movimento circular
                self.kite_angle += 45  # 45 graus por movimento
                if self.kite_angle >= 360:
                    self.kite_angle = 0

                # Converter ângulo para radianos
                angle_rad = math.radians(self.kite_angle)

                # Calcular posição circular ao redor do mob
                offset_x = int(ideal_distance * math.cos(angle_rad))
                offset_y = int(ideal_distance * math.sin(angle_rad))

                kite_x = mob_center_x + offset_x
                kite_y = mob_center_y + offset_y

        else:
            # RANGED (ARQUEIRO/MAGO): Movimento original
            if kite_type == "back":
                # Recuar direto (para emergências - mob muito perto)
                kite_distance = self.config.tile_size * 2.5
                kite_x = self.config.center_x + int(dx_norm * kite_distance)
                kite_y = self.config.center_y + int(dy_norm * kite_distance)

            else:  # strafe (movimento lateral/circular)
                # Distância ideal: 2.5 tiles (sweet spot para arqueiro)
                ideal_distance = self.config.tile_size * 2.5

                # Se muito perto, aumentar distância
            # Se muito longe, diminuir distância
            target_distance = ideal_distance

            # Calcular ângulo perpendicular para movimento lateral
            # Incrementar ângulo para criar movimento circular
            self.kite_angle += 45  # 45 graus por movimento
            if self.kite_angle >= 360:
                self.kite_angle = 0

            angle_rad = math.radians(self.kite_angle)

            # Vetor perpendicular (strafe lateral)
            perp_dx = -dy_norm
            perp_dy = dx_norm

            # Combinar movimento: para trás + lateral
            # 70% para trás, 30% lateral
            combined_dx = dx_norm * 0.7 + perp_dx * 0.3 * math.cos(angle_rad)
            combined_dy = dy_norm * 0.7 + perp_dy * 0.3 * math.sin(angle_rad)

            # Normalizar vetor combinado
            combined_dist = math.sqrt(combined_dx**2 + combined_dy**2)
            if combined_dist > 0:
                combined_dx /= combined_dist
                combined_dy /= combined_dist

            # Calcular ponto de kite
            kite_x = self.config.center_x + int(combined_dx * target_distance)
            kite_y = self.config.center_y + int(combined_dy * target_distance)

        # Garantir que está dentro da tela
        kite_x = max(100, min(self.config.screen_width - 100, kite_x))
        kite_y = max(100, min(self.config.screen_height - 100, kite_y))

        return kite_x, kite_y

    def executar_tap(self, x, y, description=""):
        """Executa tap no emulador"""
        try:
            # ZONA MORTA: Não clicar muito perto do personagem (centro da tela)
            # para evitar abrir menu do personagem
            dx = x - self.config.center_x
            dy = y - self.config.center_y
            dist_from_center = math.sqrt(dx**2 + dy**2)

            # Raio da zona morta: ~80 pixels (personagem + margem de segurança)
            DEAD_ZONE_RADIUS = 80

            if dist_from_center < DEAD_ZONE_RADIUS:
                # Ajustar clique para borda da zona morta
                if dist_from_center > 0:
                    # Normalizar e multiplicar pelo raio da zona morta
                    scale = DEAD_ZONE_RADIUS / dist_from_center
                    x = self.config.center_x + int(dx * scale)
                    y = self.config.center_y + int(dy * scale)
                    print(f"   ⚠️ Clique ajustado para fora da zona morta")
                else:
                    # Exatamente no centro, não clicar
                    print(f"   ⚠️ Clique cancelado: muito perto do personagem!")
                    return False

            # Converter coordenadas se necessário (screen vs touch)
            self.device.shell(f"input tap {x} {y}")
            if description:
                print(f"   🎯 Tap: {description} ({x}, {y})")
            return True
        except Exception as e:
            print(f"❌ Erro ao executar tap: {e}")
            return False

    def coletar_coins(self, deteccoes):
        """Coleta coins próximos"""
        coins = [d for d in deteccoes if d['class'] == 'coin']

        for coin in coins:
            dist_px, dist_tiles = self.calcular_distancia(coin['bbox'])

            # Se coin está perto (< 3 tiles), clicar nele
            if dist_tiles < 3.0:
                x1, y1, x2, y2 = coin['bbox']
                coin_x = (x1 + x2) // 2
                coin_y = (y1 + y2) // 2

                self.executar_tap(coin_x, coin_y, "Coletar coin")
                self.coins_collected += 1
                time.sleep(0.2)  # Pequeno delay

    def executar_acao(self, alvo_info):
        """Executa ação baseada no alvo (COM KITING ATIVO)"""
        if not self.bot_active:
            return "BOT_PAUSADO"

        # Cooldown entre ações
        current_time = time.time()
        if current_time - self.last_action_time < self.action_cooldown:
            return self.last_action

        if not alvo_info:
            self.last_action = "IDLE"
            self.kite_state = "ATTACK"  # Reset state
            return "IDLE"

        zona = alvo_info['zona']
        mob = alvo_info['mob']
        dist_tiles = alvo_info['dist_tiles']
        x1, y1, x2, y2 = mob['bbox']
        mob_center_x = (x1 + x2) // 2
        mob_center_y = (y1 + y2) // 2

        action = None

        if zona == "MUITO_PERTO":
            # EMERGÊNCIA: Mob MUITO perto (< 1 tile)
            # Recuar urgente!
            kite_x, kite_y = self.calcular_ponto_kite(mob['bbox'], kite_type="back", combat_style=self.combat_style)
            self.executar_tap(kite_x, kite_y, f"🔴 RECUAR URGENTE de {mob['class']}")
            action = "RECUAR"
            self.kite_state = "MOVE"  # Forçar movimento no próximo frame

        elif zona == "IDEAL" or zona == "ATACAVEL":
            # Zona de combate (1-4 tiles)
            # KITING ATIVO: Alternar entre ATACAR e MOVER

            if self.kite_state == "ATTACK":
                # ATACAR: Clicar no mob para dar dano
                self.executar_tap(mob_center_x, mob_center_y, f"⚔️ Atacar {mob['class']}")
                action = "ATACAR"
                self.kite_state = "MOVE"  # Próxima ação: mover

            else:  # kite_state == "MOVE"
                # MOVER: Kiting para manter distância
                kite_x, kite_y = self.calcular_ponto_kite(mob['bbox'], kite_type="strafe", combat_style=self.combat_style)
                self.executar_tap(kite_x, kite_y, f"🏃 Kite de {mob['class']}")
                action = "KITE"
                self.kite_state = "ATTACK"  # Próxima ação: atacar
                self.last_kite_move = current_time

        elif zona == "AGGRO":
            # Mob longe (4-6 tiles) - APROXIMAR
            dx = mob_center_x - self.config.center_x
            dy = mob_center_y - self.config.center_y
            approach_x = self.config.center_x + int(dx * 0.7)
            approach_y = self.config.center_y + int(dy * 0.7)
            self.executar_tap(approach_x, approach_y, f"Aproximar de {mob['class']}")
            action = "APROXIMAR"
            self.kite_state = "ATTACK"  # Reset para atacar quando chegar

        else:
            # Muito longe, ignorar
            action = "IGNORAR"
            self.kite_state = "ATTACK"

        self.last_action = action
        self.last_action_time = current_time
        self.actions_history.append({
            'action': action,
            'target': mob['class'],
            'dist': dist_tiles
        })

        return action

    def processar_frame(self):
        """Processa um frame completo"""
        if self.paused:
            return

        # Capturar
        img = self.capturar_frame()
        if img is None:
            return

        # Detectar
        deteccoes = self.detectar_objetos(img)

        # Bot ativo
        if self.bot_active:
            # PRIORIDADE 1: Detectar cerco (PERIGOSO!)
            cercado, num_mobs, ponto_fuga = self.detectar_cerco(deteccoes)

            if cercado:
                # 🚨 CERCO DETECTADO! FUGIR IMEDIATAMENTE!
                print(f"\n🚨 CERCO DETECTADO! {num_mobs} mobs a 1 tile!")
                print(f"   🏃 FUGINDO para ({ponto_fuga[0]}, {ponto_fuga[1]})...")
                self.executar_tap(ponto_fuga[0], ponto_fuga[1], f"🚨 FUGA DE CERCO ({num_mobs} mobs)")
                self.current_target = None  # Resetar alvo
                return  # Não fazer mais nada neste frame

            # Selecionar alvo
            alvo_info = self.selecionar_alvo(deteccoes)
            self.current_target = alvo_info

            # Executar ação
            self.executar_acao(alvo_info)

            # Coletar coins
            self.coletar_coins(deteccoes)

        # Calcular FPS
        current_time = time.time()
        fps = 1.0 / (current_time - self.last_frame_time) if current_time != self.last_frame_time else 0
        self.last_frame_time = current_time
        self.fps_buffer.append(fps)

        # Atualizar visualização
        if self.show_visualization:
            self.atualizar_display(img, deteccoes)

        self.frame_count += 1

    def desenhar_deteccoes(self, img_pil, deteccoes):
        """Desenha detecções e informações do bot"""
        draw = ImageDraw.Draw(img_pil)

        try:
            font = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Desenhar bounding boxes
        for det in deteccoes:
            class_name = det['class']
            conf = det['conf']
            x1, y1, x2, y2 = det['bbox']

            # Calcular distância
            dist_px, dist_tiles = self.calcular_distancia(det['bbox'])
            zona = self.classificar_zona(dist_tiles)

            # Cor baseada na zona (para mobs)
            if class_name in ['crab', 'rat', 'crow', 'spider', 'skeleton', 'cobra', 'worm', 'scorpion']:
                if zona == "MUITO_PERTO":
                    color = (255, 0, 0)  # Vermelho (perigo)
                elif zona == "IDEAL":
                    color = (0, 255, 0)  # Verde (atacar)
                elif zona == "ATACAVEL":
                    color = (255, 255, 0)  # Amarelo (aproximar)
                else:
                    color = (128, 128, 128)  # Cinza (longe)
            else:
                color = self.class_colors.get(class_name, (255, 255, 255))

            # Destacar alvo atual
            thickness = 5 if (self.current_target and
                            self.current_target['mob'] == det) else 3

            draw.rectangle([x1, y1, x2, y2], outline=color, width=thickness)

            # Label (com confiança se debug mode)
            if self.debug_mode:
                label = f"{class_name} {conf:.0%} {dist_tiles:.1f}t"
            else:
                label = f"{class_name} {dist_tiles:.1f}t"

            bbox = draw.textbbox((x1, y1 - 25), label, font=font)
            draw.rectangle([bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2], fill=color)
            draw.text((x1, y1 - 25), label, fill=(0, 0, 0), font=font)

        return img_pil

    def criar_overlay_info(self, img_pil, deteccoes):
        """Cria overlay com informações do bot"""
        draw = ImageDraw.Draw(img_pil)
        width, height = img_pil.size

        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_bold = ImageFont.truetype("arialbd.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            font_bold = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Painel superior
        overlay = Image.new('RGBA', img_pil.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([0, 0, width, 120], fill=(0, 0, 0, 180))

        img_pil = img_pil.convert('RGBA')
        img_pil = Image.alpha_composite(img_pil, overlay)
        img_pil = img_pil.convert('RGB')

        draw = ImageDraw.Draw(img_pil)

        # Status do bot
        bot_status = "ATIVO" if self.bot_active else "PAUSADO"
        bot_color = (0, 255, 0) if self.bot_active else (255, 255, 0)
        draw.text((10, 10), f"🤖 BOT: {bot_status}",
                 fill=bot_color, font=font_bold)

        # FPS
        avg_fps = sum(self.fps_buffer) / len(self.fps_buffer) if self.fps_buffer else 0
        draw.text((10, 35), f"FPS: {avg_fps:.1f}",
                 fill=(200, 200, 200), font=font)

        # Última ação
        action_color = {
            'ATACAR': (0, 255, 0),
            'KITE': (0, 255, 255),     # Ciano para kiting
            'RECUAR': (255, 0, 0),
            'APROXIMAR': (255, 255, 0),
            'IDLE': (128, 128, 128)
        }.get(self.last_action, (255, 255, 255))

        draw.text((10, 60), f"Ação: {self.last_action}",
                 fill=action_color, font=font)

        # Estado do kite
        draw.text((10, 85), f"Kite State: {self.kite_state}",
                 fill=(150, 150, 150), font=font_small)

        # Alvo atual
        if self.current_target:
            target_text = f"Alvo: {self.current_target['mob']['class']} ({self.current_target['dist_tiles']:.1f}t)"
            draw.text((10, 110), target_text,
                     fill=(255, 255, 255), font=font)

        # Estatísticas (direita)
        x_offset = width - 200
        y_offset = 10

        draw.text((x_offset, y_offset), f"Frames: {self.frame_count}",
                 fill=(200, 200, 200), font=font_small)

        y_offset += 20
        draw.text((x_offset, y_offset), f"Coins: {self.coins_collected}",
                 fill=(255, 255, 0), font=font_small)

        # Modo debug
        if self.debug_mode:
            draw.text((width // 2 - 100, 10), "🔍 DEBUG MODE (mostrando confiança)",
                     fill=(255, 255, 0), font=font_bold)

        # Controles (inferior)
        controls = "P: Pause Bot  |  ESPAÇO: Toggle View  |  D: Debug Mode  |  Q: Sair"
        draw.text((10, height - 25), controls,
                 fill=(150, 150, 150), font=font_small)

        return img_pil

    def atualizar_display(self, img, deteccoes):
        """Atualiza visualização"""
        # Se não tem interface gráfica (modo headless), não faz nada
        if self.root is None:
            return

        # Converter BGR para RGB para PIL
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)

        # Desenhar detecções
        img_pil = self.desenhar_deteccoes(img_pil, deteccoes)

        # Overlay info
        img_pil = self.criar_overlay_info(img_pil, deteccoes)

        # Redimensionar
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        max_width = int(screen_width * 0.8)
        max_height = int(screen_height * 0.8)

        width, height = img_pil.size
        scale = min(max_width/width, max_height/height, 1.0)

        if scale < 1.0:
            new_width = int(width * scale)
            new_height = int(height * scale)
            img_pil = img_pil.resize((new_width, new_height), Image.LANCZOS)

        # Atualizar canvas
        self.photo = ImageTk.PhotoImage(img_pil)
        self.canvas.config(width=img_pil.width, height=img_pil.height)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

    def on_key_press(self, event):
        """Handler de teclas"""
        key = event.char.lower()

        if key == 'q':
            self.stop()
        elif key == 'p':
            self.bot_active = not self.bot_active
            status = "ATIVO" if self.bot_active else "PAUSADO"
            print(f"\n🤖 Bot: {status}")
        elif key == ' ':
            self.show_visualization = not self.show_visualization
            print(f"Visualização: {'ON' if self.show_visualization else 'OFF'}")
        elif key == 'd':
            self.debug_mode = not self.debug_mode
            status = "ON" if self.debug_mode else "OFF"
            print(f"🔍 Debug Mode: {status} (mostra confiança das detecções)")

    def update_loop(self):
        """Loop principal"""
        if self.running:
            self.processar_frame()
            self.root.after(1, self.update_loop)

    def start(self):
        """Inicia bot"""
        print("\n" + "=" * 60)
        print("🤖 FARM BOT - ARQUEIRO COM KITING")
        print("=" * 60)

        # Conectar
        if not self.conectar_bluestacks():
            return

        # Carregar modelo
        if not self.carregar_modelo():
            return

        print("\n✅ Tudo pronto!")
        print("\n🎮 CONTROLES:")
        print("   P           - Ativar/Pausar bot")
        print("   D           - Debug mode (mostra % de confiança)")
        print("   ESPAÇO      - Mostrar/Ocultar visualização")
        print("   Q           - Sair")
        print("\n⚔️ COMPORTAMENTO (KITING ATIVO):")
        print(f"   • Se mob < {self.config.min_safe_distance} tiles → RECUAR URGENTE")
        print(f"   • Se mob {self.config.min_safe_distance}-{self.config.max_attack_range} tiles →")
        print(f"     KITING: Alterna ATACAR ⚔️ → MOVER 🏃 → ATACAR ⚔️ → MOVER 🏃")
        print(f"     (mantém distância enquanto ataca)")
        print(f"   • Se mob > {self.config.max_attack_range} tiles → APROXIMAR")
        print(f"   • Coleta coins < 3 tiles automaticamente")
        print("\n⚠️ AVISO: Bot iniciará PAUSADO. Pressione P para ativar!")
        print("\n▶️ Iniciando visualização...\n")

        # Criar janela
        self.root = tk.Tk()
        self.root.title("🤖 Farm Bot - Rucoy Arqueiro")

        # Canvas
        self.canvas = tk.Canvas(self.root, bg='black')
        self.canvas.pack()

        # Bind teclas
        self.root.bind('<Key>', self.on_key_press)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        # Iniciar
        self.running = True
        self.update_loop()

        # Rodar
        self.root.mainloop()

    def stop(self):
        """Para bot"""
        print("\n🛑 Encerrando bot...")

        print(f"\n📊 ESTATÍSTICAS:")
        print(f"   Frames processados: {self.frame_count}")
        print(f"   Coins coletados: {self.coins_collected}")

        if self.fps_buffer:
            avg_fps = sum(self.fps_buffer) / len(self.fps_buffer)
            print(f"   FPS médio: {avg_fps:.1f}")

        self.running = False
        if self.root:
            self.root.quit()
            self.root.destroy()


def main():
    bot = ArcherFarmBot()
    bot.start()


if __name__ == "__main__":
    main()
