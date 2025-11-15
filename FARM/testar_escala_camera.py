#!/usr/bin/env python3
"""
SCRIPT DE TESTE: Calibrar escala da câmera virtual

Testa diferentes valores de escala e compara resultados
"""

import json

def testar_escala(escala_x, escala_y, descricao):
    """
    Testa uma escala específica

    Args:
        escala_x, escala_y: Valores de escala a testar
        descricao: Descrição do teste
    """
    print("\n" + "="*70)
    print(f"🧪 TESTE: {descricao}")
    print(f"   Escala X: {escala_x:.2f}")
    print(f"   Escala Y: {escala_y:.2f}")
    print("="*70)

    # Calcular FOV no mapa mundo
    tela_largura = 1600
    tela_altura = 900

    fov_mapa_x = tela_largura / escala_x
    fov_mapa_y = tela_altura / escala_y

    print(f"\n📐 FOV no mapa mundo:")
    print(f"   Largura: {fov_mapa_x:.1f}px")
    print(f"   Altura: {fov_mapa_y:.1f}px")

    # Calcular em tiles (assumindo 1 tile = 20px no mapa)
    tiles_x = fov_mapa_x / 20
    tiles_y = fov_mapa_y / 20

    print(f"\n🎮 Em tiles (20px/tile):")
    print(f"   Horizontal: {tiles_x:.1f} tiles")
    print(f"   Vertical: {tiles_y:.1f} tiles")

    # Exemplo de conversão
    print(f"\n📍 Exemplo de conversão:")
    print(f"   Player em (374, 1342) no mapa mundo")
    print(f"   Destino em (400, 1350) no mapa mundo")

    delta_x = 400 - 374  # 26px
    delta_y = 1350 - 1342  # 8px

    x_tela = 800 + (delta_x * escala_x)
    y_tela = 450 + (delta_y * escala_y)

    print(f"   Delta: ({delta_x}, {delta_y}) pixels mundo")
    print(f"   Clique na tela: ({int(x_tela)}, {int(y_tela)})")

    # Verificar se está dentro da tela
    if 0 <= x_tela <= 1600 and 0 <= y_tela <= 900:
        print(f"   ✅ Clique dentro da tela")
    else:
        print(f"   ❌ Clique FORA da tela!")

    return {
        'escala_x': escala_x,
        'escala_y': escala_y,
        'fov_mapa': (fov_mapa_x, fov_mapa_y),
        'tiles': (tiles_x, tiles_y),
        'exemplo_clique': (x_tela, y_tela)
    }


def main():
    print("="*70)
    print("🎯 TESTE DE CALIBRAÇÃO DE ESCALA - CÂMERA VIRTUAL")
    print("="*70)

    resultados = []

    # TESTE 1: Configuração atual (ERRADA)
    resultado1 = testar_escala(20.0, 20.0, "Configuração ATUAL (20.0)")
    resultados.append(('atual', resultado1))

    # TESTE 2: Medição do usuário (Photoshop)
    resultado2 = testar_escala(4.78, 4.76, "Medição PHOTOSHOP (334×189px)")
    resultados.append(('photoshop', resultado2))

    # TESTE 3: Arredondado para 5.0 (igual navegador)
    resultado3 = testar_escala(5.0, 5.0, "Arredondado 5.0 (igual navegador)")
    resultados.append(('navegador', resultado3))

    # TESTE 4: Baseado no NCC (320×180)
    escala_ncc_x = 1600 / 320
    escala_ncc_y = 900 / 180
    resultado4 = testar_escala(escala_ncc_x, escala_ncc_y, "Baseado NCC (320×180px)")
    resultados.append(('ncc', resultado4))

    # COMPARAÇÃO FINAL
    print("\n" + "="*70)
    print("📊 COMPARAÇÃO FINAL")
    print("="*70)

    print(f"\n{'Teste':<20} {'Escala':<12} {'FOV Mapa':<15} {'Tiles':<12}")
    print("-" * 70)

    for nome, res in resultados:
        fov_str = f"{res['fov_mapa'][0]:.0f}×{res['fov_mapa'][1]:.0f}px"
        tiles_str = f"{res['tiles'][0]:.1f}×{res['tiles'][1]:.1f}"
        print(f"{nome:<20} {res['escala_x']:<12.2f} {fov_str:<15} {tiles_str:<12}")

    # RECOMENDAÇÃO
    print("\n" + "="*70)
    print("💡 RECOMENDAÇÃO")
    print("="*70)

    print(f"""
Com base nas medições do Photoshop (334×189px):

1. ✅ MELHOR OPÇÃO: Escala 4.78
   - FOV: {resultados[1][1]['fov_mapa'][0]:.0f}×{resultados[1][1]['fov_mapa'][1]:.0f}px
   - Baseado em medição REAL

2. ✅ ALTERNATIVA: Escala 5.0 (arredondada)
   - FOV: {resultados[2][1]['fov_mapa'][0]:.0f}×{resultados[2][1]['fov_mapa'][1]:.0f}px
   - Consistente com navegador
   - Erro de ~4% (aceitável)

3. ❌ EVITAR: Escala 20.0
   - FOV: {resultados[0][1]['fov_mapa'][0]:.0f}×{resultados[0][1]['fov_mapa'][1]:.0f}px
   - MUITO pequeno (erro de 318%!)

PRÓXIMO PASSO:
Execute: python FARM/atualizar_escala_camera.py
Para atualizar a configuração automaticamente.
""")


if __name__ == "__main__":
    main()
