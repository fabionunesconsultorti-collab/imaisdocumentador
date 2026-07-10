import os
import sys
import time
import subprocess
import io
from PIL import Image, ImageGrab

def grab_clipboard_image() -> Image.Image | None:
    """
    Tenta obter uma imagem da área de transferência de forma multiplataforma.
    Retorna um objeto PIL.Image ou None se nenhuma imagem estiver disponível.
    """
    # 1. Tentar método nativo do Pillow (geralmente funciona bem no Windows e macOS)
    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            # Força o carregamento da imagem para evitar problemas de lazy loading
            img.load()
            return img
    except Exception:
        pass

    # 2. Fallbacks específicos para Linux se o Pillow falhar
    if sys.platform.startswith('linux'):
        # Tentar wl-paste (Wayland)
        try:
            process = subprocess.Popen(['wl-paste', '-t', 'image/png'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode == 0 and len(stdout) > 0:
                img = Image.open(io.BytesIO(stdout))
                img.load()
                return img
        except Exception:
            pass

        # Tentar xclip (X11)
        try:
            process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode == 0 and len(stdout) > 0:
                img = Image.open(io.BytesIO(stdout))
                img.load()
                return img
        except Exception:
            pass

    return None

def trigger_native_screenshot() -> bool:
    """
    Aciona a ferramenta nativa de captura de tela do sistema operacional.
    Retorna True se conseguir disparar o comando, False caso contrário.
    """
    if sys.platform.startswith('win32'):
        # Windows Snipping Tool (modo seleção rápida)
        try:
            subprocess.Popen(['cmd.exe', '/c', 'start', 'ms-screenclip:'])
            return True
        except Exception:
            pass
    elif sys.platform.startswith('darwin'):
        # macOS Captura interativa salvando na área de transferência (-c)
        try:
            subprocess.Popen(['/usr/sbin/screencapture', '-c', '-i'])
            return True
        except Exception:
            pass
    elif sys.platform.startswith('linux'):
        # Tenta diversas ferramentas nativas comuns no Linux
        # O objetivo é copiar a seleção de área para a área de transferência
        commands = [
            ['gnome-screenshot', '-a', '-c'],      # GNOME seleciona área para clipboard
            ['gnome-screenshot', '-i'],            # GNOME interativo
            ['xfce4-screenshooter', '-r', '-c'],   # XFCE seleciona área para clipboard
            ['spectacle', '-r'],                   # KDE Spectacle seleção
            ['ksnip', '-r']                        # Ksnip retangular
        ]
        for cmd in commands:
            try:
                subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except FileNotFoundError:
                continue
    return False

def take_screenshot(root) -> Image.Image | None:
    """
    Minimiza a janela principal do Tkinter, captura a tela inteira e restaura a janela.
    """
    try:
        # Minimizar a janela para não aparecer no print
        root.withdraw()
        root.update()
        
        # Esperar um breve momento para a animação do OS de minimizar terminar
        time.sleep(0.5)
        
        # Capturar a tela
        screenshot = ImageGrab.grab()
        if screenshot:
            screenshot.load()
            
    except Exception as e:
        print(f"Erro ao capturar tela: {e}")
        screenshot = None
    finally:
        # Restaurar a janela
        root.deiconify()
        root.update()
        
    return screenshot


def get_resource_path(relative_path):
    """
    Retorna o caminho absoluto para um recurso, funcionando em desenvolvimento
    e quando empacotado pelo PyInstaller.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
