"""
POTION MANAGER - Sistema de gerenciamento automático de poções

Funcionalidades:
- Lê HP atual do texto (ex: "500/600")
- Lê Mana % da barra (azul)
- Lê XP % da barra (branca)
- Lê quantidade de poções disponíveis
- Usa poções automaticamente baseado em thresholds
- Cooldown inteligente entre usos
"""

import cv2
import numpy as np
import json
import re
import time
from pathlib import Path
try:
    import pytesseract
except ImportError:
    pytesseract = None


class PotionManager:
    """Gerenciador automático de poções"""

    def __init__(self, device, config_path='FARM/interface_config.json'):
        """
        Inicializa gerenciador de poções

        Args:
            device: Dispositivo ADB
            config_path: Caminho para interface_config.json
        """
        print("🧪 Inicializando Potion Manager...")

        self.device = device

        # Carregar configurações
        if not Path(config_path).exists():
            config_path = Path(__file__).parent / 'interface_config.json'

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        print(f"   ✅ Config carregado: {config_path}")

        # Thresholds (configurável)
        self.hp_threshold_critical = 0.3  # < 30% HP = crítico
        self.hp_threshold_low = 0.5       # < 50% HP = baixo
        self.mana_threshold = 0.3         # < 30% Mana = usar poção

        # Cooldowns
        self.potion_cooldown = 3.0  # 3 segundos entre poções
        self.last_hp_potion_time = 0
        self.last_mana_potion_time = 0

        # Cache
        self.last_hp_read = {"current": 0, "max": 0, "percentage": 1.0}
        self.last_mana_read = 1.0
        self.last_xp_read = 0.0
        self.potions_available = {"hp": 0, "mana": 0}

        print("   ✅ Potion Manager pronto!")
        print(f"      HP Thresholds: Crítico={self.hp_threshold_critical*100:.0f}%, Baixo={self.hp_threshold_low*100:.0f}%")
        print(f"      Mana Threshold: {self.mana_threshold*100:.0f}%")
        print(f"      Cooldown: {self.potion_cooldown}s")

    def ler_hp_texto(self, screenshot):
        """
        Lê HP do texto (ex: "500/600")

        Returns:
            dict: {'current': 500, 'max': 600, 'percentage': 0.83}
        """
        cfg = self.config['status_bars']['hp_texto']
        x1, y1, x2, y2 = cfg['x1'], cfg['y1'], cfg['x2'], cfg['y2']

        # Extrair ROI
        roi = screenshot[y1:y2, x1:x2]

        # Preprocessar para OCR
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Aumentar contraste
        gray = cv2.convertScaleAbs(gray, alpha=2.0, beta=0)

        # Threshold adaptativo
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        # OCR
        if pytesseract:
            try:
                texto = pytesseract.image_to_string(thresh, config='--psm 7 digits')

                # Parse "500/600" ou "500 / 600"
                match = re.search(r'(\d+)\s*/\s*(\d+)', texto)
                if match:
                    hp_atual = int(match.group(1))
                    hp_max = int(match.group(2))
                    hp_pct = hp_atual / hp_max if hp_max > 0 else 1.0

                    self.last_hp_read = {
                        'current': hp_atual,
                        'max': hp_max,
                        'percentage': hp_pct
                    }
                    return self.last_hp_read
            except:
                pass

        # Fallback: retornar último valor lido
        return self.last_hp_read

    def ler_barra_percentage(self, screenshot, barra_type='mana'):
        """
        Lê porcentagem de uma barra (Mana ou XP)

        Args:
            screenshot: Screenshot completo
            barra_type: 'mana' ou 'xp'

        Returns:
            float: 0.0 a 1.0 (porcentagem)
        """
        if barra_type == 'mana':
            cfg = self.config['status_bars']['mana_barra']
        else:  # xp
            cfg = self.config['status_bars']['xp_barra']

        x1, y1, x2, y2 = cfg['x1'], cfg['y1'], cfg['x2'], cfg['y2']

        # Extrair ROI
        roi = screenshot[y1:y2, x1:x2]

        # Converter para HSV
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Máscara da cor
        hsv_cfg = cfg['cor_cheia_hsv']
        lower = np.array([hsv_cfg['h_min'], hsv_cfg['s_min'], hsv_cfg['v_min']])
        upper = np.array([hsv_cfg['h_max'], hsv_cfg['s_max'], hsv_cfg['v_max']])
        mask = cv2.inRange(hsv, lower, upper)

        # Contar pixels da cor
        color_pixels = np.sum(mask > 0)
        total_pixels = roi.shape[0] * roi.shape[1]

        # Calcular porcentagem
        percentage = color_pixels / total_pixels if total_pixels > 0 else 0.0

        # Cache
        if barra_type == 'mana':
            self.last_mana_read = percentage
        else:
            self.last_xp_read = percentage

        return percentage

    def ler_quantidade_pocoes(self, screenshot):
        """
        Lê quantidade de poções disponíveis (OCR)

        Returns:
            dict: {'hp': 10, 'mana': 5}
        """
        result = {'hp': 0, 'mana': 0}

        if not pytesseract:
            return self.potions_available  # Retornar cache se OCR não disponível

        # Ler HP potion count
        try:
            cfg_hp = self.config['potions_count']['hp_potion_count']
            x1, y1, x2, y2 = cfg_hp['x1'], cfg_hp['y1'], cfg_hp['x2'], cfg_hp['y2']
            roi_hp = screenshot[y1:y2, x1:x2]

            gray_hp = cv2.cvtColor(roi_hp, cv2.COLOR_BGR2GRAY)
            thresh_hp = cv2.threshold(gray_hp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

            texto_hp = pytesseract.image_to_string(thresh_hp, config='--psm 7 digits')
            match_hp = re.search(r'(\d+)', texto_hp)
            if match_hp:
                result['hp'] = int(match_hp.group(1))
        except:
            result['hp'] = self.potions_available['hp']

        # Ler Mana potion count
        try:
            cfg_mana = self.config['potions_count']['mana_potion_count']
            x1, y1, x2, y2 = cfg_mana['x1'], cfg_mana['y1'], cfg_mana['x2'], cfg_mana['y2']
            roi_mana = screenshot[y1:y2, x1:x2]

            gray_mana = cv2.cvtColor(roi_mana, cv2.COLOR_BGR2GRAY)
            thresh_mana = cv2.threshold(gray_mana, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

            texto_mana = pytesseract.image_to_string(thresh_mana, config='--psm 7 digits')
            match_mana = re.search(r'(\d+)', texto_mana)
            if match_mana:
                result['mana'] = int(match_mana.group(1))
        except:
            result['mana'] = self.potions_available['mana']

        self.potions_available = result
        return result

    def usar_pocao_hp(self):
        """Usa poção HP (clica no botão)"""
        tempo_atual = time.time()

        # Verificar cooldown
        if (tempo_atual - self.last_hp_potion_time) < self.potion_cooldown:
            return False

        # Clicar botão
        x, y = self.config['buttons']['hp_potion']['x'], self.config['buttons']['hp_potion']['y']
        self.device.shell(f"input tap {x} {y}")

        self.last_hp_potion_time = tempo_atual
        print(f"      💊 Poção HP usada!")
        return True

    def usar_pocao_mana(self):
        """Usa poção Mana (clica no botão)"""
        tempo_atual = time.time()

        # Verificar cooldown
        if (tempo_atual - self.last_mana_potion_time) < self.potion_cooldown:
            return False

        # Clicar botão
        x, y = self.config['buttons']['mana_potion']['x'], self.config['buttons']['mana_potion']['y']
        self.device.shell(f"input tap {x} {y}")

        self.last_mana_potion_time = tempo_atual
        print(f"      💧 Poção Mana usada!")
        return True

    def gerenciar_automatico(self, screenshot, verbose=False):
        """
        Gerenciamento automático de poções

        Prioridades:
        1. HP CRÍTICO (< 30%) → máxima prioridade
        2. HP BAIXO (< 50%) → alta prioridade
        3. Mana baixa (< 30%) → média prioridade

        Args:
            screenshot: Screenshot atual do jogo
            verbose: Se True, mostra detalhes

        Returns:
            str: Ação tomada ('hp_critical', 'hp_low', 'mana_low', None)
        """
        # Ler status
        hp_data = self.ler_hp_texto(screenshot)
        mana_pct = self.ler_barra_percentage(screenshot, 'mana')

        hp_pct = hp_data['percentage']

        if verbose:
            print(f"      📊 Status: HP={hp_pct*100:.0f}% ({hp_data['current']}/{hp_data['max']}), Mana={mana_pct*100:.0f}%")

        # PRIORIDADE 1: HP CRÍTICO (< 30%)
        if hp_pct < self.hp_threshold_critical:
            if self.usar_pocao_hp():
                print(f"      🚨 HP CRÍTICO ({hp_pct*100:.0f}%)! Usando poção...")
                return 'hp_critical'

        # PRIORIDADE 2: HP BAIXO (< 50%)
        elif hp_pct < self.hp_threshold_low:
            if self.usar_pocao_hp():
                print(f"      ⚠️ HP baixo ({hp_pct*100:.0f}%)! Usando poção...")
                return 'hp_low'

        # PRIORIDADE 3: Mana baixa (< 30%)
        if mana_pct < self.mana_threshold:
            if self.usar_pocao_mana():
                print(f"      💧 Mana baixa ({mana_pct*100:.0f}%)! Usando poção...")
                return 'mana_low'

        return None

    def get_status_completo(self, screenshot):
        """
        Retorna status completo (para debug/dashboard)

        Returns:
            dict com todos os dados
        """
        hp_data = self.ler_hp_texto(screenshot)
        mana_pct = self.ler_barra_percentage(screenshot, 'mana')
        xp_pct = self.ler_barra_percentage(screenshot, 'xp')
        potions = self.ler_quantidade_pocoes(screenshot)

        return {
            'hp': hp_data,
            'mana': {'percentage': mana_pct},
            'xp': {'percentage': xp_pct},
            'potions': potions
        }
