"""
PROCESSADOR DE MAPA MUNDO
Cria matriz walkable e biomas a partir do MINIMAPA CERTOPRETO.png

Lógica:
- Pixel COLORIDO (não-preto) = CHÃO walkable de algum bioma
- Pixel PRETO = PAREDE ou FUNDO (não-walkable)

Gera arquivo: FARM/mapa_mundo_processado.npz
"""

import cv2
import numpy as np
import os
from pathlib import Path

# Tabela de cores dos biomas (do GPS)
ZONAS_CORES = {
    (0xf4, 0xe1, 0xae): "Praia",
    (0x48, 0x98, 0x48): "Pré-Praia",
    (0x12, 0x2b, 0x12): "Vila Inicial",
    (0x8f, 0xcc, 0x8f): "Floresta dos Corvos",
    (0xe9, 0xbf, 0x99): "Deserto",
    (0x34, 0x5e, 0x35): "Labirinto dos Assassinos",
    (0x64, 0x62, 0x2b): "Área dos Zumbis",
    (0x93, 0x8f, 0x5c): "Covil dos Esqueletos",
    (0x43, 0x3d, 0x29): "Território dos Elfos",
    (0x36, 0x75, 0x35): "Zona dos Lagartos",
    (0xb8, 0x6f, 0x27): "Área Indefinida",
    (0x30, 0xd8, 0x30): "Área dos Goblins",
}

# IDs numéricos para cada bioma
BIOMA_IDS = {
    "Desconhecido": 0,
    "Praia": 1,
    "Pré-Praia": 2,
    "Vila Inicial": 3,
    "Floresta dos Corvos": 4,
    "Deserto": 5,
    "Labirinto dos Assassinos": 6,
    "Área dos Zumbis": 7,
    "Covil dos Esqueletos": 8,
    "Território dos Elfos": 9,
    "Zona dos Lagartos": 10,
    "Área Indefinida": 11,
    "Área dos Goblins": 12,
}

def encontrar_bioma_por_cor(cor_rgb):
    """
    Encontra o bioma mais próximo baseado na cor RGB
    """
    melhor_bioma = "Desconhecido"
    menor_distancia = float('inf')

    for cor_ref, nome in ZONAS_CORES.items():
        # Distância euclidiana no espaço RGB
        dist = np.sqrt(
            (cor_rgb[0] - cor_ref[0])**2 +
            (cor_rgb[1] - cor_ref[1])**2 +
            (cor_rgb[2] - cor_ref[2])**2
        )

        if dist < menor_distancia:
            menor_distancia = dist
            melhor_bioma = nome

    return melhor_bioma, menor_distancia


def processar_mapa():
    """
    Processa MINIMAPA CERTOPRETO.png e cria matrizes:
    - walkable: 0 (não-walkable) ou 1 (walkable)
    - biomas: ID do bioma (0-12)
    """
    print("=" * 70)
    print("🗺️ PROCESSADOR DE MAPA MUNDO")
    print("=" * 70)

    # 1. Verificar se arquivo existe
    mapa_path = 'MINIMAPA CERTOPRETO.png'
    if not os.path.exists(mapa_path):
        print(f"❌ Erro: {mapa_path} não encontrado!")
        return False

    print(f"\n📂 Carregando {mapa_path}...")
    mapa_colorido = cv2.imread(mapa_path)

    if mapa_colorido is None:
        print("❌ Erro ao carregar o mapa!")
        return False

    altura, largura = mapa_colorido.shape[:2]
    print(f"   ✅ Mapa carregado: {largura}x{altura} pixels")
    print(f"   📊 Total de pixels: {largura * altura:,}")

    # 2. Criar matrizes
    print("\n🔨 Criando matrizes...")
    matriz_walkable = np.zeros((altura, largura), dtype=np.uint8)
    matriz_biomas = np.zeros((altura, largura), dtype=np.uint8)

    # 3. Processar cada pixel
    print("🔍 Processando pixels...")
    print("   Lógica: Cor (não-preto) = walkable ✅, Preto = não-walkable ❌")

    pixels_walkable = 0
    pixels_nao_walkable = 0
    contagem_biomas = {nome: 0 for nome in BIOMA_IDS.keys()}

    # Processar em blocos para mostrar progresso
    blocos = 10
    linhas_por_bloco = altura // blocos

    for bloco in range(blocos):
        y_inicio = bloco * linhas_por_bloco
        y_fim = altura if bloco == blocos - 1 else (bloco + 1) * linhas_por_bloco

        for y in range(y_inicio, y_fim):
            for x in range(largura):
                # Pegar cor BGR do pixel
                bgr = mapa_colorido[y, x]
                b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])

                # Verificar se é preto (threshold baixo para capturar quase-preto)
                is_preto = (b < 15 and g < 15 and r < 15)

                if is_preto:
                    # PRETO = NÃO WALKABLE (parede ou fundo)
                    matriz_walkable[y, x] = 0
                    matriz_biomas[y, x] = BIOMA_IDS["Desconhecido"]
                    pixels_nao_walkable += 1
                else:
                    # TEM COR = WALKABLE (chão de algum bioma)
                    matriz_walkable[y, x] = 1
                    pixels_walkable += 1

                    # Identificar bioma pela cor
                    cor_rgb = (r, g, b)
                    bioma_nome, distancia = encontrar_bioma_por_cor(cor_rgb)

                    # Se a distância for muito grande, marcar como desconhecido
                    if distancia > 100:  # Threshold
                        bioma_nome = "Desconhecido"

                    matriz_biomas[y, x] = BIOMA_IDS[bioma_nome]
                    contagem_biomas[bioma_nome] += 1

        # Mostrar progresso
        progresso = (bloco + 1) * 100 // blocos
        print(f"   [{progresso:3d}%] Processado linha {y_fim}/{altura}")

    print("\n✅ Processamento completo!")

    # 4. Estatísticas
    print("\n" + "=" * 70)
    print("📊 ESTATÍSTICAS")
    print("=" * 70)
    total_pixels = largura * altura
    print(f"Total de pixels: {total_pixels:,}")
    print(f"")
    print(f"✅ Walkable (chão):     {pixels_walkable:,} ({pixels_walkable*100/total_pixels:.1f}%)")
    print(f"❌ Não-walkable:        {pixels_nao_walkable:,} ({pixels_nao_walkable*100/total_pixels:.1f}%)")
    print(f"")
    print(f"🗺️ Distribuição por Bioma:")
    for nome, count in sorted(contagem_biomas.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            percentual = count * 100 / pixels_walkable if pixels_walkable > 0 else 0
            print(f"   {nome:25s}: {count:8,} pixels ({percentual:5.1f}% do chão)")

    # 5. Salvar arquivo
    print("\n" + "=" * 70)
    print("💾 SALVANDO MATRIZES")
    print("=" * 70)

    # Criar pasta FARM se não existir
    Path("FARM").mkdir(exist_ok=True)

    output_file = 'FARM/mapa_mundo_processado.npz'

    np.savez_compressed(
        output_file,
        walkable=matriz_walkable,
        biomas=matriz_biomas,
        dimensoes=np.array([largura, altura]),
        versao="1.0",
        fonte="MINIMAPA CERTOPRETO.png"
    )

    # Tamanho do arquivo
    tamanho_kb = os.path.getsize(output_file) / 1024

    print(f"✅ Arquivo salvo: {output_file}")
    print(f"📦 Tamanho: {tamanho_kb:.1f} KB")
    print(f"📐 Dimensões: {largura}x{altura}")
    print(f"🔢 Matrizes incluídas:")
    print(f"   - walkable: {matriz_walkable.shape} (uint8)")
    print(f"   - biomas: {matriz_biomas.shape} (uint8)")

    # 6. Teste de carregamento
    print("\n🧪 Testando carregamento...")
    dados = np.load(output_file)
    print(f"   ✅ Arquivo carregado com sucesso!")
    print(f"   📋 Chaves disponíveis: {list(dados.keys())}")

    print("\n" + "=" * 70)
    print("🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    print(f"\n📝 Para usar no farm bot:")
    print(f"   dados = np.load('{output_file}')")
    print(f"   matriz_walkable = dados['walkable']")
    print(f"   matriz_biomas = dados['biomas']")
    print(f"")
    print(f"   # Consultar se ponto é walkable:")
    print(f"   is_walkable = matriz_walkable[y][x] == 1")
    print("")

    return True


if __name__ == "__main__":
    try:
        sucesso = processar_mapa()
        if not sucesso:
            exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
