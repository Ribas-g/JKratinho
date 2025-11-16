"""
PROCESSADOR DE MAPA MUNDO V2 - COM VISUALIZAÇÃO E DEBUG

Cria matriz walkable a partir do MINIMAPA CERTOPRETO.png

CORREÇÕES:
- Formato consistente: matriz[X, Y] para facilitar acesso
- Visualização PNG da matriz gerada
- Debug extensivo com verificação de coordenadas problemáticas
- Compatível com dimensões corretas

Gera:
- FARM/mapa_mundo_processado.npz (matriz walkable)
- FARM/mapa_walkable_visual.png (visualização)
- FARM/mapa_debug_report.txt (relatório de debug)
"""

import cv2
import numpy as np
import os
from pathlib import Path
from datetime import datetime

# Cores para biomas
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
    """Encontra o bioma mais próximo baseado na cor RGB"""
    melhor_bioma = "Desconhecido"
    menor_distancia = float('inf')

    for cor_ref, nome in ZONAS_CORES.items():
        dist = np.sqrt(
            (cor_rgb[0] - cor_ref[0])**2 +
            (cor_rgb[1] - cor_ref[1])**2 +
            (cor_rgb[2] - cor_ref[2])**2
        )

        if dist < menor_distancia:
            menor_distancia = dist
            melhor_bioma = nome

    return melhor_bioma, menor_distancia


def verificar_coordenadas_problematicas(matriz, report_file):
    """
    Verifica coordenadas que deram falso positivo de parede
    Baseado nos logs do usuário
    """
    print("\n🔍 VERIFICANDO COORDENADAS PROBLEMÁTICAS...")

    # Coordenadas dos logs do usuário (mob andando)
    coords_problematicas = [
        (366, 1203),
        (366, 1204),
        (366, 1206),
        (367, 1206),
        (368, 1206),
        (369, 1206),
        (370, 1206),
        (370, 1207),
    ]

    report_file.write("\n" + "="*70 + "\n")
    report_file.write("VERIFICAÇÃO DE COORDENADAS PROBLEMÁTICAS\n")
    report_file.write("(Coordenadas onde mobs estavam andando mas detectou parede)\n")
    report_file.write("="*70 + "\n\n")

    for x, y in coords_problematicas:
        # Verificar limites
        if x < 0 or x >= matriz.shape[0] or y < 0 or y >= matriz.shape[1]:
            status = "❌ FORA DOS LIMITES"
            valor = -1
        else:
            valor = matriz[x, y]
            status = "✅ ANDÁVEL" if valor == 1 else "🚫 PAREDE"

        print(f"   ({x:3d}, {y:4d}): {status} (valor={valor})")
        report_file.write(f"({x:3d}, {y:4d}): {status} (valor={valor})\n")

        # Verificar área 3x3
        if 0 <= x < matriz.shape[0] and 0 <= y < matriz.shape[1]:
            report_file.write(f"  Área 3x3 ao redor:\n")
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < matriz.shape[0] and 0 <= ny < matriz.shape[1]:
                        v = matriz[nx, ny]
                        s = "✓" if v == 1 else "✗"
                        report_file.write(f"    [{nx:3d}, {ny:4d}] = {v} {s}\n")
            report_file.write("\n")


def gerar_visualizacao(matriz_walkable, output_path):
    """
    Gera visualização PNG da matriz walkable
    - BRANCO = andável (chão)
    - PRETO = não-andável (parede)
    """
    print(f"\n🎨 Gerando visualização...")

    # Criar imagem: 255 (branco) para walkable, 0 (preto) para parede
    img_visual = np.zeros((matriz_walkable.shape[1], matriz_walkable.shape[0]), dtype=np.uint8)

    # matriz_walkable[x, y] → img_visual[y, x] (inverter para visualização correta)
    for x in range(matriz_walkable.shape[0]):
        for y in range(matriz_walkable.shape[1]):
            if matriz_walkable[x, y] == 1:
                img_visual[y, x] = 255  # Branco = andável
            else:
                img_visual[y, x] = 0    # Preto = parede

    # Salvar
    cv2.imwrite(output_path, img_visual)

    tamanho_kb = os.path.getsize(output_path) / 1024
    print(f"   ✅ Visualização salva: {output_path}")
    print(f"   📦 Tamanho: {tamanho_kb:.1f} KB")
    print(f"   🎨 Formato: BRANCO=andável, PRETO=parede")


def processar_mapa():
    """
    Processa MINIMAPA CERTOPRETO.png e cria matriz walkable

    FORMATO DA MATRIZ: matriz[X, Y]
    - X = coordenada horizontal (largura)
    - Y = coordenada vertical (altura)
    """
    print("=" * 70)
    print("🗺️ PROCESSADOR DE MAPA MUNDO V2")
    print("=" * 70)
    print(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Criar pasta FARM
    Path("FARM").mkdir(exist_ok=True)

    # Abrir arquivo de report
    report_path = 'FARM/mapa_debug_report.txt'
    report_file = open(report_path, 'w', encoding='utf-8')
    report_file.write("RELATÓRIO DE DEBUG - PROCESSAMENTO DE MAPA\n")
    report_file.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_file.write("="*70 + "\n\n")

    # 1. Carregar mapa
    mapa_path = 'MINIMAPA CERTOPRETO.png'
    if not os.path.exists(mapa_path):
        print(f"❌ Erro: {mapa_path} não encontrado!")
        report_file.close()
        return False

    print(f"\n📂 Carregando {mapa_path}...")
    mapa_colorido = cv2.imread(mapa_path)

    if mapa_colorido is None:
        print("❌ Erro ao carregar o mapa!")
        report_file.close()
        return False

    # DIMENSÕES: altura=Y, largura=X
    altura_img, largura_img = mapa_colorido.shape[:2]
    print(f"   ✅ Mapa carregado:")
    print(f"      Dimensões da imagem: {largura_img}x{altura_img} pixels (X x Y)")
    print(f"      Total de pixels: {largura_img * altura_img:,}")

    report_file.write(f"DIMENSÕES DO MAPA ORIGINAL:\n")
    report_file.write(f"  Largura (X): {largura_img} pixels\n")
    report_file.write(f"  Altura (Y): {altura_img} pixels\n")
    report_file.write(f"  Total: {largura_img * altura_img:,} pixels\n\n")

    # 2. Criar matriz em formato [X, Y]
    print("\n🔨 Criando matriz...")
    print(f"   📐 Formato: matriz[X, Y] = matriz[{largura_img}, {altura_img}]")

    matriz_walkable = np.zeros((largura_img, altura_img), dtype=np.uint8)
    matriz_biomas = np.zeros((largura_img, altura_img), dtype=np.uint8)

    report_file.write(f"FORMATO DA MATRIZ:\n")
    report_file.write(f"  Shape: ({largura_img}, {altura_img})\n")
    report_file.write(f"  Acesso: matriz[x, y]\n")
    report_file.write(f"  Onde X = coordenada horizontal (0-{largura_img-1})\n")
    report_file.write(f"        Y = coordenada vertical (0-{altura_img-1})\n\n")

    # 3. Processar cada pixel
    print("🔍 Processando pixels...")
    print("   Lógica: Cor (não-preto) = walkable ✅, Preto = parede ❌")

    pixels_walkable = 0
    pixels_nao_walkable = 0
    contagem_biomas = {nome: 0 for nome in BIOMA_IDS.keys()}

    # IMPORTANTE: Iterar pela imagem em [y, x] mas salvar na matriz em [x, y]
    blocos = 10
    linhas_por_bloco = altura_img // blocos

    for bloco in range(blocos):
        y_inicio = bloco * linhas_por_bloco
        y_fim = altura_img if bloco == blocos - 1 else (bloco + 1) * linhas_por_bloco

        for y in range(y_inicio, y_fim):
            for x in range(largura_img):
                # Pegar cor BGR do pixel da IMAGEM [y, x]
                bgr = mapa_colorido[y, x]
                b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])

                # Verificar se é preto
                is_preto = (b < 15 and g < 15 and r < 15)

                if is_preto:
                    # PRETO = NÃO WALKABLE
                    matriz_walkable[x, y] = 0  # Salvar em [x, y]
                    matriz_biomas[x, y] = BIOMA_IDS["Desconhecido"]
                    pixels_nao_walkable += 1
                else:
                    # TEM COR = WALKABLE
                    matriz_walkable[x, y] = 1  # Salvar em [x, y]
                    pixels_walkable += 1

                    # Identificar bioma
                    cor_rgb = (r, g, b)
                    bioma_nome, distancia = encontrar_bioma_por_cor(cor_rgb)

                    if distancia > 100:
                        bioma_nome = "Desconhecido"

                    matriz_biomas[x, y] = BIOMA_IDS[bioma_nome]
                    contagem_biomas[bioma_nome] += 1

        # Progresso
        progresso = (bloco + 1) * 100 // blocos
        print(f"   [{progresso:3d}%] Processado linha {y_fim}/{altura_img}")

    print("\n✅ Processamento completo!")

    # 4. Estatísticas
    print("\n" + "=" * 70)
    print("📊 ESTATÍSTICAS")
    print("=" * 70)
    total_pixels = largura_img * altura_img
    print(f"Total de pixels: {total_pixels:,}")
    print(f"✅ Walkable (chão):     {pixels_walkable:,} ({pixels_walkable*100/total_pixels:.1f}%)")
    print(f"❌ Não-walkable:        {pixels_nao_walkable:,} ({pixels_nao_walkable*100/total_pixels:.1f}%)")

    report_file.write("ESTATÍSTICAS:\n")
    report_file.write(f"  Total de pixels: {total_pixels:,}\n")
    report_file.write(f"  Walkable: {pixels_walkable:,} ({pixels_walkable*100/total_pixels:.1f}%)\n")
    report_file.write(f"  Não-walkable: {pixels_nao_walkable:,} ({pixels_nao_walkable*100/total_pixels:.1f}%)\n\n")

    # 5. Verificar coordenadas problemáticas
    verificar_coordenadas_problematicas(matriz_walkable, report_file)

    # 6. Gerar visualização
    visual_path = 'FARM/mapa_walkable_visual.png'
    gerar_visualizacao(matriz_walkable, visual_path)

    # 7. Salvar arquivo NPZ
    print("\n" + "=" * 70)
    print("💾 SALVANDO MATRIZES")
    print("=" * 70)

    output_file = 'FARM/mapa_mundo_processado.npz'

    np.savez_compressed(
        output_file,
        walkable=matriz_walkable,
        biomas=matriz_biomas,
        dimensoes=np.array([largura_img, altura_img]),  # [X, Y]
        versao="2.0",
        fonte="MINIMAPA CERTOPRETO.png",
        formato="matriz[x, y]"
    )

    tamanho_kb = os.path.getsize(output_file) / 1024

    print(f"✅ Arquivo salvo: {output_file}")
    print(f"📦 Tamanho: {tamanho_kb:.1f} KB")
    print(f"📐 Dimensões: {largura_img}x{altura_img} (X x Y)")
    print(f"🔢 Formato: matriz[x, y]")
    print(f"🔢 Shape: {matriz_walkable.shape}")

    report_file.write("ARQUIVO GERADO:\n")
    report_file.write(f"  Path: {output_file}\n")
    report_file.write(f"  Tamanho: {tamanho_kb:.1f} KB\n")
    report_file.write(f"  Formato: matriz[x, y]\n")
    report_file.write(f"  Shape: {matriz_walkable.shape}\n\n")

    # 8. Teste de carregamento
    print("\n🧪 Testando carregamento...")
    dados = np.load(output_file)
    print(f"   ✅ Arquivo carregado com sucesso!")
    print(f"   📋 Chaves: {list(dados.keys())}")
    print(f"   📐 Dimensões salvas: {dados['dimensoes']}")
    print(f"   🔖 Versão: {dados['versao']}")
    print(f"   📝 Formato: {dados['formato']}")

    # Fechar report
    report_file.write("\n" + "="*70 + "\n")
    report_file.write("PROCESSAMENTO CONCLUÍDO COM SUCESSO!\n")
    report_file.write("="*70 + "\n")
    report_file.close()

    print("\n" + "=" * 70)
    print("🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    print(f"\n📝 Arquivos gerados:")
    print(f"   1. {output_file} (matriz walkable)")
    print(f"   2. {visual_path} (visualização PNG)")
    print(f"   3. {report_path} (relatório de debug)")
    print(f"\n💡 USO:")
    print(f"   dados = np.load('{output_file}')")
    print(f"   matriz_walkable = dados['walkable']")
    print(f"   # Consultar: is_walkable = matriz_walkable[x, y] == 1")
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
