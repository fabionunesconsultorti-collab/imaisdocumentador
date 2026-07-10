import sys
from app import DocumentadorApp

def main():
    try:
        # Inicializar a aplicação principal
        app = DocumentadorApp()
        app.mainloop()
    except Exception as e:
        print(f"Erro crítico ao iniciar a aplicação: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
