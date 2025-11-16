"""
TESTE DA MATRIZ WALKABLE V2

Verifica se a nova matriz está correta:
1. Carrega a matriz
2. Verifica dimensões
3. Testa coordenadas problemáticas
4. Testa área ao redor do player
"""

import numpy as np
import sys

def testar_matriz():
    print("=" * 70)
    print("🧪 TESTE DA MATRIZ WALKABLE V2")
    print("=" * 70)

    # 1. Carregar matriz
    print("\n📂 Carregando matriz...")
    try:
        dados = np.load('FARM/mapa_mundo_processado.npz')
        matriz = dados['walkable']
        dimensoes = dados['dimensoes']
        formato = dados.get('formato', 'desconhecido')
        versao = dados.get('versao', 'desconhecido')

        print(f"   ✅ Matriz carregada com sucesso!")
        print(f"      Versão: {versao}")
        print(f"      Formato: {formato}")
        print(f"      Dimensões salvas: {dimensoes}")
        print(f"      Shape real: {matriz.shape}")

    except FileNotFoundError:
        print("   ❌ ERRO: FARM/mapa_mundo_processado.npz não encontrado!")
        return False
    except Exception as e:
        print(f"   ❌ ERRO ao carregar: {e}")
        return False

    # 2. Verificar dimensões
    print("\n📐 Verificando dimensões...")
    largura = dimensoes[0]
    altura = dimensoes[1]

    if matriz.shape[0] == largura and matriz.shape[1] == altura:
        print(f"   ✅ Dimensões CORRETAS!")
        print(f"      Esperado: ({largura}, {altura})")
        print(f"      Obtido: {matriz.shape}")
    else:
        print(f"   ⚠️ ALERTA: Dimensões não batem!")
        print(f"      Esperado: ({largura}, {altura})")
        print(f"      Obtido: {matriz.shape}")

    # 3. Testar coordenadas problemáticas
    print("\n🔍 Testando coordenadas problemáticas...")
    print("   (Coordenadas onde mobs estavam andando)")

    coords_teste = [
        (366, 1203),
        (366, 1204),
        (366, 1206),
        (367, 1206),
        (368, 1206),
        (369, 1206),
        (370, 1206),
        (370, 1207),
    ]

    problemas = 0
    for x, y in coords_teste:
        try:
            # Acessar como matriz[x, y] conforme formato v2
            valor = matriz[x, y]
            status = "✅ ANDÁVEL" if valor == 1 else "❌ PAREDE"
            simbolo = "✓" if valor == 1 else "✗"
            print(f"   matriz[{x:3d}, {y:4d}] = {valor} {simbolo} {status}")

            if valor != 1:
                problemas += 1

        except IndexError:
            print(f"   matriz[{x:3d}, {y:4d}] = ❌ FORA DOS LIMITES!")
            problemas += 1

    if problemas == 0:
        print(f"\n   🎉 TODAS as coordenadas problemáticas agora estão ANDÁVEIS!")
    else:
        print(f"\n   ⚠️ ALERTA: {problemas} coordenadas ainda com problema!")

    # 4. Testar posição exemplo do player
    print("\n🧑 Testando área ao redor de posição exemplo (374, 1190)...")
    player_x, player_y = 374, 1190

    # Verificar área 5x5
    print(f"   Área 5x5 ao redor de ({player_x}, {player_y}):")
    for dy in range(-2, 3):
        linha = "   "
        for dx in range(-2, 3):
            x = player_x + dx
            y = player_y + dy

            try:
                valor = matriz[x, y]
                simbolo = "█" if valor == 1 else "░"
                linha += simbolo
            except:
                linha += "X"

        print(linha)

    print("\n   Legenda: █ = andável, ░ = parede, X = fora dos limites")

    # 5. Estatísticas gerais
    print("\n📊 Estatísticas da matriz:")
    total = matriz.size
    andaveis = np.sum(matriz == 1)
    paredes = np.sum(matriz == 0)

    print(f"   Total de pixels: {total:,}")
    print(f"   Andáveis (1): {andaveis:,} ({andaveis*100/total:.1f}%)")
    print(f"   Paredes (0): {paredes:,} ({paredes*100/total:.1f}%)")

    # 6. Teste de acesso randômico
    print("\n🎲 Teste de acesso aleatório (10 pontos):")
    import random
    random.seed(42)

    for i in range(10):
        x = random.randint(0, largura - 1)
        y = random.randint(0, altura - 1)

        try:
            valor = matriz[x, y]
            status = "✓" if valor == 1 else "✗"
            print(f"   matriz[{x:4d}, {y:4d}] = {valor} {status}")
        except Exception as e:
            print(f"   matriz[{x:4d}, {y:4d}] = ❌ ERRO: {e}")

    print("\n" + "=" * 70)
    print("✅ TESTE COMPLETO!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        sucesso = testar_matriz()
        sys.exit(0 if sucesso else 1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
