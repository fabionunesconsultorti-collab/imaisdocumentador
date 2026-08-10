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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, KeepTogether, Flowable, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


if REPORTLAB_AVAILABLE:
    class PageMarker(Flowable):
        def __init__(self, step_index, page_tracker):
            super().__init__()
            self.step_index = step_index
            self.page_tracker = page_tracker
            
        def wrap(self, availWidth, availHeight):
            return 0, 0
            
        def draw(self):
            # Registrar a página atual no dicionário compartilhado
            self.page_tracker[self.step_index] = self.canv.getPageNumber()
else:
    class PageMarker:
        pass


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


def parse_description_to_html(description):
    """
    Analisa marcações na descrição e as converte em elementos HTML formatados e callouts.
    """
    if not description:
        return ""
        
    import html
    import re
    
    # 1. Escapar HTML para evitar XSS e quebra de layout
    text = html.escape(description)
    
    # 2. Negritos: **texto** -> <strong>texto</strong>
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text, flags=re.DOTALL)
    
    # 3. Grifados: ==texto== -> <mark>texto</mark>
    text = re.sub(r"==(.*?)==", r'<mark style="background-color: #fef08a; padding: 2px 4px; border-radius: 4px; color: #0f172a; font-weight: 500;">\1</mark>', text, flags=re.DOTALL)
    
    # 4. Adesivos (Callouts)
    # Emojis/SVG podem ser inline. Vamos usar SVGs inline elegantes de tamanho 20px
    # Para Atenção
    def replace_attention(match):
        content = match.group(1).strip()
        return f'<div class="flag-callout flag-attention">⚠️ <strong>[ATENÇÃO]</strong> {content}</div>'
        
    text = re.sub(r"\[atenção\](.*?)\[/atenção\]", replace_attention, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[atencao\](.*?)\[/atencao\]", replace_attention, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Para Observação
    def replace_observation(match):
        content = match.group(1).strip()
        return f'<div class="flag-callout flag-observation">ℹ️ <strong>[OBSERVAÇÃO]</strong> {content}</div>'
        
    text = re.sub(r"\[observação\](.*?)\[/observação\]", replace_observation, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[observacao\](.*?)\[/observacao\]", replace_observation, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Para Conceito
    def replace_concept(match):
        content = match.group(1).strip()
        return f'<div class="flag-callout flag-concept">💡 <strong>[CONCEITO]</strong> {content}</div>'
        
    text = re.sub(r"\[conceito\](.*?)\[/conceito\]", replace_concept, text, flags=re.DOTALL | re.IGNORECASE)
    
    # 5. Converter quebras de linha para <br/>
    text = text.replace("\n", "<br/>")
    return text


def parse_description_to_pdf_flowables(description, description_style, available_width):
    """
    Analisa a descrição e retorna uma lista de Flowables (Paragraphs e Tables para os adesivos).
    """
    if not description:
        return []
        
    import re
    import html
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    
    # 1. Separar o texto em blocos de texto comum e blocos de adesivos (flags)
    pattern = r"(\[(?:atenção|atencao|observação|observacao|conceito)\].*?\[/(?:atenção|atencao|observação|observacao|conceito)\])"
    parts = re.split(pattern, description, flags=re.DOTALL | re.IGNORECASE)
    
    flowables = []
    
    for part in parts:
        if not part:
            continue
            
        # Verificar se a parte é um adesivo
        match_att = re.match(r"\[(?:atenção|atencao)\](.*?)\[/(?:atenção|atencao)\]", part, re.DOTALL | re.IGNORECASE)
        match_obs = re.match(r"\[(?:observação|observacao)\](.*?)\[/(?:observação|observacao)\]", part, re.DOTALL | re.IGNORECASE)
        match_con = re.match(r"\[conceito\](.*?)\[/conceito\]", part, re.DOTALL | re.IGNORECASE)
        
        if match_att or match_obs or match_con:
            # Identificar o tipo do adesivo, cores e rótulo
            if match_att:
                tag_type = "ATENÇÃO"
                content = match_att.group(1).strip()
                bg_color = colors.HexColor("#fdf2f2")
                border_color = colors.HexColor("#ef4444")
                text_color = colors.HexColor("#991b1b")
                emoji_char = "⚠️"
            elif match_obs:
                tag_type = "OBSERVAÇÃO"
                content = match_obs.group(1).strip()
                bg_color = colors.HexColor("#f0f9ff")
                border_color = colors.HexColor("#0ea5e9")
                text_color = colors.HexColor("#075985")
                emoji_char = "ℹ️"
            else:
                tag_type = "CONCEITO"
                content = match_con.group(1).strip()
                bg_color = colors.HexColor("#f0fdf4")
                border_color = colors.HexColor("#10b981")
                text_color = colors.HexColor("#166534")
                emoji_char = "💡"
                
            # Tratar formatação interna (negrito e grifado)
            content_escaped = html.escape(content)
            content_formatted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", content_escaped, flags=re.DOTALL)
            content_formatted = re.sub(r"==(.*?)==", r'<font backcolor="#fef08a">\1</font>', content_formatted, flags=re.DOTALL)
            content_formatted = content_formatted.replace("\n", "<br/>")
            
            # Montar o parágrafo de texto simples do callout
            callout_text = f"<b>{emoji_char} [{tag_type}]</b> {content_formatted}"
            callout_style = ParagraphStyle(
                'CalloutText',
                parent=description_style,
                textColor=text_color,
                backColor=bg_color,
                borderPadding=8,
                spaceBefore=8,
                spaceAfter=8
            )
            p = Paragraph(callout_text, callout_style)
            
            flowables.append(p)
            flowables.append(Spacer(1, 10))
        else:
            # Texto comum
            text_escaped = html.escape(part.strip())
            if not text_escaped:
                continue
            text_formatted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text_escaped, flags=re.DOTALL)
            text_formatted = re.sub(r"==(.*?)==", r'<font backcolor="#fef08a">\1</font>', text_formatted, flags=re.DOTALL)
            text_formatted = text_formatted.replace("\n", "<br/>")
            
            p = Paragraph(text_formatted, description_style)
            flowables.append(p)
            flowables.append(Spacer(1, 10))
            
    # Remover o último Spacer desnecessário
    if flowables and isinstance(flowables[-1], Spacer):
        flowables.pop()
        
    return flowables


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
        .flag-callout {
            display: flex;
            align-items: flex-start;
            padding: 12px 16px;
            border-radius: 6px;
            margin: 15px 0;
            white-space: normal;
            border-left: 4px solid;
            font-size: 14px;
        }
        .flag-callout strong {
            display: block;
            margin-bottom: 4px;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .flag-attention {
            background-color: #fdf2f2;
            border-left-color: #ef4444;
            color: #991b1b;
        }
        .flag-observation {
            background-color: #f0f9ff;
            border-left-color: #0ea5e9;
            color: #075985;
        }
        .flag-concept {
            background-color: #f0fdf4;
            border-left-color: #10b981;
            color: #166534;
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
        parsed_description = parse_description_to_html(description)
        
        # Anexos do passo
        attachments_html = ""
        attachments = getattr(step, "attachments", [])
        if attachments:
            att_chips = []
            for att in attachments:
                att_name = att["filename"]
                att_b64 = base64.b64encode(att["data"]).decode("utf-8")
                download_link = f"data:application/octet-stream;base64,{att_b64}"
                att_chips.append(f'<a href="{download_link}" download="{att_name}" style="display: inline-flex; align-items: center; background-color: #e2e8f0; color: #475569; padding: 4px 10px; border-radius: 9999px; text-decoration: none; font-size: 13px; font-weight: 500; margin-right: 8px; margin-bottom: 8px; transition: background-color 0.2s;"><span style="margin-right: 4px;">📎</span> {att_name}</a>')
            
            attachments_html = f"""
            <div style="margin-top: 15px; border-top: 1px solid #eef2f6; padding-top: 15px;">
                <span style="font-weight: 600; font-size: 13px; color: #64748b; display: block; margin-bottom: 8px;">Arquivos Anexados:</span>
                <div style="display: flex; flex-wrap: wrap;">
                    {"".join(att_chips)}
                </div>
            </div>
            """
            
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
                <div class="step-description">{parsed_description}</div>
                {attachments_html}
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
    Exporta o documento para PDF profissional usando a biblioteca reportlab,
    incluindo um Sumário automático de passos.
    Caso o reportlab não esteja disponível, retorna Falso.
    """
    if not REPORTLAB_AVAILABLE:
        return False
        
    styles = getSampleStyleSheet()
    
    # Largura disponível da página A4 (595.27 x 841.89 pontos)
    # Margens: 40 pontos -> Largura = 515.27
    available_width = 515.27
    
    # 1. Função auxiliar para desenhar o rodapé (com número de páginas e data)
    def draw_footer(canvas, pdf_doc):
        canvas.saveState()
        from datetime import datetime
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
        canvas.setLineWidth(0.5)
        canvas.line(40, 45, pdf_doc.pagesize[0] - 40, 45)
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#718096'))
        
        canvas.drawString(40, 30, f"Gerado em: {current_date}")
        canvas.drawRightString(pdf_doc.pagesize[0] - 40, 30, f"Página {pdf_doc.page}")
        
        try:
            logo_path = utils.get_resource_path(os.path.join("img", "logo.png"))
            if os.path.exists(logo_path):
                canvas.drawImage(logo_path, 267.63, 23, width=60, height=15, mask='auto')
        except Exception as e:
            print(f"Erro ao adicionar logo ao rodapé do PDF: {e}")
            
        canvas.restoreState()

    # 2. Função auxiliar para construir o "story" baseado nos números de páginas conhecidos
    def build_pdf_story(doc_obj, page_tracker_dict, tmpdir):
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
            spaceAfter=15
        )

        meta_style = ParagraphStyle(
            'DocMeta',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=10,
            textColor=colors.HexColor('#4a5568'),
            spaceAfter=25
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
        
        story_list = []
        
        # Título do Documento
        doc_title = getattr(document, "title", "Documentação de Processo ERP")
        doc_subtitle = getattr(document, "subtitle", "Documento gerado automaticamente pelo Documentador de Processos")
        story_list.append(Paragraph(doc_title, title_style))
        story_list.append(Paragraph(doc_subtitle, subtitle_style))
        
        # Metadados
        category = getattr(document, "category", "")
        author = getattr(document, "author", "")
        meta_parts = []
        if category:
            meta_parts.append(f"<b>Categoria:</b> {category}")
        if author:
            meta_parts.append(f"<b>Autor:</b> {author}")
        from datetime import datetime
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        meta_parts.append(f"<b>Data:</b> {current_date}")
        meta_html = " | ".join(meta_parts)
        story_list.append(Paragraph(meta_html, meta_style))
        
        # Sumário
        toc_data = []
        toc_data.append([Paragraph("<b>Sumário da Documentação</b>", step_title_style), ""])
        
        for idx, step in enumerate(document.steps):
            step_title = step.title if step.title else f"Passo {idx + 1}"
            page_num = page_tracker_dict.get(idx, "--")
            page_str = f"Página {page_num}" if page_num != "--" else "--"
            
            toc_text = f"<b>Passo {idx + 1}:</b> {step_title}"
            toc_data.append([Paragraph(toc_text, description_style), page_str])
            
        toc_table = Table(toc_data, colWidths=[available_width - 60, 60])
        toc_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#1a73e8')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story_list.append(toc_table)
        story_list.append(PageBreak())
        
        # Passos
        for idx, step in enumerate(document.steps):
            step_story = []
            
            # Marcador de página
            step_story.append(PageMarker(idx, page_tracker_dict))
            
            # Título do Passo
            step_title = step.title if step.title else f"Passo {idx + 1}"
            step_story.append(Paragraph(f"Passo {idx + 1}: {step_title}", step_title_style))
            
            # Imagem do Passo
            num_arrows = getattr(document, "num_arrows", True)
            ann_img = get_annotated_image(step, num_arrows)
            ow, oh = ann_img.size
            
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
                
            max_height = 420
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
            
            # Anexos do Passo
            attachments = getattr(step, "attachments", [])
            if attachments:
                att_names = ", ".join([att["filename"] for att in attachments])
                description += f"\n\n**📎 Arquivos Anexados:** {att_names}"
                
            desc_flowables = parse_description_to_pdf_flowables(description, description_style, available_width)
            step_story.extend(desc_flowables)
            story_list.append(KeepTogether(step_story))
            
            if idx < len(document.steps) - 1:
                story_list.append(Spacer(1, 20))
                
        return story_list

    # 3. Execução das duas passadas usando diretório temporário para as imagens
    with tempfile.TemporaryDirectory() as tmpdir:
        # Passada 1: Gravar em buffer temporário para descobrir as páginas
        page_tracker = {}
        # Iniciar dicionário com placeholders
        for idx in range(len(document.steps)):
            page_tracker[idx] = "--"
            
        temp_buffer = io.BytesIO()
        doc_temp = SimpleDocTemplate(
            temp_buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=60
        )
        story_temp = build_pdf_story(doc_temp, page_tracker, tmpdir)
        doc_temp.build(story_temp, onFirstPage=draw_footer, onLaterPages=draw_footer)
        
        # Passada 2: Renderizar o PDF real com as páginas corretas detectadas
        doc_final = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=60
        )
        story_final = build_pdf_story(doc_final, page_tracker, tmpdir)
        doc_final.build(story_final, onFirstPage=draw_footer, onLaterPages=draw_footer)
        
    return True


def slugify(value):
    import re
    import unicodedata
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)


def export_to_wiki_repository(documents, output_dir):
    """
    Compila uma lista de objetos Document em um repositório Wiki estático organizado.
    """
    import shutil
    import json
    from datetime import datetime
    
    # 1. Criar estrutura de diretórios
    docs_dir = os.path.join(output_dir, "docs")
    img_dir = os.path.join(output_dir, "img")
    att_dir = os.path.join(output_dir, "attachments")
    css_dir = os.path.join(output_dir, "css")
    js_dir = os.path.join(output_dir, "js")
    
    for d in [output_dir, docs_dir, img_dir, att_dir, css_dir, js_dir]:
        os.makedirs(d, exist_ok=True)
        
    # 2. Copiar logos/ícones do sistema
    logo_filename = ""
    try:
        logo_path = utils.get_resource_path(os.path.join("img", "logo.png"))
        if os.path.exists(logo_path):
            shutil.copy(logo_path, os.path.join(img_dir, "logo.png"))
            logo_filename = "logo.png"
    except Exception as e:
        print(f"Erro ao copiar logo para Wiki: {e}")
        
    try:
        icon_path = utils.get_resource_path(os.path.join("img", "icone.png"))
        if os.path.exists(icon_path):
            shutil.copy(icon_path, os.path.join(img_dir, "icone.png"))
    except Exception as e:
        print(f"Erro ao copiar icone para Wiki: {e}")
        
    # Processar cada documento
    compiled_docs = []
    
    for doc_idx, doc in enumerate(documents):
        raw_title = getattr(doc, "title", f"Documento_{doc_idx + 1}")
        doc_slug = slugify(raw_title)
        # Garantir slug única
        if any(d["slug"] == doc_slug for d in compiled_docs):
            doc_slug = f"{doc_slug}-{doc_idx}"
            
        doc_subtitle = getattr(doc, "subtitle", "")
        category = getattr(doc, "category", "")
        tags = getattr(doc, "tags", "")
        author = getattr(doc, "author", "")
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Mapear passos do documento
        steps_data = []
        for idx, step in enumerate(doc.steps):
            step_title = step.title if step.title else f"Passo {idx + 1}"
            step_desc = step.description if step.description else ""
            
            # Gerar imagem anotada
            num_arrows = getattr(doc, "num_arrows", True)
            ann_img = get_annotated_image(step, num_arrows)
            img_filename = f"step_{doc_slug}_{idx}.png"
            ann_img.save(os.path.join(img_dir, img_filename))
            
            # Exportar anexos
            step_attachments = []
            attachments = getattr(step, "attachments", [])
            if attachments:
                doc_att_dir = os.path.join(att_dir, doc_slug)
                os.makedirs(doc_att_dir, exist_ok=True)
                for att in attachments:
                    att_filename = att["filename"]
                    att_filepath = os.path.join(doc_att_dir, att_filename)
                    with open(att_filepath, "wb") as f:
                        f.write(att["data"])
                    step_attachments.append({
                        "filename": att_filename,
                        "rel_path": f"attachments/{doc_slug}/{att_filename}"
                    })
                    
            steps_data.append({
                "title": step_title,
                "description": step_desc,
                "image": f"img/{img_filename}",
                "attachments": step_attachments
            })
            
        compiled_docs.append({
            "slug": doc_slug,
            "title": raw_title,
            "subtitle": doc_subtitle,
            "category": category,
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
            "author": author,
            "date": current_date,
            "steps": steps_data
        })
        
    # 3. Gerar arquivos estáticos
    
    # 3.1 style.css (sober, premium, Dark/Light Mode)
    style_content = """/* Variables */
:root {
    --bg-primary: #f8fafc;
    --bg-card: #ffffff;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #64748b;
    --accent: #1a73e8;
    --accent-hover: #1557b0;
    --border: #e2e8f0;
    --header-bg: #ffffff;
    --sidebar-bg: #f8fafc;
    --tag-bg: #f1f5f9;
    --tag-text: #475569;
    --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
    --font-stack: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

[data-theme="dark"] {
    --bg-primary: #0f172a;
    --bg-card: #1e293b;
    --text-primary: #f8fafc;
    --text-secondary: #cbd5e1;
    --text-muted: #94a3b8;
    --accent: #3b82f6;
    --accent-hover: #60a5fa;
    --border: #334155;
    --header-bg: #1e293b;
    --sidebar-bg: #1e293b;
    --tag-bg: #334155;
    --tag-text: #cbd5e1;
    --shadow: 0 10px 15px -3px rgb(0 0 0 / 0.3);
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-stack);
    line-height: 1.6;
    transition: background-color 0.3s, color 0.3s;
}

header {
    background-color: var(--header-bg);
    border-bottom: 1px solid var(--border);
    padding: 1rem 2rem;
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: var(--shadow);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.header-logo {
    max-height: 32px;
}

.header-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent);
    text-decoration: none;
}

.theme-toggle-btn {
    background-color: var(--tag-bg);
    color: var(--tag-text);
    border: 1px solid var(--border);
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.875rem;
    transition: background-color 0.2s, border-color 0.2s;
}

.theme-toggle-btn:hover {
    background-color: var(--border);
}

.container {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 1.5rem;
}

/* Dashboard Style */
.dashboard-hero {
    margin-bottom: 2rem;
    text-align: center;
}

.dashboard-hero h1 {
    font-size: 2.5rem;
    color: var(--accent);
    margin-bottom: 8px;
}

.dashboard-hero p {
    color: var(--text-secondary);
}

.search-filters-bar {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
}

.search-wrapper {
    flex: 2;
    min-width: 250px;
    position: relative;
}

.search-input {
    width: 100%;
    padding: 10px 15px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.95rem;
    outline: none;
}

.search-input:focus {
    border-color: var(--accent);
}

.filter-wrapper {
    flex: 1;
    min-width: 180px;
}

.filter-select {
    width: 100%;
    padding: 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.95rem;
    outline: none;
    cursor: pointer;
}

.docs-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;
}

.doc-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.2s, box-shadow 0.2s;
    text-decoration: none;
    color: inherit;
}

.doc-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 20px -5px rgb(0 0 0 / 0.1);
    border-color: var(--accent);
}

.doc-card-header {
    margin-bottom: 15px;
}

.doc-category {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 4px;
    display: block;
}

.doc-card-title {
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 6px;
}

.doc-card-subtitle {
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.doc-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
}

.doc-tag {
    background-color: var(--tag-bg);
    color: var(--tag-text);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
}

.doc-card-footer {
    border-top: 1px solid var(--border);
    padding-top: 10px;
    margin-top: 15px;
    font-size: 0.8rem;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Wiki Page layout */
.wiki-layout {
    display: flex;
    gap: 30px;
    margin: 2rem auto;
    max-width: 1200px;
    padding: 0 1.5rem;
}

.wiki-sidebar {
    width: 260px;
    position: sticky;
    top: 5rem;
    height: calc(100vh - 7rem);
    overflow-y: auto;
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
    box-shadow: var(--shadow);
}

.wiki-sidebar-title {
    font-size: 0.9rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 10px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
}

.wiki-sidebar-list {
    list-style: none;
}

.wiki-sidebar-item {
    margin-bottom: 6px;
}

.wiki-sidebar-link {
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 0.925rem;
    display: block;
    padding: 6px 10px;
    border-radius: 4px;
    transition: background-color 0.15s, color 0.15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.wiki-sidebar-link:hover {
    background-color: var(--tag-bg);
    color: var(--accent);
}

.wiki-content {
    flex: 1;
    min-width: 0;
}

.wiki-doc-header {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
}

.wiki-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    color: var(--text-muted);
    font-size: 0.875rem;
    margin-top: 15px;
    border-top: 1px solid var(--border);
    padding-top: 10px;
}

.step-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
    overflow: hidden;
}

.step-header {
    background-color: var(--tag-bg);
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 12px;
}

.step-number {
    background-color: var(--accent);
    color: #ffffff;
    font-weight: 700;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
}

.step-title {
    font-size: 1.125rem;
    font-weight: 700;
}

.step-body {
    padding: 1.5rem;
}

.image-container {
    text-align: center;
    margin-bottom: 1.25rem;
    background-color: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px;
}

.step-image {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
}

.step-description {
    color: var(--text-secondary);
    white-space: pre-wrap;
    background-color: var(--bg-primary);
    padding: 15px 20px;
    border-radius: 6px;
    border-left: 4px solid var(--accent);
}
.flag-callout {
    display: flex;
    align-items: flex-start;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 15px 0;
    white-space: normal;
    border-left: 4px solid;
    font-size: 14px;
}
.flag-callout strong {
    display: block;
    margin-bottom: 4px;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.flag-attention {
    background-color: #fdf2f2;
    border-left-color: #ef4444;
    color: #991b1b;
}
.flag-observation {
    background-color: #f0f9ff;
    border-left-color: #0ea5e9;
    color: #075985;
}
.flag-concept {
    background-color: #f0fdf4;
    border-left-color: #10b981;
    color: #166534;
}

.attachments-section {
    margin-top: 1.25rem;
    border-top: 1px solid var(--border);
    padding-top: 12px;
}

.attachments-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--text-muted);
    margin-bottom: 8px;
    display: block;
}

.attachment-chip {
    display: inline-flex;
    align-items: center;
    background-color: var(--tag-bg);
    color: var(--tag-text);
    padding: 4px 12px;
    border-radius: 20px;
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 600;
    margin-right: 8px;
    margin-bottom: 8px;
    border: 1px solid var(--border);
    transition: background-color 0.15s;
}

.attachment-chip:hover {
    background-color: var(--border);
    color: var(--accent);
}

/* Print Friendly Styles */
@media print {
    body {
        background-color: #ffffff;
        color: #000000;
    }
    header, .wiki-sidebar, .theme-toggle-btn, .attachments-section {
        display: none !important;
    }
    .wiki-layout {
        display: block;
        margin: 0;
        padding: 0;
    }
    .wiki-content {
        width: 100%;
    }
    .step-card {
        box-shadow: none;
        border: 1px solid #000000;
        page-break-inside: avoid;
    }
    .step-header {
        background-color: #f1f5f9 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
}
"""
    with open(os.path.join(css_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(style_content)
        
    # 3.2 js/wiki.js
    js_content = """document.addEventListener('DOMContentLoaded', () => {
    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    const currentTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    if (themeToggle) {
        themeToggle.textContent = currentTheme === 'dark' ? '☀️ Modo Claro' : '🌙 Modo Escuro';
        themeToggle.addEventListener('click', () => {
            const theme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
            themeToggle.textContent = theme === 'dark' ? '☀️ Modo Claro' : '🌙 Modo Escuro';
        });
    }

    // Search and Filters in Dashboard
    const searchInput = document.getElementById('search-input');
    const categoryFilter = document.getElementById('category-filter');
    const authorFilter = document.getElementById('author-filter');
    const cards = document.querySelectorAll('.doc-card');

    function filterCards() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const selectedCategory = categoryFilter ? categoryFilter.value : '';
        const selectedAuthor = authorFilter ? authorFilter.value : '';

        cards.forEach(card => {
            const title = card.dataset.title.toLowerCase();
            const subtitle = card.dataset.subtitle.toLowerCase();
            const category = card.dataset.category;
            const author = card.dataset.author;
            const tags = card.dataset.tags.toLowerCase();
            const stepsContent = card.dataset.stepsContent.toLowerCase();

            const matchesQuery = query === '' || 
                title.includes(query) || 
                subtitle.includes(query) || 
                tags.includes(query) || 
                stepsContent.includes(query);

            const matchesCategory = selectedCategory === '' || category === selectedCategory;
            const matchesAuthor = selectedAuthor === '' || author === selectedAuthor;

            if (matchesQuery && matchesCategory && matchesAuthor) {
                card.style.display = 'flex';
            } else {
                card.style.display = 'none';
            }
        });
    }

    if (searchInput) searchInput.addEventListener('input', filterCards);
    if (categoryFilter) categoryFilter.addEventListener('change', filterCards);
    if (authorFilter) authorFilter.addEventListener('change', filterCards);
});
"""
    with open(os.path.join(js_dir, "wiki.js"), "w", encoding="utf-8") as f:
        f.write(js_content)
        
    # 3.3 index.html (Dashboard)
    categories = sorted(list(set([d["category"] for d in compiled_docs if d["category"]])))
    authors = sorted(list(set([d["author"] for d in compiled_docs if d["author"]])))
    
    cat_options = "\n".join([f'<option value="{c}">{c}</option>' for c in categories])
    aut_options = "\n".join([f'<option value="{a}">{a}</option>' for a in authors])
    
    cards_html = []
    for d in compiled_docs:
        tags_html = "\n".join([f'<span class="doc-tag">{t}</span>' for t in d["tags"]])
        steps_content = " ".join([s["title"] + " " + s["description"] for s in d["steps"]])
        
        # Obter número de anexos total
        total_attachments = sum([len(s["attachments"]) for s in d["steps"]])
        attachments_str = f" • 📎 {total_attachments} anexos" if total_attachments > 0 else ""
        
        cards_html.append(f"""
        <a href="docs/{d["slug"]}.html" class="doc-card" 
           data-title="{d["title"]}" 
           data-subtitle="{d["subtitle"]}" 
           data-category="{d["category"]}" 
           data-author="{d["author"]}" 
           data-tags="{",".join(d["tags"])}"
           data-steps-content="{steps_content.replace('"', '&quot;')}">
            <div class="doc-card-header">
                <span class="doc-category">{d["category"] if d["category"] else "Geral"}</span>
                <h2 class="doc-card-title">{d["title"]}</h2>
                <p class="doc-card-subtitle">{d["subtitle"]}</p>
                <div class="doc-tags">
                    {tags_html}
                </div>
            </div>
            <div class="doc-card-footer">
                <span>👤 {d["author"] if d["author"] else "Sem autor"}</span>
                <span>⏱️ {len(d["steps"])} passos{attachments_str}</span>
            </div>
        </a>
        """)
        
    logo_tag = f'<img src="img/{logo_filename}" alt="Logo" class="header-logo">' if logo_filename else ''
    
    index_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Repositório de Documentações</title>
    <link rel="stylesheet" href="css/style.css">
    <link rel="icon" type="image/png" href="img/icone.png">
</head>
<body>
    <header>
        <div class="header-left">
            {logo_tag}
            <span class="header-title">Wiki de Documentações</span>
        </div>
        <button id="theme-toggle" class="theme-toggle-btn">🌙 Modo Escuro</button>
    </header>
    
    <main class="container">
        <div class="dashboard-hero">
            <h1>Acervo de Processos</h1>
            <p>Consulte e explore todos os manuais e documentações ERP cadastrados.</p>
        </div>
        
        <div class="search-filters-bar">
            <div class="search-wrapper">
                <input type="text" id="search-input" class="search-input" placeholder="Pesquisar por título, tags ou conteúdo dos passos...">
            </div>
            
            <div class="filter-wrapper">
                <select id="category-filter" class="filter-select">
                    <option value="">Todas as Categorias</option>
                    {cat_options}
                </select>
            </div>
            
            <div class="filter-wrapper">
                <select id="author-filter" class="filter-select">
                    <option value="">Todos os Autores</option>
                    {aut_options}
                </select>
            </div>
        </div>
        
        <div class="docs-grid">
            {"".join(cards_html) if cards_html else "<p>Nenhuma documentação cadastrada.</p>"}
        </div>
    </main>
    
    <script src="js/wiki.js"></script>
</body>
</html>
"""
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
        
    # 3.4 docs/{slug}.html
    for d in compiled_docs:
        sidebar_items = []
        for idx, s in enumerate(d["steps"]):
            sidebar_items.append(f"""
            <li class="wiki-sidebar-item">
                <a href="#passo-{idx + 1}" class="wiki-sidebar-link" title="{s["title"]}">
                    {idx + 1}. {s["title"]}
                </a>
            </li>
            """)
            
        steps_cards = []
        for idx, s in enumerate(d["steps"]):
            parsed_description = parse_description_to_html(s["description"])
            att_chips = []
            for att in s["attachments"]:
                att_chips.append(f"""
                <a href="../{att["rel_path"]}" download="{att["filename"]}" class="attachment-chip">
                    <span>📎</span> {att["filename"]}
                </a>
                """)
                
            att_section = ""
            if att_chips:
                att_section = f"""
                <div class="attachments-section">
                    <span class="attachments-title">Arquivos Anexados:</span>
                    <div style="display: flex; flex-wrap: wrap;">
                        {"".join(att_chips)}
                    </div>
                </div>
                """
                
            steps_cards.append(f"""
            <div class="step-card" id="passo-{idx + 1}">
                <div class="step-header">
                    <div class="step-number">{idx + 1}</div>
                    <h2 class="step-title">{s["title"]}</h2>
                </div>
                <div class="step-body">
                    <div class="image-container">
                        <img class="step-image" src="../{s["image"]}" alt="{s["title"]}" loading="lazy">
                    </div>
                    <div class="step-description">{parsed_description}</div>
                    {att_section}
                </div>
            </div>
            """)
            
        logo_tag_doc = f'<img src="../img/{logo_filename}" alt="Logo" class="header-logo">' if logo_filename else ''
        
        tags_doc_html = "\n".join([f'<span class="doc-tag">{t}</span>' for t in d["tags"]])
        
        meta_html_doc = []
        if d["category"]:
            meta_html_doc.append(f"<span>📁 Categoria: <b>{d["category"]}</b></span>")
        if d["author"]:
            meta_html_doc.append(f"<span>👤 Autor: <b>{d["author"]}</b></span>")
        meta_html_doc.append(f"<span>⏱️ Publicado em: {d["date"]}</span>")
        
        doc_html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{d["title"]}</title>
    <link rel="stylesheet" href="../css/style.css">
    <link rel="icon" type="image/png" href="../img/icone.png">
</head>
<body>
    <header>
        <div class="header-left">
            {logo_tag_doc}
            <a href="../index.html" class="header-title" style="font-size: 0.95rem; text-decoration: underline;">← Voltar ao Portfólio</a>
        </div>
        <button id="theme-toggle" class="theme-toggle-btn">Modo Escuro</button>
    </header>
    
    <div class="wiki-layout">
        <aside class="wiki-sidebar">
            <h3 class="wiki-sidebar-title">Índice do Manual</h3>
            <ul class="wiki-sidebar-list">
                {'\n'.join(sidebar_items)}
            </ul>
        </aside>
        
        <main class="wiki-content">
            <div class="wiki-doc-header">
                <h1>{d["title"]}</h1>
                <p style="font-size: 1.1rem; color: var(--text-secondary); margin-top: 8px;">{d["subtitle"]}</p>
                <div class="doc-tags" style="margin-top: 12px; margin-bottom: 5px;">
                    {tags_doc_html}
                </div>
                <div class="wiki-meta">
                    {'\n'.join(meta_html_doc)}
                </div>
            </div>
            
            <div class="steps-container">
                {'\n'.join(steps_cards)}
            </div>
        </main>
    </div>
    
    <script src="../js/wiki.js"></script>
</body>
</html>
"""
        with open(os.path.join(docs_dir, f"{d['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(doc_html_content)
        
    return True
