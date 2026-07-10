import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

class TextDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Texto", initial_text="", size=16):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        
        # Centralizar na tela
        self.geometry("350x200")
        self.resizable(False, False)
        
        # Garantir que a janela apareça no topo e com foco
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        
        self.label = ctk.CTkLabel(self, text="Texto da Anotação:", font=("Arial", 13, "bold"))
        self.label.pack(pady=(15, 5))
        
        self.entry = ctk.CTkEntry(self, width=280)
        self.entry.insert(0, initial_text)
        self.entry.pack(pady=5)
        self.entry.focus_set()
        self.entry.select_range(0, tk.END)
        
        # Frame de tamanho de fonte
        font_frame = ctk.CTkFrame(self, fg_color="transparent")
        font_frame.pack(pady=5)
        
        self.size_label = ctk.CTkLabel(font_frame, text="Tamanho:")
        self.size_label.pack(side="left", padx=5)
        
        self.size_var = ctk.StringVar(value=str(size))
        self.size_menu = ctk.CTkOptionMenu(
            font_frame, 
            values=["12", "14", "16", "18", "20", "24", "28", "32", "40"], 
            variable=self.size_var,
            width=80
        )
        self.size_menu.pack(side="left", padx=5)
        
        self.result = None
        
        # Botões
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        self.btn_ok = ctk.CTkButton(btn_frame, text="Confirmar", width=100, command=self.on_ok)
        self.btn_ok.pack(side="left", padx=10)
        
        self.btn_cancel = ctk.CTkButton(btn_frame, text="Cancelar", width=100, command=self.on_cancel)
        self.btn_cancel.pack(side="right", padx=10)
        
        # Atalhos de teclado
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())
        
        # Aguardar fechar
        self.wait_window(self)
        
    def on_ok(self):
        text = self.entry.get().strip()
        if text:
            self.result = {
                "text": text,
                "size": int(self.size_var.get())
            }
        self.destroy()
        
    def on_cancel(self):
        self.result = None
        self.destroy()


class EditorCanvas(ctk.CTkFrame):
    def __init__(self, parent, on_changed_callback=None):
        super().__init__(parent)
        self.on_changed_callback = on_changed_callback
        
        self.step = None
        self.tool = "select"  # select, arrow, text
        self.num_arrows = True
        
        # Configurações de desenho
        self.current_color = "#FF0000"  # Vermelho padrão
        self.current_width = 3
        self.current_size = 16
        
        self.selected_anno_id = None
        self.drag_start_pos = None
        self.temp_draw_id = None
        self.initial_anno_coords = None
        
        # Mapeamentos para detecção de clique
        self.canvas_id_to_anno_id = {}
        
        # Widget Canvas do Tkinter padrão (dentro do frame do CTk)
        self.canvas = tk.Canvas(
            self, 
            bg="#2b2b2b", 
            bd=0, 
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Eventos do canvas
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Guardar referência de imagem do Tkinter para não ser coletada pelo GC
        self.tk_image = None
        
    def set_step(self, step):
        self.step = step
        self.selected_anno_id = None
        self.drag_start_pos = None
        self.temp_draw_id = None
        self.initial_anno_coords = None
        self.redraw()
        
    def set_tool(self, tool):
        self.tool = tool
        self.selected_anno_id = None
        self.initial_anno_coords = None
        self.redraw()
        
    def set_num_arrows(self, enabled):
        self.num_arrows = enabled
        self.redraw()
        
    def set_color(self, color):
        self.current_color = color
        if self.selected_anno_id and self.step:
            # Alterar cor do elemento selecionado
            for anno in self.step.annotations:
                if anno.get("id") == self.selected_anno_id:
                    anno["color"] = color
                    self.redraw()
                    self.notify_change()
                    break

    def set_thickness(self, width):
        self.current_width = width
        if self.selected_anno_id and self.step:
            # Alterar espessura do elemento selecionado (se for seta)
            for anno in self.step.annotations:
                if anno.get("id") == self.selected_anno_id and anno.get("type") == "arrow":
                    anno["width"] = width
                    self.redraw()
                    self.notify_change()
                    break

    def set_font_size(self, size):
        self.current_size = size
        if self.selected_anno_id and self.step:
            # Alterar tamanho da fonte do elemento selecionado (se for texto)
            for anno in self.step.annotations:
                if anno.get("id") == self.selected_anno_id and anno.get("type") == "text":
                    anno["size"] = size
                    self.redraw()
                    self.notify_change()
                    break

    def get_scaling_and_offsets(self):
        if not self.step or not self.step.image:
            return 1.0, 0, 0
            
        ow, oh = self.step.image.size
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        if canvas_w <= 1 or canvas_h <= 1:
            # Canvas ainda não foi renderizado — agendar nova tentativa de desenho
            self.after(50, self.redraw)
            return 1.0, 0, 0
            
        s = min(canvas_w / ow, canvas_h / oh)
        s = max(s, 0.01)  # Evitar divisão por zero
        
        dx = (canvas_w - ow * s) / 2
        dy = (canvas_h - oh * s) / 2
        
        return s, dx, dy

    def canvas_to_img_coords(self, cx, cy):
        s, dx, dy = self.get_scaling_and_offsets()
        ix = (cx - dx) / s
        iy = (cy - dy) / s
        
        if self.step and self.step.image:
            ow, oh = self.step.image.size
            ix = max(0, min(ow, ix))
            iy = max(0, min(oh, iy))
            
        return int(ix), int(iy)

    def img_to_canvas_coords(self, ix, iy):
        s, dx, dy = self.get_scaling_and_offsets()
        cx = ix * s + dx
        cy = iy * s + dy
        return int(cx), int(cy)

    def redraw(self):
        self.canvas.delete("all")
        self.canvas_id_to_anno_id.clear()
        
        if not self.step or not self.step.image:
            return
            
        s, dx, dy = self.get_scaling_and_offsets()
        ow, oh = self.step.image.size
        dw = int(ow * s)
        dh = int(oh * s)
        
        if dw <= 0 or dh <= 0:
            return
            
        # Renderizar imagem de fundo
        resized_img = self.step.image.resize((dw, dh), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_img)
        self.canvas.create_image(dx, dy, image=self.tk_image, anchor="nw")
        
        # Desenhar anotações
        arrow_count = 0
        for anno in self.step.annotations:
            atype = anno.get("type")
            color = anno.get("color", "#FF0000")
            
            if atype == "arrow":
                arrow_count += 1
                x1, y1 = self.img_to_canvas_coords(anno["x1"], anno["y1"])
                x2, y2 = self.img_to_canvas_coords(anno["x2"], anno["y2"])
                width = anno.get("width", 3)
                
                # Se selecionado, desenha destaque ao redor
                if anno.get("id") == self.selected_anno_id:
                    self.canvas.create_line(
                        x1, y1, x2, y2, 
                        arrow=tk.LAST, 
                        fill="#00FF00",  # Destaque verde
                        width=width + 4, 
                        arrowshape=(12, 14, 6)
                    )
                
                line_id = self.canvas.create_line(
                    x1, y1, x2, y2, 
                    arrow=tk.LAST, 
                    fill=color, 
                    width=width, 
                    arrowshape=(10, 12, 5)
                )
                self.canvas_id_to_anno_id[line_id] = anno.get("id")
                
                if self.num_arrows:
                    r = 10
                    self.canvas.create_oval(
                        x1 - r, y1 - r, x1 + r, y1 + r,
                        fill="#ffffff",
                        outline=color,
                        width=2
                    )
                    self.canvas.create_text(
                        x1, y1,
                        text=str(arrow_count),
                        fill=color,
                        font=("Arial", 9, "bold")
                    )
                
            elif atype == "text":
                x, y = self.img_to_canvas_coords(anno["x"], anno["y"])
                size = anno.get("size", 16)
                # Escalar fonte de acordo com o zoom do canvas para preview correto
                scaled_size = max(8, int(size * s))
                
                text_id = self.canvas.create_text(
                    x, y, 
                    text=anno["text"], 
                    fill=color, 
                    font=("Arial", scaled_size, "bold"), 
                    anchor="nw"
                )
                self.canvas_id_to_anno_id[text_id] = anno.get("id")
                
                # Desenhar caixa de fundo (retângulo) para o texto
                bbox = self.canvas.bbox(text_id)
                if bbox:
                    bg_rect_id = self.canvas.create_rectangle(
                        bbox[0] - 4, bbox[1] - 2, 
                        bbox[2] + 4, bbox[3] + 2, 
                        fill="#ffffff", 
                        outline=color, 
                        width=1
                    )
                    self.canvas.tag_lower(bg_rect_id, text_id)
                    self.canvas_id_to_anno_id[bg_rect_id] = anno.get("id")
                    
                    # Se selecionado, desenha borda pontilhada verde ao redor da caixa
                    if anno.get("id") == self.selected_anno_id:
                        self.canvas.create_rectangle(
                            bbox[0] - 7, bbox[1] - 5, 
                            bbox[2] + 7, bbox[3] + 5, 
                            outline="#00FF00", 
                            width=1.5, 
                            dash=(4, 4)
                        )

    def on_resize(self, event):
        self.redraw()

    def on_click(self, event):
        if not self.step:
            return
            
        if self.tool == "select":
            # Usar find_overlapping do canvas para detecção precisa
            overlapping = self.canvas.find_overlapping(event.x - 4, event.y - 4, event.x + 4, event.y + 4)
            found_id = None
            for cid in reversed(overlapping):
                if cid in self.canvas_id_to_anno_id:
                    found_id = self.canvas_id_to_anno_id[cid]
                    break
            
            self.selected_anno_id = found_id
            if found_id:
                self.drag_start_pos = (event.x, event.y)
                # Salvar coordenadas iniciais da anotação selecionada
                self.initial_anno_coords = None
                for anno in self.step.annotations:
                    if anno.get("id") == found_id:
                        if anno.get("type") == "text":
                            self.initial_anno_coords = (anno["x"], anno["y"])
                        elif anno.get("type") == "arrow":
                            self.initial_anno_coords = (anno["x1"], anno["y1"], anno["x2"], anno["y2"])
                        break
            else:
                self.drag_start_pos = None
                self.initial_anno_coords = None
            self.redraw()
                
        elif self.tool == "arrow":
            self.drag_start_pos = (event.x, event.y)
            # Criar linha temporária
            self.temp_draw_id = self.canvas.create_line(
                event.x, event.y, event.x, event.y, 
                arrow=tk.LAST, 
                fill=self.current_color, 
                width=self.current_width,
                arrowshape=(10, 12, 5)
            )
            
        elif self.tool == "text":
            ix, iy = self.canvas_to_img_coords(event.x, event.y)
            # Abrir diálogo para digitar texto
            dialog = TextDialog(self.winfo_toplevel(), title="Adicionar Texto", size=self.current_size)
            if dialog.result:
                self.step.add_text(
                    ix, iy, 
                    dialog.result["text"], 
                    color=self.current_color, 
                    size=dialog.result["size"]
                )
                self.redraw()
                self.notify_change()

    def on_drag(self, event):
        if self.tool == "select" and self.selected_anno_id and self.drag_start_pos and getattr(self, 'initial_anno_coords', None):
            x1, y1 = self.drag_start_pos
            x2, y2 = event.x, event.y
            
            s, _, _ = self.get_scaling_and_offsets()
            dx_img = (x2 - x1) / s
            dy_img = (y2 - y1) / s
            
            # Encontrar a anotação e atualizar coordenadas em tempo real
            for anno in self.step.annotations:
                if anno.get("id") == self.selected_anno_id:
                    ow, oh = self.step.image.size
                    if anno.get("type") == "text":
                        init_x, init_y = self.initial_anno_coords
                        anno["x"] = max(0, min(ow, int(init_x + dx_img)))
                        anno["y"] = max(0, min(oh, int(init_y + dy_img)))
                    elif anno.get("type") == "arrow":
                        init_x1, init_y1, init_x2, init_y2 = self.initial_anno_coords
                        anno["x1"] = max(0, min(ow, int(init_x1 + dx_img)))
                        anno["y1"] = max(0, min(oh, int(init_y1 + dy_img)))
                        anno["x2"] = max(0, min(ow, int(init_x2 + dx_img)))
                        anno["y2"] = max(0, min(oh, int(init_y2 + dy_img)))
                    break
            self.redraw()
            
        elif self.tool == "arrow" and self.drag_start_pos and self.temp_draw_id:
            x1, y1 = self.drag_start_pos
            self.canvas.coords(self.temp_draw_id, x1, y1, event.x, event.y)

    def on_release(self, event):
        if self.tool == "select" and self.selected_anno_id and self.drag_start_pos:
            self.drag_start_pos = None
            self.initial_anno_coords = None
            self.notify_change()
            
        elif self.tool == "arrow" and self.drag_start_pos and self.temp_draw_id:
            x1, y1 = self.drag_start_pos
            x2, y2 = event.x, event.y
            
            # Deletar linha temporária do canvas
            self.canvas.delete(self.temp_draw_id)
            self.temp_draw_id = None
            self.drag_start_pos = None
            
            # Só adicionar se o arraste foi significativo (evitar clique acidental)
            if ((x2 - x1)**2 + (y2 - y1)**2)**0.5 > 5:
                ix1, iy1 = self.canvas_to_img_coords(x1, y1)
                ix2, iy2 = self.canvas_to_img_coords(x2, y2)
                
                self.step.add_arrow(
                    ix1, iy1, ix2, iy2, 
                    color=self.current_color, 
                    width=self.current_width
                )
                self.redraw()
                self.notify_change("arrow")

    def on_double_click(self, event):
        if not self.step or self.tool != "select" or not self.selected_anno_id:
            return
            
        # Editar texto de anotação
        for anno in self.step.annotations:
            if anno.get("id") == self.selected_anno_id and anno.get("type") == "text":
                dialog = TextDialog(
                    self.winfo_toplevel(), 
                    title="Editar Texto", 
                    initial_text=anno["text"], 
                    size=anno.get("size", 16)
                )
                if dialog.result:
                    anno["text"] = dialog.result["text"]
                    anno["size"] = dialog.result["size"]
                    self.redraw()
                    self.notify_change()
                break

    def delete_selected(self):
        """
        Exclui o elemento selecionado atualmente.
        """
        if self.step and self.selected_anno_id:
            self.step.remove_annotation(self.selected_anno_id)
            self.selected_anno_id = None
            self.redraw()
            self.notify_change()
            return True
        return False

    def notify_change(self, annotation_type=None):
        if self.on_changed_callback:
            try:
                self.on_changed_callback(annotation_type)
            except TypeError:
                self.on_changed_callback()
