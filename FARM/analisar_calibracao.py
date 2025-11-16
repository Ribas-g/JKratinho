"""
ANALISADOR DE CALIBRAÇÃO DA CÂMERA VIRTUAL

Este script analisa dados coletados MANUALMENTE e calcula a escala ideal.

COMO USAR:
1. Rode o camera_virtual.py e faça vários testes manuais
2. Para cada teste, anote os dados da seção "📊 COMPARAÇÃO VIRTUAL vs REAL"
3. Rode este script e cole os dados
4. Script vai calcular a escala média ideal!

DADOS NECESSÁRIOS DE CADA TESTE:
- Clique tela (ex: 745)
- Delta real (quanto andou no mapa, ex: -4)
"""

import json
from pathlib import Path

def analisar_calibracao():
    print("=" * 70)
    print("📊 ANALISADOR DE CALIBRAÇÃO - CÂMERA VIRTUAL")
    print("=" * 70)
    print()
    print("Cole os dados dos seus testes manuais:")
    print("Para cada teste, informe:")
    print("  1. Coordenada X do clique na tela")
    print("  2. Quanto andou REAL no mapa (delta X ou Y)")
    print()
    print("Pressione ENTER sem digitar nada para finalizar")
    print()

    centro_tela = 800  # Centro X da tela
    dados_testes = []

    while True:
        print("-" * 70)
        teste_num = len(dados_testes) + 1
        print(f"\n📝 TESTE {teste_num}:")

        # Pedir clique na tela
        clique_input = input("  Clique tela (ex: 745, ou ENTER para parar): ").strip()
        if not clique_input:
            break

        try:
            clique_tela = int(clique_input)
        except ValueError:
            print("  ❌ Valor inválido! Use apenas números.")
            continue

        # Pedir delta real
        delta_input = input("  Delta REAL no mapa (ex: -4 ou +8): ").strip()
        if not delta_input:
            break

        try:
            delta_real = float(delta_input)
        except ValueError:
            print("  ❌ Valor inválido! Use números (pode usar negativo).")
            continue

        # Calcular delta na tela
        delta_tela = abs(clique_tela - centro_tela)

        # Calcular escala deste teste
        if abs(delta_real) < 0.1:
            print("  ⚠️ Delta real muito pequeno (< 0.1px), pulando...")
            continue

        escala = delta_tela / abs(delta_real)

        dados_testes.append({
            'clique_tela': clique_tela,
            'delta_tela': delta_tela,
            'delta_real': delta_real,
            'escala': escala
        })

        print(f"  ✅ Registrado!")
        print(f"     Delta tela: {delta_tela}px")
        print(f"     Delta real: {delta_real}px")
        print(f"     Escala calculada: {escala:.3f}")

    if not dados_testes:
        print("\n❌ Nenhum teste registrado!")
        return

    print("\n" + "=" * 70)
    print("📊 ANÁLISE DOS RESULTADOS")
    print("=" * 70)

    # Mostrar todos os testes
    print(f"\n📋 Total de testes: {len(dados_testes)}")
    print()
    for i, teste in enumerate(dados_testes, 1):
        print(f"  Teste {i}:")
        print(f"    Clique: {teste['clique_tela']}px")
        print(f"    Delta tela: {teste['delta_tela']}px")
        print(f"    Delta real: {teste['delta_real']:+.1f}px")
        print(f"    Escala: {teste['escala']:.3f}")
        print()

    # Calcular média e desvio
    escalas = [t['escala'] for t in dados_testes]
    escala_media = sum(escalas) / len(escalas)
    escala_min = min(escalas)
    escala_max = max(escalas)

    # Calcular desvio padrão simples
    if len(escalas) > 1:
        variancia = sum((e - escala_media) ** 2 for e in escalas) / len(escalas)
        desvio = variancia ** 0.5
    else:
        desvio = 0

    print("=" * 70)
    print("🎯 ESCALA RECOMENDADA:")
    print("=" * 70)
    print(f"  Média:         {escala_media:.3f}")
    print(f"  Mínima:        {escala_min:.3f}")
    print(f"  Máxima:        {escala_max:.3f}")
    print(f"  Desvio padrão: {desvio:.3f}")
    print()

    # Calcular FOV com a nova escala
    fov_largura = 1600 / escala_media
    fov_altura = 900 / escala_media

    print(f"📐 FOV no mapa mundo (com escala {escala_media:.1f}):")
    print(f"  Largura: {fov_largura:.0f}px")
    print(f"  Altura:  {fov_altura:.0f}px")
    print()

    # Calcular 1 tile no mapa
    # Se sabemos que 1 tile na tela = 100px
    # E a escala é X, então 1 tile no mapa = 100/X
    tile_no_mapa = 100 / escala_media
    print(f"📏 1 tile do jogo = {tile_no_mapa:.1f}px no mapa mundo")
    print()

    # Perguntar se quer salvar
    print("=" * 70)
    salvar = input("💾 Salvar esta escala no map_transform_config.json? (s/n): ").strip().lower()

    if salvar == 's':
        config = {
            'centro_mapa_tela': {'x': 800, 'y': 450},
            'escala': {
                'x': round(escala_media, 3),
                'y': round(escala_media, 3)
            },
            'observacoes': f'Calibrado via testes manuais - {len(dados_testes)} amostras. FOV {fov_largura:.0f}×{fov_altura:.0f}px. 1 tile = {tile_no_mapa:.1f}px mundo'
        }

        with open('map_transform_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"✅ Salvo! Escala: {escala_media:.3f}")
        print(f"   Arquivo: map_transform_config.json")
    else:
        print("❌ Não salvo. Você pode rodar o script novamente.")

    print()
    print("=" * 70)
    print("✅ Análise concluída!")
    print("=" * 70)

if __name__ == "__main__":
    analisar_calibracao()
