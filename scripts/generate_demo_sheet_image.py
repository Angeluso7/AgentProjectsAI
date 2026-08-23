import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs("./data/rendered", exist_ok=True)
target_path = "./data/rendered/demo_sheet_1.png"
thumb_path = "./data/rendered/demo_sheet_1_thumb.png"

# Crear lienzo de alta resolución 4200 x 2970 px (A3/A2 @ 150/300 DPI)
width, height = 4200, 2970
img = Image.new("RGB", (width, height), color="#080e1a")
draw = ImageDraw.Draw(img)

# Dibujar grid técnico tenue
grid_size = 100
for x in range(0, width, grid_size):
    draw.line([(x, 0), (x, height)], fill="#0f1f38", width=1)
for y in range(0, height, grid_size):
    draw.line([(0, y), (width, y)], fill="#0f1f38", width=1)

# Marco exterior del plano
margin = 80
draw.rectangle([margin, margin, width - margin, height - margin], outline="#38bdf8", width=4)

# Marco interior
draw.rectangle([margin + 20, margin + 20, width - margin - 20, height - margin - 20], outline="#1e3a5f", width=2)

# Región de Viñeta (Title Block) en esquina inferior derecha
tb_w, tb_h = 1300, 650
tb_x0 = width - margin - 20 - tb_w
tb_y0 = height - margin - 20 - tb_h
draw.rectangle([tb_x0, tb_y0, width - margin - 20, height - margin - 20], fill="#0c1728", outline="#38bdf8", width=3)
draw.line([(tb_x0, tb_y0 + 150), (width - margin - 20, tb_y0 + 150)], fill="#38bdf8", width=2)
draw.line([(tb_x0, tb_y0 + 350), (width - margin - 20, tb_y0 + 350)], fill="#1e3a5f", width=2)
draw.line([(tb_x0 + 650, tb_y0 + 150), (tb_x0 + 650, height - margin - 20)], fill="#1e3a5f", width=2)

# Textos en Viñeta
draw.text((tb_x0 + 40, tb_y0 + 40), "PROYECTO: EDIFICIO RESIDENCIAL PARQUE CENTRAL", fill="#ffffff")
draw.text((tb_x0 + 40, tb_y0 + 90), "MANDANTE: INMOBILIARIA Y CONSTRUCTORA NACIONAL S.A.", fill="#94a3b8")
draw.text((tb_x0 + 40, tb_y0 + 180), "CONTENIDO: PLANTA ARQUITECTURA Y ESPECIALIDADES", fill="#38bdf8")
draw.text((tb_x0 + 40, tb_y0 + 240), "DISCIPLINA: ARQUITECTURA / ESTRUCTURA", fill="#e2e8f0")
draw.text((tb_x0 + 40, tb_y0 + 380), "ESCALA: 1:50  •  FECHA: 2026-08-20", fill="#94a3b8")
draw.text((tb_x0 + 40, tb_y0 + 440), "REVISIÓN: REV-0  •  LÁMINA: ARQ-01", fill="#38bdf8")

# Región de Dibujo Arquitectónico Principal (Muros, Ejes, Cuartos)
draw.rectangle([250, 250, 2400, 2100], outline="#60a5fa", width=3)

# Ejes estructurales
for i, x in enumerate(range(350, 2300, 300), start=1):
    draw.line([(x, 200), (x, 2150)], fill="#f59e0b", width=2)
    draw.ellipse([x - 25, 175, x + 25, 225], fill="#080e1a", outline="#f59e0b", width=2)
    draw.text((x - 8, 190), str(i), fill="#f59e0b")

for j, y in enumerate(range(350, 2050, 300), start=1):
    eje_letter = chr(64 + j)
    draw.line([(200, y), (2450, y)], fill="#f59e0b", width=2)
    draw.ellipse([175, y - 25, 225, y + 25], fill="#080e1a", outline="#f59e0b", width=2)
    draw.text((192, y - 10), eje_letter, fill="#f59e0b")

# Muros y Recintos
draw.rectangle([400, 400, 1100, 1000], outline="#ffffff", width=4)
draw.text((600, 680), "SALA DE ESTAR / LIVING", fill="#cbd5e1")

draw.rectangle([1150, 400, 1850, 1000], outline="#ffffff", width=4)
draw.text((1350, 680), "DORMITORIO PRINCIPAL", fill="#cbd5e1")

draw.rectangle([400, 1050, 1100, 1650], outline="#ffffff", width=4)
draw.text((650, 1320), "COCINA / COMEDOR", fill="#cbd5e1")

draw.rectangle([1150, 1050, 1850, 1650], outline="#ffffff", width=4)
draw.text((1400, 1320), "BAÑO SUITE", fill="#cbd5e1")

# Región de Notas Técnicas en lateral derecho superior
draw.rectangle([2550, 250, width - margin - 50, 1200], fill="#0c1728", outline="#f59e0b", width=2)
draw.text((2580, 280), "NOTAS GENERALES DE CONSTRUCCIÓN:", fill="#f59e0b")
draw.text((2580, 340), "1. COTAS EN MILÍMETROS, NIVELES EN METROS.", fill="#94a3b8")
draw.text((2580, 390), "2. HORMIGÓN H-30 SEGÚN NCh 170 Of. 2016.", fill="#94a3b8")
draw.text((2580, 440), "3. RECUBRIMIENTO MÍNIMO SEGÚN ESPECIFICACIÓN TÉCNICA.", fill="#94a3b8")
draw.text((2580, 490), "4. VALIDAR INTERFERENCIAS CON ESPECIALIDAD ELÉCTRICA Y PIPING.", fill="#94a3b8")

# Región de Tablas de Cuadro de Superficies
draw.rectangle([2550, 1300, width - margin - 50, 2100], fill="#0c1728", outline="#10b981", width=2)
draw.text((2580, 1330), "CUADRO GENERAL DE SUPERFICIES:", fill="#10b981")
draw.line([(2550, 1380), (width - margin - 50, 1380)], fill="#10b981", width=1)
draw.text((2580, 1420), "RECINTO                     SUPERFICIE ÚTIL (m²)", fill="#e2e8f0")
draw.text((2580, 1470), "LIVING - COMEDOR            32.50 m²", fill="#94a3b8")
draw.text((2580, 1520), "DORMITORIO PRINCIPAL        18.40 m²", fill="#94a3b8")
draw.text((2580, 1570), "COCINA EQUIPADA             12.80 m²", fill="#94a3b8")
draw.text((2580, 1620), "BAÑO SUITE                  6.20 m²", fill="#94a3b8")
draw.text((2580, 1670), "TERRAZA EXTERIOR            8.50 m²", fill="#94a3b8")
draw.line([(2550, 1720), (width - margin - 50, 1720)], fill="#1e3a5f", width=1)
draw.text((2580, 1750), "TOTAL SUPERFICIE:           78.40 m²", fill="#38bdf8")

# Guardar master y thumbnail
img.save(target_path, "PNG")
print(f"Master demo image saved to {target_path} ({width}x{height})")

thumb = img.resize((700, 495), Image.Resampling.LANCZOS)
thumb.save(thumb_path, "PNG")
print(f"Thumbnail demo image saved to {thumb_path}")
