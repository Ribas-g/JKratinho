"""
TESTADOR DA MATRIZ MUNDO
Carrega e testa a matriz processada
"""

import numpy as np
import cv2

def testar_matriz():
    """Testa a matriz gerada"""
    print("=" * 70)
    print("🧪 TESTADOR DA MATRIZ MUNDO")
    print("=" * 70)

    # 1. Carregar matriz
    print("\n📂 Carregando matriz processada...")
    try:
        dados = np.load('FARM/mapa_mundo_processado.npz')
        print("   ✅ Arquivo carregado!")
    except FileNotFoundError:
        print("   ❌ Arquivo não encontrado!")
        print("   Execute primeiro: python processar_mapa_mundo.py")
        return False

    # 2. Extrair dados
    matriz_walkable = dados['walkable']
    matriz_biomas = dados['biomas']
    dimensoes = dados['dimensoes']
    versao = dados['versao']
    fonte = dados['fonte']

    print(f"\n📋 Informações do arquivo:")
    print(f"   Versão: {versao}")
    print(f"   Fonte: {fonte}")
    print(f"   Dimensões: {dimensoes[0]}x{dimensoes[1]}")
    print(f"   Shape walkable: {matriz_walkable.shape}")
    print(f"   Shape biomas: {matriz_biomas.shape}")

    # 3. Testar coordenadas conhecidas
    print("\n" + "=" * 70)
    print("🎯 TESTANDO COORDENADAS CONHECIDAS")
    print("=" * 70)

    testes = [
        # (x, y, descrição)
        (374, 1342, "Deserto (spawn point)"),
        (147, 1468, "Praia (spawn point)"),
        (220, 1153, "Pré-Praia (spawn point)"),
        (0, 0, "Canto superior esquerdo (fundo)"),
        (1599, 1688, "Canto inferior direito (fundo)"),
        (800, 800, "Centro aproximado do mapa"),
    ]

    BIOMA_NOMES = {
        0: "Desconhecido",
        1: "Praia",
        2: "Pré-Praia",
        3: "Vila Inicial",
        4: "Floresta dos Corvos",
        5: "Deserto",
        6: "Labirinto dos Assassinos",
        7: "Área dos Zumbis",
        8: "Covil dos Esqueletos",
        9: "Território dos Elfos",
        10: "Zona dos Lagartos",
        11: "Área Indefinida",
        12: "Área dos Goblins",
    }

    for x, y, descricao in testes:
        # Verificar limites
        if 0 <= y < matriz_walkable.shape[0] and 0 <= x < matriz_walkable.shape[1]:
            is_walkable = matriz_walkable[y, x] == 1
            bioma_id = matriz_biomas[y, x]
            bioma_nome = BIOMA_NOMES.get(bioma_id, "Erro")

            status = "✅ Walkable" if is_walkable else "❌ Não-walkable"

            print(f"\n📍 ({x:4d}, {y:4d}) - {descricao}")
            print(f"   {status}")
            print(f"   🗺️ Bioma: {bioma_nome}")
        else:
            print(f"\n📍 ({x:4d}, {y:4d}) - {descricao}")
            print(f"   ⚠️ Fora dos limites!")

    # 4. Estatísticas gerais
    print("\n" + "=" * 70)
    print("📊 ESTATÍSTICAS GERAIS")
    print("=" * 70)

    total_pixels = matriz_walkable.size
    walkable_count = np.sum(matriz_walkable == 1)
    nao_walkable_count = np.sum(matriz_walkable == 0)

    print(f"Total de pixels: {total_pixels:,}")
    print(f"✅ Walkable: {walkable_count:,} ({walkable_count*100/total_pixels:.1f}%)")
    print(f"❌ Não-walkable: {nao_walkable_count:,} ({nao_walkable_count*100/total_pixels:.1f}%)")

    # 5. Visualização (opcional)
    print("\n" + "=" * 70)
    print("🎨 GERANDO VISUALIZAÇÃO")
    print("=" * 70)

    # Criar imagem de visualização
    vis_walkable = (matriz_walkable * 255).astype(np.uint8)
    cv2.imwrite('FARM/visualizacao_walkable.png', vis_walkable)
    print(f"✅ Salvo: FARM/visualizacao_walkable.png")
    print(f"   (Branco = walkable, Preto = não-walkable)")

    # Criar imagem de biomas (colorida)
    vis_biomas = np.zeros((matriz_biomas.shape[0], matriz_biomas.shape[1], 3), dtype=np.uint8)

    # Cores para cada bioma
    cores_biomas = {
        0: (0, 0, 0),           # Desconhecido - Preto
        1: (244, 225, 174),     # Praia
        2: (72, 152, 72),       # Pré-Praia
        3: (18, 43, 18),        # Vila
        4: (143, 204, 143),     # Floresta
        5: (233, 191, 153),     # Deserto
        6: (52, 94, 53),        # Labirinto
        7: (100, 98, 43),       # Zumbis
        8: (147, 143, 92),      # Esqueletos
        9: (67, 61, 41),        # Elfos
        10: (54, 117, 53),      # Lagartos
        11: (184, 111, 39),     # Indefinida
        12: (48, 216, 48),      # Goblins
    }

    for bioma_id, cor in cores_biomas.items():
        mask = matriz_biomas == bioma_id
        vis_biomas[mask] = cor

    cv2.imwrite('FARM/visualizacao_biomas.png', vis_biomas)
    print(f"✅ Salvo: FARM/visualizacao_biomas.png")
    print(f"   (Cada bioma com sua cor)")

    print("\n" + "=" * 70)
    print("✅ TESTES CONCLUÍDOS COM SUCESSO!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        testar_matriz()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
