import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

# Importações internas
from document import Document, Step
from editor_canvas import EditorCanvas
from exporter import export_to_html, export_to_svg, export_to_pdf, export_to_wiki_repository
import utils

# Configuração global do CustomTkinter
ctk.set_appearance_mode("System")  # Segue o tema do SO (Dark/Light)
ctk.set_default_color_theme("blue")  # Tema de cores azul padrão (muito elegante)


class DocumentadorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configurações da Janela
        self.title("I+ documentador")
        self.geometry("1200x800")
        self.minimum_size = (1000, 700)
        self.minsize(self.minimum_size[0], self.minimum_size[1])
        
        # Configurar ícone da janela
        try:
            icon_path = utils.get_resource_path(os.path.join("img", "icone.png"))
            if os.path.exists(icon_path):
                img = tk.PhotoImage(file=icon_path)
                self.iconphoto(False, img)
        except Exception as e:
            print(f"Erro ao carregar ícone: {e}")
        
        # Objeto de dados
        self.document = Document()
        self.current_step_index = None
        
        # Referências de imagens para thumbnails da lista lateral para evitar coleta de GC
        self.thumb_images = []
        
        # Configurar Grid principal (linha 0: top_bar, linha 1: doc_metadata_bar, linha 2: sidebar/workspace)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # 1. Barra de Menu Superior
        self.create_top_bar()
        
        # 1b. Barra de Metadados da Documentação (em linha)
        self.create_doc_metadata_bar()
        
        # 2. Painel Lateral Esquerdo (Lista de Passos e Botões de Captura)
        self.create_left_sidebar()
        
        # 3. Área Central (Editor Canvas e Metadados do Passo)
        self.create_center_workspace()
        
        # Evento de fechar janela
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Inicializar variáveis para monitoramento automático
        self.monitoring_clipboard = True
        self.last_clipboard_hash = None
        self.polling_lock = threading.Lock()
        
        # Binds globais de teclado para colar imagem
        self.bind("<Control-v>", self.paste_image)
        self.bind("<Command-v>", self.paste_image)  # macOS
        
        # Atualizar a UI para estado inicial (vazio)
        self.update_ui_state()
        
        # Iniciar monitoramento automático de prints por padrão
        self.toggle_clipboard_monitoring()

    def create_top_bar(self):
        # Frame do topo
        self.top_bar = ctk.CTkFrame(self, height=45, corner_radius=0)
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=(0, 1))
        
        # Botões de Arquivo
        self.btn_new = ctk.CTkButton(self.top_bar, text="Novo Documento 📄", width=120, command=self.new_document, fg_color="#34495e", hover_color="#2c3e50")
        self.btn_new.pack(side="left", padx=10, pady=8)
        
        self.btn_open = ctk.CTkButton(self.top_bar, text="Abrir Arquivo 📂", width=120, command=self.open_document, fg_color="#34495e", hover_color="#2c3e50")
        self.btn_open.pack(side="left", padx=5, pady=8)
        
        self.btn_save = ctk.CTkButton(self.top_bar, text="Salvar Documento 💾", width=130, command=self.save_document, fg_color="#2ecc71", hover_color="#27ae60")
        self.btn_save.pack(side="left", padx=5, pady=8)
        
        # Botões de Exportação
        self.btn_link_wiki = ctk.CTkButton(self.top_bar, text="Vincular à Wiki 📚", width=130, command=self.link_document_to_wiki, fg_color="#9b59b6", hover_color="#8e44ad")
        self.btn_link_wiki.pack(side="left", padx=15, pady=8)
        
        self.btn_export_pdf = ctk.CTkButton(self.top_bar, text="Exportar PDF 📕", width=120, command=self.export_pdf, fg_color="#e67e22", hover_color="#d35400")
        self.btn_export_pdf.pack(side="left", padx=5, pady=8)
        
        # Indicador de Arquivo Atual
        self.lbl_filename = ctk.CTkLabel(self.top_bar, text="Sem título.docp", font=("Arial", 12, "italic"))
        self.lbl_filename.pack(side="right", padx=15)
        
        # Switch de tema escuro/claro
        self.theme_switch = ctk.CTkSwitch(self.top_bar, text="Modo Escuro", command=self.toggle_theme)
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        self.theme_switch.pack(side="right", padx=10)

        # Botão de verificação de atualizações (consulta releases no GitHub)
        self.btn_check_update = ctk.CTkButton(
            self.top_bar, text="Verificar Atualizações 🔄", width=170,
            command=self.check_for_updates, fg_color="#34495e", hover_color="#2c3e50"
        )
        self.btn_check_update.pack(side="right", padx=10)

    def create_doc_metadata_bar(self):
        # Barra em linha para Metadados da Documentação (row 1, abaixo dos comandos principais)
        self.metadata_bar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.metadata_bar.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=(0, 2))
        
        # Título
        lbl_doc_title = ctk.CTkLabel(self.metadata_bar, text="Título:", font=("Arial", 11, "bold"))
        lbl_doc_title.pack(side="left", padx=(10, 2), pady=6)
        self.doc_title_entry = ctk.CTkEntry(self.metadata_bar, height=26)
        self.doc_title_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        self.doc_title_entry.insert(0, self.document.title)
        self.doc_title_entry.bind("<KeyRelease>", self.on_doc_title_changed)
        
        # Subtítulo
        lbl_doc_subtitle = ctk.CTkLabel(self.metadata_bar, text="Subtítulo:", font=("Arial", 11, "bold"))
        lbl_doc_subtitle.pack(side="left", padx=(4, 2), pady=6)
        self.doc_subtitle_entry = ctk.CTkEntry(self.metadata_bar, height=26)
        self.doc_subtitle_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        self.doc_subtitle_entry.insert(0, self.document.subtitle)
        self.doc_subtitle_entry.bind("<KeyRelease>", self.on_doc_subtitle_changed)

        # Categoria
        lbl_doc_category = ctk.CTkLabel(self.metadata_bar, text="Categoria:", font=("Arial", 11, "bold"))
        lbl_doc_category.pack(side="left", padx=(4, 2), pady=6)
        self.doc_category_entry = ctk.CTkEntry(self.metadata_bar, width=130, height=26)
        self.doc_category_entry.pack(side="left", padx=(0, 8), pady=6)
        self.doc_category_entry.insert(0, getattr(self.document, "category", ""))
        self.doc_category_entry.bind("<KeyRelease>", self.on_doc_category_changed)

        # Tags
        lbl_doc_tags = ctk.CTkLabel(self.metadata_bar, text="Tags:", font=("Arial", 11, "bold"))
        lbl_doc_tags.pack(side="left", padx=(4, 2), pady=6)
        self.doc_tags_entry = ctk.CTkEntry(self.metadata_bar, width=130, height=26)
        self.doc_tags_entry.pack(side="left", padx=(0, 8), pady=6)
        self.doc_tags_entry.insert(0, getattr(self.document, "tags", ""))
        self.doc_tags_entry.bind("<KeyRelease>", self.on_doc_tags_changed)

        # Autor
        lbl_doc_author = ctk.CTkLabel(self.metadata_bar, text="Autor:", font=("Arial", 11, "bold"))
        lbl_doc_author.pack(anchor="w", side="left", padx=(4, 2), pady=6)
        self.doc_author_entry = ctk.CTkEntry(self.metadata_bar, width=120, height=26)
        self.doc_author_entry.pack(side="left", padx=(0, 10), pady=6)
        self.doc_author_entry.insert(0, getattr(self.document, "author", ""))
        self.doc_author_entry.bind("<KeyRelease>", self.on_doc_author_changed)

    def create_left_sidebar(self):
        # Frame lateral
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(2, weight=1)
        
        # Logo no painel lateral
        try:
            logo_path = utils.get_resource_path(os.path.join("img", "logo.png"))
            if os.path.exists(logo_path):
                pil_logo = Image.open(logo_path)
                # Redimensionar mantendo proporção (largura desejada = 240)
                width_target = 240
                w_percent = (width_target / float(pil_logo.size[0]))
                h_size = int((float(pil_logo.size[1]) * float(w_percent)))
                self.logo_ctk_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(width_target, h_size))
                self.logo_label = ctk.CTkLabel(self.sidebar, image=self.logo_ctk_img, text="")
                self.logo_label.grid(row=0, column=0, padx=15, pady=(15, 5))
        except Exception as e:
            print(f"Erro ao carregar logo: {e}")
        
        # Título dos Passos
        lbl_sidebar = ctk.CTkLabel(self.sidebar, text="Passos do Processo", font=("Arial", 16, "bold"))
        lbl_sidebar.grid(row=1, column=0, padx=15, pady=(10, 5), sticky="w")
        
        # Container rolável para a lista de passos (ocupa a maior área vertical da sidebar)
        self.scroll_steps = ctk.CTkScrollableFrame(self.sidebar, width=250, label_text="")
        self.scroll_steps.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        
        # Frame inferior da sidebar com botões de Ações de Passos
        actions_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        actions_frame.grid(row=3, column=0, padx=10, pady=15, sticky="ew")
        
        # Botões de captura rápida
        btn_paste = ctk.CTkButton(actions_frame, text="Colar Print (Clipboard) 📋", command=self.paste_image, fg_color="#1a73e8", hover_color="#1557b0")
        btn_paste.pack(fill="x", pady=4)
        
        btn_shoot = ctk.CTkButton(actions_frame, text="Tirar Print da Tela 📸", command=self.capture_screen, fg_color="#1a73e8", hover_color="#1557b0")
        btn_shoot.pack(fill="x", pady=4)
        
        btn_import = ctk.CTkButton(actions_frame, text="Importar Imagem... 🖼️", command=self.import_image, fg_color="#34495e", hover_color="#2c3e50")
        btn_import.pack(fill="x", pady=4)
        
        # Switch para monitorar área de transferência automaticamente
        self.monitor_switch = ctk.CTkSwitch(actions_frame, text="Autocolar Novos Prints 🔄", command=self.toggle_clipboard_monitoring)
        self.monitor_switch.select()
        self.monitor_switch.pack(fill="x", pady=(10, 4))
        
        # Controles de Ordenação e Exclusão
        reorder_frame = ctk.CTkFrame(actions_frame, fg_color="transparent")
        reorder_frame.pack(fill="x", pady=4)
        
        self.btn_up = ctk.CTkButton(reorder_frame, text="Mover ↑", width=70, command=self.move_step_up, fg_color="#95a5a6", hover_color="#7f8c8d", text_color="#1a1a1a")
        self.btn_up.pack(side="left", padx=(0, 5))
        
        self.btn_down = ctk.CTkButton(reorder_frame, text="Mover ↓", width=70, command=self.move_step_down, fg_color="#95a5a6", hover_color="#7f8c8d", text_color="#1a1a1a")
        self.btn_down.pack(side="left", padx=5)
        
        self.btn_remove_step = ctk.CTkButton(reorder_frame, text="Remover Passo 🗑️", width=100, command=self.remove_step, fg_color="#e74c3c", hover_color="#c0392b")
        self.btn_remove_step.pack(side="right", padx=(5, 0))

    def create_center_workspace(self):
        # Frame central do editor
        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.grid(row=2, column=1, sticky="nsew", padx=10, pady=10)
        self.workspace.grid_rowconfigure(1, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)
        
        # 1. Barra de Ferramentas de Desenho
        self.create_drawing_toolbar()
        
        # 2. Canvas de Edição
        self.editor_canvas = EditorCanvas(self.workspace, on_changed_callback=self.on_canvas_changed)
        self.editor_canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Placeholder para quando não houver passos
        self.placeholder_label = ctk.CTkLabel(
            self.workspace, 
            text="Adicione ou cole uma captura de tela para começar a documentar.",
            font=("Arial", 16, "italic"),
            fg_color="#2b2b2b",
            text_color="#888888",
            corner_radius=8
        )
        self.placeholder_label.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # 3. Painel de Descrições (Parte Inferior)
        self.create_details_panel()

    def create_drawing_toolbar(self):
        self.toolbar = ctk.CTkFrame(self.workspace, height=45)
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        # Modos de Ferramenta
        self.tool_var = ctk.StringVar(value="select")
        
        self.tool_select = ctk.CTkRadioButton(self.toolbar, text="Selecionar 🖱️", variable=self.tool_var, value="select", command=self.change_tool)
        self.tool_select.pack(side="left", padx=15, pady=10)
        
        self.tool_arrow = ctk.CTkRadioButton(self.toolbar, text="Seta 🏹", variable=self.tool_var, value="arrow", command=self.change_tool)
        self.tool_arrow.pack(side="left", padx=10, pady=10)
        
        # Checkbox para numeração sequencial de setas
        self.num_arrows_var = ctk.BooleanVar(value=True)
        self.cb_num_arrows = ctk.CTkCheckBox(
            self.toolbar, 
            text="Numerar Setas 🔢", 
            variable=self.num_arrows_var,
            command=self.toggle_num_arrows
        )
        self.cb_num_arrows.pack(side="left", padx=15, pady=10)
        
        # Divisor vertical lógico
        self.lbl_div1 = ctk.CTkLabel(self.toolbar, text="|", text_color="#888888")
        self.lbl_div1.pack(side="left", padx=10)
        
        # Excluir Elemento Selecionado
        self.btn_delete_element = ctk.CTkButton(
            self.toolbar, 
            text="Excluir Elemento 🗑️", 
            width=140, 
            fg_color="#e74c3c", 
            hover_color="#c0392b",
            command=self.delete_selected_element
        )
        self.btn_delete_element.pack(side="left", padx=10, pady=8)
        
        # Divisor vertical lógico
        self.lbl_div2 = ctk.CTkLabel(self.toolbar, text="|", text_color="#888888")
        self.lbl_div2.pack(side="left", padx=10)
        
        # Cor de Desenho
        self.lbl_color = ctk.CTkLabel(self.toolbar, text="Cor:")
        self.lbl_color.pack(side="left", padx=5)
        
        self.color_var = ctk.StringVar(value="Vermelho")
        self.color_menu = ctk.CTkOptionMenu(
            self.toolbar, 
            values=["Vermelho", "Azul", "Verde", "Amarelo", "Preto"], 
            variable=self.color_var,
            command=self.change_color,
            width=100
        )
        self.color_menu.pack(side="left", padx=5)

    def create_details_panel(self):
        self.details_panel = ctk.CTkFrame(self.workspace, height=210)
        self.details_panel.grid(row=2, column=0, sticky="ew", padx=5, pady=(5, 0))
        self.details_panel.grid_rowconfigure(3, weight=1)
        self.details_panel.grid_columnconfigure(0, weight=1)
        
        # Título do Passo
        title_frame = ctk.CTkFrame(self.details_panel, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 2))
        
        lbl_title = ctk.CTkLabel(title_frame, text="Título do Passo:", font=("Arial", 12, "bold"))
        lbl_title.pack(side="left", padx=(0, 10))
        
        self.title_entry = ctk.CTkEntry(title_frame)
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.title_entry.bind("<KeyRelease>", self.sync_step_data)
        
        # Descrição do Passo (largura total)
        lbl_desc = ctk.CTkLabel(self.details_panel, text="Explicação / Descrição do Passo:", font=("Arial", 12, "bold"))
        lbl_desc.grid(row=1, column=0, sticky="w", padx=15, pady=(2, 0))
        
        # Barra de Ferramentas de Formatação (Negrito, Grifar e Adesivos)
        self.formatting_toolbar = ctk.CTkFrame(self.details_panel, fg_color="transparent")
        self.formatting_toolbar.grid(row=2, column=0, sticky="ew", padx=15, pady=(2, 2))
        
        btn_bold = ctk.CTkButton(self.formatting_toolbar, text="B", width=30, height=24, font=("Arial", 11, "bold"), fg_color="#34495e", hover_color="#2c3e50", command=lambda: self.insert_formatting_tag("**", "**"))
        btn_bold.pack(side="left", padx=(0, 5))
        
        btn_highlight = ctk.CTkButton(self.formatting_toolbar, text="Grifar 🖍️", width=70, height=24, font=("Arial", 11), fg_color="#34495e", hover_color="#2c3e50", command=lambda: self.insert_formatting_tag("==", "=="))
        btn_highlight.pack(side="left", padx=5)
        
        lbl_sep = ctk.CTkLabel(self.formatting_toolbar, text="|", text_color="#888888")
        lbl_sep.pack(side="left", padx=10)
        
        btn_attention = ctk.CTkButton(self.formatting_toolbar, text="⚠️ Atenção", width=95, height=24, fg_color="#e74c3c", hover_color="#c0392b", font=("Arial", 11, "bold"), command=lambda: self.insert_formatting_tag("[atenção]", "[/atenção]"))
        btn_attention.pack(side="left", padx=5)
        
        btn_observation = ctk.CTkButton(self.formatting_toolbar, text="ℹ️ Observação", width=115, height=24, fg_color="#3498db", hover_color="#2980b9", font=("Arial", 11, "bold"), command=lambda: self.insert_formatting_tag("[observação]", "[/observação]"))
        btn_observation.pack(side="left", padx=5)
        
        btn_concept = ctk.CTkButton(self.formatting_toolbar, text="💡 Conceito", width=95, height=24, fg_color="#2ecc71", hover_color="#27ae60", font=("Arial", 11, "bold"), command=lambda: self.insert_formatting_tag("[conceito]", "[/conceito]"))
        btn_concept.pack(side="left", padx=5)
        
        self.desc_textbox = ctk.CTkTextbox(self.details_panel, height=75, undo=True)
        self.desc_textbox.grid(row=3, column=0, sticky="nsew", padx=15, pady=(2, 10))
        self.desc_textbox.bind("<KeyRelease>", self.sync_step_data)
        
        self.selected_attachment_data = None

    def insert_formatting_tag(self, start_tag, end_tag):
        """
        Insere tags de formatação ao redor da seleção atual ou no cursor no desc_textbox.
        """
        if self.current_step_index is None:
            return
            
        try:
            # Tentar obter os índices de seleção
            start_idx = self.desc_textbox._textbox.index("sel.first")
            end_idx = self.desc_textbox._textbox.index("sel.last")
            
            selected_text = self.desc_textbox._textbox.get(start_idx, end_idx)
            new_text = f"{start_tag}{selected_text}{end_tag}"
            
            self.desc_textbox._textbox.delete(start_idx, end_idx)
            self.desc_textbox._textbox.insert(start_idx, new_text)
            
            self.desc_textbox._textbox.focus_set()
        except tk.TclError:
            # Se não houver seleção, insere no cursor
            cursor_idx = self.desc_textbox._textbox.index("insert")
            self.desc_textbox._textbox.insert(cursor_idx, f"{start_tag}{end_tag}")
            
            # Posicionar cursor entre as tags
            offset = len(start_tag)
            row, col = map(int, cursor_idx.split('.'))
            new_cursor_idx = f"{row}.{col + offset}"
            self.desc_textbox._textbox.mark_set("insert", new_cursor_idx)
            self.desc_textbox._textbox.focus_set()
            
        self.sync_step_data()

    def apply_formatting_tags(self, event=None):
        """
        Analisa o conteúdo do desc_textbox e aplica tags de formatação e adesivos visuais.
        """
        if self.current_step_index is None:
            return
            
        import re
        textbox = self.desc_textbox._textbox
        
        # 1. Configurar tags de estilo
        if "bold" not in textbox.tag_names():
            textbox.tag_configure("bold", font=("Arial", 12, "bold"))
        if "highlight" not in textbox.tag_names():
            textbox.tag_configure("highlight", background="#fef08a", foreground="#0f172a")
            
        if "flag_attention" not in textbox.tag_names():
            textbox.tag_configure(
                "flag_attention", 
                background="#fdf2f2", 
                foreground="#991b1b",
                spacing1=6, 
                spacing3=6, 
                lmargin1=25, 
                lmargin2=25, 
                rmargin=25
            )
        if "flag_observation" not in textbox.tag_names():
            textbox.tag_configure(
                "flag_observation", 
                background="#f0f9ff", 
                foreground="#075985",
                spacing1=6, 
                spacing3=6, 
                lmargin1=25, 
                lmargin2=25, 
                rmargin=25
            )
        if "flag_concept" not in textbox.tag_names():
            textbox.tag_configure(
                "flag_concept", 
                background="#f0fdf4", 
                foreground="#166534",
                spacing1=6, 
                spacing3=6, 
                lmargin1=25, 
                lmargin2=25, 
                rmargin=25
            )
            
        # 2. Remover tags antigas
        for tag in ["bold", "highlight", "flag_attention", "flag_observation", "flag_concept"]:
            textbox.tag_remove(tag, "1.0", "end")
            
        content = textbox.get("1.0", "end-1c")
        
        def get_tkinter_index(text, char_idx):
            lines = text[:char_idx].split('\n')
            return f"{len(lines)}.{len(lines[-1])}"
            
        # 3. Aplicar Negritos
        for match in re.finditer(r"\*\*(.*?)\*\*", content, re.DOTALL):
            start_tk = get_tkinter_index(content, match.start())
            end_tk = get_tkinter_index(content, match.end())
            textbox.tag_add("bold", start_tk, end_tk)
            
        # 4. Aplicar Destaques (Grifado)
        for match in re.finditer(r"==(.*?)==", content, re.DOTALL):
            start_tk = get_tkinter_index(content, match.start())
            end_tk = get_tkinter_index(content, match.end())
            textbox.tag_add("highlight", start_tk, end_tk)
            
        # 5. Aplicar Adesivo Atenção
        for pattern in [r"\[atenção\](.*?)\[/atenção\]", r"\[atencao\](.*?)\[/atencao\]"]:
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                start_tk = get_tkinter_index(content, match.start())
                end_tk = get_tkinter_index(content, match.end())
                textbox.tag_add("flag_attention", start_tk, end_tk)
                
        # 6. Aplicar Adesivo Observação
        for pattern in [r"\[observação\](.*?)\[/observação\]", r"\[observacao\](.*?)\[/observacao\]"]:
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                start_tk = get_tkinter_index(content, match.start())
                end_tk = get_tkinter_index(content, match.end())
                textbox.tag_add("flag_observation", start_tk, end_tk)
                
        # 7. Aplicar Adesivo Conceito
        for match in re.finditer(r"\[conceito\](.*?)\[/conceito\]", content, re.DOTALL | re.IGNORECASE):
            start_tk = get_tkinter_index(content, match.start())
            end_tk = get_tkinter_index(content, match.end())
            textbox.tag_add("flag_concept", start_tk, end_tk)

    # --- Controle de Fluxo de Passos e UI ---

    def sync_step_data(self, event=None):
        """
        Sincroniza os dados inseridos nas caixas de texto com o objeto Step atual.
        """
        if self.current_step_index is not None and 0 <= self.current_step_index < len(self.document.steps):
            step = self.document.steps[self.current_step_index]
            
            # Sincronizar título
            step.title = self.title_entry.get().strip()
            
            # Sincronizar descrição
            step.description = self.desc_textbox.get("1.0", "end-1c").strip()
            
            # Aplicar realce de sintaxe em tempo real
            self.apply_formatting_tags()
            
            # Atualizar legenda do botão na barra lateral sem redesenhar tudo
            self.refresh_step_button_text(self.current_step_index, step.title)
            
            self.mark_as_changed()

    def refresh_step_button_text(self, idx, title):
        # Localizar botão específico na scroll list
        for child in self.scroll_steps.winfo_children():
            if hasattr(child, "step_index") and child.step_index == idx:
                display_title = title if title else f"Passo {idx + 1}"
                child.configure(text=f"  {idx + 1}. {display_title}")
                break

    def change_tool(self):
        self.editor_canvas.set_tool(self.tool_var.get())

    def change_color(self, name):
        colors_map = {
            "Vermelho": "#FF0000",
            "Azul": "#1a73e8",
            "Verde": "#2ecc71",
            "Amarelo": "#f1c40f",
            "Preto": "#1a1a1a"
        }
        hex_color = colors_map.get(name, "#FF0000")
        self.editor_canvas.set_color(hex_color)

    def delete_selected_element(self):
        if self.editor_canvas.delete_selected():
            self.mark_as_changed()

    def toggle_theme(self):
        if self.theme_switch.get():
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def check_for_updates(self):
        self.btn_check_update.configure(state="disabled", text="Verificando... ⏳")

        def worker():
            try:
                result = utils.check_for_updates()
            except Exception as e:
                result = {"error": str(e)}
            self.after(0, lambda: self._on_update_check_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_done(self, result):
        self.btn_check_update.configure(state="normal", text="Verificar Atualizações 🔄")

        if "error" in result:
            messagebox.showerror(
                "Erro ao verificar atualização",
                f"Não foi possível verificar atualizações no GitHub:\n{result['error']}"
            )
            return

        if result["has_update"]:
            abrir = messagebox.askyesno(
                "Atualização disponível",
                f"Uma nova versão está disponível: v{result['latest_version']} "
                f"(versão atual: v{result['current_version']}).\n\n"
                "Deseja abrir a página de download no GitHub?"
            )
            if abrir:
                webbrowser.open(result["url"])
        else:
            messagebox.showinfo(
                "Sem atualizações",
                f"Você já está usando a versão mais recente (v{result['current_version']})."
            )

    def on_doc_title_changed(self, event=None):
        self.document.title = self.doc_title_entry.get().strip()
        self.mark_as_changed()

    def on_doc_subtitle_changed(self, event=None):
        self.document.subtitle = self.doc_subtitle_entry.get().strip()
        self.mark_as_changed()

    def on_doc_category_changed(self, event=None):
        self.document.category = self.doc_category_entry.get().strip()
        self.mark_as_changed()

    def on_doc_tags_changed(self, event=None):
        self.document.tags = self.doc_tags_entry.get().strip()
        self.mark_as_changed()

    def on_doc_author_changed(self, event=None):
        self.document.author = self.doc_author_entry.get().strip()
        self.mark_as_changed()

    def toggle_num_arrows(self):
        enabled = self.num_arrows_var.get()
        self.document.num_arrows = enabled
        self.editor_canvas.set_num_arrows(enabled)

    def on_canvas_changed(self, annotation_type=None):
        self.mark_as_changed()
        if annotation_type == "arrow" and self.num_arrows_var.get():
            if self.current_step_index is not None and 0 <= self.current_step_index < len(self.document.steps):
                step = self.document.steps[self.current_step_index]
                arrow_count = sum(1 for a in step.annotations if a.get("type") == "arrow")
                
                # Append "* Passo N: " to description textbox
                current_desc = self.desc_textbox.get("1.0", "end-1c").strip()
                ref_str = f"* Passo {arrow_count}: "
                
                if ref_str not in current_desc:
                    if current_desc:
                        new_desc = current_desc + f"\n{ref_str}"
                    else:
                        new_desc = ref_str
                    
                    self.desc_textbox.delete("1.0", "end")
                    self.desc_textbox.insert("1.0", new_desc)
                    self.sync_step_data()

    def mark_as_changed(self):
        self.document.changed = True
        self.update_title_bar()

    def update_title_bar(self):
        filename = os.path.basename(self.document.filepath) if self.document.filepath else "Sem título.docp"
        marker = " * (Modificado)" if self.document.changed else ""
        self.lbl_filename.configure(text=f"{filename}{marker}")

    def update_ui_state(self):
        """
        Atualiza o estado dos widgets de acordo com a seleção e quantidade de passos.
        """
        num_steps = len(self.document.steps)
        
        # Desabilitar/habilitar botões de ordenação baseados na seleção e tamanho da lista
        if num_steps > 0 and self.current_step_index is not None:
            self.btn_up.configure(state="normal")
            self.btn_down.configure(state="normal")
            self.btn_remove_step.configure(state="normal")
            
            # Habilitar painéis de edição
            self.title_entry.configure(state="normal")
            self.desc_textbox.configure(state="normal")
            if hasattr(self, "btn_add_attachment") and self.btn_add_attachment:
                self.btn_add_attachment.configure(state="normal")
            if hasattr(self, "btn_remove_attachment") and self.btn_remove_attachment:
                self.btn_remove_attachment.configure(state="normal")
            self.editor_canvas.grid()
            self.placeholder_label.grid_remove()
            self.btn_delete_element.configure(state="normal")
        else:
            self.btn_up.configure(state="disabled")
            self.btn_down.configure(state="disabled")
            self.btn_remove_step.configure(state="disabled")
            
            # Limpar e desabilitar painéis de edição
            self.title_entry.delete(0, "end")
            self.title_entry.configure(state="disabled")
            self.desc_textbox.delete("1.0", "end")
            self.desc_textbox.configure(state="disabled")
            if hasattr(self, "btn_add_attachment") and self.btn_add_attachment:
                self.btn_add_attachment.configure(state="disabled")
            if hasattr(self, "btn_remove_attachment") and self.btn_remove_attachment:
                self.btn_remove_attachment.configure(state="disabled")
            self.editor_canvas.grid_remove()
            self.placeholder_label.grid()
            self.btn_delete_element.configure(state="disabled")
            
        self.update_title_bar()

    def select_step(self, index):
        """
        Seleciona o passo especificado, exibindo seus detalhes e anotações.
        """
        if index is None or index < 0 or index >= len(self.document.steps):
            self.current_step_index = None
            self.editor_canvas.set_step(None)
            self.update_attachments_list()
            self.update_ui_state()
            return
            
        self.current_step_index = index
        step = self.document.steps[index]
        
        # Temporariamente desligar os binds para não marcar o documento como mudado ao carregar dados na interface
        self.title_entry.configure(state="normal")
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, step.title)
        
        self.desc_textbox.configure(state="normal")
        self.desc_textbox.delete("1.0", "end")
        self.desc_textbox.insert("1.0", step.description)
        self.apply_formatting_tags()
        
        self.editor_canvas.set_step(step)
        
        # Mudar ferramenta selecionada para sincronizar com canvas
        self.tool_var.set("select")
        self.editor_canvas.set_tool("select")
        
        self.highlight_sidebar_button(index)
        self.update_attachments_list()
        self.update_ui_state()

    def highlight_sidebar_button(self, selected_idx):
        for child in self.scroll_steps.winfo_children():
            if hasattr(child, "step_index"):
                if child.step_index == selected_idx:
                    child.configure(fg_color="#1a73e8", hover_color="#1557b0", text_color="#ffffff")
                else:
                    # Restaurar cores padrão (None não é aceito pelo CustomTkinter)
                    child.configure(fg_color="transparent", hover_color=("gray75", "gray25"), text_color=("gray10", "#DCE4EE"))

    def rebuild_sidebar_list(self):
        """
        Limpa e reconstrói a lista vertical de passos na barra lateral.
        """
        # Destruir botões existentes
        for child in self.scroll_steps.winfo_children():
            child.destroy()
            
        self.thumb_images.clear()
        
        for idx, step in enumerate(self.document.steps):
            # Criar thumbnail da imagem original do passo
            thumb_img = step.image.copy()
            thumb_img.thumbnail((70, 45), Image.Resampling.LANCZOS)
            
            # Guardar em CTkImage (fornecendo mesmo objeto em light e dark)
            ctk_thumb = ctk.CTkImage(light_image=thumb_img, dark_image=thumb_img, size=(70, 45))
            self.thumb_images.append(ctk_thumb)  # Manter referência para evitar Garbage Collection
            
            display_title = step.title if step.title else f"Passo {idx + 1}"
            
            btn = ctk.CTkButton(
                self.scroll_steps,
                text=f"  {idx + 1}. {display_title}",
                image=ctk_thumb,
                compound="left",
                anchor="w",
                height=55,
                fg_color="transparent",
                command=lambda i=idx: self.select_step(i)
            )
            btn.step_index = idx  # Injetar atributo no widget
            btn.pack(fill="x", pady=2)
            
        # Re-selecionar o passo atual se válido, ou o último passo, ou nada
        if len(self.document.steps) > 0:
            if self.current_step_index is None or self.current_step_index >= len(self.document.steps):
                self.select_step(len(self.document.steps) - 1)
            else:
                self.select_step(self.current_step_index)
        else:
            self.select_step(None)

    # --- Ações de Manipulação de Passos ---

    def add_new_step_with_image(self, img: Image.Image):
        """
        Adiciona um novo passo com a imagem fornecida, abrindo a caixa de descrição.
        """
        step = self.document.add_step(img)
        self.rebuild_sidebar_list()
        # Selecionar o recém adicionado
        self.select_step(len(self.document.steps) - 1)
        
        # Colocar o cursor em foco no título do passo para digitação imediata
        self.title_entry.focus_set()

    def paste_image(self, event=None):
        # Se o foco estiver em um campo de texto ativo, deixa o atalho de teclado funcionar nativamente
        focused = self.focus_get()
        if isinstance(focused, (ctk.CTkEntry, ctk.CTkTextbox, tk.Entry, tk.Text)):
            try:
                if str(focused.cget("state")) != "disabled":
                    return
            except Exception:
                return
            
        img = utils.grab_clipboard_image()
        if img:
            self.last_clipboard_hash = self.get_image_hash(img)
            self.add_new_step_with_image(img)
        else:
            # Só mostrar aviso se foi invocado manualmente por botão (sem event)
            if event is None:
                messagebox.showwarning(
                    "Área de Transferência Vazia", 
                    "Não encontramos nenhuma imagem copiada na área de transferência.\n\n"
                    "Pressione PrintScreen no sistema desejado e clique aqui novamente ou use a opção 'Tirar Print' ou 'Importar Imagem'."
                )

    def capture_screen(self):
        # Minimizar a janela para não aparecer na captura nativa
        self.withdraw()
        self.update()
        
        success = utils.trigger_native_screenshot()
        
        if not success:
            # Restaurar imediatamente e avisar se falhar
            self.deiconify()
            self.update()
            messagebox.showinfo(
                "Captura do Sistema",
                "Não foi possível abrir a ferramenta de captura do sistema automaticamente.\n\n"
                "Por favor, use o atalho padrão do seu sistema:\n"
                "- Windows: Win + Shift + S\n"
                "- macOS: Cmd + Shift + 4\n"
                "- Linux: PrtScn ou Alt + PrtScn\n\n"
                "Em seguida, cole na aplicação clicando em 'Colar Print' ou usando Ctrl+V."
            )
        else:
            if not self.monitoring_clipboard:
                # Se não estiver monitorando automaticamente, agendar restauração
                self.after(3000, self.restore_after_screenshot)

    def restore_after_screenshot(self):
        self.deiconify()
        self.update()

    def toggle_clipboard_monitoring(self):
        if self.monitor_switch.get():
            self.monitoring_clipboard = True
            # Inicializar com o hash atual na thread principal (rápido)
            img = utils.grab_clipboard_image()
            if img:
                self.last_clipboard_hash = self.get_image_hash(img)
            else:
                self.last_clipboard_hash = None
            # Iniciar polling
            self.poll_clipboard()
        else:
            self.monitoring_clipboard = False

    def get_image_hash(self, img):
        import hashlib
        try:
            return hashlib.md5(img.tobytes()).hexdigest()
        except Exception:
            return None

    def poll_clipboard(self):
        """Agenda a leitura da área de transferência numa thread daemon para não bloquear a UI."""
        if not self.monitoring_clipboard:
            return

        def check_in_thread():
            if not self.polling_lock.acquire(blocking=False):
                return
            try:
                img = utils.grab_clipboard_image()
                if img:
                    current_hash = self.get_image_hash(img)
                    if current_hash and current_hash != self.last_clipboard_hash:
                        # Chamar a atualização de volta na thread principal via after()
                        self.after(0, lambda: self._on_new_clipboard_image(img, current_hash))
            except Exception as e:
                print(f"Erro ao ler área de transferência: {e}")
            finally:
                self.polling_lock.release()

        threading.Thread(target=check_in_thread, daemon=True).start()
        
        # Agendar próximo ciclo de polling (700ms) na thread principal (100% thread-safe)
        self.after(700, self.poll_clipboard)

    def _on_new_clipboard_image(self, img, current_hash):
        """Chamado na thread principal quando um novo print é detectado no clipboard."""
        # Verificar novamente para evitar race conditions
        if current_hash != self.last_clipboard_hash:
            self.last_clipboard_hash = current_hash
            self.add_new_step_with_image(img)
            # Trazer aplicativo de volta e colocá-lo em foco temporariamente
            self.deiconify()
            self.update()
            self.lift()
            self.attributes("-topmost", True)
            self.after_idle(self.attributes, "-topmost", False)

    def import_image(self):
        filepath = filedialog.askopenfilename(
            title="Importar Captura de Tela",
            filetypes=[("Arquivos de Imagem", "*.png *.jpg *.jpeg *.bmp"), ("Todos os arquivos", "*.*")]
        )
        if filepath:
            try:
                img = Image.open(filepath)
                img.load()  # Forçar leitura em memória
                self.add_new_step_with_image(img)
            except Exception as e:
                messagebox.showerror("Erro de Importação", f"Não foi possível ler o arquivo de imagem:\n{e}")

    def move_step_up(self):
        if self.current_step_index is not None and self.current_step_index > 0:
            idx = self.current_step_index
            if self.document.move_step_up(idx):
                self.current_step_index = idx - 1
                self.rebuild_sidebar_list()
                self.mark_as_changed()

    def move_step_down(self):
        if self.current_step_index is not None and self.current_step_index < len(self.document.steps) - 1:
            idx = self.current_step_index
            if self.document.move_step_down(idx):
                self.current_step_index = idx + 1
                self.rebuild_sidebar_list()
                self.mark_as_changed()

    def remove_step(self):
        if self.current_step_index is not None:
            confirm = messagebox.askyesno(
                "Confirmar Exclusão", 
                "Tem certeza que deseja excluir o passo selecionado? Esta ação não pode ser desfeita."
            )
            if confirm:
                try:
                    deleted_step = self.document.steps[self.current_step_index]
                    deleted_step_hash = self.get_image_hash(deleted_step.image)
                except Exception:
                    deleted_step_hash = None

                self.document.remove_step(self.current_step_index)
                
                # Se o print removido era o que estava no clipboard (último hash),
                # limpar o hash e o clipboard para permitir novas capturas/re-capturas
                if deleted_step_hash and deleted_step_hash == self.last_clipboard_hash:
                    self.last_clipboard_hash = None
                    try:
                        self.clipboard_clear()
                    except Exception:
                        pass
                
                # Ajustar índice de seleção
                if len(self.document.steps) == 0:
                    self.current_step_index = None
                elif self.current_step_index >= len(self.document.steps):
                    self.current_step_index = len(self.document.steps) - 1
                    
                self.rebuild_sidebar_list()
                self.mark_as_changed()

    # --- Operações com Arquivos (.docp) ---

    def new_document(self):
        if self.check_unsaved_changes():
            self.document.clear()
            self.current_step_index = None
            self.doc_title_entry.delete(0, "end")
            self.doc_title_entry.insert(0, self.document.title)
            self.doc_subtitle_entry.delete(0, "end")
            self.doc_subtitle_entry.insert(0, self.document.subtitle)
            self.doc_category_entry.delete(0, "end")
            self.doc_category_entry.insert(0, "")
            self.doc_tags_entry.delete(0, "end")
            self.doc_tags_entry.insert(0, "")
            self.doc_author_entry.delete(0, "end")
            self.doc_author_entry.insert(0, "")
            self.num_arrows_var.set(self.document.num_arrows)
            self.editor_canvas.set_num_arrows(self.document.num_arrows)
            self.rebuild_sidebar_list()
            self.update_title_bar()

    def open_document(self):
        if self.check_unsaved_changes():
            filepath = filedialog.askopenfilename(
                title="Abrir Documento",
                filetypes=[("Documento de Processos ERP", "*.docp")]
            )
            if filepath:
                try:
                    self.document.load(filepath)
                    self.current_step_index = 0 if len(self.document.steps) > 0 else None
                    self.doc_title_entry.delete(0, "end")
                    self.doc_title_entry.insert(0, self.document.title)
                    self.doc_subtitle_entry.delete(0, "end")
                    self.doc_subtitle_entry.insert(0, self.document.subtitle)
                    self.doc_category_entry.delete(0, "end")
                    self.doc_category_entry.insert(0, getattr(self.document, "category", ""))
                    self.doc_tags_entry.delete(0, "end")
                    self.doc_tags_entry.insert(0, getattr(self.document, "tags", ""))
                    self.doc_author_entry.delete(0, "end")
                    self.doc_author_entry.insert(0, getattr(self.document, "author", ""))
                    self.num_arrows_var.set(self.document.num_arrows)
                    self.editor_canvas.set_num_arrows(self.document.num_arrows)
                    self.rebuild_sidebar_list()
                    self.update_title_bar()
                except Exception as e:
                    messagebox.showerror("Erro ao Abrir", f"Erro carregando o arquivo:\n{e}")

    def save_document(self) -> bool:
        if not self.document.filepath:
            filepath = filedialog.asksaveasfilename(
                title="Salvar Documento",
                defaultextension=".docp",
                filetypes=[("Documento de Processos ERP", "*.docp")]
            )
            if not filepath:
                return False
            self.document.filepath = filepath
            
        try:
            self.document.save(self.document.filepath)
            self.update_title_bar()
            return True
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}")
            return False

    def check_unsaved_changes(self) -> bool:
        """
        Verifica se há alterações pendentes.
        Retorna True se for seguro continuar, False se a ação deve ser cancelada.
        """
        if self.document.changed:
            res = messagebox.askyesnocancel(
                "Salvar Alterações", 
                "Há alterações não salvas no documento.\nVocê deseja salvá-las agora?"
            )
            if res is True:  # Sim
                return self.save_document()
            elif res is False:  # Não
                return True
            else:  # Cancelar
                return False
        return True

    def on_closing(self):
        if self.check_unsaved_changes():
            self.destroy()

    # --- Operações de Exportação ---

    def export_pdf(self):
        if len(self.document.steps) == 0:
            messagebox.showwarning("Exportação Vazia", "Adicione pelo menos um passo para poder exportar.")
            return
            
        filepath = filedialog.asksaveasfilename(
            title="Exportar para PDF",
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")]
        )
        if filepath:
            try:
                success = export_to_pdf(self.document, filepath)
                if success:
                    messagebox.showinfo("Exportação Concluída", f"Documento exportado com sucesso para PDF em:\n{filepath}")
                else:
                    messagebox.showerror("Erro de Dependência", "Não foi possível carregar a biblioteca de geração de PDF (ReportLab).")
            except Exception as e:
                messagebox.showerror("Erro de Exportação", f"Erro exportando PDF:\n{e}")

    def link_document_to_wiki(self):
        if len(self.document.steps) == 0:
            messagebox.showwarning("Documento Vazio", "Adicione pelo menos um passo para poder vincular à base Wiki.")
            return
            
        wiki_dir = filedialog.askdirectory(title="Selecionar diretório da Base Wiki")
        if not wiki_dir:
            return
            
        try:
            # 1. Criar a pasta docp/ na base Wiki se não existir
            docp_dir = os.path.join(wiki_dir, "docp")
            os.makedirs(docp_dir, exist_ok=True)
            
            # 2. Determinar o slug do documento baseado no título
            from exporter import slugify
            doc_slug = slugify(self.document.title if self.document.title else "documento")
            if not doc_slug:
                doc_slug = "documento"
                
            # 3. Salvar o documento atual em docp/{doc_slug}.docp
            target_filepath = os.path.join(docp_dir, f"{doc_slug}.docp")
            self.document.save(target_filepath)
            
            # Atualizar o caminho local do documento ativo
            self.document.filepath = target_filepath
            self.update_title_bar()
            
            # 4. Escanear todos os arquivos .docp na pasta docp/
            files = [os.path.join(docp_dir, f) for f in os.listdir(docp_dir) if f.endswith(".docp")]
            
            # 5. Carregar todos os documentos em memória
            docs_to_compile = []
            for f in files:
                doc = Document()
                doc.load(f)
                docs_to_compile.append(doc)
                
            # 6. Compilar o repositório Wiki estático completo
            export_to_wiki_repository(docs_to_compile, wiki_dir)
            
            messagebox.showinfo("Vinculação Concluída", f"Manual vinculado com sucesso!\nO repositório Wiki foi atualizado com {len(docs_to_compile)} manual(ais).")
        except Exception as e:
            messagebox.showerror("Erro de Vinculação", f"Erro ao vincular documento à Wiki:\n{e}")

    def update_attachments_list(self):
        if not hasattr(self, "attachments_listbox") or not self.attachments_listbox:
            return
            
        for child in self.attachments_listbox.winfo_children():
            child.destroy()
            
        if self.current_step_index is None:
            if hasattr(self, "btn_add_attachment") and self.btn_add_attachment:
                self.btn_add_attachment.configure(state="disabled")
            if hasattr(self, "btn_remove_attachment") and self.btn_remove_attachment:
                self.btn_remove_attachment.configure(state="disabled")
            return
            
        if hasattr(self, "btn_add_attachment") and self.btn_add_attachment:
            self.btn_add_attachment.configure(state="normal")
        if hasattr(self, "btn_remove_attachment") and self.btn_remove_attachment:
            self.btn_remove_attachment.configure(state="normal")
        
        step = self.document.steps[self.current_step_index]
        attachments = getattr(step, "attachments", [])
        
        for att in attachments:
            lbl = ctk.CTkLabel(self.attachments_listbox, text=att["filename"], font=("Arial", 11), anchor="w")
            lbl.pack(fill="x", padx=5, pady=2)
            lbl.bind("<Button-1>", lambda e, a=att, l=lbl: self.select_attachment(a, l))
            
        self.selected_attachment_data = None

    def select_attachment(self, attachment, label_widget):
        for child in self.attachments_listbox.winfo_children():
            child.configure(fg_color="transparent", text_color=("gray10", "#DCE4EE"))
        label_widget.configure(fg_color="#1a73e8", text_color="#ffffff")
        self.selected_attachment_data = attachment

    def add_step_attachment(self):
        if self.current_step_index is None:
            return
        filepath = filedialog.askopenfilename(
            title="Selecionar arquivo para anexar",
            filetypes=[("Todos os arquivos", "*.*")]
        )
        if filepath:
            try:
                filename = os.path.basename(filepath)
                with open(filepath, "rb") as f:
                    file_data = f.read()
                step = self.document.steps[self.current_step_index]
                if not hasattr(step, "attachments"):
                    step.attachments = []
                if any(att["filename"] == filename for att in step.attachments):
                    messagebox.showwarning("Arquivo Duplicado", f"O arquivo '{filename}' já está anexado a este passo.")
                    return
                import uuid
                step.attachments.append({
                    "id": uuid.uuid4().hex,
                    "filename": filename,
                    "data": file_data
                })
                self.mark_as_changed()
                self.update_attachments_list()
            except Exception as e:
                messagebox.showerror("Erro ao Carregar Anexo", f"Erro: {e}")

    def remove_step_attachment(self):
        if self.current_step_index is None or not getattr(self, "selected_attachment_data", None):
            messagebox.showwarning("Nenhum Anexo Selecionado", "Por favor, clique em um anexo da lista para selecioná-lo primeiro.")
            return
        step = self.document.steps[self.current_step_index]
        att_id = self.selected_attachment_data["id"]
        step.attachments = [a for a in getattr(step, "attachments", []) if a["id"] != att_id]
        self.mark_as_changed()
        self.selected_attachment_data = None
        self.update_attachments_list()





if __name__ == "__main__":
    app = DocumentadorApp()
    app.mainloop()
