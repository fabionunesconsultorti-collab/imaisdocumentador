import os
import unittest
from PIL import Image
from document import Document, Step
from exporter import (
    export_to_html, 
    export_to_svg, 
    export_to_pdf, 
    get_annotated_image,
    parse_description_to_html,
    parse_description_to_pdf_flowables
)

class TestDocumentadorLogic(unittest.TestCase):
    def setUp(self):
        # Criar uma imagem simples para testes (800x600)
        self.test_image = Image.new("RGB", (800, 600), color="blue")
        self.doc = Document()
        
    def test_document_lifecycle(self):
        # 1. Adicionar um passo
        self.doc.subtitle = "Subtítulo de Teste Específico"
        step = self.doc.add_step(self.test_image, title="Passo Inicial", description="Testando a criação de passos.")
        self.assertEqual(len(self.doc.steps), 1)
        self.assertEqual(self.doc.steps[0].title, "Passo Inicial")
        
        # 2. Adicionar anotações
        step.add_arrow(50, 50, 200, 200, color="#FF0000", width=4)
        step.add_text(220, 200, "Texto de Teste", color="#00FF00", size=20)
        
        self.assertEqual(len(step.annotations), 2)
        self.assertEqual(step.annotations[0]["type"], "arrow")
        self.assertEqual(step.annotations[1]["type"], "text")
        
        # 3. Salvar documento em arquivo
        self.doc.category = "TI"
        self.doc.tags = "teste, doc"
        self.doc.author = "Agente Antigravity"
        
        # Adicionar anexo ao passo
        import uuid
        att_data = b"dados de teste do anexo"
        step.attachments.append({
            "id": uuid.uuid4().hex,
            "filename": "teste_anexo.txt",
            "data": att_data
        })
        
        test_file = "test_document.docp"
        if os.path.exists(test_file):
            os.remove(test_file)
            
        self.doc.save(test_file)
        self.assertTrue(os.path.exists(test_file))
        
        # 4. Carregar documento em nova instância
        new_doc = Document()
        new_doc.load(test_file)
        
        self.assertEqual(len(new_doc.steps), 1)
        self.assertEqual(new_doc.subtitle, "Subtítulo de Teste Específico")
        self.assertEqual(new_doc.category, "TI")
        self.assertEqual(new_doc.tags, "teste, doc")
        self.assertEqual(new_doc.author, "Agente Antigravity")
        
        loaded_step = new_doc.steps[0]
        self.assertEqual(loaded_step.title, "Passo Inicial")
        self.assertEqual(loaded_step.description, "Testando a criação de passos.")
        self.assertEqual(len(loaded_step.annotations), 2)
        
        # Validar anexo carregado
        self.assertEqual(len(loaded_step.attachments), 1)
        self.assertEqual(loaded_step.attachments[0]["filename"], "teste_anexo.txt")
        self.assertEqual(loaded_step.attachments[0]["data"], att_data)
        
        # Validar coordenadas e atributos
        self.assertEqual(loaded_step.annotations[0]["x1"], 50)
        self.assertEqual(loaded_step.annotations[0]["y2"], 200)
        self.assertEqual(loaded_step.annotations[1]["text"], "Texto de Teste")
        self.assertEqual(loaded_step.annotations[1]["size"], 20)
        
        # 5. Excluir anotação
        anno_id_to_remove = loaded_step.annotations[0]["id"]
        loaded_step.remove_annotation(anno_id_to_remove)
        self.assertEqual(len(loaded_step.annotations), 1)
        self.assertEqual(loaded_step.annotations[0]["type"], "text")
        
        # Limpeza
        if os.path.exists(test_file):
            os.remove(test_file)

    def test_exporters(self):
        # Preparar documento com 2 passos
        step1 = self.doc.add_step(
            self.test_image, 
            title="Passo 1", 
            description="Descrição do primeiro passo com **negrito** e ==grifado==.\n[atenção]Aviso importante![/atenção]\n[observação]Nota informativa.[/observação]"
        )
        step1.add_arrow(100, 100, 300, 200, color="#FF0000", width=3)
        
        step2 = self.doc.add_step(self.test_image, title="Passo 2", description="Descrição do segundo passo.")
        step2.add_text(150, 150, "Anotação", color="#0000FF", size=18)
        
        # Testar mesclagem de imagem do Pillow
        annotated_img = get_annotated_image(step1)
        self.assertEqual(annotated_img.size, (800, 600))
        
        # Exportar HTML
        html_file = "test_output.html"
        if os.path.exists(html_file):
            os.remove(html_file)
        export_to_html(self.doc, html_file)
        self.assertTrue(os.path.exists(html_file))
        self.assertGreater(os.path.getsize(html_file), 0)
        
        # Exportar SVG
        svg_file = "test_output.svg"
        if os.path.exists(svg_file):
            os.remove(svg_file)
        export_to_svg(self.doc, svg_file)
        self.assertTrue(os.path.exists(svg_file))
        self.assertGreater(os.path.getsize(svg_file), 0)
        
        # Exportar PDF
        pdf_file = "test_output.pdf"
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        success = export_to_pdf(self.doc, pdf_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(pdf_file))
        self.assertGreater(os.path.getsize(pdf_file), 0)
        
        # Limpeza
        for f in [html_file, svg_file, pdf_file]:
            if os.path.exists(f):
                os.remove(f)

    def test_formatting_and_flags_parsing(self):
        # Testar parsing de HTML
        html_desc = parse_description_to_html("Isso é **negrito** e ==grifado==. [atenção]Perigo![/atenção]")
        self.assertIn("<strong>negrito</strong>", html_desc)
        self.assertIn("flag-callout flag-attention", html_desc)
        self.assertIn("Perigo!", html_desc)
        
        # Testar parsing de PDF
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        pdf_flowables = parse_description_to_pdf_flowables(
            "Texto normal. [observação]Info.[/observação]",
            styles['Normal'],
            available_width=500
        )
        # Deve gerar pelo menos dois flowables (o texto normal e a tabela do callout)
        self.assertGreaterEqual(len(pdf_flowables), 2)

    def test_italic_underline_and_lists_parsing(self):
        html_desc = parse_description_to_html(
            "Clique em _Novo_ e preencha ++todos++ os campos:\n"
            "- Nome\n"
            "- CNPJ\n"
            "Em seguida:\n"
            "1. Salvar\n"
            "2. Validar"
        )
        self.assertIn("<em>Novo</em>", html_desc)
        self.assertIn("<u>todos</u>", html_desc)
        self.assertIn("<ul><li>Nome</li><li>CNPJ</li></ul>", html_desc)
        self.assertIn("<ol><li>Salvar</li><li>Validar</li></ol>", html_desc)

        # Underscores no meio de palavras não devem virar itálico
        self.assertEqual(parse_description_to_html("campo nome_do_cliente"), "campo nome_do_cliente")

        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        pdf_flowables = parse_description_to_pdf_flowables(
            "Passos:\n- Primeiro\n- Segundo",
            styles['Normal'],
            available_width=500
        )
        item_texts = [getattr(f, "text", "") for f in pdf_flowables]
        self.assertTrue(any("• Primeiro" in t for t in item_texts))
        self.assertTrue(any("• Segundo" in t for t in item_texts))
 
if __name__ == "__main__":
    unittest.main()
