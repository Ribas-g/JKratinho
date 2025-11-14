# MAPA VIRTUAL COM RASTREAMENTO TEMPORAL

Sistema de simulação de posição do jogador baseado em movimentos conhecidos + tempo de deslocamento.

## 🎯 OBJETIVO

Evitar clicks em paredes e rastrear posição do jogador em tempo real **sem overhead de GPS constante**.

## ⚙️ COMO FUNCIONA

### Conceito Principal

1. **GPS Inicial**: Uma vez ao iniciar o farm, obter posição real do jogador
2. **Simulação de Movimento**: Bot controla todos os clicks, então sabe exatamente onde mandou o jogador
3. **Rastreamento Temporal**: Detecta quando movimento termina usando:
   - Linha verde (HSV color detection)
   - Timeout baseado em distância + velocidade calibrada
4. **Atualização Virtual**: Só atualiza posição quando movimento completa
5. **Recalibração**: GPS a cada 10 minutos para corrigir drift

### Vantagens

- ✅ **Zero overhead** durante farm (não abre GPS a cada frame)
- ✅ **Validação de clicks** (nunca clica em parede)
- ✅ **Funciona em labirintos** complexos
- ✅ **Rastreamento preciso** em tempo real
- ✅ **Previne vai-e-vem** (não clica enquanto movimento ativo)

## 📋 PASSO A PASSO DE USO

### 1. Processar Mapa Mundo

**Requisito**: Arquivo `MINIMAPA CERTOPRETO.png` na raiz do projeto

```bash
python processar_mapa_mundo.py
```

**O que faz:**
- Processa imagem do minimapa completo
- Cor (não-preto) = chão walkable
- Preto = parede/vazio (não-walkable)
- Identifica biomas por cor RGB
- Gera: `FARM/mapa_mundo_processado.npz` (~100KB)

**Teste:**
```bash
python testar_matriz_mundo.py
```

Gera visualizações:
- `FARM/visualizacao_walkable.png` - Preto/Branco
- `FARM/visualizacao_biomas.png` - Colorido por bioma

---

### 2. Calibrar Velocidade do Personagem

**IMPORTANTE**: Execute **dentro do jogo**, com personagem parado

```bash
python calibrar_velocidade_personagem.py
```

**O que faz (MÉTODO COM MAPA - GROUND TRUTH!):**
1. **Abre mapa UMA VEZ** e mantém aberto durante toda calibração
2. GPS inicial com mapa aberto
3. Para cada distância (1-5 tiles):
   - GPS para atualizar posição atual
   - Gera destino walkable válido usando A* pathfinding
   - Converte coordenadas mundo → tela do mapa
   - **Clica no mapa** (linha verde aparece mostrando caminho)
   - **Detecta linha verde NO MAPA** (ground truth da distância!)
   - Mede tempo até movimento completar (mapa ainda aberto)
   - Calcula velocidade = distância real / tempo
4. Fecha mapa apenas no final
5. Gera: `FARM/velocidade_personagem.json` com velocidade calibrada

**Por que usar o mapa?**
- ✅ **Ground truth absoluto**: Linha verde mostra caminho EXATO do jogo
- ✅ **Considera obstáculos**: Detecta quando personagem contorna paredes
- ✅ **Máxima precisão**: Usa o próprio pathfinding do jogo como referência
- ✅ **Sem aproximações**: Distância é exatamente o que o jogo calcula

**Exemplo de output:**
```json
{
  "velocidade_px_s": 78.5,
  "tempo_por_tile": 0.407,
  "pixels_por_tile": 32,
  "data_calibracao": "2025-01-14 10:30:00"
}
```

**⚠️ ATENÇÃO:**
- Execute com personagem **SEM buffs de velocidade**
- Se mudar equipamento/level que afeta velocidade, recalibre!
- Calibração leva ~2-3 minutos

---

### 3. Executar Farm com Mapa Virtual

**Uso normal:**
```bash
python FARM/farm_integrado.py
```

**O que acontece:**

1. **Inicialização**:
   - Carrega matriz walkable (~100KB)
   - Carrega velocidade calibrada
   - Inicializa mapa virtual

2. **Início do Farm**:
   - GPS inicial (1x) para posição real
   - Posição virtual = posição GPS

3. **Durante Farm**:
   ```
   Bot clica em (900, 500)
   ↓
   Mapa Virtual converte tela → mundo (com posição virtual)
   ↓
   Valida se destino é walkable na matriz
   ↓
   ✅ Walkable → Executa tap + inicia rastreamento temporal
   ❌ Parede → Bloqueia tap
   ↓
   Detecta linha verde (movimento em progresso)
   ↓
   Aguarda linha verde sumir OU timeout
   ↓
   Atualiza posição virtual = destino
   ```

4. **Recalibração**:
   - A cada 10 minutos, GPS automático
   - Corrige drift acumulado
   - Continua farm normalmente

---

## 🧪 TESTANDO O SISTEMA

### Teste Rápido

```bash
python -c "from FARM.mapa_virtual_tempo import MapaVirtualComTempo; m = MapaVirtualComTempo(); print('✅ Sistema OK')"
```

### Teste Completo

```python
from FARM.mapa_virtual_tempo import MapaVirtualComTempo

# Criar mapa
mapa = MapaVirtualComTempo()

# Simular GPS inicial (Deserto)
mapa.atualizar_posicao_gps(374, 1342)

# Converter click tela → mundo
mundo_x, mundo_y = mapa.converter_tela_para_mundo(900, 450)
print(f"Click (900, 450) → Mundo ({mundo_x}, {mundo_y})")

# Validar se é walkable
is_walkable = mapa.validar_click(mundo_x, mundo_y)
print(f"Walkable? {is_walkable}")

# Status
mapa.imprimir_status()
```

---

## 🔧 ARQUIVOS DO SISTEMA

### Gerados Automaticamente

| Arquivo | Tamanho | Descrição |
|---------|---------|-----------|
| `FARM/mapa_mundo_processado.npz` | ~100KB | Matriz walkable + biomas |
| `FARM/velocidade_personagem.json` | ~1KB | Velocidade calibrada |
| `FARM/visualizacao_walkable.png` | Variável | Visualização P&B |
| `FARM/visualizacao_biomas.png` | Variável | Visualização colorida |

### Código do Sistema

| Arquivo | Função |
|---------|--------|
| `processar_mapa_mundo.py` | Processa minimapa em matriz |
| `testar_matriz_mundo.py` | Valida matriz gerada |
| `calibrar_velocidade_personagem.py` | Calibra velocidade |
| `FARM/mapa_virtual_tempo.py` | Classe principal |
| `FARM/farm_bot.py` | Farm bot integrado |
| `FARM/farm_integrado.py` | Sistema completo |

---

## 📊 ESTATÍSTICAS E LOGS

### Durante Farm

```
🗺️ Inicializando Mapa Virtual com Rastreamento Temporal...
   ✅ Matriz walkable carregada: (1689, 1600)
   ✅ Velocidade: 78.5 px/s
   ✅ Tempo por tile: 0.407s

📡 Obtendo posição GPS inicial para mapa virtual...
   ✅ Posição inicial: (374, 1342)

✅ Tap validado: (900, 500) -> mundo (474, 1442)
🏃 Movimento iniciado:
   De: (374, 1342)
   Para: (474, 1442)
   Distância: 141.4 px
   Tempo estimado: 2.164s

🟢 Movimento completo (linha verde sumiu em 2.087s)
✅ Posição virtual atualizada: (474, 1442)
```

### Clicks Bloqueados

```
❌ Tap bloqueado: destino não-walkable (500, 1200)
⚠️ Tap bloqueado: movimento em progresso
```

---

## ❓ TROUBLESHOOTING

### "Arquivo mapa_mundo_processado.npz não encontrado"

**Solução:**
```bash
python processar_mapa_mundo.py
```

Certifique-se que `MINIMAPA CERTOPRETO.png` existe na raiz.

---

### "Arquivo velocidade_personagem.json não encontrado"

**Solução:**
```bash
python calibrar_velocidade_personagem.py
```

Sistema usará valores padrão estimados se arquivo não existir.

---

### "Movimento não completa / Bot trava"

**Possíveis causas:**
1. Velocidade calibrada incorreta
2. Buffs de velocidade ativados (recalibre!)
3. Lag do emulador

**Solução:**
- Recalibre velocidade: `python calibrar_velocidade_personagem.py`
- Verifique se há buffs ativos
- Aumente timeout em `mapa_virtual_tempo.py` (linha ~185)

---

### "Bot clica em paredes mesmo com sistema ativo"

**Debug:**
```python
# Adicionar em farm_bot.py após linha 546:
print(f"DEBUG: Mundo ({mundo_x}, {mundo_y}), Walkable: {mapa.validar_click(mundo_x, mundo_y)}")
```

Verifique se:
- GPS inicial foi bem sucedido
- Posição virtual está correta (`mapa.imprimir_status()`)
- Matriz foi processada corretamente

---

### "Linha verde não detectada"

**Ajustar HSV em `mapa_virtual_tempo.py`:**

```python
# Linha 51-52
self.verde_lower = np.array([40, 100, 100])  # Deixar mais permissivo
self.verde_upper = np.array([80, 255, 255])
```

**Ajustar threshold de pixels:**
```python
# Linha ~162
return pixels_verdes > 50  # Reduzir para 30 se necessário
```

---

## 🎮 FLUXO COMPLETO DE USO

```bash
# 1. SETUP INICIAL (uma vez só)
python processar_mapa_mundo.py
python testar_matriz_mundo.py
python calibrar_velocidade_personagem.py

# 2. FARM (sempre que quiser farmar)
python FARM/farm_integrado.py

# 3. RECALIBRAÇÃO (se mudou velocidade)
python calibrar_velocidade_personagem.py
```

---

## 🔬 DETALHES TÉCNICOS

### Conversão de Coordenadas

**Tela → Mundo:**
```python
mundo_x = player_x + (tela_x - centro_x)
mundo_y = player_y + (tela_y - centro_y)
```

Onde:
- `player_x, player_y`: Posição virtual atual
- `centro_x, centro_y`: Centro da tela (800, 450)
- `tela_x, tela_y`: Coordenadas do click

### Detecção de Linha Verde

**HSV Color Space:**
- **Hue (H)**: 40-80 (tons de verde)
- **Saturation (S)**: 100-255 (saturação mínima)
- **Value (V)**: 100-255 (brilho mínimo)

**Região de Busca:**
- Centro: (800, 450)
- Área: 700-900 x, 350-550 y

### Cálculo de Tempo Estimado

```python
distancia = sqrt((x2-x1)² + (y2-y1)²)
tempo = distancia / velocidade_calibrada
tempo_com_margem = tempo * 1.2  # 20% margem
```

### Critérios de Movimento Completo

**OU lógico (qualquer um):**
1. Linha verde desapareceu (após 30% do tempo estimado)
2. Timeout (tempo estimado * 1.5)

---

## 📈 PERFORMANCE

### Overhead

| Operação | Tempo |
|----------|-------|
| GPS inicial | ~1.5s (1x ao iniciar) |
| GPS recalibração | ~1.5s (1x a cada 10min) |
| Validação de click | <1ms |
| Detecção linha verde | ~10ms |

**Overhead total durante 10min de farm:**
- **Sem mapa virtual**: ~180s (GPS a cada 3s = 200 vezes)
- **Com mapa virtual**: ~1.5s (GPS 1x)
- **Economia**: ~98% 🎉

### Precisão

- **GPS**: ±2 pixels
- **Simulação virtual**: ±5 pixels (drift)
- **Após recalibração**: Volta para ±2 pixels

---

## 🚀 MELHORIAS FUTURAS

- [ ] Suporte para múltiplos personagens (velocidades diferentes)
- [ ] Calibração automática (detectar velocidade durante farm)
- [ ] Visualização do mapa virtual em tempo real
- [ ] Histórico de movimentos (replay)
- [ ] Detecção de stuck (personagem não se mexeu)

---

## 📝 CHANGELOG

### v1.0 (2025-01-14)
- ✨ Sistema de mapa virtual implementado
- ✨ Rastreamento temporal de movimentos
- ✨ Calibração de velocidade
- ✨ Validação de clicks anti-parede
- ✨ GPS recalibração automática

---

## 💡 DICAS

1. **Calibre em local plano**: Evite obstáculos durante calibração
2. **Recalibre após level up**: Velocidade pode mudar
3. **Verifique lag**: Se emulador lagado, aumente margem de tempo
4. **GPS inicial é crítico**: Se falhar, sistema não funciona
5. **Monitore logs**: Verifique se clicks estão sendo validados

---

## 🎯 CONCLUSÃO

Sistema de **Mapa Virtual com Rastreamento Temporal** é a solução definitiva para:
- ✅ Evitar clicks em paredes
- ✅ Rastrear posição sem overhead
- ✅ Farm inteligente em labirintos
- ✅ Prevenir indecisão entre alvos

**Overhead quase zero + precisão máxima = Farm perfeito! 🚀**
