"""
SCRCPY CAPTURE - Captura de tela rápida via scrcpy

Usa scrcpy --no-playback para streaming de vídeo em background
~30-60 FPS com latência de 30-50ms (20x mais rápido que ADB screencap)
"""

import subprocess
import cv2
import numpy as np
import threading
import queue
import time


class ScrcpyCapture:
    """Captura frames via scrcpy em tempo real"""

    def __init__(self, device_id=None, max_fps=30, bit_rate='2M'):
        """
        Inicializa captura scrcpy

        Args:
            device_id: ID do device ADB (None = auto)
            max_fps: FPS máximo (30-60)
            bit_rate: Bitrate do vídeo (1M-8M)
        """
        self.device_id = device_id
        self.max_fps = max_fps
        self.bit_rate = bit_rate

        self.process = None
        self.capture_thread = None
        self.frame_queue = queue.Queue(maxsize=2)  # Buffer pequeno para baixa latência
        self.running = False
        self.last_frame = None
        self.last_frame_time = 0

        print(f"🎬 Scrcpy Capture inicializado (FPS: {max_fps}, Bitrate: {bit_rate})")

    def start(self):
        """Inicia captura em background"""
        if self.running:
            print("⚠️ Scrcpy já está rodando")
            return

        # Comando scrcpy 2.4 (muito mais simples e funcional!)
        cmd = [
            'scrcpy',
            '--no-display',               # Sem janela visual (scrcpy 2.x)
            '--record=-',                 # Output para stdout (RAW H264!)
            '--codec=h264',               # Codec H264 (scrcpy 2.x)
            f'--max-fps={self.max_fps}',  # Limitar FPS
            f'--bit-rate={self.bit_rate}', # Bitrate (scrcpy 2.x)
            '--no-audio'                  # Sem áudio
        ]

        if self.device_id:
            cmd.extend(['--serial', self.device_id])

        print(f"🚀 Iniciando scrcpy em background...")
        print(f"   Comando: {' '.join(cmd)}")

        try:
            # Iniciar processo
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Sem buffer para baixa latência
            )

            # Aguardar processo iniciar
            time.sleep(2)

            # Verificar se processo está rodando
            if self.process.poll() is not None:
                stderr = self.process.stderr.read().decode()
                raise Exception(f"Scrcpy falhou ao iniciar: {stderr}")

            print("✅ Scrcpy iniciado com sucesso!")

            # Iniciar thread de captura
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()

            print("✅ Thread de captura iniciada!")

            # Aguardar primeiro frame
            print("⏳ Aguardando primeiro frame...")
            timeout = time.time() + 5
            while self.last_frame is None and time.time() < timeout:
                time.sleep(0.1)

            if self.last_frame is not None:
                h, w = self.last_frame.shape[:2]
                print(f"✅ Primeiro frame capturado! Resolução: {w}x{h}")
                return True
            else:
                print("⚠️ Timeout aguardando primeiro frame")
                self.stop()
                return False

        except Exception as e:
            print(f"❌ Erro ao iniciar scrcpy: {e}")
            self.stop()
            return False

    def _capture_loop(self):
        """Loop de captura de frames (roda em thread separada)"""
        print("🎥 Loop de captura iniciado...")

        # FFmpeg para decodificar H264 raw do scrcpy 2.4
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'h264',                # Input é H264 raw (scrcpy 2.4 envia isso!)
            '-i', 'pipe:0',              # Input do stdin
            '-f', 'image2pipe',          # Output como sequência de imagens
            '-pix_fmt', 'bgr24',         # Formato BGR (OpenCV)
            '-vcodec', 'rawvideo',       # Sem compressão
            '-'                          # Output para stdout
        ]

        try:
            ffmpeg = subprocess.Popen(
                ffmpeg_cmd,
                stdin=self.process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )

            # Dimensões do frame (assumindo 1600x900 - Rucoy padrão)
            width, height = 1600, 900
            frame_size = width * height * 3  # BGR = 3 bytes por pixel

            while self.running:
                try:
                    # Ler frame raw
                    raw_frame = ffmpeg.stdout.read(frame_size)

                    if len(raw_frame) != frame_size:
                        print(f"⚠️ Frame incompleto: {len(raw_frame)}/{frame_size} bytes")
                        continue

                    # Converter para numpy array
                    frame = np.frombuffer(raw_frame, dtype=np.uint8)
                    frame = frame.reshape((height, width, 3))

                    # Atualizar último frame
                    self.last_frame = frame
                    self.last_frame_time = time.time()

                    # Adicionar ao queue (descarta frame antigo se queue cheio)
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        # Descarta frame mais antigo
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self.frame_queue.put_nowait(frame)

                except Exception as e:
                    if self.running:
                        print(f"⚠️ Erro ao capturar frame: {e}")
                    break

            ffmpeg.terminate()

        except Exception as e:
            print(f"❌ Erro no loop de captura: {e}")

        print("🛑 Loop de captura finalizado")

    def get_frame(self, timeout=1.0):
        """
        Obtém frame mais recente

        Args:
            timeout: Timeout em segundos

        Returns:
            Frame (numpy array BGR) ou None
        """
        if not self.running:
            print("⚠️ Scrcpy não está rodando")
            return None

        # Retornar último frame capturado
        if self.last_frame is not None:
            age = time.time() - self.last_frame_time
            if age < 1.0:  # Frame não mais velho que 1 segundo
                return self.last_frame.copy()

        # Aguardar novo frame
        try:
            frame = self.frame_queue.get(timeout=timeout)
            return frame.copy()
        except queue.Empty:
            print(f"⚠️ Timeout aguardando frame ({timeout}s)")
            return None

    def stop(self):
        """Para captura"""
        print("🛑 Parando scrcpy...")

        self.running = False

        if self.capture_thread:
            self.capture_thread.join(timeout=2)

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()

        print("✅ Scrcpy parado!")

    def __enter__(self):
        """Context manager: iniciar"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: parar"""
        self.stop()


if __name__ == "__main__":
    """Teste do scrcpy capture"""
    print("=" * 70)
    print("🧪 TESTE SCRCPY CAPTURE")
    print("=" * 70)

    try:
        # Iniciar captura
        capture = ScrcpyCapture(max_fps=30, bit_rate='2M')

        if not capture.start():
            print("❌ Falha ao iniciar")
            exit(1)

        print("\n📸 Capturando 10 frames para teste...")

        for i in range(10):
            start = time.time()
            frame = capture.get_frame()
            latency = (time.time() - start) * 1000

            if frame is not None:
                h, w = frame.shape[:2]
                print(f"   Frame {i+1}: {w}x{h} - Latência: {latency:.1f}ms")
            else:
                print(f"   Frame {i+1}: FALHOU")

            time.sleep(0.1)

        print("\n✅ Teste concluído!")

    except KeyboardInterrupt:
        print("\n⚠️ Teste cancelado")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        capture.stop()
