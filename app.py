from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import json
import io
import os
from datetime import datetime, timedelta

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def cargar_datos():
    with open(os.path.join(BASE_DIR, "data", "vacunas.json"), encoding="utf-8") as f:
        datos = json.load(f)
    return datos

def cargar_programas():
    with open(os.path.join(BASE_DIR, "data", "programas.json"), encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def index():
    datos = cargar_datos()
    return render_template("index.html", enfermedades=datos["enfermedades"])

@app.route("/generar", methods=["POST"])
def generar():
    datos_req = request.get_json()
    enfermedades_sel = set(datos_req.get("enfermedades", []))
    fecha_inicio_str = datos_req.get("fecha_inicio", "")
    nombre_lote = datos_req.get("nombre_lote", "Lote")

    fecha_inicio = None
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")
        except ValueError:
            pass

    datos = cargar_datos()
    programas = cargar_programas()

    vacunas_map = {v["id"]: v for v in datos["vacunas"]}

    programa = programas["programas"][0]
    calendario = []

    for app_item in programa["aplicaciones"]:
        vacuna = vacunas_map.get(app_item["vacuna_id"], {})
        protege = set(vacuna.get("protege_contra", []))

        if not enfermedades_sel or protege.intersection(enfermedades_sel):
            entrada = {
                "dia": app_item["dia"],
                "semana": app_item["semana"],
                "vacuna": vacuna.get("nombre_comercial", ""),
                "protege_contra": ", ".join(protege),
                "via": app_item.get("via", vacuna.get("via", "")),
                "lugar": app_item.get("lugar", ""),
                "proveedor": vacuna.get("proveedor", ""),
                "notas": app_item.get("notas", vacuna.get("notas", ""))
            }
            if fecha_inicio:
                fecha_app = fecha_inicio + timedelta(days=app_item["dia"] - 1)
                entrada["fecha"] = fecha_app.strftime("%d/%m/%Y")
            else:
                entrada["fecha"] = ""
            calendario.append(entrada)

    calendario.sort(key=lambda x: x["dia"])

    return jsonify({
        "calendario": calendario,
        "nombre_lote": nombre_lote,
        "fecha_inicio": fecha_inicio_str
    })

@app.route("/exportar_pdf", methods=["POST"])
def exportar_pdf():
    datos_req = request.get_json()
    calendario = datos_req.get("calendario", [])
    nombre_lote = datos_req.get("nombre_lote", "Lote")
    fecha_inicio = datos_req.get("fecha_inicio", "")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=2*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    verde = colors.HexColor("#2e7d32")
    verde_claro = colors.HexColor("#c8e6c9")

    estilo_titulo = ParagraphStyle(
        "titulo",
        parent=styles["Title"],
        textColor=verde,
        fontSize=16,
        spaceAfter=6
    )
    estilo_sub = ParagraphStyle(
        "subtitulo",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=12
    )
    estilo_celda = ParagraphStyle(
        "celda",
        parent=styles["Normal"],
        fontSize=8,
        leading=10
    )

    elementos = []

    titulo_txt = f"CALENDARIO DE VACUNACIÓN - {nombre_lote.upper()}"
    elementos.append(Paragraph(titulo_txt, estilo_titulo))
    sub_txt = f"Generado: {datetime.now().strftime('%d/%m/%Y')} | Fecha inicio lote: {fecha_inicio or 'No especificada'}"
    elementos.append(Paragraph(sub_txt, estilo_sub))
    elementos.append(Spacer(1, 0.3*cm))

    encabezados = ["Día", "Sem.", "Fecha", "Vacuna", "Protege contra", "Vía", "Lugar", "Proveedor", "Notas"]
    filas = [encabezados]

    for item in calendario:
        protege_display = item.get("protege_contra", "").replace("_", " ").title()
        via_display = item.get("via", "").replace("_", " ").capitalize()
        fila = [
            str(item.get("dia", "")),
            str(item.get("semana", "")),
            item.get("fecha", ""),
            Paragraph(item.get("vacuna", ""), estilo_celda),
            Paragraph(protege_display, estilo_celda),
            Paragraph(via_display, estilo_celda),
            Paragraph(item.get("lugar", ""), estilo_celda),
            item.get("proveedor", ""),
            Paragraph(item.get("notas", ""), estilo_celda),
        ]
        filas.append(fila)

    col_widths = [1.2*cm, 1.2*cm, 2.2*cm, 4*cm, 5*cm, 3*cm, 4*cm, 2.5*cm, 4.5*cm]

    tabla = Table(filas, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), verde),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, verde_claro]),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 1), (1, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elementos.append(tabla)

    elementos.append(Spacer(1, 0.5*cm))
    nota = Paragraph(
        "<i>* El programa de vacunación puede variar según zona geográfica, historia sanitaria del plantel y disponibilidad de vacunas.</i>",
        ParagraphStyle("nota", parent=styles["Normal"], fontSize=7, textColor=colors.grey)
    )
    elementos.append(nota)

    doc.build(elementos)
    buffer.seek(0)

    nombre_archivo = f"calendario_vacunacion_{nombre_lote.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True, port=5001)
