"""
SKILL MANAGER - Sistema de gerenciamento de habilidades (Skills)

Funcionalidades:
- Gerencia cooldowns de skills
- Decide quando usar cada skill baseado em situação
- Suporta todas as 3 classes (Guerreiro, Arqueiro, Mago)

SKILLS POR CLASSE:
- Guerreiro: Dash (movimento + dano), Whirlwind (AoE)
- Arqueiro: Multi-shot (área), Power Shot (dano alto)
- Mago: Fireball (área), Ice Blast (slow + dano)
"""

import time
import json
from pathlib import Path


class SkillManager:
    """Gerenciador de habilidades (Skills)"""

    def __init__(self, device, classe='warrior', config_path='FARM/interface_config.json'):
        """
        Inicializa gerenciador de skills

        Args:
            device: Dispositivo ADB
            classe: 'warrior', 'archer' ou 'mage'
            config_path: Caminho para interface_config.json
        """
        print(f"⚔️ Inicializando Skill Manager ({classe})...")

        self.device = device
        self.classe = classe

        # Carregar configurações de interface
        if not Path(config_path).exists():
            config_path = Path(__file__).parent / 'interface_config.json'

        with open(config_path, 'r', encoding='utf-8') as f:
            self.interface_config = json.load(f)

        # Database de skills por classe
        self.skills_database = {
            'warrior': {
                'dash': {
                    'nome': 'Dash',
                    'cooldown': 10.0,
                    'last_used': 0,
                    'descricao': 'Movimento rápido + dano'
                },
                'whirlwind': {
                    'nome': 'Whirlwind',
                    'cooldown': 15.0,
                    'last_used': 0,
                    'descricao': 'AoE - ataque em área'
                }
            },
            'archer': {
                'multi_shot': {
                    'nome': 'Multi-shot',
                    'cooldown': 8.0,
                    'last_used': 0,
                    'descricao': 'Atira em área'
                },
                'power_shot': {
                    'nome': 'Power Shot',
                    'cooldown': 12.0,
                    'last_used': 0,
                    'descricao': 'Dano alto em 1 alvo'
                }
            },
            'mage': {
                'fireball': {
                    'nome': 'Fireball',
                    'cooldown': 7.0,
                    'last_used': 0,
                    'descricao': 'Dano em área (fogo)'
                },
                'ice_blast': {
                    'nome': 'Ice Blast',
                    'cooldown': 10.0,
                    'last_used': 0,
                    'descricao': 'Slow + dano (gelo)'
                }
            }
        }

        self.skills = self.skills_database[self.classe]

        print(f"   ✅ Skills carregadas:")
        for skill_name, skill_data in self.skills.items():
            print(f"      - {skill_data['nome']}: CD={skill_data['cooldown']}s ({skill_data['descricao']})")

    def pode_usar_skill(self, skill_name):
        """
        Verifica se skill está fora de cooldown

        Args:
            skill_name: Nome da skill ('dash', 'whirlwind', etc)

        Returns:
            bool: True se pode usar
        """
        if skill_name not in self.skills:
            return False

        skill = self.skills[skill_name]
        tempo_atual = time.time()
        tempo_desde_uso = tempo_atual - skill['last_used']

        return tempo_desde_uso >= skill['cooldown']

    def usar_skill(self, skill_name):
        """
        Usa skill (clica no botão)

        Args:
            skill_name: Nome da skill

        Returns:
            bool: True se usou, False se em cooldown
        """
        if not self.pode_usar_skill(skill_name):
            return False

        # Clicar botão skill
        x, y = self.interface_config['buttons']['skill']['x'], self.interface_config['buttons']['skill']['y']
        self.device.shell(f"input tap {x} {y}")

        # Registrar uso
        self.skills[skill_name]['last_used'] = time.time()

        print(f"      ⚡ Skill usada: {self.skills[skill_name]['nome']}")
        return True

    def decidir_skill_guerreiro(self, mobs_detectados, target, calcular_distancia_func):
        """
        Decide qual skill usar para GUERREIRO

        Lógica:
        1. DASH: Se alvo distante (> 2.0 tiles) - fechar distância
        2. WHIRLWIND: Se 3+ mobs muito próximos (< 1.5 tiles) - AoE

        Args:
            mobs_detectados: Lista de mobs detectados
            target: Alvo atual (ou None)
            calcular_distancia_func: Função para calcular distância em tiles

        Returns:
            str: Nome da skill a usar ou None
        """
        # DASH: Fechar distância com alvo
        if target:
            dist_tiles = calcular_distancia_func(target['bbox'])[1]  # [dist_px, dist_tiles]

            # Se alvo está longe (> 2 tiles), usar Dash
            if dist_tiles > 2.0 and self.pode_usar_skill('dash'):
                print(f"      🎯 Alvo longe ({dist_tiles:.1f}t) - Dash para fechar!")
                return 'dash'

        # WHIRLWIND: Múltiplos mobs próximos (AoE)
        mobs_proximos = []
        for mob in mobs_detectados:
            dist_tiles = calcular_distancia_func(mob['bbox'])[1]
            if dist_tiles <= 1.5:  # Muito próximo
                mobs_proximos.append(mob)

        if len(mobs_proximos) >= 3 and self.pode_usar_skill('whirlwind'):
            print(f"      💥 {len(mobs_proximos)} mobs próximos - Whirlwind AoE!")
            return 'whirlwind'

        return None

    def decidir_skill_arqueiro(self, mobs_detectados, target, calcular_distancia_func):
        """
        Decide qual skill usar para ARQUEIRO

        Lógica:
        1. MULTI-SHOT: Se 3+ mobs próximos (< 3.0 tiles)
        2. POWER SHOT: Para mobs fortes/bosses

        Returns:
            str: Nome da skill a usar ou None
        """
        # MULTI-SHOT: Grupos de mobs
        mobs_proximos = []
        for mob in mobs_detectados:
            dist_tiles = calcular_distancia_func(mob['bbox'])[1]
            if dist_tiles <= 3.0:
                mobs_proximos.append(mob)

        if len(mobs_proximos) >= 3 and self.pode_usar_skill('multi_shot'):
            print(f"      🏹 {len(mobs_proximos)} mobs agrupados - Multi-shot!")
            return 'multi_shot'

        # POWER SHOT: Mobs fortes (skeleton, spider, etc)
        if target and target.get('class') in ['skeleton', 'spider', 'scorpion']:
            if self.pode_usar_skill('power_shot'):
                print(f"      🎯 Mob forte ({target['class']}) - Power Shot!")
                return 'power_shot'

        return None

    def decidir_skill_mago(self, mobs_detectados, target, calcular_distancia_func):
        """
        Decide qual skill usar para MAGO

        Lógica:
        1. FIREBALL: Se 2+ mobs próximos (< 4.0 tiles) - AoE
        2. ICE BLAST: Para kiting (slow no alvo)

        Returns:
            str: Nome da skill a usar ou None
        """
        # FIREBALL: Grupos
        mobs_proximos = []
        for mob in mobs_detectados:
            dist_tiles = calcular_distancia_func(mob['bbox'])[1]
            if dist_tiles <= 4.0:
                mobs_proximos.append(mob)

        if len(mobs_proximos) >= 2 and self.pode_usar_skill('fireball'):
            print(f"      🔥 {len(mobs_proximos)} mobs em range - Fireball!")
            return 'fireball'

        # ICE BLAST: Kiting (slow)
        if target:
            dist_tiles = calcular_distancia_func(target['bbox'])[1]
            if dist_tiles < 3.0 and self.pode_usar_skill('ice_blast'):
                print(f"      ❄️ Mob próximo - Ice Blast para slow!")
                return 'ice_blast'

        return None

    def decidir_e_usar_skill(self, mobs_detectados, target, calcular_distancia_func):
        """
        Decide e usa skill automaticamente baseado na classe

        Args:
            mobs_detectados: Lista de mobs detectados
            target: Alvo atual
            calcular_distancia_func: Função para calcular distância

        Returns:
            str: Skill usada ou None
        """
        # Decidir skill baseado na classe
        if self.classe == 'warrior':
            skill_to_use = self.decidir_skill_guerreiro(mobs_detectados, target, calcular_distancia_func)
        elif self.classe == 'archer':
            skill_to_use = self.decidir_skill_arqueiro(mobs_detectados, target, calcular_distancia_func)
        elif self.classe == 'mage':
            skill_to_use = self.decidir_skill_mago(mobs_detectados, target, calcular_distancia_func)
        else:
            return None

        # Usar skill se decidiu usar
        if skill_to_use:
            if self.usar_skill(skill_to_use):
                return skill_to_use

        return None

    def trocar_classe(self, nova_classe):
        """
        Troca de classe (clica no botão)

        Args:
            nova_classe: 'warrior', 'archer' ou 'mage'

        Returns:
            bool: True se trocou
        """
        if nova_classe not in ['warrior', 'archer', 'mage']:
            print(f"      ❌ Classe inválida: {nova_classe}")
            return False

        if nova_classe == self.classe:
            print(f"      ℹ️ Já está na classe {nova_classe}")
            return False

        # Pegar coordenadas do botão
        button_key = f'class_{nova_classe}'
        x, y = self.interface_config['buttons'][button_key]['x'], self.interface_config['buttons'][button_key]['y']

        # Clicar
        self.device.shell(f"input tap {x} {y}")

        # Atualizar classe
        self.classe = nova_classe
        self.skills = self.skills_database[self.classe]

        print(f"      🔄 Trocado para classe: {nova_classe.upper()}")
        return True

    def get_cooldowns_status(self):
        """
        Retorna status de cooldowns (para debug/dashboard)

        Returns:
            dict: Status de cada skill
        """
        tempo_atual = time.time()
        status = {}

        for skill_name, skill_data in self.skills.items():
            tempo_desde_uso = tempo_atual - skill_data['last_used']
            tempo_restante = max(0, skill_data['cooldown'] - tempo_desde_uso)
            disponivel = tempo_restante == 0

            status[skill_name] = {
                'nome': skill_data['nome'],
                'disponivel': disponivel,
                'tempo_restante': tempo_restante,
                'cooldown_total': skill_data['cooldown']
            }

        return status
