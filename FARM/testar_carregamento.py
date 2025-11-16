"""
TESTE DE CARREGAMENTO DE ARQUIVOS

Verifica se todos os arquivos necessários estão sendo encontrados
"""

import sys
from pathlib import Path
import numpy as np
import json

# Adicionar FARM ao path
sys.path.insert(0, str(Path(__file__).parent))

def testar_carregamentos():
    print("=" * 70)
    print("🧪 TESTE DE CARREGAMENTO DE ARQUIVOS")
    print("=" * 70)

    pasta_farm = Path(__file__).parent
    print(f"\n📂 Pasta FARM: {pasta_farm}")
    print(f"   Existe: {pasta_farm.exists()}")

    # Listar arquivos na pasta FARM
    print(f"\n📋 Arquivos na pasta FARM:")
    arquivos = list(pasta_farm.glob("*.npz")) + list(pasta_farm.glob("*.json"))
    for arq in sorted(arquivos):
        tamanho = arq.stat().st_size / 1024  # KB
        print(f"   ✅ {arq.name} ({tamanho:.1f} KB)")

    # 1. Testar carregamento da matriz
    print("\n" + "=" * 70)
    print("1️⃣ TESTANDO MATRIZ WALKABLE")
    print("=" * 70)

    caminho_matriz = pasta_farm / 'mapa_mundo_processado.npz'
    print(f"   Procurando: {caminho_matriz}")
    print(f"   Existe: {caminho_matriz.exists()}")

    if caminho_matriz.exists():
        try:
            dados = np.load(str(caminho_matriz))
            print(f"   ✅ Arquivo carregado com sucesso!")
            print(f"   📋 Chaves: {list(dados.keys())}")
            print(f"   📐 Dimensões: {dados['dimensoes']}")
            print(f"   🔢 Shape: {dados['walkable'].shape}")
            print(f"   🔖 Versão: {dados.get('versao', 'N/A')}")
            print(f"   📝 Formato: {dados.get('formato', 'N/A')}")
        except Exception as e:
            print(f"   ❌ Erro ao carregar: {e}")
    else:
        print(f"   ❌ ARQUIVO NÃO ENCONTRADO!")

    # 2. Testar carregamento de configuração do mapa
    print("\n" + "=" * 70)
    print("2️⃣ TESTANDO MAP_TRANSFORM_CONFIG.JSON")
    print("=" * 70)

    config_path = pasta_farm / 'map_transform_config.json'
    print(f"   Procurando: {config_path}")
    print(f"   Existe: {config_path.exists()}")

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"   ✅ Arquivo carregado com sucesso!")
            print(f"   📋 Chaves: {list(config.keys())}")
            if 'escala' in config:
                print(f"   📐 Escala: x={config['escala']['x']}, y={config['escala']['y']}")
        except Exception as e:
            print(f"   ❌ Erro ao carregar: {e}")
    else:
        print(f"   ⚠️ Arquivo não encontrado (usará escala padrão 25.0)")

    # 3. Testar importação da camera_virtual
    print("\n" + "=" * 70)
    print("3️⃣ TESTANDO IMPORTAÇÃO CAMERA_VIRTUAL")
    print("=" * 70)

    try:
        from camera_virtual import CameraVirtual
        print(f"   ✅ camera_virtual importado com sucesso!")

        # Tentar criar instância (sem GPS)
        print(f"\n   Tentando criar instância da CameraVirtual...")
        print(f"   (Isso vai carregar a matriz walkable automaticamente)")

        # Criar instância sem GPS (vai falhar mas podemos ver se carrega a matriz)
        # camera = CameraVirtual(...)

    except ImportError as e:
        print(f"   ❌ Erro ao importar: {e}")
    except Exception as e:
        print(f"   ⚠️ Erro ao criar instância: {e}")

    print("\n" + "=" * 70)
    print("✅ TESTE COMPLETO!")
    print("=" * 70)

if __name__ == "__main__":
    testar_carregamentos()
