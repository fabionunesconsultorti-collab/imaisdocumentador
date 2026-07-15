import io
import os
import base64
import math
import tempfile
import utils
from PIL import Image, ImageDraw, ImageFont

# Importações seguras do reportlab
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def get_system_font(size=16):
    """
    Tenta obter uma fonte TrueType instalada no sistema para o Pillow.
    Retorna o objeto ImageFont.
    """
    fonts = [
        "Arial.ttf", "arial.ttf", 
        "DejaVuSans.ttf", "dejavusans.ttf", 
        "Helvetica.ttf", "helvetica.ttf",
        "LiberationSans-Regular.ttf",
        "FreeSans.ttf"
    ]
    for font_name in fonts:
        try:
            return ImageFont.truetype(font_name, size)
        except IOError:
            continue
    return ImageFont.load_default()


def draw_arrow_on_pil(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width):
    """
    Desenha uma linha com cabeça de seta no objeto ImageDraw do Pillow.
    """
    # 1. Desenhar a linha principal
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    
    # 2. Calcular vetor da linha
    dx = x2 - x1
    dy = y2 - y1
    length = (dx*dx + dy*dy)**0.5
    
    if length < 1e-5:
        return
        
    # Normalizar o vetor de direção
    ux = dx / length
    uy = dy / length
    
    # Vetor perpendicular (normal)
    vx = -uy
    vy = ux
    
    # Dimensões da ponta da seta proporcionais à espessura
    arrow_len = max(14, int(width * 4))
    arrow_width = max(8, int(width * 2.5))
    
    # Ponto de base da ponta da seta
    bx = x2 - arrow_len * ux
    by = y2 - arrow_len * uy
    
    # Vértices do triângulo da seta
    c1_x = bx + arrow_width * vx
    c1_y = by + arrow_width * vy
    c2_x = bx - arrow_width * vx
    c2_y = by - arrow_width * vy
    
    # Desenhar o triângulo (cabeça da seta)
    draw.polygon([(c1_x, c1_y), (x2, y2), (c2_x, c2_y)], fill=color)


def get_annotated_image(step, num_arrows=True) -> Image.Image:
    """
    Retorna uma cópia da imagem do passo com as anotações fundidas nela.
    """
    img_copy = step.image.copy()
    draw = ImageDraw.Draw(img_copy)
    
    arrow_count = 0
    for anno in step.annotations:
        atype = anno.get("type")
        color = anno.get("color", "#FF0000")
        
        if atype == "arrow":
            arrow_count += 1
            x1, y1 = anno["x1"], anno["y1"]
            x2, y2 = anno["x2"], anno["y2"]
            width = anno.get("width", 3)
            draw_arrow_on_pil(draw, x1, y1, x2, y2, color, width)
            
            if num_arrows:
                # Desenhar um círculo com o número sequencial no início da seta
                r = 12
                draw.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill="#ffffff", outline=color, width=2)
                font = get_system_font(13)
                txt = str(arrow_count)
                try:
                    # Pillow 8.0.0+
                    bbox = draw.textbbox((x1, y1), txt, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                except Exception:
                    tw, th = 8, 12
                draw.text((x1 - tw/2, y1 - th/2 - 2), txt, fill=color, font=font)
            
        elif atype == "text":
            x, y = anno["x"], anno["y"]
            size = anno.get("size", 16)
            font = get_system_font(size)
            
            # Obter o tamanho do texto para desenhar a caixa de fundo (caixa de texto real)
            try:
                # Pillow 8.0.0+
                bbox = draw.textbbox((x, y), anno["text"], font=font)
                rect_coords = [bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2]
                draw.rectangle(rect_coords, fill="#ffffff", outline=color, width=1)
            except Exception:
                try:
                    # Fallback para versões antigas de Pillow
                    w, h = draw.textsize(anno["text"], font=font)
                    draw.rectangle([x - 4, y - 2, x + w + 4, y + h + 2], fill="#ffffff", outline=color, width=1)
                except Exception:
                    pass # Sem fundo se falhar tudo
            
            draw.text((x, y), anno["text"], fill=color, font=font)
            
    return img_copy


def export_to_html(document, filepath):
    """
    Exporta o documento para um único arquivo HTML auto-contido com imagens base64.
    """
    html_content = []
    header_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__DOC_TITLE__</title>
    <style>
        body {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
            background-color: #f5f7fb;
            color: #333333;
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }
        .container {
            max-width: 1000px;
            margin: 40px auto;
            padding: 0 20px;
        }
        header {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            margin-bottom: 30px;
            border-left: 6px solid #1a73e8;
        }
        h1 {
            margin: 0 0 10px 0;
            color: #1a73e8;
            font-size: 28px;
        }
        .meta-info {
            color: #666666;
            font-size: 14px;
        }
        .step-card {
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            margin-bottom: 40px;
            overflow: hidden;
            border: 1px solid #eef2f6;
        }
        .step-header {
            background-color: #f8fafc;
            padding: 15px 25px;
            border-bottom: 1px solid #eef2f6;
            display: flex;
            align-items: center;
        }
        .step-number {
            background-color: #1a73e8;
            color: #ffffff;
            font-weight: bold;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            font-size: 14px;
        }
        .step-title {
            margin: 0;
            font-size: 18px;
            color: #2c3e50;
            font-weight: 600;
        }
        .step-body {
            padding: 25px;
        }
        .image-container {
            text-align: center;
            margin-bottom: 20px;
            background-color: #fcfcfc;
            border: 1px solid #f0f0f0;
            border-radius: 8px;
            padding: 10px;
        }
        .step-image {
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .step-description {
            font-size: 16px;
            color: #4a5568;
            white-space: pre-wrap;
            background-color: #fafbfc;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #b2ccd6;
            margin: 0;
        }
        footer {
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #888888;
            font-size: 13px;
            border-top: 1px solid #e2e8f0;
        }
        .footer-logo {
            display: block;
            margin: 10px auto;
            max-width: 80px;
            height: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>__DOC_TITLE__</h1>
            <div class="meta-info">__DOC_SUBTITLE__</div>
        </header>
"""
    # Exibir título do documento
    doc_title = getattr(document, "title", "Documentação de Processo ERP")
    doc_subtitle = getattr(document, "subtitle", "Documento gerado automaticamente pelo Documentador de Processos")
    header_html = header_html.replace("__DOC_TITLE__", doc_title)
    header_html = header_html.replace("__DOC_SUBTITLE__", doc_subtitle)
    html_content.append(header_html)

    for idx, step in enumerate(document.steps):
        # Obter imagem com anotações e converter para base64
        num_arrows = getattr(document, "num_arrows", True)
        ann_img = get_annotated_image(step, num_arrows)
        buffered = io.BytesIO()
        ann_img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        step_title = step.title if step.title else f"Passo {idx + 1}"
        description = step.description if step.description else "Nenhuma descrição fornecida."
        
        html_content.append(f"""
        <div class="step-card">
            <div class="step-header">
                <div class="step-number">{idx + 1}</div>
                <h2 class="step-title">{step_title}</h2>
            </div>
            <div class="step-body">
                <div class="image-container">
                    <img class="step-image" src="data:image/png;base64,{img_str}" alt="{step_title}">
                </div>
                <p class="step-description">{description}</p>
            </div>
        </div>
        """)

    # Converter logo.png para base64 para o rodapé do HTML
    logo_base64 = ""
    try:
        logo_path = utils.get_resource_path(os.path.join("img", "logo.png"))
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Erro ao carregar logo para HTML: {e}")
        
    from datetime import datetime
    current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    logo_img_tag = f'<img class="footer-logo" src="data:image/png;base64,{logo_base64}" alt="Logo I+documentador">' if logo_base64 else ''
    
    html_content.append(f"""
        <footer>
            <p>Gerado em: {current_date}</p>
            {logo_img_tag}
        </footer>
    </div>
</body>
</html>
""")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_content))


def export_to_svg(document, filepath):
    """
    Exporta todo o fluxo do documento em um único SVG compilado (passos dispostos verticalmente).
    As anotações continuam como elementos vetoriais SVG reais sobre o print.
    """
    svg_elements = []
    
    # Configurações de layout
    width = 1000  # Largura padrão das seções do SVG
    current_y = 20
    padding = 30
    
    # 0. Título e Subtítulo do Documento no topo do SVG
    doc_title = getattr(document, "title", "Documentação de Processo ERP")
    doc_subtitle = getattr(document, "subtitle", "Documento gerado automaticamente pelo Documentador de Processos")
    
    svg_elements.append(f'<text x="{padding}" y="{current_y + 30}" font-family="sans-serif" font-size="28" font-weight="bold" fill="#1a73e8">{doc_title}</text>')
    svg_elements.append(f'<text x="{padding}" y="{current_y + 55}" font-family="sans-serif" font-size="14" fill="#666666">{doc_subtitle}</text>')
    
    # Linha divisória após o cabeçalho
    current_y += 75
    svg_elements.append(f'<line x1="{padding}" y1="{current_y}" x2="{width - padding}" y2="{current_y}" stroke="#1a73e8" stroke-width="2" />')
    current_y += 30
    
    # Escrever cabeçalho do SVG temporário e acumular elementos
    for idx, step in enumerate(document.steps):
        # Converter imagem original do passo para base64
        # Não usamos get_annotated_image aqui pois as anotações serão vetoriais SVG!
        buffered = io.BytesIO()
        step.image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        ow, oh = step.image.size
        
        # Ajustar tamanho da imagem para caber na largura (mantendo a proporção) ou usar natural
        available_w = width - (padding * 2)
        if ow <= available_w:
            display_w = ow
            scale = 1.0
        else:
            display_w = available_w
            scale = display_w / ow
        display_h = oh * scale
        
        # 1. Título do Passo
        step_title = step.title if step.title else f"Passo {idx + 1}"
        svg_elements.append(f'<text x="{padding}" y="{current_y + 25}" font-family="sans-serif" font-size="22" font-weight="bold" fill="#1a73e8">{idx + 1}. {step_title}</text>')
        current_y += 40
        
        # 2. Imagem (Print)
        img_y = current_y
        svg_elements.append(f'<image href="data:image/png;base64,{img_str}" x="{padding}" y="{img_y}" width="{display_w}" height="{display_h}" />')
        
        # 3. Anotações vetoriais sobre a imagem
        arrow_count = 0
        for anno in step.annotations:
            atype = anno.get("type")
            color = anno.get("color", "#FF0000")
            
            if atype == "arrow":
                arrow_count += 1
                # Escalar coordenadas da imagem original para a exibição SVG
                ax1 = anno["x1"] * scale + padding
                ay1 = anno["y1"] * scale + img_y
                ax2 = anno["x2"] * scale + padding
                ay2 = anno["y2"] * scale + img_y
                awidth = anno.get("width", 3)
                
                # Desenhar linha
                svg_elements.append(f'<line x1="{ax1}" y1="{ay1}" x2="{ax2}" y2="{ay2}" stroke="{color}" stroke-width="{awidth}" />')
                
                # Desenhar cabeça de seta (polígono)
                dx = ax2 - ax1
                dy = ay2 - ay1
                length = (dx*dx + dy*dy)**0.5
                if length > 0:
                    ux, uy = dx / length, dy / length
                    vx, vy = -uy, ux
                    
                    arrow_len = max(14, int(awidth * 4))
                    arrow_width = max(8, int(awidth * 2.5))
                    
                    bx = ax2 - arrow_len * ux
                    by = ay2 - arrow_len * uy
                    
                    c1_x = bx + arrow_width * vx
                    c1_y = by + arrow_width * vy
                    c2_x = bx - arrow_width * vx
                    c2_y = by - arrow_width * vy
                    
                    svg_elements.append(f'<polygon points="{ax2},{ay2} {c1_x},{c1_y} {c2_x},{c2_y}" fill="{color}" />')
                    
                    # Desenhar numeração sequencial se ativado
                    if getattr(document, "num_arrows", True):
                        r = 10
                        svg_elements.append(f'<circle cx="{ax1}" cy="{ay1}" r="{r}" fill="#ffffff" stroke="{color}" stroke-width="2" />')
                        svg_elements.append(f'<text x="{ax1}" y="{ay1 + 4}" font-family="sans-serif" font-size="11" font-weight="bold" fill="{color}" text-anchor="middle">{arrow_count}</text>')
                    
            elif atype == "text":
                tx = anno["x"] * scale + padding
                ty = anno["y"] * scale + img_y
                tsize = anno.get("size", 16)
                # Escalar fonte ligeiramente para o SVG
                scaled_font_size = tsize * scale
                
                # Desenhar caixa de texto no SVG para legibilidade (caixa de texto real)
                text_len = len(anno["text"])
                box_w = text_len * scaled_font_size * 0.6 + 8
                box_h = scaled_font_size * 1.2 + 4
                svg_elements.append(f'<rect x="{tx - 4}" y="{ty}" width="{box_w}" height="{box_h}" fill="#ffffff" stroke="{color}" stroke-width="1" />')
                
                svg_elements.append(f'<text x="{tx}" y="{ty + scaled_font_size * 0.95}" font-family="sans-serif" font-size="{scaled_font_size}" font-weight="bold" fill="{color}">{anno["text"]}</text>')
                
        current_y += display_h + 20
        
        # 4. Descrição do Passo
        description = step.description if step.description else "Nenhuma descrição fornecida."
        # Quebrar texto de descrição manualmente para caber
        words = description.split()
        lines = []
        current_line = []
        for word in words:
            if len(" ".join(current_line + [word])) * 8 < display_w:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
            
        svg_elements.append(f'<rect x="{padding}" y="{current_y}" width="{display_w}" height="{len(lines)*20 + 20}" fill="#fafbfc" rx="5" stroke="#b2ccd6" stroke-width="2" />')
        
        for l_idx, line in enumerate(lines):
            svg_elements.append(f'<text x="{padding + 15}" y="{current_y + 25 + (l_idx * 20)}" font-family="sans-serif" font-size="14" fill="#4a5568">{line}</text>')
            
        current_y += (len(lines) * 20) + 50
        
        # Linha separadora entre passos
        if idx < len(document.steps) - 1:
            svg_elements.append(f'<line x1="{padding}" y1="{current_y}" x2="{width - padding}" y2="{current_y}" stroke="#eef2f6" stroke-width="2" />')
            current_y += 30

    # Converter logo.png para base64 para o rodapé do SVG
    logo_base64 = ""
    try:
        logo_path = utils.get_resource_path(os.path.join("img", "logo.png"))
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Erro ao carregar logo para SVG: {e}")

    # 5. Rodapé do SVG
    current_y += 20
    # Linha acima do rodapé
    svg_elements.append(f'<line x1="{padding}" y1="{current_y}" x2="{width - padding}" y2="{current_y}" stroke="#e2e8f0" stroke-width="1" />')
    current_y += 25
    
    # Data no rodapé
    from datetime import datetime
    current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    svg_elements.append(f'<text x="{padding}" y="{current_y}" font-family="sans-serif" font-size="11" fill="#718096">Gerado em: {current_date}</text>')
    
    # Logo do I+documentador no centro do rodapé
    if logo_base64:
        logo_w = 60
        logo_h = 15
        logo_x = (width / 2) - (logo_w / 2)
        logo_y = current_y - 12
        svg_elements.append(f'<image href="data:image/png;base64,{logo_base64}" x="{logo_x}" y="{logo_y}" width="{logo_w}" height="{logo_h}" />')
        
    current_y += 20

    # Adicionar cabeçalho do arquivo completo com a altura final ajustada
    header_svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {current_y}" width="{width}" height="{current_y}" style="background-color: #f5f7fb;">'
    svg_elements.insert(0, header_svg)
    svg_elements.append('</svg>')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(svg_elements))


def export_to_pdf(document, filepath):
    """
    Exporta o documento para PDF profissional usando a biblioteca reportlab.
    Caso o reportlab não esteja disponível, retorna Falso.
    """
    if not REPORTLAB_AVAILABLE:
        return False
        
    # Criar documento PDF com margens
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=60
    )
    
    styles = getSampleStyleSheet()
    
    # Criar estilos personalizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1a73e8'),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#666666'),
        spaceAfter=30
    )
    
    step_title_style = ParagraphStyle(
        'StepTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceBefore=10,
        spaceAfter=10
    )
    
    description_style = ParagraphStyle(
        'StepDescription',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#4a5568'),
        spaceBefore=10,
        spaceAfter=10
    )

    story = []
    
    # 1. Título do Documento
    doc_title = getattr(document, "title", "Documentação de Processo ERP")
    doc_subtitle = getattr(document, "subtitle", "Documento gerado automaticamente pelo Documentador de Processos")
    story.append(Paragraph(doc_title, title_style))
    story.append(Paragraph(doc_subtitle, subtitle_style))
    
    # Largura disponível da página A4
    # A4 = 595.27 x 841.89 pontos
    available_width = doc.width  # Cerca de 515 pontos
    
    # Usar diretório temporário para gerar imagens anexadas
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, step in enumerate(document.steps):
            step_story = []
            
            # Título do Passo
            step_title = step.title if step.title else f"Passo {idx + 1}"
            step_story.append(Paragraph(f"Passo {idx + 1}: {step_title}", step_title_style))
            
            # Imagem do Passo fundida com anotações
            num_arrows = getattr(document, "num_arrows", True)
            ann_img = get_annotated_image(step, num_arrows)
            ow, oh = ann_img.size
            
            # Converter pixels para pontos (ex: 96 DPI -> 1 pixel = 0.75 pontos)
            pixel_scale = 0.75
            natural_w = ow * pixel_scale
            natural_h = oh * pixel_scale
            
            if natural_w <= available_width:
                display_w = natural_w
                display_h = natural_h
            else:
                scale = available_width / ow
                display_w = available_width
                display_h = oh * scale
            
            # Se for muito alta para caber na página com margens, limitar pela altura
            max_height = 420  # Cerca de metade de uma página A4
            if display_h > max_height:
                scale = max_height / oh
                display_w = ow * scale
                display_h = max_height
                
            tmp_img_path = os.path.join(tmpdir, f"step_{idx}.png")
            ann_img.save(tmp_img_path)
            
            rl_img = RLImage(tmp_img_path, width=display_w, height=display_h)
            rl_img.hAlign = 'LEFT'
            step_story.append(rl_img)
            step_story.append(Spacer(1, 10))
            
            # Descrição do Passo
            description = step.description if step.description else "Nenhuma descrição fornecida."
            # Substituir quebras de linha por tag <br/> para o ReportLab Paragraph
            formatted_description = description.replace('\n', '<br/>')
            step_story.append(Paragraph(formatted_description, description_style))
            
            # Agrupar elementos de cada passo para evitar quebras estranhas entre páginas
            story.append(KeepTogether(step_story))
            
            if idx < len(document.steps) - 1:
                story.append(Spacer(1, 20))
                
        # Função de desenho do rodapé
        def draw_footer(canvas, pdf_doc):
            canvas.saveState()
            
            # Obter data atual formatada
            from datetime import datetime
            current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            # Fazer linha separadora acima do rodapé
            canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
            canvas.setLineWidth(0.5)
            canvas.line(40, 45, pdf_doc.pagesize[0] - 40, 45)
            
            # Configurar fonte do rodapé
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.HexColor('#718096'))
            
            # Desenhar data e número de página
            canvas.drawString(40, 30, f"Gerado em: {current_date}")
            canvas.drawRightString(pdf_doc.pagesize[0] - 40, 30, f"Página {pdf_doc.page}")
            
            # Adicionar o logo do rodapé
            try:
                logo_path = utils.get_resource_path(os.path.join("img", "logo.png"))
                if os.path.exists(logo_path):
                    # A4 width = 595.27. Centro = 297.63. Logo width = 60, height = 15
                    canvas.drawImage(logo_path, 267.63, 23, width=60, height=15, mask='auto')
            except Exception as e:
                print(f"Erro ao adicionar logo ao rodapé do PDF: {e}")
                
            canvas.restoreState()

        # Construir o PDF
        doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
        
    return True
