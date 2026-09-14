import io
import json
import uuid
import zipfile
from PIL import Image

class Step:
    def __init__(self, id=None, title="", description="", image=None, annotations=None, attachments=None):
        self.id = id if id else uuid.uuid4().hex
        self.title = title
        self.description = description
        self.image = image  # PIL.Image object
        self.annotations = annotations if annotations is not None else []
        self.attachments = attachments if attachments is not None else []
        
    def add_arrow(self, x1, y1, x2, y2, color="#FF0000", width=3):
        """
        Adiciona uma seta no espaço de coordenadas da imagem original.
        """
        annotation = {
            "id": uuid.uuid4().hex,
            "type": "arrow",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "color": color,
            "width": width
        }
        self.annotations.append(annotation)
        return annotation

    def add_text(self, x, y, text, color="#FF0000", size=16):
        """
        Adiciona um texto no espaço de coordenadas da imagem original.
        """
        annotation = {
            "id": uuid.uuid4().hex,
            "type": "text",
            "x": x,
            "y": y,
            "text": text,
            "color": color,
            "size": size
        }
        self.annotations.append(annotation)
        return annotation

    def remove_annotation(self, anno_id):
        """
        Remove uma anotação pelo ID.
        """
        self.annotations = [a for a in self.annotations if a.get("id") != anno_id]


class Document:
    def __init__(self):
        self.steps = []
        self.filepath = None
        self.changed = False
        self.title = "Documentação de Processo ERP"
        self.subtitle = "Documento gerado automaticamente pelo Documentador de Processos"
        self.num_arrows = True
        self.category = ""
        self.tags = ""
        self.author = ""

    def clear(self):
        self.steps = []
        self.filepath = None
        self.changed = False
        self.title = "Documentação de Processo ERP"
        self.subtitle = "Documento gerado automaticamente pelo Documentador de Processos"
        self.num_arrows = True
        self.category = ""
        self.tags = ""
        self.author = ""

    def add_step(self, image: Image.Image, title="", description="") -> Step:
        # Garantir que a imagem está em RGB ou RGBA
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        
        step = Step(title=title, description=description, image=image)
        self.steps.append(step)
        self.changed = True
        return step

    def remove_step(self, index: int):
        if 0 <= index < len(self.steps):
            self.steps.pop(index)
            self.changed = True

    def move_step_up(self, index: int) -> bool:
        if 1 <= index < len(self.steps):
            self.steps[index], self.steps[index - 1] = self.steps[index - 1], self.steps[index]
            self.changed = True
            return True
        return False

    def move_step_down(self, index: int) -> bool:
        if 0 <= index < len(self.steps) - 1:
            self.steps[index], self.steps[index + 1] = self.steps[index + 1], self.steps[index]
            self.changed = True
            return True
        return False

    def save(self, filepath: str):
        """
        Salva o documento em um arquivo .docp (formato ZIP compactado contendo JSON e imagens),
        atualizando o caminho do arquivo atual e limpando o marcador de alterações pendentes.
        """
        self._write_to(filepath)
        self.filepath = filepath
        self.changed = False

    def save_copy(self, filepath: str):
        """
        Salva uma cópia do documento em filepath sem alterar o caminho do arquivo
        atual nem o marcador de alterações pendentes. Usado pelo autosave de
        recuperação, que não deve interferir no fluxo normal de salvar do usuário.
        """
        self._write_to(filepath)

    def _write_to(self, filepath: str):
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            metadata = {
                "title": self.title,
                "subtitle": self.subtitle,
                "num_arrows": self.num_arrows,
                "category": getattr(self, "category", ""),
                "tags": getattr(self, "tags", ""),
                "author": getattr(self, "author", ""),
                "steps": []
            }
            
            for step in self.steps:
                # Salvar a imagem original no zip
                img_byte_arr = io.BytesIO()
                step.image.save(img_byte_arr, format='PNG')
                img_data = img_byte_arr.getvalue()
                
                image_name = f"images/{step.id}.png"
                zipf.writestr(image_name, img_data)
                
                # Salvar anexos do passo no zip
                attachments_meta = []
                for att in getattr(step, "attachments", []):
                    att_filename = att["filename"]
                    att_data = att["data"]
                    zip_path = f"attachments/{step.id}/{att_filename}"
                    zipf.writestr(zip_path, att_data)
                    attachments_meta.append({
                        "id": att["id"],
                        "filename": att_filename,
                        "zip_path": zip_path
                    })
                
                # Adicionar dados do passo aos metadados
                metadata["steps"].append({
                    "id": step.id,
                    "title": step.title,
                    "description": step.description,
                    "image_filename": image_name,
                    "annotations": step.annotations,
                    "attachments": attachments_meta
                })
                
            # Salvar o document.json no zip
            metadata_str = json.dumps(metadata, indent=4, ensure_ascii=False)
            zipf.writestr("document.json", metadata_str.encode('utf-8'))

    def load(self, filepath: str):
        """
        Carrega o documento a partir de um arquivo .docp.
        """
        self.clear()
        self.filepath = filepath
        
        with zipfile.ZipFile(filepath, 'r') as zipf:
            # Ler metadados
            metadata_content = zipf.read("document.json").decode('utf-8')
            metadata = json.loads(metadata_content)
            
            self.title = metadata.get("title", "Documentação de Processo ERP")
            self.subtitle = metadata.get("subtitle", "Documento gerado automaticamente pelo Documentador de Processos")
            self.num_arrows = metadata.get("num_arrows", True)
            self.category = metadata.get("category", "")
            self.tags = metadata.get("tags", "")
            self.author = metadata.get("author", "")
            
            for step_data in metadata["steps"]:
                # Ler imagem correspondente
                img_data = zipf.read(step_data["image_filename"])
                image = Image.open(io.BytesIO(img_data))
                image.load()  # Força o carregamento da imagem em memória
                
                # Ler anexos do passo
                attachments = []
                attachments_meta = step_data.get("attachments", [])
                for att_meta in attachments_meta:
                    att_id = att_meta["id"]
                    att_filename = att_meta["filename"]
                    zip_path = att_meta["zip_path"]
                    try:
                        att_data = zipf.read(zip_path)
                        attachments.append({
                            "id": att_id,
                            "filename": att_filename,
                            "data": att_data
                        })
                    except Exception as e:
                        print(f"Erro ao ler anexo {att_filename}: {e}")
                
                step = Step(
                    id=step_data["id"],
                    title=step_data["title"],
                    description=step_data["description"],
                    image=image,
                    annotations=step_data["annotations"],
                    attachments=attachments
                )
                self.steps.append(step)
                
        self.changed = False
