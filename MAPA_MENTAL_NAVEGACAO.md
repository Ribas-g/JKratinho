# 🧭 MAPA MENTAL - SISTEMA DE NAVEGAÇÃO AUTOMÁTICA

## 📋 VISÃO GERAL

Este documento explica como funciona o sistema de navegação automática do bot, desde o cálculo do caminho até a execução dos cliques.

---

## 🎯 FLUXO PRINCIPAL

```
┌─────────────────────────────────────────────────────────────────┐
│                    INÍCIO DA NAVEGAÇÃO                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. OBTER POSIÇÃO INICIAL (GPS)                                 │
│     • Captura screenshot do emulador                            │
│     • Processa imagem (levels, resize)                          │
│     • Template matching (NCC) para encontrar player no mapa     │
│     • Retorna: (x_inicial, y_inicial, zona)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. CALCULAR ROTA COM A* PATHFINDING                            │
│     • Entrada: (x_inicial, y_inicial) → (destino_x, destino_y) │
│     • Usa mapa P&B (0=walkable, 1=parede)                      │
│     • Aplica margem de segurança (5px) nas paredes             │
│     • Retorna: path_completo = [(x1,y1), (x2,y2), ..., (xn,yn)]│
│     • Path tem TODOS os pontos pixel-a-pixel do caminho        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. INICIALIZAR ÍNDICE DO PATH                                  │
│     • Encontra ponto do path mais próximo da posição inicial   │
│     • Índice inicial = ponto_mais_proximo + 1                  │
│     • Garante que começamos à frente no path                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOOP DE NAVEGAÇÃO                            │
│                    (até 200 passos)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASSO N:                                                       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.1. CAPTURAR TELA ATUAL                                 │  │
│  │     • Screenshot do emulador                             │  │
│  │     • GPS: obter posição atual do player                 │  │
│  │     • Atualizar: x_atual, y_atual                        │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.2. VERIFICAR SE CHEGOU                                 │  │
│  │     • Distância ao destino <= 30px?                      │  │
│  │     • SIM → ✅ SUCESSO! Fim                              │  │
│  │     • NÃO → Continuar                                    │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.3. CALCULAR ÁREA VISÍVEL                               │  │
│  │     • Player está no centro da tela                      │  │
│  │     • Área visível = player_pos ± (tela_size / 2 / escala)│
│  │     • Retorna: (x_min, x_max, y_min, y_max)             │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.4. ESCOLHER PRÓXIMO PONTO DE CLIQUE                   │  │
│  │                                                           │  │
│  │  OPÇÃO A: Destino está visível E muito perto?            │  │
│  │           • Distância <= 150px                           │  │
│  │           • Player não está preso                        │  │
│  │           → Clicar DIRETO no destino                     │  │
│  │                                                           │  │
│  │  OPÇÃO B: Usar path A* (contorna obstáculos)             │  │
│  │           • Filtrar pontos do path que estão:            │  │
│  │             - À frente (índice >= indice_atual)          │  │
│  │             - Visíveis na tela                           │  │
│  │             - Distância: 50px <= dist <= 350px           │  │
│  │           • Agrupar pontos consecutivos                  │  │
│  │           • Pegar PRIMEIRO grupo (seguindo ordem)        │  │
│  │           • Escolher ponto MAIS DISTANTE do grupo        │  │
│  │           → wp_x, wp_y = ponto escolhido                 │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.5. CONVERTER COORDENADAS MUNDO → TELA                 │  │
│  │     • Delta = (wp_x - x_atual, wp_y - y_atual)          │  │
│  │     • Escala = tamanho_tela / tamanho_mapa_mundo        │  │
│  │     • Clique_x = centro_tela_x + delta_x * escala_x     │  │
│  │     • Clique_y = centro_tela_y + delta_y * escala_y     │  │
│  │     • Retorna: (x_clique, y_clique) em pixels da tela   │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.6. ATUALIZAR VISUALIZAÇÃO                              │  │
│  │     • Desenha screenshot atual                           │  │
│  │     • Path completo (linha amarela)                      │  │
│  │     • Player (círculo azul 'P')                          │  │
│  │     • Waypoint (círculo verde 'WP')                      │  │
│  │     • PRÓXIMO CLIQUE (círculo vermelho grande 'X')       │  │
│  │     • Destino (círculo rosa)                             │  │
│  │     • Área visível (retângulo ciano)                     │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.7. CLICAR NO MAPA                                      │  │
│  │     • ADB: adb shell input tap x_clique y_clique         │  │
│  │     • Aguardar 0.3s                                      │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3.8. AGUARDAR CHEGADA                                    │  │
│  │     • Detectar linha verde (movimento iniciado)          │  │
│  │     • Aguardar linha verde sumir (parou)                 │  │
│  │     • GPS: confirmar posição final                       │  │
│  │     • Distância ao waypoint <= 30px?                     │  │
│  │     • SIM → Continuar para próximo passo                 │  │
│  │     • NÃO → Tentar novamente                             │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       └─────────────┐                           │
│                                     │                           │
│                                     ▼                           │
│                          ┌──────────────────┐                   │
│                          │  Próximo Passo   │                   │
│                          │  (step += 1)     │                   │
│                          └──────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 DETALHAMENTO DAS ETAPAS

### 1️⃣ GPS - Localização do Player

```
Screenshot → Processar → Template Matching (NCC) → Posição (x, y)
```

**Como funciona:**
- Captura screenshot do emulador (1600x900)
- Extrai região do mapa (configurada em `map_calibration.json`)
- Aplica ajuste de levels (contraste)
- Reduz para 20% do tamanho (para matching rápido)
- Compara com mapa mundo completo usando NCC (Normalized Cross-Correlation)
- Encontra melhor match → posição do player no mapa mundo

---

### 2️⃣ A* Pathfinding

```
Mapa P&B (0/1) → A* Algorithm → Path completo (lista de pontos)
```

**Características:**
- **Mapa de entrada:** Matriz binária (0 = walkable, 1 = parede)
- **Margem de segurança:** Dilata paredes em 5px (evita cliques perto de paredes)
- **Algoritmo:** A* (A-star) - encontra caminho ótimo evitando obstáculos
- **Saída:** Lista ordenada de pontos `[(x1,y1), (x2,y2), ..., (xn,yn)]`
- **Path completo:** TODOS os pontos pixel-a-pixel (não simplificado)

**Exemplo:**
```
Path: [(366, 1220), (365, 1219), (364, 1218), ..., (34, 1058)]
       ↑ início (player)                              ↑ destino
```

---

### 3️⃣ Navegação Incremental

**Conceito chave:** O bot NÃO calcula todos os cliques de uma vez. Ele:
1. Calcula o path completo UMA VEZ
2. A cada passo, escolhe o próximo clique baseado na **tela atual**
3. Após cada movimento, recaptura a tela e recalcula

**Por quê?**
- O mapa visível muda conforme o player se move
- Pontos que estavam longe podem ficar visíveis
- Permite clicar no ponto mais distante visível (mais eficiente)

---

### 4️⃣ Escolha do Próximo Ponto de Clique

**Algoritmo:**

```
1. Calcular área visível (baseado na posição atual do player)

2. Filtrar pontos do path que estão:
   ✓ À frente (índice >= indice_atual)
   ✓ Visíveis na tela (dentro da área visível)
   ✓ Distância adequada (50px <= dist <= 350px)

3. Agrupar pontos consecutivos (gap <= 20 índices)

4. Pegar PRIMEIRO grupo (mais próximo no path)

5. Escolher ponto MAIS DISTANTE do primeiro grupo

6. Se primeiro grupo muito próximo (< 80px) e houver próximo grupo:
   → Usar próximo grupo (mas gap <= 50 índices)
```

**Exemplo visual:**

```
Path: [P1, P2, P3, ..., P50, P51, ..., P200, ..., P393]
       ↑ início                                    ↑ final

Player em: P15
Área visível: [P20, P21, P22, ..., P100, P101, ..., P375]

Pontos visíveis filtrados:
  Grupo 1: [P20, P21, P22, P23, P24]  ← PRIMEIRO GRUPO
  Grupo 2: [P100, P101, P102]
  Grupo 3: [P370, P371, P372, P373, P374, P375]

Escolha: P24 (mais distante do Grupo 1)
```

---

### 5️⃣ Conversão de Coordenadas

**Problema:** Path está em coordenadas do **mapa mundo** (ex: 1730x1459), mas precisamos clicar na **tela do emulador** (ex: 1600x900).

**Solução:**

```
1. Calcular delta (diferença):
   delta_x = wp_x - x_atual
   delta_y = wp_y - y_atual

2. Calcular escala (tamanho real):
   escala_x = map_capturado_width / mapa_mundo_width
   escala_y = map_capturado_height / mapa_mundo_height

3. Converter para coordenadas de tela:
   centro_x = map_region['x'] + map_region['width'] / 2
   centro_y = map_region['y'] + map_region['height'] / 2
   
   clique_x = centro_x + delta_x * escala_x
   clique_y = centro_y + delta_y * escala_y
```

**Exemplo:**
```
Player: (366, 1220) - centro da tela
Waypoint: (200, 1150)
Delta: (-166, -70)

Escala: X=0.9249, Y=0.6162
Centro tela: (800, 450)

Clique: (800 + (-166)*0.9249, 450 + (-70)*0.6162)
      = (646, 407)
```

---

### 6️⃣ Visualização em Tempo Real

**O que é mostrado:**

```
┌─────────────────────────────────────────┐
│  Status: Passo 5/200                    │
│  Player: (366, 1220)                    │
│  Waypoint: (200, 1150)                  │
│  Clique: (646, 407)                     │
│                                         │
│  [Screenshot do mapa do jogo]           │
│                                         │
│  🟦 P = Player (azul)                   │
│  🟩 WP = Waypoint (verde)               │
│  🟥 X = PRÓXIMO CLIQUE (vermelho)       │
│  🟪 = Destino (rosa)                    │
│  🟨 = Path completo (linha amarela)     │
│  ⬜ = Área visível (retângulo ciano)    │
│                                         │
│  Legenda: ...                           │
└─────────────────────────────────────────┘
```

**Destaque especial:** O próximo clique é mostrado com:
- Círculo vermelho grande (3 camadas)
- Cruz vermelha grande
- Texto ">>> PROXIMO CLIQUE <<<"
- Linha amarela conectando player ao clique

---

## 🎯 DECISÕES DE DESIGN

### Por que usar path completo (não simplificado)?

**Vantagens:**
- Mais opções de clique disponíveis
- Pode escolher qualquer ponto visível do path
- Mais flexível para navegação incremental

**Desvantagens:**
- Mais pontos para processar (ex: 393 pontos)
- Pode ser mais lento (mas ainda rápido o suficiente)

---

### Por que navegação incremental?

**Vantagens:**
- Adapta-se a mudanças na tela
- Pode clicar no ponto mais distante visível
- Mais eficiente (menos cliques intermediários)

**Desvantagens:**
- Precisa recapturar tela a cada passo
- Mais complexo de implementar

---

### Por que primeiro grupo (não último)?

**Problema anterior:** Pegava último grupo → pulava para pontos do final do path → player ia na direção errada.

**Solução:** Pegar primeiro grupo → garante que seguimos a ordem do path → player vai na direção certa.

---

## 🔧 CONFIGURAÇÕES IMPORTANTES

### Distâncias

- **Distância mínima de clique:** 50px (não clicar muito perto)
- **Distância máxima de clique:** 350px (limite de alcance)
- **Tolerância de chegada:** 30px (considera que chegou)
- **Margem de parede:** 5px (evita clicar perto de paredes)

### Área Visível

- **Cálculo:** `player_pos ± (tela_size / 2 / escala)`
- **Exemplo:** Player em (366, 1220), tela 1600x900, escala 0.92/0.61
  - Raio X: (1600/2) / 0.92 = 870px
  - Raio Y: (900/2) / 0.61 = 738px
  - Área: (-504, 482) a (1236, 1958)

---

## 📊 FLUXO DETALHADO COMPLETO

```
═══════════════════════════════════════════════════════════════════════════
                    🚀 INÍCIO DA NAVEGAÇÃO
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ ETAPA 0: INICIALIZAÇÃO                                                  │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Carregar configurações (map_calibration.json)
  │   • map_region: {x, y, width, height}
  │   • map_scale: 20.0
  │   • buttons: {open_map, close_map}
  │
  ├─ Carregar mapas
  │   • mapa_pb.npz (preto e branco, 0=walkable, 1=parede)
  │   • mapa_colorido.npz (cores dos biomas)
  │
  ├─ Inicializar GPS
  │   • Conectar ADB ao emulador
  │   • Carregar mapa de referência (MINIMAPA CERTO.png)
  │
  └─ Inicializar Pathfinder A*
      • Criar walkable_mask do mapa P&B
      • Aplicar margem de segurança (5px) nas paredes
      • Areas walkaveis: 64.5% do mapa

═══════════════════════════════════════════════════════════════════════════
                    📍 ETAPA 1: OBTER POSIÇÃO INICIAL
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ 1.1. Capturar Screenshot do Emulador                                   │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ ADB: adb shell screencap -p
  │   • Screenshot completo: 1600x900 pixels
  │
  └─ Extrair região do mapa
      • map_region: {x: 0, y: 0, width: 1600, height: 900}
      • map_img: 1600x900 pixels

┌─────────────────────────────────────────────────────────────────────────┐
│ 1.2. Processar Imagem                                                   │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Aplicar ajuste de levels (contraste)
  │   • input_min: 0.43, input_max: 0.65
  │   • Melhora detecção de features
  │
  ├─ Reduzir para matching (20% do tamanho)
  │   • 1600x900 → 320x180 (para matching rápido)
  │
  └─ Converter para grayscale

┌─────────────────────────────────────────────────────────────────────────┐
│ 1.3. Template Matching (NCC)                                            │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Comparar map_img (320x180) com mapa mundo completo (1730x1459)
  │   • Usar Normalized Cross-Correlation (NCC)
  │   • Encontrar melhor match (correlação máxima)
  │
  ├─ Validar confiança (SSIM)
  │   • Se confiança < 70% → ERRO
  │
  └─ Retornar posição
      • x_inicial, y_inicial (coordenadas no mapa mundo)
      • zona (identificada por cor do bioma)
      • confidence (%)

RESULTADO: Player em (366, 1220) - Deserto - 95% confiança

═══════════════════════════════════════════════════════════════════════════
                    🗺️ ETAPA 2: CALCULAR ROTA COM A*
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ 2.1. Preparar Mapa para Pathfinding                                     │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Carregar mapa P&B (map_data.npz)
  │   • 0 = walkable (chão)
  │   • 1 = não-walkable (parede)
  │
  ├─ Aplicar margem de segurança
  │   • Dilatar paredes em 5px (cv2.dilate)
  │   • Evita cliques muito perto de paredes
  │
  └─ Criar walkable_mask
      • True = pode andar
      • False = não pode andar

┌─────────────────────────────────────────────────────────────────────────┐
│ 2.2. Executar Algoritmo A*                                              │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Entrada:
  │   • Início: (x_inicial, y_inicial) = (366, 1220)
  │   • Destino: (destino_x, destino_y) = (34, 1058)
  │
  ├─ Algoritmo:
  │   • Fila de prioridade (open_set)
  │   • Custo g(n) = distância percorrida
  │   • Heurística h(n) = distância euclidiana ao destino
  │   • f(n) = g(n) + h(n) (prioridade)
  │
  ├─ Processo:
  │   • Expandir nós adjacentes (8 direções)
  │   • Verificar se é walkable
  │   • Atualizar custos
  │   • Continuar até chegar no destino
  │
  └─ Resultado:
      • path_raw = [(366, 1220), (365, 1219), ..., (34, 1058)]
      • 393 pontos (pixel-a-pixel)
      • 15758 iterações

┌─────────────────────────────────────────────────────────────────────────┐
│ 2.3. Fallback se Pathfinding Falhar                                     │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Se pathfinding falhar com margem:
  │   • Tentar SEM margem (wall_margin=0)
  │   • Se ainda falhar → usar navegação direta
  │
  └─ Se posição inicial não for walkable:
      • ERRO: "Posição inicial não é walkable!"
      • Tentar pathfinding sem margem

RESULTADO: Path completo com 393 pontos

═══════════════════════════════════════════════════════════════════════════
                    🎯 ETAPA 3: INICIALIZAR ÍNDICE DO PATH
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ 3.1. Encontrar Ponto Mais Próximo da Posição Inicial                    │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ├─ Percorrer todos os pontos do path
  │   • Calcular distância de cada ponto até (x_inicial, y_inicial)
  │
  ├─ Encontrar menor distância
  │   • Exemplo: Ponto P15 está a 5px da posição inicial
  │
  └─ Definir índice inicial
      • indice_waypoint_atual = 15 + 1 = 16
      • Garante que começamos à frente no path

RESULTADO: Índice inicial = 16/393 (ponto mais próximo: 15)

═══════════════════════════════════════════════════════════════════════════
                    🔄 ETAPA 4: LOOP DE NAVEGAÇÃO (até 200 passos)
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ PASSO N:                                                                │
└─────────────────────────────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.1. CAPTURAR TELA ATUAL E OBTER POSIÇÃO                             │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Abrir mapa no jogo (se não estiver aberto)
    │   • Clicar no botão "open_map" (coordenadas configuradas)
    │   • Aguardar 1.5s
    │
    ├─ Capturar screenshot
    │   • ADB: screencap
    │   • Extrair região do mapa
    │
    ├─ Processar imagem
    │   • Levels (contraste)
    │   • Reduzir para matching
    │
    ├─ GPS: Template matching
    │   • Encontrar posição atual do player
    │   • x_atual, y_atual, zona
    │
    └─ Atualizar estado
        • vis_state['x_atual'] = x_atual
        • vis_state['y_atual'] = y_atual
        • vis_state['step'] = N

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.2. DETECTAR SE PLAYER ESTÁ PRESO                                    │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Comparar posição atual com posição anterior
    │   • Se (x_atual, y_atual) == (x_anterior, y_anterior)
    │
    ├─ Incrementar contador
    │   • cliques_sem_movimento += 1
    │
    └─ Se cliques_sem_movimento >= 3:
        • Player está preso!
        • Ajustar estratégia (avançar waypoint, aumentar distância)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.3. VERIFICAR SE CHEGOU NO DESTINO                                  │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Calcular distância ao destino
    │   • dist = sqrt((destino_x - x_atual)² + (destino_y - y_atual)²)
    │
    ├─ Se dist <= 30px (tolerance_pixels):
    │   • ✅ SUCESSO! Chegou no destino!
    │   • Fechar mapa
    │   • Retornar True
    │
    └─ Se dist > 30px:
        • Continuar navegação

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.4. CALCULAR ÁREA VISÍVEL NA TELA                                    │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Calcular raio visível
    │   • raio_x = (map_region['width'] / 2) / escala_x
    │   • raio_y = (map_region['height'] / 2) / escala_y
    │   • Exemplo: raio_x = 865px, raio_y = 731px
    │
    ├─ Calcular limites
    │   • x_min = x_atual - raio_x
    │   • x_max = x_atual + raio_x
    │   • y_min = y_atual - raio_y
    │   • y_max = y_atual + raio_y
    │
    └─ Resultado
        • Área visível: (x_min, y_min) a (x_max, y_max)
        • Exemplo: (-499, 489) a (1231, 1951)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.5. ESCOLHER PRÓXIMO PONTO DE CLIQUE                                │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ DECISÃO A: Destino está visível E muito perto?
    │   │
    │   ├─ Verificar se destino está na área visível
    │   │   • x_min <= destino_x <= x_max?
    │   │   • y_min <= destino_y <= y_max?
    │   │
    │   ├─ Verificar distância
    │   │   • 30px <= dist_destino <= 150px?
    │   │
    │   ├─ Verificar se player não está preso
    │   │   • cliques_sem_movimento == 0?
    │   │
    │   └─ Se TODAS as condições:
    │       • wp_x, wp_y = destino_x, destino_y
    │       • Clicar DIRETO no destino
    │
    └─ DECISÃO B: Usar path A* (contorna obstáculos)
        │
        ├─ 4.5.1. Atualizar índice do path (se necessário)
        │   │
        │   ├─ Verificar se player andou além do índice atual
        │   │   • dist_ao_indice_atual > 50px?
        │   │
        │   ├─ Se sim, encontrar novo índice mais próximo
        │   │   • Percorrer path do índice atual até o final
        │   │   • Encontrar ponto mais próximo da posição atual
        │   │
        │   └─ Atualizar indice_waypoint_atual
        │       • indice_waypoint_atual = indice_mais_proximo + 1
        │
        ├─ 4.5.2. Filtrar pontos visíveis do path
        │   │
        │   ├─ Percorrer path do índice atual até o final
        │   │   • for i in range(indice_waypoint_atual, len(path_completo))
        │   │
        │   ├─ Para cada ponto (px, py):
        │   │   • Calcular distância: dist = sqrt((px-x_atual)² + (py-y_atual)²)
        │   │   • Verificar se está visível: x_min <= px <= x_max AND y_min <= py <= y_max
        │   │   • Verificar distância: 50px <= dist <= 350px
        │   │
        │   └─ Se todas condições: adicionar à lista pontos_visiveis
        │       • pontos_visiveis.append((i, px, py, dist))
        │
        ├─ 4.5.3. Agrupar pontos consecutivos
        │   │
        │   ├─ Ordenar pontos_visiveis por índice (ordem do path)
        │   │
        │   ├─ Agrupar em blocos consecutivos
        │   │   • Se gap entre índices <= 20 → mesmo grupo
        │   │   • Se gap > 20 → novo grupo
        │   │
        │   └─ Resultado: grupos = [[grupo1], [grupo2], [grupo3], ...]
        │
        ├─ 4.5.4. Escolher ponto do primeiro grupo
        │   │
        │   ├─ Pegar primeiro grupo (mais próximo no path)
        │   │   • primeiro_grupo = grupos[0]
        │   │
        │   ├─ Ordenar por distância (maior primeiro)
        │   │   • primeiro_grupo.sort(key=lambda x: x[3], reverse=True)
        │   │
        │   ├─ Escolher ponto mais distante do primeiro grupo
        │   │   • i_escolhido, wp_x, wp_y, dist_escolhida = primeiro_grupo[0]
        │   │
        │   └─ Se primeiro grupo muito próximo (< 80px) E houver próximo grupo:
        │       • Verificar próximo grupo
        │       • Se distância maior E gap <= 50 índices:
        │         → Usar próximo grupo
        │
        └─ 4.5.5. Fallback se nenhum ponto visível
            │
            ├─ Avançar para próximo ponto no path
            │   • Procurar próximo ponto com dist >= 50px
            │
            └─ Se não encontrar:
                • wp_x, wp_y = destino_x, destino_y (último recurso)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.6. CONVERTER COORDENADAS MUNDO → TELA                              │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Calcular delta (diferença)
    │   • delta_x = wp_x - x_atual
    │   • delta_y = wp_y - y_atual
    │   • Exemplo: delta = (-166, -70)
    │
    ├─ Calcular escala real
    │   • escala_x = map_capturado_width / mapa_mundo_width
    │   • escala_y = map_capturado_height / mapa_mundo_height
    │   • Exemplo: escala_x = 0.9249, escala_y = 0.6162
    │
    ├─ Calcular centro da tela
    │   • centro_x = map_region['x'] + map_region['width'] / 2
    │   • centro_y = map_region['y'] + map_region['height'] / 2
    │   • Exemplo: centro = (800, 450)
    │
    └─ Converter para coordenadas de clique
        • clique_x = centro_x + delta_x * escala_x
        • clique_y = centro_y + delta_y * escala_y
        • Exemplo: clique = (646, 407)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.7. ATUALIZAR VISUALIZAÇÃO                                          │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Capturar screenshot atual
    │
    ├─ Extrair região do mapa
    │
    ├─ Desenhar elementos:
    │   • Path completo (linha amarela)
    │   • Player (círculo azul 'P' no centro)
    │   • Waypoint (círculo verde 'WP')
    │   • PRÓXIMO CLIQUE (círculo vermelho grande 'X' + texto)
    │   • Destino (círculo rosa)
    │   • Área visível (retângulo ciano)
    │   • Linha do player ao clique (amarela)
    │
    ├─ Adicionar informações de debug:
    │   • Status: Passo N/200
    │   • Player: (x, y)
    │   • Waypoint: (x, y)
    │   • Clique: (x, y)
    │
    └─ Mostrar janela OpenCV
        • cv2.imshow("Navegação ao Vivo", vis_img)
        • cv2.waitKey(1)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.8. CLICAR NO MAPA                                                   │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Validar coordenadas
    │   • Verificar se clique está dentro da região do mapa
    │   • Aplicar margem de segurança (10px das bordas)
    │
    ├─ Executar clique via ADB
    │   • adb shell input tap x_clique y_clique
    │   • Exemplo: adb shell input tap 646 407
    │
    └─ Aguardar
        • time.sleep(0.3s)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.9. AGUARDAR CHEGADA                                                 │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ FASE 1: Detectar início do movimento
    │   │
    │   ├─ Procurar linha verde (indicador de movimento)
    │   │   • Capturar screenshot
    │   │   • Converter para HSV
    │   │   • Filtrar cor verde (hue: 60-80)
    │   │   • Verificar se há pixels verdes
    │   │
    │   ├─ Se linha verde detectada:
    │   │   • ✅ Movimento iniciado!
    │   │   • Continuar para FASE 2
    │   │
    │   └─ Se não detectada (movimento curto):
    │       • Verificar GPS diretamente
    │       • Se player andou >= 3px → movimento detectado
    │       • Se não andou → player preso
    │
    ├─ FASE 2: Aguardar parar
    │   │
    │   ├─ Loop (até 10 segundos):
    │   │   • Capturar screenshot
    │   │   • Verificar se linha verde ainda existe
    │   │   • Se não existe por 3 frames consecutivos:
    │   │     → ✅ Player parou!
    │   │
    │   └─ Timeout:
    │       • Continuar mesmo assim
    │
    └─ FASE 3: Confirmar com GPS
        │
        ├─ Obter posição atual via GPS
        │   • x_depois, y_depois
        │
        ├─ Calcular distância ao waypoint
        │   • dist = sqrt((wp_x - x_depois)² + (wp_y - y_depois)²)
        │
        ├─ Se dist <= 30px:
        │   • ✅ Chegou no waypoint!
        │   • Retornar True
        │
        └─ Se dist > 30px:
            • ↻ Ainda não chegou
            • Retornar False (continuar navegação)

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.10. VERIFICAR SE PRECISA REAJUSTAR ESTRATÉGIA                      │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ Se player ficou preso tentando ir direto ao destino:
    │   • Resetar indice_waypoint_atual
    │   • Forçar uso de path waypoints na próxima iteração
    │
    └─ Se player não se moveu:
        • Incrementar cliques_sem_movimento
        • Se >= 3: avançar waypoint forçadamente

  ┌───────────────────────────────────────────────────────────────────────┐
  │ 4.11. CONTINUAR PARA PRÓXIMO PASSO                                   │
  └───────────────────────────────────────────────────────────────────────┘
    │
    ├─ step += 1
    │
    ├─ Se step >= 200:
    │   • ⚠️ Máximo de passos atingido!
    │   • Fechar mapa
    │   • Retornar False
    │
    └─ Se step < 200:
        • Voltar para 4.1 (próximo passo)

═══════════════════════════════════════════════════════════════════════════
                    ✅ FIM: SUCESSO OU FALHA
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ SUCESSO:                                                                │
│   • Distância ao destino <= 30px                                       │
│   • Fechar mapa                                                         │
│   • Retornar True                                                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ FALHA:                                                                  │
│   • Máximo de passos atingido (200)                                    │
│   • Pathfinding falhou e navegação direta não funcionou                │
│   • Player ficou preso por muitos passos                               │
│   • Fechar mapa                                                         │
│   • Retornar False                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 EXEMPLO COMPLETO PASSO A PASSO

```
═══════════════════════════════════════════════════════════════════════════
                    EXEMPLO: Navegar de Deserto para Praia
═══════════════════════════════════════════════════════════════════════════

INÍCIO:
  Player: (366, 1220) - Deserto
  Destino: (34, 1058) - Praia
  Distância inicial: 369.4 pixels

ETAPA 2: A* Pathfinding
  ✅ Path calculado: 393 pontos
  ✅ Índice inicial: 16/393 (ponto mais próximo: 15)

═══════════════════════════════════════════════════════════════════════════
                    PASSO 1
═══════════════════════════════════════════════════════════════════════════

4.1. Capturar tela e obter posição
  ✅ Player: (366, 1220) - Deserto

4.2. Detectar se preso
  ✅ Player não está preso (primeiro passo)

4.3. Verificar se chegou
  📏 Distância ao destino: 369.4px (ainda longe)

4.4. Calcular área visível
  📐 Área visível: (-499, 489) a (1231, 1951)
  📐 Raio: X=865px, Y=731px

4.5. Escolher próximo ponto
  🔍 Filtrando pontos do path...
  ✅ Pontos visíveis encontrados: 325 pontos
  📊 Grupos: 3 grupos
    • Grupo 1: [P20, P21, P22, P23, P24] (índices 19-23)
    • Grupo 2: [P100, P101, P102] (índices 99-101)
    • Grupo 3: [P370, P371, ..., P375] (índices 369-374)
  
  🎯 Escolhendo do Grupo 1 (primeiro grupo):
    • P24 (índice 23) - distância: 180px ← ESCOLHIDO
  ✅ Waypoint: (52, 1066)

4.6. Converter coordenadas
  📐 Delta: (-314, -154)
  📐 Escala: X=0.9249, Y=0.6162
  📐 Centro tela: (800, 450)
  🖱️ Clique calculado: (509, 355)

4.7. Atualizar visualização
  ✅ Overlay atualizado
  ✅ Próximo clique destacado em vermelho

4.8. Clicar no mapa
  🖱️ Clicando em (509, 355)
  ⏳ Aguardando 0.3s

4.9. Aguardar chegada
  FASE 1: Detectar movimento
    ⚠️ Linha verde não detectada (movimento curto)
    🔍 Verificando GPS...
    ✅ Player andou: (366, 1220) → (368, 1215)
    ✅ Movimento detectado! (5.4px)
  
  FASE 2: Aguardar parar
    ⏳ Aguardando linha verde sumir...
    ✅ Player parou!
  
  FASE 3: Confirmar com GPS
    📍 Posição GPS: (377, 1207)
    📏 Distância ao waypoint: 349.4px
    ↻ Ainda não chegou (continuar)

4.10. Verificar estratégia
  ✅ Player se moveu, tudo OK

4.11. Continuar
  ✅ Próximo passo: 2/200

═══════════════════════════════════════════════════════════════════════════
                    PASSO 2
═══════════════════════════════════════════════════════════════════════════

4.1. Capturar tela e obter posição
  ✅ Player: (377, 1207) - Vila Inicial

4.2. Detectar se preso
  ✅ Player se moveu (cliques_sem_movimento = 0)

4.3. Verificar se chegou
  📏 Distância ao destino: 374.0px (ainda longe)

4.4. Calcular área visível
  📐 Área visível: (-488, 478) a (1242, 1936)

4.5. Escolher próximo ponto
  🔍 Filtrando pontos do path...
  ⚠️ Nenhum ponto visível na tela atual
  ↻ Avançando para próximo ponto no path...
  ✅ Ponto 376/393: (51, 1065) - distância: 355.6px
  ✅ Waypoint: (51, 1065)

4.6. Converter coordenadas
  📐 Delta: (-326, -142)
  🖱️ Clique calculado: (498, 362)

4.7. Atualizar visualização
  ✅ Overlay atualizado

4.8. Clicar no mapa
  🖱️ Clicando em (498, 362)

4.9. Aguardar chegada
  FASE 1: Detectar movimento
    ✅ Linha verde detectada!
    ✅ Movimento iniciado!
  
  FASE 2: Aguardar parar
    ⏳ Ainda em movimento... (0s)
    ⏳ Ainda em movimento... (2s)
    ⏳ Ainda em movimento... (4s)
    ⏳ Ainda em movimento... (7s)
    ✅ Player parou!
  
  FASE 3: Confirmar com GPS
    📍 Posição GPS: (443, 1136)
    📏 Distância ao waypoint: 398.4px
    ↻ Ainda não chegou (continuar)

4.11. Continuar
  ✅ Próximo passo: 3/200

... (continua até chegar no destino)

═══════════════════════════════════════════════════════════════════════════
                    PASSO N (Final)
═══════════════════════════════════════════════════════════════════════════

4.1. Capturar tela e obter posição
  ✅ Player: (40, 1060) - Praia

4.3. Verificar se chegou
  📏 Distância ao destino: 25px
  ✅ CHEGOU NO DESTINO!

═══════════════════════════════════════════════════════════════════════════
                    ✅ SUCESSO!
═══════════════════════════════════════════════════════════════════════════
  • Fechar mapa
  • Retornar True
```

---

## 🎨 LEGENDA VISUAL

```
🟦 P = Player (círculo azul)
🟩 WP = Waypoint (círculo verde)
🟥 X = PRÓXIMO CLIQUE (círculo vermelho grande)
🟪 = Destino final (círculo rosa)
🟨 = Path completo (linha amarela)
⬜ = Área visível (retângulo ciano)
```

---

## ✅ CHECKLIST DE FUNCIONAMENTO

- [x] GPS localiza player corretamente
- [x] A* calcula path evitando obstáculos
- [x] Path completo mantém ordem correta
- [x] Índice inicial baseado na posição do player
- [x] Área visível calculada corretamente
- [x] Pontos filtrados por visibilidade e distância
- [x] Primeiro grupo escolhido (ordem do path)
- [x] Ponto mais distante do grupo selecionado
- [x] Coordenadas convertidas corretamente (mundo → tela)
- [x] Clique executado no emulador
- [x] Movimento detectado (linha verde)
- [x] Chegada confirmada (GPS)
- [x] Visualização mostra próximo clique destacado

---

## 🚀 PRÓXIMOS PASSOS (MELHORIAS FUTURAS)

- [ ] Otimizar escolha de pontos (heurística mais inteligente)
- [ ] Detectar obstáculos dinâmicos (outros players, mobs)
- [ ] Ajustar velocidade baseado na distância
- [ ] Cache de paths para destinos frequentes
- [ ] Suporte a múltiplos waypoints intermediários

---

**Última atualização:** 2024
**Versão:** 2.0

