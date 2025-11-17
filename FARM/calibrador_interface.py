"""
CALIBRADOR DE INTERFACE - Captura screenshot para calibração

COMO USAR:
1. Execute este script: python calibrador_interface.py
2. Script captura screenshot do BlueStacks
3. Salva PNG na pasta FARM/screenshots/
4. Abra o PNG no Photoshop
5. Use a ferramenta de seleção para pegar coordenadas (x1, y1, x2, y2)
6. Anote as cores das barras (Mana e XP) usando eyedropper

REGIÕES PARA MARCAR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 LEITURA DE STATUS:
  1. HP Texto (ex: "500/600")         → x1, y1, x2, y2
  2. Barra de Mana (% azul)           → x1, y1, x2, y2 + cor HSV
  3. Barra de XP (branca)             → x1, y1, x2, y2 + cor HSV
  4. Quantidade Poção HP (texto)      → x1, y1, x2, y2
  5. Quantidade Poção Mana (texto)    → x1, y1, x2, y2

🎮 BOTÕES (apenas centro x, y):
  6. Skill (habilidade)               → x, y
  7. Poção HP                         → x, y
  8. Poção Mana                       → x, y
  9. Trocar Guerreiro                 → x, y
  10. Trocar Arqueiro                 → x, y
  11. Trocar Mago                     → x, y
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import cv2
import numpy as np
from adbutils import adb
from pathlib import Path
from datetime import datetime
import os


class CalibradorInterface:
    """Captura screenshot para calibração de interface"""

    def __init__(self):
        print("=" * 70)
        print("🎯 CALIBRADOR DE INTERFACE - Captura Screenshot")
        print("=" * 70)

        # Conectar BlueStacks
        print("\n📱 Conectando ao BlueStacks...")
        devices = adb.device_list()
        if not devices:
            raise Exception("❌ Nenhum dispositivo ADB conectado!")

        self.device = devices[0]
        print(f"   ✅ Conectado: {self.device.serial}")

        # Criar pasta para screenshots
        self.screenshots_dir = Path(__file__).parent / 'screenshots'
        self.screenshots_dir.mkdir(exist_ok=True)
        print(f"   📁 Pasta: {self.screenshots_dir}")

    def capturar_screenshot(self, salvar=True, mostrar_preview=False):
        """
        Captura screenshot do BlueStacks

        Args:
            salvar: Se True, salva PNG
            mostrar_preview: Se True, mostra preview com cv2.imshow

        Returns:
            numpy array (BGR)
        """
        print("\n📸 Capturando screenshot...")

        # Capturar via ADB
        screenshot_bytes = self.device.shell("screencap -p", encoding=None)

        # Converter para numpy array
        nparr = np.frombuffer(screenshot_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise Exception("❌ Falha ao capturar screenshot!")

        print(f"   ✅ Capturado: {img.shape[1]}x{img.shape[0]} pixels")

        # Salvar
        if salvar:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"calibracao_{timestamp}.png"
            filepath = self.screenshots_dir / filename

            cv2.imwrite(str(filepath), img)
            print(f"   💾 Salvo: {filepath}")
            print(f"\n   ℹ️  Abra este arquivo no Photoshop para pegar coordenadas!")

        # Preview
        if mostrar_preview:
            print("\n   👁️  Mostrando preview (pressione qualquer tecla para fechar)...")
            cv2.namedWindow("Screenshot - Calibração", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Screenshot - Calibração", 1200, 675)
            cv2.imshow("Screenshot - Calibração", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return img

    def criar_template_config(self):
        """Cria template de configuração JSON para preencher depois"""
        config_template = {
            "_comentario": "Preencha as coordenadas obtidas no Photoshop",
            "_resolucao": "1600x900",

            "status_bars": {
                "hp_texto": {
                    "x1": 0, "y1": 0, "x2": 0, "y2": 0,
                    "comentario": "Região do texto HP (ex: 500/600)"
                },
                "mana_barra": {
                    "x1": 0, "y1": 0, "x2": 0, "y2": 0,
                    "cor_cheia_hsv": {
                        "h_min": 100, "s_min": 100, "v_min": 100,
                        "h_max": 130, "s_max": 255, "v_max": 255,
                        "comentario": "Ajustar conforme cor azul da mana"
                    },
                    "comentario": "Região da barra de mana (azul)"
                },
                "xp_barra": {
                    "x1": 0, "y1": 0, "x2": 0, "y2": 0,
                    "cor_cheia_hsv": {
                        "h_min": 0, "s_min": 0, "v_min": 200,
                        "h_max": 180, "s_max": 30, "v_max": 255,
                        "comentario": "Branco - ajustar se necessário"
                    },
                    "comentario": "Região da barra de XP (branca)"
                }
            },

            "potions_count": {
                "hp_potion_count": {
                    "x1": 0, "y1": 0, "x2": 0, "y2": 0,
                    "comentario": "Região do número de poções HP"
                },
                "mana_potion_count": {
                    "x1": 0, "y1": 0, "x2": 0, "y2": 0,
                    "comentario": "Região do número de poções Mana"
                }
            },

            "buttons": {
                "skill": {
                    "x": 0, "y": 0,
                    "comentario": "Centro do botão de skill (habilidade)"
                },
                "hp_potion": {
                    "x": 0, "y": 0,
                    "comentario": "Centro do botão de poção HP"
                },
                "mana_potion": {
                    "x": 0, "y": 0,
                    "comentario": "Centro do botão de poção Mana"
                },
                "class_warrior": {
                    "x": 0, "y": 0,
                    "comentario": "Centro do botão trocar para Guerreiro"
                },
                "class_archer": {
                    "x": 0, "y": 0,
                    "comentario": "Centro do botão trocar para Arqueiro"
                },
                "class_mage": {
                    "x": 0, "y": 0,
                    "comentario": "Centro do botão trocar para Mago"
                }
            }
        }

        # Salvar template
        import json
        template_path = Path(__file__).parent / 'interface_config_TEMPLATE.json'
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump(config_template, f, indent=2, ensure_ascii=False)

        print(f"\n   📋 Template criado: {template_path}")
        print(f"   ℹ️  Preencha este arquivo com as coordenadas do Photoshop")

    def gerar_instrucoes_photoshop(self):
        """Gera arquivo de instruções detalhadas"""
        instrucoes = """
╔════════════════════════════════════════════════════════════════════════════╗
║                  📐 GUIA: COMO PEGAR COORDENADAS NO PHOTOSHOP              ║
╚════════════════════════════════════════════════════════════════════════════╝

🎯 PASSO A PASSO:

1. Abra o PNG no Photoshop
2. Vá em Window → Info (para mostrar coordenadas do mouse)
3. Use a ferramenta Rectangular Marquee Tool (M)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 PARA REGIÕES (x1, y1, x2, y2):

1. Selecione a região desejada com Rectangular Marquee
2. No painel Info, você verá:
   - X: coordenada X do canto superior esquerdo (x1)
   - Y: coordenada Y do canto superior esquerdo (y1)
   - W: largura da seleção
   - H: altura da seleção

3. Calcule x2 e y2:
   - x2 = X + W
   - y2 = Y + H

Exemplo:
   Info mostra: X=50, Y=30, W=100, H=20
   Resultado:   x1=50, y1=30, x2=150, y2=50

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎮 PARA BOTÕES (x, y):

1. Use a ferramenta Eyedropper (I)
2. Clique no CENTRO do botão
3. No painel Info, veja X e Y
4. Esses são os valores x e y do botão

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎨 PARA CORES (HSV):

1. Use Eyedropper (I) na barra CHEIA (100%)
2. Veja o painel Color (Window → Color)
3. Mude para modo HSB (pequeno menu no canto do painel)
4. Anote os valores H, S, B

   IMPORTANTE:
   - Photoshop usa H=0-360°, S=0-100%, B=0-100%
   - OpenCV usa H=0-180, S=0-255, V=0-255

   CONVERSÃO:
   - H_opencv = H_photoshop / 2
   - S_opencv = S_photoshop * 2.55
   - V_opencv = B_photoshop * 2.55

Exemplo - Barra Azul (Mana):
   Photoshop: H=200°, S=80%, B=90%
   OpenCV:    H=100, S=204, V=230

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CHECKLIST DE CALIBRAÇÃO:

Status Bars:
  [ ] 1. HP Texto (500/600)      → x1, y1, x2, y2
  [ ] 2. Barra Mana (azul)       → x1, y1, x2, y2 + cor HSV
  [ ] 3. Barra XP (branca)       → x1, y1, x2, y2 + cor HSV

Potion Count:
  [ ] 4. Quantidade Poção HP     → x1, y1, x2, y2
  [ ] 5. Quantidade Poção Mana   → x1, y1, x2, y2

Buttons:
  [ ] 6. Skill                   → x, y
  [ ] 7. Poção HP                → x, y
  [ ] 8. Poção Mana              → x, y
  [ ] 9. Trocar Guerreiro        → x, y
  [ ] 10. Trocar Arqueiro        → x, y
  [ ] 11. Trocar Mago            → x, y

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 DICAS:

- Zoom in (Ctrl + +) para precisão nas bordas
- Use guides (Ctrl + R) para alinhar
- Para barras, selecione APENAS a parte preenchida (não a borda)
- Para botões, clique BEM no centro
- Salve as coordenadas em interface_config.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        instrucoes_path = Path(__file__).parent / 'INSTRUCOES_CALIBRACAO.txt'
        with open(instrucoes_path, 'w', encoding='utf-8') as f:
            f.write(instrucoes)

        print(f"   📖 Instruções salvas: {instrucoes_path}")


def main():
    """Main - Executa captura"""
    try:
        calibrador = CalibradorInterface()

        # Capturar screenshot
        print("\n" + "=" * 70)
        img = calibrador.capturar_screenshot(salvar=True, mostrar_preview=False)

        # Criar template de config
        print("\n" + "=" * 70)
        print("📋 Gerando arquivos auxiliares...")
        calibrador.criar_template_config()
        calibrador.gerar_instrucoes_photoshop()

        # Instruções finais
        print("\n" + "=" * 70)
        print("✅ CAPTURA CONCLUÍDA!")
        print("=" * 70)
        print("\n📝 PRÓXIMOS PASSOS:")
        print("   1. Abra o PNG na pasta screenshots/ no Photoshop")
        print("   2. Leia INSTRUCOES_CALIBRACAO.txt")
        print("   3. Pegue as coordenadas de todas as regiões")
        print("   4. Preencha interface_config_TEMPLATE.json")
        print("   5. Renomeie para interface_config.json")
        print("   6. Me passe o JSON preenchido!")
        print("\n" + "=" * 70)

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
