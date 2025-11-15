# Como Instalar Scrcpy para Captura Ultra-Rápida

## Por que instalar scrcpy?

O sistema de calibração agora usa **FastCapture**, que automaticamente detecta o melhor método disponível:

- **Com scrcpy**: Latência de **30-50ms** (~30-60 FPS)
- **Sem scrcpy** (fallback ADB): Latência de **~300ms** (~3 FPS)

**Scrcpy é 10x mais rápido!** 🚀

## Instalação

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install scrcpy ffmpeg
```

### Arch Linux

```bash
sudo pacman -S scrcpy ffmpeg
```

### Fedora

```bash
sudo dnf install scrcpy ffmpeg
```

### Via Snap (qualquer distro)

```bash
sudo snap install scrcpy
```

### Compilar do source (mais recente)

```bash
# Instalar dependências
sudo apt install ffmpeg libsdl2-2.0-0 adb wget \
                 gcc git pkg-config meson ninja-build libsdl2-dev \
                 libavcodec-dev libavdevice-dev libavformat-dev libavutil-dev \
                 libswresample-dev libusb-1.0-0 libusb-1.0-0-dev

# Clonar e compilar
git clone https://github.com/Genymobile/scrcpy
cd scrcpy
./install_release.sh
```

## Verificar Instalação

```bash
scrcpy --version
ffmpeg -version
```

## Como Funciona

O **FastCapture** detecta automaticamente:

1. Verifica se `scrcpy` e `ffmpeg` estão instalados
2. Se **SIM**: Usa scrcpy em modo `--no-display` (background, sem janela)
3. Se **NÃO**: Usa ADB screencap (mais lento, mas funciona)

Você não precisa alterar nada no código! O sistema escolhe automaticamente.

## Testando

Execute o calibrador e veja qual método está sendo usado:

```bash
python calibrar_mapa_manual.py
```

Você verá uma das mensagens:

- `🚀 Usando SCRCPY (~30-50ms latência)` ✅
- `📱 Usando ADB screencap (~300ms latência)` ⚠️

## Performance Esperada

### Com scrcpy
```
✅ Detecção precisa de quando linha verde aparece/desaparece
✅ Polling de 10ms efetivo (~100 FPS)
✅ Erro de timing: ~40ms
✅ Velocidade consistente entre medições
```

### Sem scrcpy (fallback ADB)
```
⚠️ Detecção com delay significativo
⚠️ Polling de ~300ms (~3 FPS)
⚠️ Erro de timing: ~150ms
⚠️ Possível variação entre medições
```

## Solução de Problemas

### "scrcpy: command not found"

Instale o scrcpy conforme instruções acima.

### Scrcpy instalado mas não detectado

Verifique se está no PATH:

```bash
which scrcpy
# Deve mostrar: /usr/bin/scrcpy ou similar
```

### Erro ao iniciar scrcpy

1. Verifique se device está conectado:
   ```bash
   adb devices
   ```

2. Tente iniciar scrcpy manualmente:
   ```bash
   scrcpy --no-display
   ```

3. Se funcionar manualmente mas não no script, reporte o erro.

## Referências

- [Scrcpy GitHub](https://github.com/Genymobile/scrcpy)
- [FFmpeg](https://ffmpeg.org/)

---

**Resumo**: Instale scrcpy para obter captura 10x mais rápida! O sistema funciona sem ele, mas com performance reduzida.
