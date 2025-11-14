"""
FAST CAPTURE - Sistema híbrido de captura rápida

Tenta usar scrcpy (30-50ms latência) se disponível
Fallback para ADB otimizado (~300ms) se scrcpy não estiver instalado

Para instalar scrcpy e obter máxima performance:
  sudo apt install scrcpy ffmpeg
  # ou
  sudo snap install scrcpy
"""

import subprocess
import cv2
import numpy as np
import threading
import queue
import time
import shutil


class FastCapture:
    """Captura rápida com fallback automático scrcpy → ADB"""

    def __init__(self, device=None, preferred_method='auto'):
        """
        Args:
            device: Device ppadb (para fallback ADB)
            preferred_method: 'scrcpy', 'adb', ou 'auto' (tenta scrcpy primeiro)
        """
        self.device = device
        self.preferred_method = preferred_method
        self.active_method = None

        # Extrair serial do device (para scrcpy --serial)
        self.device_serial = None
        if device is not None and hasattr(device, 'serial'):
            self.device_serial = device.serial

        # Scrcpy vars
        self.scrcpy_process = None
        self.ffmpeg_process = None
        self.capture_thread = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = False
        self.last_frame = None
        self.last_frame_time = 0

        # Detectar método disponível
        self._detect_method()

    def _detect_method(self):
        """Detecta qual método de captura usar"""
        if self.preferred_method == 'adb':
            self.active_method = 'adb'
            print("📱 Usando ADB screencap (~300ms latência)")
            return

        # Verificar se scrcpy está disponível
        scrcpy_available = shutil.which('scrcpy') is not None
        ffmpeg_available = shutil.which('ffmpeg') is not None

        if scrcpy_available and ffmpeg_available:
            self.active_method = 'scrcpy'
            print("🚀 Usando SCRCPY (~30-50ms latência)")
        else:
            self.active_method = 'adb'
            print("📱 Usando ADB screencap (~300ms latência)")

            if not scrcpy_available or not ffmpeg_available:
                print("\n⚠️  SCRCPY NÃO ENCONTRADO - Para captura 10x mais rápida:")
                print("    sudo apt install scrcpy ffmpeg")
                print("    # ou")
                print("    sudo snap install scrcpy")
                print()

    def start(self):
        """Inicia captura"""
        if self.active_method == 'scrcpy':
            return self._start_scrcpy()
        else:
            # ADB não precisa start
            print("✅ ADB pronto para capturas")
            return True

    def _start_scrcpy(self):
        """Inicia captura via scrcpy"""
        if self.running:
            print("⚠️ Scrcpy já está rodando")
            return True

        # Comando scrcpy 2.4 (parâmetros corretos!)
        cmd = [
            'scrcpy',
            '--no-playback',             # Sem janela visual (mesmo na 2.4 já era --no-playback)
            '--record=-',                # Output para stdout (RAW H264!)
            '--video-codec=h264',        # Codec H264 (2.4 usa --video-codec)
            '--max-fps=30',              # Limitar FPS
            '--bit-rate=2M',             # Bitrate
            '--no-audio'                 # Sem áudio
        ]

        # Adicionar serial do device se disponível (importante quando há múltiplos devices)
        if self.device_serial:
            cmd.extend(['--serial', self.device_serial])
            print(f"🚀 Iniciando scrcpy em background (device: {self.device_serial})...")
        else:
            print("🚀 Iniciando scrcpy em background...")

        try:
            # Iniciar scrcpy
            self.scrcpy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )

            # Aguardar iniciar
            time.sleep(2)

            if self.scrcpy_process.poll() is not None:
                stderr = self.scrcpy_process.stderr.read().decode()
                raise Exception(f"Scrcpy falhou: {stderr}")

            # Iniciar thread de captura
            self.running = True
            self.capture_thread = threading.Thread(target=self._scrcpy_loop, daemon=True)
            self.capture_thread.start()

            # Aguardar primeiro frame
            print("⏳ Aguardando primeiro frame...")
            timeout = time.time() + 5
            while self.last_frame is None and time.time() < timeout:
                time.sleep(0.1)

            if self.last_frame is not None:
                h, w = self.last_frame.shape[:2]
                print(f"✅ Scrcpy ativo! Resolução: {w}x{h}")
                return True
            else:
                print("⚠️ Timeout - voltando para ADB")
                self.stop()
                self.active_method = 'adb'
                return True

        except Exception as e:
            print(f"⚠️ Scrcpy falhou: {e}")
            print("   Voltando para ADB...")
            self.stop()
            self.active_method = 'adb'
            return True

    def _scrcpy_loop(self):
        """Loop de captura scrcpy"""
        print("🔧 Iniciando decodificação ffmpeg...")

        # Dar tempo ao scrcpy iniciar
        time.sleep(1.0)

        # Verificar se scrcpy ainda está rodando
        if self.scrcpy_process.poll() is not None:
            stderr = self.scrcpy_process.stderr.read().decode(errors='ignore')
            print(f"❌ Scrcpy morreu antes do ffmpeg! Stderr:\n{stderr}")
            return

        print("✅ Scrcpy ainda rodando, iniciando ffmpeg...")

        # FFmpeg para decodificar H264 raw do scrcpy 2.4
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'h264',                 # Input é H264 raw (scrcpy 2.4 envia isso!)
            '-i', 'pipe:0',               # Input do pipe
            '-f', 'image2pipe',           # Output como sequência de imagens
            '-pix_fmt', 'bgr24',          # Formato BGR24 (OpenCV)
            '-vcodec', 'rawvideo',        # Raw video output
            '-'                           # Output para stdout
        ]

        try:
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=self.scrcpy_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # Mudado de DEVNULL para PIPE para debug
                bufsize=0
            )

            # Assumir 1600x900 (Rucoy padrão)
            width, height = 1600, 900
            frame_size = width * height * 3

            print(f"📐 Aguardando frames {width}x{height} ({frame_size} bytes cada)...")
            frames_recebidos = 0

            while self.running:
                try:
                    raw_frame = self.ffmpeg_process.stdout.read(frame_size)

                    if frames_recebidos == 0 and len(raw_frame) > 0:
                        print(f"✅ Primeiro frame recebido! ({len(raw_frame)} bytes)")

                    if len(raw_frame) != frame_size:
                        # Verificar se ffmpeg teve erro
                        if self.ffmpeg_process.poll() is not None:
                            stderr = self.ffmpeg_process.stderr.read().decode(errors='ignore')
                            print(f"❌ FFmpeg morreu! Erro: {stderr[-500:]}")  # Últimos 500 chars
                            break
                        continue

                    frame = np.frombuffer(raw_frame, dtype=np.uint8)
                    frame = frame.reshape((height, width, 3))

                    self.last_frame = frame
                    self.last_frame_time = time.time()
                    frames_recebidos += 1

                    # Atualizar queue
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self.frame_queue.put_nowait(frame)

                except Exception as e:
                    if self.running:
                        print(f"⚠️ Erro na captura: {e}")
                    break

            self.ffmpeg_process.terminate()

        except Exception as e:
            print(f"❌ Erro no loop scrcpy: {e}")

    def get_frame(self, timeout=1.0):
        """Captura frame (automático via scrcpy ou ADB)"""
        if self.active_method == 'scrcpy':
            return self._get_frame_scrcpy(timeout)
        else:
            return self._get_frame_adb()

    def _get_frame_scrcpy(self, timeout=1.0):
        """Pega frame do scrcpy (baixa latência)"""
        if not self.running:
            return None

        # Retornar último frame se recente
        if self.last_frame is not None:
            age = time.time() - self.last_frame_time
            if age < 1.0:
                return self.last_frame.copy()

        # Aguardar novo frame
        try:
            frame = self.frame_queue.get(timeout=timeout)
            return frame.copy()
        except queue.Empty:
            return None

    def _get_frame_adb(self):
        """Captura via ADB (fallback)"""
        if self.device is None:
            raise Exception("Device ADB não fornecido para fallback")

        try:
            screenshot_bytes = self.device.shell("screencap -p", encoding=None)
            nparr = np.frombuffer(screenshot_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"❌ Erro ao capturar via ADB: {e}")
            return None

    def stop(self):
        """Para captura"""
        if self.active_method == 'scrcpy':
            self.running = False

            if self.capture_thread:
                self.capture_thread.join(timeout=2)

            if self.scrcpy_process:
                self.scrcpy_process.terminate()
                try:
                    self.scrcpy_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.scrcpy_process.kill()

            print("✅ Scrcpy parado")

    def get_latency_estimate(self):
        """Retorna estimativa de latência do método ativo"""
        if self.active_method == 'scrcpy':
            return 0.04  # ~40ms
        else:
            return 0.30  # ~300ms

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


if __name__ == "__main__":
    """Teste rápido"""
    print("=" * 70)
    print("🧪 TESTE FAST CAPTURE")
    print("=" * 70)

    # Teste sem device (apenas para ver detecção)
    capture = FastCapture(device=None, preferred_method='auto')

    print(f"\n📊 Método ativo: {capture.active_method}")
    print(f"   Latência estimada: {capture.get_latency_estimate() * 1000:.0f}ms")

    if capture.active_method == 'scrcpy':
        print("\n🧪 Testando scrcpy...")
        if capture.start():
            for i in range(5):
                start = time.time()
                frame = capture.get_frame()
                latency = (time.time() - start) * 1000

                if frame is not None:
                    h, w = frame.shape[:2]
                    print(f"   Frame {i+1}: {w}x{h} - {latency:.1f}ms")
                else:
                    print(f"   Frame {i+1}: FALHOU")

                time.sleep(0.2)

        capture.stop()
    else:
        print("\n✅ ADB pronto (precisa de device para testar)")

    print("\n✅ Teste concluído!")
