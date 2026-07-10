#!/usr/bin/env bash
# =============================================================================
# build.sh — Script de build para Linux e macOS
# =============================================================================
# Uso:
#   chmod +x build.sh
#   ./build.sh
#
# Dependências do sistema (Linux):
#   Ubuntu/Debian: sudo apt install python3-tk python3-dev upx-ucl
#   Arch:          sudo pacman -S python-tk upx
#
# Dependências do sistema (macOS):
#   brew install python-tk upx
#   Para gerar .dmg: brew install create-dmg
# =============================================================================

set -euo pipefail

APP_NAME="I+ documentador"
VERSION="1.0.0"
DIST_DIR="dist"
BUILD_DIR="build"

echo "=================================================="
echo "  Build: $APP_NAME v$VERSION"
echo "  Plataforma: $(uname -s)"
echo "=================================================="

# 1. Criar e ativar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "[1/5] Criando ambiente virtual..."
    python3 -m venv venv
fi

echo "[1/5] Ativando ambiente virtual e instalando dependências..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller

# 2. Limpar builds anteriores
echo "[2/5] Limpando builds anteriores..."
rm -rf "$DIST_DIR" "$BUILD_DIR"

# 3. Executar PyInstaller
echo "[3/5] Executando PyInstaller..."
pyinstaller documentador.spec --noconfirm --clean

# 4. Pós-processamento por plataforma
if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "[4/5] macOS: criando arquivo .dmg..."
    
    if command -v create-dmg &> /dev/null; then
        create-dmg \
            --volname "$APP_NAME" \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --icon "$APP_NAME.app" 175 190 \
            --hide-extension "$APP_NAME.app" \
            --app-drop-link 425 190 \
            "$DIST_DIR/${APP_NAME}-${VERSION}-macOS.dmg" \
            "$DIST_DIR/$APP_NAME.app"
        echo "    → DMG gerado: $DIST_DIR/${APP_NAME}-${VERSION}-macOS.dmg"
    else
        echo "    ⚠ create-dmg não encontrado. Instale com: brew install create-dmg"
        echo "    → App bundle disponível em: $DIST_DIR/$APP_NAME.app"
    fi
    
elif [[ "$(uname -s)" == "Linux" ]]; then
    echo "[4/5] Linux: empacotando como .tar.gz..."
    
    BINARY="$DIST_DIR/documentador"
    if [ -f "$BINARY" ]; then
        chmod +x "$BINARY"
        
        # Criar estrutura de pasta de distribuição
        PKG_DIR="$DIST_DIR/${APP_NAME}-${VERSION}-Linux"
        mkdir -p "$PKG_DIR"
        cp "$BINARY" "$PKG_DIR/"
        
        # Criar arquivo .desktop para integração com o sistema
        cat > "$PKG_DIR/documentador.desktop" << EOF
[Desktop Entry]
Name=Documentador de Processos
Comment=Ferramenta de documentação de processos ERP com capturas de tela
Exec=./documentador
Icon=documentador
Terminal=false
Type=Application
Categories=Office;Utility;
EOF
        
        # Compactar
        tar -czf "$DIST_DIR/${APP_NAME}-${VERSION}-Linux.tar.gz" -C "$DIST_DIR" "${APP_NAME}-${VERSION}-Linux"
        echo "    → Pacote gerado: $DIST_DIR/${APP_NAME}-${VERSION}-Linux.tar.gz"
    else
        echo "    ✗ Binário não encontrado em $BINARY"
        exit 1
    fi
fi

echo "[5/5] Build concluído com sucesso!"
echo ""
echo "Arquivos gerados em: $DIST_DIR/"
ls -lh "$DIST_DIR/"
