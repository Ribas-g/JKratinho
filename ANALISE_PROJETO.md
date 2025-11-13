# 📊 ANÁLISE DO PROJETO "NAVEGADOR 2.0"

## 📋 VISÃO GERAL

O **Navegador 2.0** é um sistema completo de navegação automática para o jogo Rucoy Online. Ele usa GPS com NCC (Normalized Cross Correlation) para localização e pathfinding A* para calcular rotas.

---

## 🏗️ ARQUITETURA DO PROJETO

### **Arquivo Principal:** `navegador_automatico_ncc.py`

#### **Classe Principal:** `NavegadorAutomaticoNCC`

Sistema de navegação que:
1. **Obtém posição atual** usando GPS com NCC
2. **Escolhe destino** (por zona ou coordenadas)
3. **Calcula rota** usando pathfinding A*
4. **Navega clicando** no mapa minimap
5. **Detecta movimento** (linha verde)
6. **Aguarda chegada** em cada waypoint
7. **Repete** até chegar no destino final

---

## 📦 DEPENDÊNCIAS

### **Módulos Importados:**
- `gps_ncc_realtime.py` → `GPSRealtimeNCC` (GPS com NCC)
- `pathfinding_astar.py` → `AStarPathfinder` (Pathfinding A*)

### **Bibliotecas:**
- `cv2` (OpenCV) - Processamento de imagem
- `numpy` - Arrays e cálculos
- `time` - Controle de tempo
- `json` - Configurações
- `os` - Sistema de arquivos

---

## 🗺️ MAPAS USADOS

1. **`MINIMAPA CERTOPRETO.png`** (Mapa colorido)
   - Usado para referência visual
   - Identificação de biomas por cor
   - Verificação de chão (área colorida vs. preta)

2. **`MAPA PRETO E BRANCO.png`** (Mapa P&B)
   - Usado para pathfinding A*
   - Melhor definição de paredes
   - Matriz binária (0 = walkable, 1 = parede)

---

## 🎯 FUNCIONALIDADES PRINCIPAIS

### **1. Navegação para Zona**
```python
nav.navegar_para_zona('Deserto')
```
- Navega para o spawn de uma zona
- Usa coordenadas pré-definidas em `ZONAS_DISPONIVEIS`

### **2. Navegação para Coordenadas**
```python
nav.navegar_para_coordenadas(500, 300)
```
- Navega para coordenadas específicas
- Usa pathfinding A* para calcular rota
- Segue waypoints visíveis no mapa

### **3. Conversão de Coordenadas**
- **`mundo_to_tela()`**: Converte coordenadas do mundo para coordenadas de clique na tela
- **Escala**: Usa escala do GPS (padrão: 20% = 0.2)
- **Limitação**: Cliques são limitados à região do mapa visível

### **4. Detecção de Movimento**
- **`detectar_linha_verde()`**: Detecta linha verde no mapa (player em movimento)
- **HSV Range**: H=50-70 (verde puro, exclui ciano H=90)
- **Exclusão do Centro**: Remove região central onde fica o player (ciano)

### **5. Aguardar Chegada**
- **Fase 1**: Aguarda linha verde APARECER (player começou a andar)
- **Fase 2**: Aguarda linha verde SUMIR (player parou)
- **Fase 3**: Confirma com GPS (realmente chegou)
- **Timeout**: 10 segundos (configurável)

---

## 🛣️ ALGORITMO DE NAVEGAÇÃO

### **Fluxo:**
```
1. Obter posição inicial (GPS)
2. Calcular rota A* até destino
3. Simplificar path (waypoints espaçados)
4. Para cada waypoint:
   a. Encontrar ponto visível no path
   b. Verificar se é walkable
   c. Clicar no mapa
   d. Aguardar chegada
   e. Verificar se chegou ao destino final
5. Se chegou: ✅ Sucesso
   Se timeout: ❌ Falhou
```

### **Encontrar Ponto Visível:**
- Percorre path **NA ORDEM** (importante para contornar obstáculos)
- Pega o ponto **mais distante** que está visível
- **Limites:**
  - Distância mínima: 50px (não clicar muito perto)
  - Distância máxima: 200px (não clicar muito longe)
  - Raio visível: 25% da região do mapa

---

## ⚙️ CONFIGURAÇÕES

### **Parâmetros:**
- `click_distance`: 35% do raio visível (no mapa mundo)
- `wait_after_click`: 1.0 segundos
- `max_steps`: 200 passos
- `tolerance_pixels`: 30 pixels (considerar "chegou")
- `escala_x/y`: 0.2 (20% - escala do GPS)

### **Calibração:**
- Arquivo: `map_transform_config.json`
- Se não existir, calcula automaticamente usando escala do GPS

---

## 🗺️ ZONAS DISPONÍVEIS

```python
ZONAS_DISPONIVEIS = {
    'Praia': {'spawn': (34, 1058), 'color': (0xf4, 0xe1, 0xae)},
    'Pré-Praia': {'spawn': (177, 1139), 'color': (0x48, 0x98, 0x48)},
    'Vila Inicial': {'spawn': (379, 1147), 'color': (0x12, 0x2b, 0x12)},
    'Floresta dos Corvos': {'spawn': (548, 1135), 'color': (0x8f, 0xcc, 0x8f)},
    'Deserto': {'spawn': (374, 1342), 'color': (0xe9, 0xbf, 0x99)},
    'Labirinto dos Assassinos': {'spawn': (377, 931), 'color': (0x34, 0x5e, 0x35)},
    'Área dos Zumbis': {'spawn': (369, 727), 'color': (0x64, 0x62, 0x2b)},
    'Covil dos Esqueletos': {'spawn': (564, 727), 'color': (0x93, 0x8f, 0x5c)},
    'Território dos Elfos': {'spawn': (690, 933), 'color': (0x43, 0x3d, 0x29)},
    'Zona dos Lagartos': {'spawn': (886, 632), 'color': (0x36, 0x75, 0x35)},
    'Área Indefinida': {'spawn': (476, 430), 'color': (0xb8, 0x6f, 0x27)},
    'Área dos Goblins': {'spawn': (787, 1228), 'color': (0x30, 0xd8, 0x30)},
}
```

---

## 🔍 FUNÇÕES AUXILIARES

### **Validação:**
- `is_walkable()`: Verifica se coordenada é walkable (usa pathfinder)
- `_tem_chao()`: Verifica se coordenada tem chão (não é buraco preto)

### **Cálculos:**
- `calcular_distancia()`: Distância euclidiana entre dois pontos
- `encontrar_ponto_visivel_no_path()`: Encontra próximo waypoint visível

### **Interação:**
- `clicar_no_mapa()`: Clica no mapa na direção do destino
- `detectar_linha_verde()`: Detecta linha verde (movimento)

---

## 🐛 DEBUG E TESTES

### **Arquivos de Debug:**
1. **`debug_escolha_ponto.py`**: Mostra qual ponto do path está sendo escolhido
2. **`debug_transform_mundo_tela.py`**: Testa transformação de coordenadas
3. **`debug_visual_completo.py`**: Visualização completa do processo
4. **`ver_escalas.py`**: Verifica escalas calculadas

---

## ⚠️ PROBLEMAS IDENTIFICADOS

### **1. Arquivos Faltando:**
- `gps_ncc_realtime.py` (não encontrado na pasta)
- `pathfinding_astar.py` (não encontrado na pasta)

### **2. Dependências:**
- Os módulos `GPSRealtimeNCC` e `AStarPathfinder` precisam estar disponíveis
- Podem estar em outro diretório ou precisam ser criados

---

## 🔧 MELHORIAS SUGERIDAS

1. **Adicionar tratamento de erros** para arquivos faltando
2. **Criar fallback** se pathfinding falhar
3. **Adicionar logs** mais detalhados
4. **Otimizar** detecção de linha verde (atualmente 0.0002 threshold)
5. **Adicionar retry** em caso de falha
6. **Validar** configuração de calibração antes de usar

---

## 📝 PRÓXIMOS PASSOS

1. ✅ Localizar/criar `gps_ncc_realtime.py`
2. ✅ Localizar/criar `pathfinding_astar.py`
3. ✅ Testar navegação básica
4. ✅ Validar conversão de coordenadas
5. ✅ Testar detecção de movimento
6. ✅ Otimizar performance

---

## 🎮 USO

```python
from navegador_automatico_ncc import NavegadorAutomaticoNCC

# Inicializar
nav = NavegadorAutomaticoNCC()

# Navegar para zona
nav.navegar_para_zona('Deserto')

# Ou navegar para coordenadas
nav.navegar_para_coordenadas(500, 300)

# Menu interativo
python navegador_automatico_ncc.py
```

---

**Última atualização:** Análise baseada no código atual
**Status:** ⚠️ Dependências faltando (`gps_ncc_realtime.py`, `pathfinding_astar.py`)


