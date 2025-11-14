# Como Instalar Scrcpy no Windows (BlueStacks)

## Por que instalar scrcpy?

O sistema de calibração usa **FastCapture**, que automaticamente detecta o melhor método:

- **Com scrcpy**: Latência de **30-50ms** (~30-60 FPS) 🚀
- **Sem scrcpy** (fallback ADB): Latência de **~300ms** (~3 FPS) 🐌

**Scrcpy é 10x mais rápido!**

---

## 🪟 Instalação no Windows

### Opção 1: Download Direto (Recomendado) ⭐

#### Passo 1: Baixar scrcpy

1. Acesse: https://github.com/Genymobile/scrcpy/releases/latest
2. Baixe o arquivo: `scrcpy-win64-vX.X.X.zip`
3. Extraia em uma pasta, exemplo: `C:\scrcpy\`

#### Passo 2: Adicionar ao PATH

1. Pressione `Win + R`
2. Digite: `sysdm.cpl` e aperte Enter
3. Vá na aba **"Avançado"**
4. Clique em **"Variáveis de Ambiente"**
5. Em "Variáveis do sistema", encontre **"Path"** e clique em **"Editar"**
6. Clique em **"Novo"** e adicione: `C:\scrcpy\` (caminho onde extraiu)
7. Clique **OK** em todas as janelas
8. **Feche e abra novamente** o terminal/PowerShell/CMD

#### Passo 3: Testar

Abra um **novo** CMD ou PowerShell e teste:

```cmd
scrcpy --version
```

Deve mostrar algo como: `scrcpy 2.4 <https://github.com/Genymobile/scrcpy>`

✅ Pronto! O scrcpy está instalado.

---

### Opção 2: Via Scoop (Package Manager)

Se você usa Scoop (gerenciador de pacotes para Windows):

```powershell
# Instalar Scoop (se ainda não tiver)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex

# Instalar scrcpy
scoop install scrcpy
```

---

### Opção 3: Via Chocolatey

Se você usa Chocolatey:

```cmd
choco install scrcpy
```

---

## 📱 BlueStacks + ADB

### Conectar ao BlueStacks

O BlueStacks usa uma porta ADB específica. Você precisa conectar manualmente:

```cmd
# BlueStacks geralmente usa uma destas portas:
adb connect 127.0.0.1:5555
# ou
adb connect 127.0.0.1:5565
# ou (BlueStacks 5)
adb connect 127.0.0.1:5556

# Verificar se conectou
adb devices
```

Deve aparecer algo como:
```
List of devices attached
127.0.0.1:5555    device
```

### Testar scrcpy com BlueStacks

```cmd
scrcpy --no-display
```

Se aparecer `INFO: Device: ...` e não dar erro, está funcionando! ✅

Pressione `Ctrl+C` para parar.

---

## 🧪 Testando com o Calibrador

Execute o calibrador:

```cmd
python calibrar_mapa_manual.py
```

Você verá uma das mensagens:

- `🚀 Usando SCRCPY (~30-50ms latência)` ✅ **Instalado corretamente!**
- `📱 Usando ADB screencap (~300ms latência)` ⚠️ **Não detectado, usando fallback**

Se ver a mensagem de ADB mesmo após instalar scrcpy:

1. Verifique se scrcpy está no PATH: `scrcpy --version`
2. Feche e abra novamente o terminal
3. Verifique se ADB está conectado: `adb devices`

---

## 🚀 Performance Esperada

### Com scrcpy instalado
```
✅ Latência: ~40ms (10x mais rápido)
✅ Detecção precisa de linha verde
✅ Velocidade consistente entre medições
✅ Polling de ~100 FPS
```

### Sem scrcpy (fallback ADB)
```
⚠️ Latência: ~300ms (funciona, mas lento)
⚠️ Possível variação entre medições
⚠️ Polling de ~3 FPS
```

---

## ❓ Solução de Problemas

### "scrcpy não é reconhecido como comando"

- Você adicionou ao PATH?
- Fechou e abriu novamente o terminal?
- Verifique se o caminho está correto em Variáveis de Ambiente

### "ERROR: Could not find any ADB device"

```cmd
# Conectar ao BlueStacks
adb connect 127.0.0.1:5555
adb devices

# Tentar novamente
scrcpy --no-display
```

### "ERROR: Could not open video stream"

Pode ser problema de codec. Tente:

```cmd
scrcpy --no-display --video-codec=h264 --max-fps=30
```

### Scrcpy abre uma janela

Isso é esperado ao testar! No código Python, usamos `--no-display` automaticamente (não abre janela).

---

## 📦 O que o FastCapture faz automaticamente

```python
# O FastCapture detecta e escolhe automaticamente:

if scrcpy instalado:
    usar_scrcpy()      # 30-50ms ✅
else:
    usar_adb()         # 300ms (fallback)
```

Você **não precisa mudar nada no código**! O sistema escolhe sozinho.

---

## 📚 Referências

- [Scrcpy GitHub](https://github.com/Genymobile/scrcpy)
- [Scrcpy Releases (Download)](https://github.com/Genymobile/scrcpy/releases)
- [Scoop Package Manager](https://scoop.sh/)

---

**Resumo**: Baixe o ZIP, extraia, adicione ao PATH, teste com `scrcpy --version`. O calibrador vai usar automaticamente! 🚀
