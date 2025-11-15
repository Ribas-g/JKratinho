"""
FAST CAPTURE - Sistema híbrido de captura rápida

Tenta usar adbnativeblitz (50-80ms) se disponível
Fallback para ADB screencap (~300ms) se não instalado

Para instalar adbnativeblitz e obter alta performance:
  pip install adbnativeblitz

Requer Python 3.11+
"""

import subprocess
import cv2
import numpy as np
import threading
import queue
import time
import shutil


class FastCapture:
    """Captura rápida com fallback automático adbnativeblitz → ADB"""

    def __init__(self, device=None, preferred_method='auto'):
        """
        Args:
            device: Device ppadb (para fallback ADB)
            preferred_method: 'adbnativeblitz', 'adb', ou 'auto' (tenta adbnativeblitz primeiro)
        """
        self.device = device
        self.preferred_method = preferred_method
        self.active_method = None

        # Extrair serial do device
        self.device_serial = None
        if device is not None and hasattr(device, 'serial'):
            self.device_serial = device.serial

        # adbnativeblitz vars
        self.adbblitz = None
        self.adbblitz_thread = None
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

        # Verificar se adbnativeblitz está disponível
        try:
            import adbnativeblitz
            self.active_method = 'adbnativeblitz'
            print("🚀 Usando adbnativeblitz (~50-80ms latência)")
        except ImportError:
            self.active_method = 'adb'
            print("📱 Usando ADB screencap (~300ms latência)")
            print("\n⚠️  ADBNATIVEBLITZ NÃO ENCONTRADO - Para captura 5x mais rápida:")
            print("    pip install adbnativeblitz")
            print()

    def start(self):
        """Inicia captura"""
        if self.active_method == 'adbnativeblitz':
            return self._start_adbnativeblitz()
        else:
            # ADB não precisa start
            print("✅ ADB pronto para capturas")
            return True

    def _start_adbnativeblitz(self):
        """Inicia captura via adbnativeblitz"""
        try:
            from adbnativeblitz import AdbFastScreenshots
            import os

            # Encontrar adb.exe
            adb_path = shutil.which('adb')
            if not adb_path:
                print("❌ ADB não encontrado no PATH")
                self.active_method = 'adb'
                return True

            print(f"🚀 Iniciando adbnativeblitz (device: {self.device_serial})...")

            # Iniciar adbnativeblitz
            self.adbblitz = AdbFastScreenshots(
                adb_path=adb_path,
                device_serial=self.device_serial,
                time_interval=179,  # Máximo antes de reiniciar
                width=1600,
                height=900,
                bitrate="20M",
                screenshotbuffer=10,
                go_idle=0  # 0 = máxima performance
            )

            # Entrar no context manager
            self.adbblitz.__enter__()

            # Iniciar thread para consumir frames
            self.running = True
            self.adbblitz_thread = threading.Thread(target=self._adbnativeblitz_loop, daemon=True)
            self.adbblitz_thread.start()

            # Aguardar primeiro frame
            print("⏳ Aguardando primeiro frame...")
            timeout = time.time() + 5
            while self.last_frame is None and time.time() < timeout:
                time.sleep(0.1)

            if self.last_frame is not None:
                h, w = self.last_frame.shape[:2]
                print(f"✅ adbnativeblitz ativo! Resolução: {w}x{h}")
                return True
            else:
                print("⚠️ Timeout - voltando para ADB")
                self.stop()
                self.active_method = 'adb'
                return True

        except Exception as e:
            print(f"⚠️ adbnativeblitz falhou: {e}")
            print("   Voltando para ADB...")
            self.stop()
            self.active_method = 'adb'
            return True

    def _adbnativeblitz_loop(self):
        """Loop de captura adbnativeblitz"""
        try:
            for frame in self.adbblitz:
                if not self.running:
                    break

                self.last_frame = frame
                self.last_frame_time = time.time()

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
                print(f"⚠️ Erro no loop adbnativeblitz: {e}")

    def _start_scrcpy(self):
        """Inicia captura via scrcpy"""
        if self.running:
            print("⚠️ Scrcpy já está rodando")
            return True

        # Comando scrcpy 2.4 (parâmetros corretos!)
        cmd = [
            'scrcpy',
            '--no-playback',             # Sem janela visual (2.4 usa --no-playback)
            '--record=-',                # Output para stdout (RAW H264!)
            '--video-codec=h264',        # Codec H264
            '--max-fps=30',              # Limitar FPS
            '--video-bit-rate=2M',       # Bitrate do vídeo (2.4 já usa --video-bit-rate)
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
        """Captura frame (automático via adbnativeblitz ou ADB)"""
        if self.active_method == 'adbnativeblitz':
            return self._get_frame_adbnativeblitz(timeout)
        else:
            return self._get_frame_adb()

    def _get_frame_adbnativeblitz(self, timeout=1.0):
        """Pega frame do adbnativeblitz (baixa latência)"""
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
        if self.active_method == 'adbnativeblitz':
            self.running = False

            if self.adbblitz_thread:
                self.adbblitz_thread.join(timeout=2)

            if self.adbblitz:
                try:
                    self.adbblitz.__exit__(None, None, None)
                except:
                    pass

            print("✅ adbnativeblitz parado")

    def get_latency_estimate(self):
        """Retorna estimativa de latência do método ativo"""
        if self.active_method == 'adbnativeblitz':
            return 0.06  # ~60ms
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
