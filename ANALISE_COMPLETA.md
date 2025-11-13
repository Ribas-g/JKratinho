# 📊 ANÁLISE COMPLETA DO PROJETO "NAVEGADOR 2.0"

## 📋 VISÃO GERAL

O **Navegador 2.0** é um sistema completo de navegação automática para Rucoy Online, integrando:
- **GPS Realtime** com NCC (Normalized Cross-Correlation) para localização
- **Pathfinding A*** para cálculo de rotas
- **Detecção de movimento** (linha verde HSV)
- **Navegação automática** por cliques no mapa

---

## 🏗️ ARQUITETURA DO SISTEMA

### **Módulos Principais:**

1. **`gps_ncc_realtime.py`** → `GPSRealtimeNCC`
   - GPS em tempo real usando NCC
   - Template matching com escala 0.2x
   - Detecção de player (ciano HSV)
   - Identificação de zona por cor

2. **`pathfinding_astar.py`** → `AStarPathfinder`
   - Algoritmo A* para pathfinding
   - Simplificação de caminhos
   - Verificação de linha de visão (Bresenham)
   - 8 direções (cardinais + diagonais)

3. **`navegador_automatico_ncc.py`** → `NavegadorAutomaticoNCC`
   - Sistema principal que integra GPS + Pathfinding
   - Navegação por waypoints
   - Detecção de movimento
   - Aguardar chegada

---

## 📦 GPS REALTIME NCC (`gps_ncc_realtime.py`)

### **Funcionalidades:**

#### **1. Inicialização:**
```python
gps = GPSRealtimeNCC()
```
- Conecta via ADB (BlueStacks)
- Carrega mapas (P&B e colorido)
- Carrega configurações (`map_calibration.json`, `levels_config.json`)

#### **2. Obter Posição:**
```python
pos = gps.get_current_position(keep_map_open=False, verbose=True)
```
**Fluxo:**
1. Abre mapa in-game
2. Captura screenshot
3. Extrai região do mapa
4. Aplica levels (ajuste de contraste)
5. Detecta player (ciano HSV: H=80-100)
6. **NCC Template Matching** (escala 0.2x)
7. Identifica zona por cor
8. Fecha mapa
9. Retorna: `{x, y, zone, confidence}`

#### **3. NCC Template Matching:**
- **Escala fixa:** 0.2x (já testada e funcionando)
- **Método:** `match_template` do scikit-image
- **Template:** Mapa capturado (0.2x)
- **Alvo:** Mapa mundo P&B completo
- **Resultado:** Posição no mapa mundo + confiança

#### **4. Detecção de Player:**
- **Cor:** Ciano (#00ffff) → HSV: H=80-100, S=100-255, V=100-255
- **Método:** Contornos + centro de massa
- **Fallback:** Se não detectar, assume centro do mapa

#### **5. Identificação de Zona:**
- **Método:** Compara cor RGB do pixel no mapa colorido
- **Tabela:** 12 zonas pré-definidas com cores
- **Distância:** Distância euclidiana em RGB

### **Configurações Necessárias:**
- `map_calibration.json`: Região do mapa, botões, escala
- `levels_config.json`: Parâmetros de ajuste de contraste

### **Mapas Necessários:**
- `MAPA PRETO E BRANCO.png`: Para matching NCC
- `MINIMAPA CERTOPRETO.png`: Para identificação de zona

---

## 🛣️ PATHFINDING A* (`pathfinding_astar.py`)

### **Funcionalidades:**

#### **1. Inicialização:**
```python
pathfinder = AStarPathfinder(mapa_pb)
```
- Carrega mapa P&B
- Cria máscara de walkability:
  - **PRETO** (< 128) = Walkable
  - **BRANCO** (>= 128) = Obstáculo/Parede

#### **2. Encontrar Caminho:**
```python
path = pathfinder.find_path(start_x, start_y, goal_x, goal_y)
```
**Algoritmo A*:**
- **Fila prioritária:** Menor f_score primeiro
- **Heurística:** Distância euclidiana
- **Movimentos:** 8 direções
  - Cardinais: custo 1.0
  - Diagonais: custo 1.4
- **Limite:** 50.000 iterações
- **Fallback:** Se destino não é walkable, procura ponto walkable próximo (raio até 100px)

#### **3. Simplificar Caminho:**
```python
simplified = pathfinder.simplify_path(path, max_distance=100)
```
**Algoritmo:**
- Percorre path de trás para frente
- Tenta "pular" pontos intermediários
- Mantém linha de visão (Bresenham)
- **Parâmetros:**
  - `min_distance`: 50px (evitar pontos muito próximos)
  - `max_distance`: 100px (limite de salto)

#### **4. Verificação de Linha de Visão:**
- **Método:** Algoritmo de Bresenham
- **Verifica:** Todos os pixels entre dois pontos são walkables
- **Uso:** Simplificação de caminho

---

## 🧭 NAVEGADOR AUTOMÁTICO (`navegador_automatico_ncc.py`)

### **Funcionalidades:**

#### **1. Inicialização:**
```python
nav = NavegadorAutomaticoNCC()
```
- Inicializa GPS (`GPSRealtimeNCC`)
- Inicializa Pathfinder (`AStarPathfinder`)
- Carrega calibração
- Configura parâmetros de navegação

#### **2. Navegar para Zona:**
```python
nav.navegar_para_zona('Deserto')
```
- Usa coordenadas pré-definidas em `ZONAS_DISPONIVEIS`
- Chama `navegar_para_coordenadas()`

#### **3. Navegar para Coordenadas:**
```python
nav.navegar_para_coordenadas(500, 300)
```
**Fluxo:**
1. Obter posição inicial (GPS)
2. Calcular rota A* até destino
3. Simplificar path (waypoints espaçados)
4. Loop de navegação:
   - Obter posição atual
   - Verificar se chegou (tolerância: 30px)
   - Encontrar próximo waypoint visível
   - Clicar no mapa
   - Aguardar chegada
5. Se chegou: ✅ Sucesso
   Se timeout: ❌ Falhou

#### **4. Encontrar Ponto Visível:**
```python
ponto = nav.encontrar_ponto_visivel_no_path(path, x_atual, y_atual)
```
**Lógica:**
- Percorre path **NA ORDEM** (importante!)
- Pega o ponto **mais distante** visível
- **Limites:**
  - Distância mínima: 50px
  - Distância máxima: 200px
  - Raio visível: 25% do mapa
- **Validação:** Verifica se tem chão (não é buraco preto)

#### **5. Conversão de Coordenadas:**
```python
x_tela, y_tela = nav.mundo_to_tela(x_mundo, y_mundo, x_atual, y_atual)
```
**Cálculo:**
- Delta = destino - atual
- Aplica escala (0.2x)
- Soma ao centro do mapa
- **Limitação:** Clampar à região do mapa (margem de 20px)

#### **6. Detecção de Movimento:**
```python
tem_movimento = nav.detectar_linha_verde()
```
**Método:**
- Captura screenshot
- Extrai região do mapa
- Aplica levels
- Converte para HSV
- **Range verde:** H=50-70 (exclui ciano H=90)
- **Exclusão:** Remove região central (raio: 40px)
- **Threshold:** 0.02% de pixels verdes

#### **7. Aguardar Chegada:**
```python
chegou = nav.aguardar_chegada(destino_x, destino_y, x_antes, y_antes)
```
**Fases:**
1. **Fase 1:** Aguarda linha verde APARECER (1.5s timeout)
   - Se não detectar, verifica GPS se player andou
2. **Fase 2:** Aguarda linha verde SUMIR (10s timeout)
   - Precisa 3 verificações consecutivas sem verde
3. **Fase 3:** Confirmação por GPS
   - Verifica distância ao destino (tolerância: 30px)
   - Se chegou: ✅ Retorna True
   - Se não: ↻ Retorna False (precisa clicar de novo)

---

## ⚙️ CONFIGURAÇÕES

### **Parâmetros de Navegação:**
```python
click_distance = 35% do raio visível
wait_after_click = 1.0 segundos
max_steps = 200 passos
tolerance_pixels = 30 pixels
escala_x/y = 0.2 (20%)
```

### **Parâmetros de Pathfinding:**
```python
max_iterations = 50000
min_distance = 50px (waypoints)
max_distance = 100px (simplificação)
directions = 8 (cardinais + diagonais)
```

### **Parâmetros de Detecção:**
```python
green_hsv_lower = [50, 180, 180]
green_hsv_upper = [70, 255, 255]
exclusion_radius = 40px (centro)
green_threshold = 0.0002 (0.02%)
```

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

### **GPS:**
- `capture_screen()`: Screenshot via ADB
- `click_button()`: Clica em botões (open/close map)
- `apply_levels()`: Ajuste de contraste
- `extract_map_region()`: Extrai região do mapa
- `detect_player()`: Detecta player (ciano)
- `find_closest_zone()`: Identifica zona por cor
- `create_debug_images()`: Gera imagens de debug

### **Pathfinding:**
- `is_walkable()`: Verifica se coordenada é walkable
- `get_neighbors()`: Retorna vizinhos walkáveis
- `heuristic()`: Distância euclidiana
- `_has_line_of_sight()`: Verifica linha de visão (Bresenham)

### **Navegador:**
- `mundo_to_tela()`: Converte coordenadas mundo → tela
- `is_walkable()`: Validação (usa pathfinder)
- `_tem_chao()`: Verifica se tem chão (não é buraco)
- `clicar_no_mapa()`: Clica no mapa
- `calcular_distancia()`: Distância euclidiana

---

## 🐛 DEBUG E TESTES

### **Arquivos de Debug:**

1. **`debug_escolha_ponto.py`**
   - Testa lógica de escolha de waypoints
   - Gera visualização dos pontos analisados
   - Cores: Verde = escolhido, Amarelo = válido, Azul = muito perto, Vermelho = muito longe

2. **`debug_transform_mundo_tela.py`**
   - Testa transformação de coordenadas
   - Valida escalas calculadas

3. **`debug_visual_completo.py`**
   - Visualização completa do processo
   - Mostra GPS + Pathfinding + Navegação

4. **`ver_escalas.py`**
   - Verifica escalas calculadas
   - Compara mapa mundo vs. tela

### **Imagens de Debug (GPS):**
- `gps_debug_*.png`: 3 painéis (captura, mapa mundo, zoom)
- `gps_mapa_*.png`: Mapa com marcação da posição

---

## ⚠️ PONTOS DE ATENÇÃO

### **1. Dependências:**
- `adbutils`: Para ADB (BlueStacks)
- `cv2`: OpenCV
- `numpy`: Arrays
- `skimage`: Para NCC (`match_template`)
- `matplotlib`: Para debug (opcional)

### **2. Arquivos Necessários:**
- `MAPA PRETO E BRANCO.png`: Mapa para matching
- `MINIMAPA CERTOPRETO.png`: Mapa colorido para zonas
- `map_calibration.json`: Configuração do mapa
- `levels_config.json`: Configuração de levels
- `map_transform_config.json`: Configuração de transformação (opcional)

### **3. Calibrações:**
- **Mapa:** Região, botões, escala
- **Levels:** Ajuste de contraste
- **Transformação:** Centro e escala (pode calcular automaticamente)

### **4. Problemas Potenciais:**
- **Player não detectado:** Assume centro (pode causar erro)
- **NCC baixa confiança:** Pode dar posição errada
- **Pathfinding timeout:** Muito longe ou sem caminho
- **Linha verde não detectada:** Movimento muito curto
- **Clique fora do mapa:** Limitado à região do mapa

---

## ✅ MELHORIAS SUGERIDAS

1. **Retry automático** em caso de falha
2. **Validação de posição GPS** antes de confiar
3. **Cache de caminhos** para otimização
4. **Logging detalhado** para debug
5. **Timeout configurável** por etapa
6. **Fallback** se NCC falhar
7. **Detecção de obstáculos** dinâmicos
8. **Re-pathfinding** se player sair da rota

---

## 🎮 USO

### **Exemplo Básico:**
```python
from navegador_automatico_ncc import NavegadorAutomaticoNCC

# Inicializar
nav = NavegadorAutomaticoNCC()

# Navegar para zona
nav.navegar_para_zona('Deserto')

# Ou navegar para coordenadas
nav.navegar_para_coordenadas(500, 300)
```

### **Menu Interativo:**
```bash
python navegador_automatico_ncc.py
```

### **Testes Individuais:**
```bash
# Teste GPS
python gps_ncc_realtime.py

# Teste Pathfinding
python pathfinding_astar.py

# Debug escolha de pontos
python debug_escolha_ponto.py
```

---

## 📊 FLUXO COMPLETO

```
1. Inicialização
   ├── GPS: Conecta ADB, carrega mapas, configurações
   ├── Pathfinder: Cria máscara de walkability
   └── Navegador: Integra GPS + Pathfinder

2. Navegação para Destino
   ├── Obter posição inicial (GPS)
   ├── Calcular rota A*
   ├── Simplificar caminho
   └── Loop de navegação:
       ├── Obter posição atual (GPS)
       ├── Verificar chegada
       ├── Encontrar próximo waypoint
       ├── Converter coordenadas mundo → tela
       ├── Clicar no mapa
       ├── Detectar movimento (linha verde)
       ├── Aguardar parada
       └── Confirmar chegada (GPS)

3. Validação Final
   └── Se chegou: ✅ Sucesso
       Se timeout: ❌ Falhou
```

---

**Última atualização:** Análise completa com todas as dependências
**Status:** ✅ Todas as dependências presentes
**Pronto para uso:** Sim (requer calibrações)


