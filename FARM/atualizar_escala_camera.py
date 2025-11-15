#!/usr/bin/env python3
"""
ATUALIZAR ESCALA DA CÂMERA VIRTUAL

Atualiza map_transform_config.json com escala correta
baseada na medição do Photoshop
"""

import json
import os
import sys
from pathlib import Path

# Valores baseados na medição do Photoshop
ESCALA_MEDIDA_X = 1600 / 334  # 4.79
ESCALA_MEDIDA_Y = 900 / 189   # 4.76
ESCALA_ARREDONDADA = 5.0

def atualizar_config(escala_x, escala_y, usar_arredondada=False):
    """
    Atualiza arquivo de configuração

    Args:
        escala_x, escala_y: Valores de escala
        usar_arredondada: Se True, usa 5.0 ao invés de 4.78
    """
    # Caminho do arquivo (na raiz do projeto)
    config_path = Path(__file__).parent.parent / 'map_transform_config.json'

    # Configuração nova
    config = {
        "centro_mapa_tela": {
            "x": 800,
            "y": 450
        },
        "escala": {
            "x": escala_x,
            "y": escala_y
        },
        "observacoes": (
            f"Calibrado via medição Photoshop - FOV visão do jogo: 334×189px no mapa mundo. "
            f"Escala calculada: {ESCALA_MEDIDA_X:.2f}×{ESCALA_MEDIDA_Y:.2f}. "
            f"{'Arredondada para 5.0 (compatibilidade navegador)' if usar_arredondada else 'Valor exato da medição'}"
        )
    }

    # Salvar
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Configuração atualizada: {config_path}")
    print(f"   Escala X: {escala_x:.2f}")
    print(f"   Escala Y: {escala_y:.2f}")

    # Calcular FOV resultante
    fov_x = 1600 / escala_x
    fov_y = 900 / escala_y
    print(f"\n📐 FOV no mapa mundo:")
    print(f"   {fov_x:.1f}×{fov_y:.1f}px")
    print(f"   {fov_x/20:.1f}×{fov_y/20:.1f} tiles (assumindo 20px/tile)")


def main():
    print("="*70)
    print("🔧 ATUALIZAR ESCALA DA CÂMERA VIRTUAL")
    print("="*70)

    print(f"""
Medição do Photoshop:
- FOV visível: 334×189px (no mapa mundo)
- Escala calculada: {ESCALA_MEDIDA_X:.2f}×{ESCALA_MEDIDA_Y:.2f}

Opções:
[1] Usar escala EXATA (4.78)
[2] Usar escala ARREDONDADA (5.0) - recomendado!
[3] Cancelar
""")

    while True:
        escolha = input("Escolha [1/2/3]: ").strip()

        if escolha == '1':
            print("\n✅ Usando escala EXATA da medição...")
            atualizar_config(ESCALA_MEDIDA_X, ESCALA_MEDIDA_Y, usar_arredondada=False)
            break

        elif escolha == '2':
            print("\n✅ Usando escala ARREDONDADA (5.0)...")
            atualizar_config(ESCALA_ARREDONDADA, ESCALA_ARREDONDADA, usar_arredondada=True)
            break

        elif escolha == '3':
            print("\n❌ Cancelado!")
            return

        else:
            print("❌ Opção inválida! Escolha 1, 2 ou 3.")

    print(f"""
{"="*70}
✅ CONFIGURAÇÃO ATUALIZADA!
{"="*70}

PRÓXIMOS PASSOS:

1. Testar o sistema:
   python FARM/camera_virtual.py

2. No modo interativo:
   - Use WASD para mover
   - SPACE para executar movimento
   - Veja se os cliques acertam o alvo

3. Ajustar se necessário:
   - Teclas M/N para ajustar escala
   - Tecla X para salvar nova calibração

4. Quando estiver perfeito:
   - O sistema está pronto para usar!
   - GPS uma vez + rastreamento virtual funcionando
""")


if __name__ == "__main__":
    main()
