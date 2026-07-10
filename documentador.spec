# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file para Documentador de Processos ERP.
Compatível com Windows, macOS e Linux.

Uso:
    pyinstaller documentador.spec
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Coletar arquivos de dados do customtkinter (temas, ícones, etc.)
ctk_datas = collect_data_files('customtkinter')

# Coletar arquivos de dados do darkdetect
darkdetect_datas = collect_data_files('darkdetect')

# Coletar hidden imports necessários
ctk_hidden = collect_submodules('customtkinter')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Dados do customtkinter (temas e assets obrigatórios)
        *ctk_datas,
        # Dados do darkdetect
        *darkdetect_datas,
        # Ícones e logos do aplicativo
        ('img', 'img'),
    ],
    hiddenimports=[
        # customtkinter e dependências
        *ctk_hidden,
        'customtkinter',
        'darkdetect',
        # Pillow - codecs de imagem comuns
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageTk',
        'PIL.ImageGrab',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.TiffImagePlugin',
        # reportlab
        'reportlab',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.colors',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.platypus',
        'reportlab.platypus.doctemplate',
        'reportlab.platypus.paragraph',
        'reportlab.platypus.flowables',
        'reportlab.graphics',
        'reportlab.pdfgen',
        'reportlab.pdfbase',
        'reportlab.pdfbase.ttfonts',
        'reportlab.pdfbase.pdfmetrics',
        # stdlib
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'zipfile',
        'threading',
        'hashlib',
        'io',
        'uuid',
        'subprocess',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excluir módulos pesados desnecessários
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ─── Configuração por plataforma ─────────────────────────────────────────────

if sys.platform == 'darwin':
    # macOS: bundle como .app
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Documentador',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # Sem terminal no macOS
        icon='assets/icon.icns' if os.path.exists('assets/icon.icns') else None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Documentador',
    )
    app = BUNDLE(
        coll,
        name='Documentador.app',
        icon='assets/icon.icns' if os.path.exists('assets/icon.icns') else None,
        bundle_identifier='com.documentador.erp',
        info_plist={
            'CFBundleDisplayName': 'Documentador de Processos',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.15',
        },
    )

elif sys.platform == 'win32':
    # Windows: executável único .exe
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='Documentador',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # Sem janela de terminal
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
        version='version_info.txt' if os.path.exists('version_info.txt') else None,
    )

else:
    # Linux: executável único
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='documentador',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
