# generate_pdf_report.py
import pandas as pd
import plotly.graph_objects as go
import plotly.colors as pc
import plotly.express as px
import yaml
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
import locale
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
import os

import plotly.express as px
import plotly

from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors


# === Coloca tu token aquí ===
plotly.io.templates.default = "plotly_white"
plotly.io.templates["plotly_white"].layout.mapbox.accesstoken = os.environ.get("MAPBOX_ACCESS_TOKEN", "")

'''
styles = getSampleStyleSheet()

style_centered = ParagraphStyle(
    'centered',
    parent=styles['Normal'],
    alignment=TA_CENTER
)
'''

def header_logos(canvas, doc):
    canvas.saveState()
    target_height = 50

    # Logo FIC (centrado)
    try:
        fic_path = "../assets/logo_fic.png"
        fic_img = ImageReader(fic_path)
        fic_width, fic_height = fic_img.getSize()
        fic_scaled_width = fic_width * (target_height / fic_height)

        canvas.drawImage(fic_path,
            x=(A4[0] - fic_scaled_width) / 2,  # centrado
            y=A4[1] - target_height - 30,
            width=fic_scaled_width,
            height=target_height,
            mask='auto')
    except Exception as e:
        print(f"Error loading FIC logo: {e}")

    canvas.restoreState()



def footer(canvas, doc):
    year = datetime.now().year
    line1 = f'Proyecto FIC IDI 40059070-0 "Transferencia tecnologías 4.0 para la gestión del riesgo en la cadena de valor de la cereza"'
    line2 = f"Universidad de O'Higgins - Av. Libertador Gral. Bernardo O'Higgins 611, Rancagua, O'Higgins"
    line3 = f"Contacto: cerezas@uoh.cl"
    page_text = f"Página {doc.page}"

    canvas.saveState()
    canvas.setFont('Helvetica-Oblique', 8)
    canvas.drawCentredString(A4[0] / 2, 65, line1)
    canvas.setFont('Helvetica', 7)
    canvas.drawCentredString(A4[0] / 2, 55, line2)
    canvas.drawCentredString(A4[0] / 2, 45, line3)
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(A4[0] - 70, 35, page_text)  # margen inferior derecha
    canvas.restoreState()


def add_page_decorations(canvas, doc):
    header_logos(canvas, doc)
    footer(canvas, doc)

def create_figure(df, columns, title, color_map, image_path):
    fig = go.Figure()
    for col in columns:
        base_id = col.split()[0]
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df[col],
            mode='lines+markers',
            name=col,
            line=dict(color=color_map.get(base_id, 'gray')),
            opacity=1.0
        ))
    fig.update_layout(title=title, xaxis_title="Fecha y Hora", template="plotly_white")
    fig.write_image(image_path, format="jpg", engine="kaleido", scale=3, width=1000, height=600)




def create_weekly_table(df, start_date, end_date, style_centered):
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    weeks = []
    current = start_dt

    if current.weekday() != 0:
        first_sunday = current + pd.Timedelta(days=(6 - current.weekday()))
        weeks.append( (current, min(first_sunday, end_dt)) )
        current = first_sunday + pd.Timedelta(days=1)

    while current <= end_dt:
        week_start = current
        week_end = current + pd.Timedelta(days=6)
        if week_start > end_dt:
            break
        weeks.append( (week_start, min(week_end, end_dt)) )
        current = current + pd.Timedelta(days=7)

    data = [[
        'Semana',
        Paragraph('HF', style_centered),
        Paragraph('PF', style_centered)
    ]]

    for i, (week_start, week_end) in enumerate(weeks):
        # Generar rango de la semana
        week_dates = pd.date_range(week_start, week_end)

        # Buscar último día con datos en la semana
        df_week = df[df['timestamp'].dt.date.isin(week_dates.date)]
        if not df_week.empty:
            last_day = df_week['timestamp'].dt.date.max()
            df_last_day = df_week[df_week['timestamp'].dt.date == last_day]

            hf_cols = [c for c in df_last_day.columns if c.endswith("HF")]
            pf_cols = [c for c in df_last_day.columns if c.endswith("PF")]

            hf_last_day_avg = df_last_day[hf_cols].mean().mean() if not df_last_day.empty else 0
            pf_last_day_avg = df_last_day[pf_cols].mean().mean() if not df_last_day.empty else 0
        else:
            hf_last_day_avg = 0
            pf_last_day_avg = 0

        week_number = pd.Timestamp(week_start).isocalendar()[1]

        semana_texto = f"Semana {week_number} ({week_start.strftime('%A %d de %B')} - {week_end.strftime('%A %d de %B')})"
        semana_texto = semana_texto.capitalize()

        data.append([semana_texto,
                     round(hf_last_day_avg,1),
                     round(pf_last_day_avg,1)])

    return Table(data, hAlign='CENTER')







def create_daily_pf_table(df, start_month):
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    print("Meses disponibles en df:", sorted(df['timestamp'].dt.month.unique()))

    # Filtrar desde el mes indicado en adelante
    df_filtered = df[df['timestamp'].dt.month >= start_month]

    months = sorted(df_filtered['timestamp'].dt.month.unique())
    month_names = [pd.Timestamp(month=month, day=1, year=2025).strftime('%B').capitalize() for month in months]
    print("Meses incluidos en tabla:", month_names)

    data = [['Día'] + month_names]

    for day in range(1,32):
        row = [str(day)]
        for month in months:
            df_day = df_filtered[(df_filtered['timestamp'].dt.month == month) & (df_filtered['timestamp'].dt.day == day)]
            if not df_day.empty:
                pf_mean = df_day[[c for c in df_day.columns if c.endswith("PF")]].mean().mean()
                row.append(round(pf_mean,1) if not pd.isna(pf_mean) else '')
            else:
                row.append('')
        data.append(row)

    return Table(data, hAlign='CENTER')



def style_table(table):
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E0E0E0")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.black),
        ('ALIGN',(1,1),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))


def main(base_path_reports, fic_name, dataset_key, month_root, month_words_root, start_date_root, end_date_root, last_7_days_root):
    
    styles = getSampleStyleSheet()
    current_year_label = str(pd.Timestamp(end_date_root).year)
    
    style_centered = ParagraphStyle(
        'centered',
        parent=styles['Normal'],
        alignment=TA_CENTER
    )

    with open("../assets/site_metadata.yaml", "r", encoding="utf-8") as f:
        site_info = yaml.safe_load(f)

    #dataset_key = "rengo-ceaf"
    site_name = site_info[dataset_key]["nombre"]
    site_location = site_info[dataset_key]["ubicacion"] + ", Región del Libertador Bernardo O’Higgins"

    df_raw = pd.read_csv(f"{base_path_reports}{fic_name}.csv")
    df_raw["timestamp"] = pd.to_datetime(dict(year=df_raw["Año"], month=df_raw["Mes"], day=df_raw["Dia"], hour=df_raw["Hora"]))

    with open(f"../locations/sensor_locations_{fic_name}.txt", "r", encoding="utf-8") as f:
        local_vars = {}
        exec(f.read(), {}, local_vars)
        sensor_locations = local_vars.get("sensor_locations")
        if sensor_locations is None:
            raise ValueError("El archivo no define 'sensor_locations'")

    sensor_locations_df = pd.DataFrame([
        {"device_id": device_id, **info} for device_id, info in sensor_locations.items()
    ])

    excluded_sensors = {"A8404136485A9878", "A84041BC2F5A9851"}
    sensor_locations_df = sensor_locations_df[~sensor_locations_df["device_id"].isin(excluded_sensors)]
    num_sensores = len(sensor_locations_df)


    sensor_cols = [col for col in df_raw.columns if col.startswith("A8") and " " not in col and not any(col.startswith(s) for s in excluded_sensors)]
    hf_cols = [col for col in df_raw.columns if col.endswith("HF") and not any(col.startswith(s) for s in excluded_sensors)]
    pf_cols = [col for col in df_raw.columns if col.endswith("PF") and not any(col.startswith(s) for s in excluded_sensors)]

    colors = pc.qualitative.Plotly
    sensor_ids = sensor_cols
    color_map = {sensor: colors[i % len(colors)] for i, sensor in enumerate(sensor_ids)}

    start_date = pd.Timestamp(start_date_root)
    end_date = pd.Timestamp(end_date_root)
    df_may = df_raw[(df_raw["timestamp"] >= start_date) & (df_raw["timestamp"] <= end_date)]

    output_dir = Path("pdf")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{month_root} UOH Cerezas Boletin Mensual - {site_name}.pdf"

    img_temp = output_dir / "fig_temp.jpg"
    img_hf = output_dir / "fig_hf.jpg"
    img_pf = output_dir / "fig_pf.jpg"
    img_map = output_dir / "map_sensores.jpg"

    img_temp7 = output_dir / "fig_temp_ultimos7.jpg"
    df_last7 = df_may[(df_may["timestamp"] >= last_7_days_root) & (df_may["timestamp"] <= end_date_root)]
    create_figure(df_last7, sensor_cols, f"Temperatura - Últimos 7 días ({last_7_days_root} al {end_date_root})", color_map, img_temp7)

    create_figure(df_may, sensor_cols, "Temperatura (°C)", color_map, img_temp)
    create_figure(df_may, hf_cols, "Horas Frío", color_map, img_hf)
    create_figure(df_may, pf_cols, "Porciones de Frío", color_map, img_pf)

    sensor_locations_df["color"] = sensor_locations_df["device_id"].map(color_map)

    center_lat = sensor_locations_df["latitud"].mean()
    center_lon = sensor_locations_df["longitud"].mean()


    if len(sensor_locations_df) == 1:
        mapbox_zoom = 16
    else:
        # Calcular rango máximo (latitud o longitud)
        lat_range = sensor_locations_df["latitud"].max() - sensor_locations_df["latitud"].min()
        lon_range = sensor_locations_df["longitud"].max() - sensor_locations_df["longitud"].min()
        max_range = max(lat_range, lon_range)

        # Asignar zoom aproximado basado en max_range (en grados)
        # Escala orientativa para Chile central (ajusta según tus pruebas):
        if max_range < 0.001:
            mapbox_zoom = 17
        elif max_range < 0.005:
            mapbox_zoom = 16
        elif max_range < 0.01:
            mapbox_zoom = 15
        elif max_range < 0.05:
            mapbox_zoom = 14
        elif max_range < 0.1:
            mapbox_zoom = 13
        elif max_range < 0.5:
            mapbox_zoom = 12
        else:
            mapbox_zoom = 11

        print(len(sensor_locations_df), max_range, mapbox_zoom)

    fig_map = px.scatter_mapbox(
        sensor_locations_df,
        lat="latitud",
        lon="longitud",
        hover_name="device_id",
        zoom=mapbox_zoom,
        width=1000,
        height=600
    )

    fig_map.update_traces(
        marker=dict(size=18, color=sensor_locations_df["color"])
    )

    fig_map.update_layout(
        #mapbox_style="open-street-map",
        mapbox_style="satellite",
        mapbox_center={"lat": center_lat, "lon": center_lon},
        mapbox_zoom=mapbox_zoom,
        margin={"r":0,"t":0,"l":0,"b":0}
    )

    fig_map.write_image(str(img_map), engine="kaleido", scale=3)

    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        title=f"{month_root} UOH Cerezas Boletin Mensual - {site_name}",
        topMargin=100  # Ajusta según la altura de tus logos + espacio deseado
    )

    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
    story = []

    styles.add(ParagraphStyle(
        name='Heading1Center',
        parent=styles['Heading1'],
        alignment=TA_CENTER
    ))

    styles.add(ParagraphStyle(
        name='Heading2Center',
        parent=styles['Heading2'],
        alignment=TA_CENTER
    ))

    story.append(Paragraph(f"<b>UOH Cerezas - Boletín Mensual Agroclimático</b>", styles['Heading1Center']))
    story.append(Paragraph(f"<b>{site_name} - {month_words_root}</b>", styles['Heading2Center']))
    story.append(Paragraph(f"{site_location}", styles['Center']))
    story.append(Paragraph(datetime.now().strftime("Fecha del reporte: %d de %B del %Y").replace(datetime.now().strftime("%B"), datetime.now().strftime("%B").title()), styles['Center']))
    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Resumen</b>", styles['Heading2']))

    resumen_text = (
        "Para la evaluación de riesgos y proyecciones de eventos climáticos de interés para la "
        "producción de cereza en la región de O’Higgins se ha disponibilizado la reportería de "
        f"parámetros climáticos del año {current_year_label}.<br/><br/>"
        f"El historial de temperaturas es registrado a través de {num_sensores} sensores ambientales "
        f"distribuidos en diferentes sectores de la zona de producción de {site_name}.<br/><br/>"
        f"La revisión de los datos climáticos de la temporada {current_year_label} a la fecha considera la revisión de "
        "la temperatura promedio del aire como también la evaluación de las variables "
        "agroclimáticas necesarias para los frutales de hoja caduca como lo son las Horas de Frío y "
        "Porciones de Frío.<br/><br/>"
        "De esta forma, a continuación se reportan las métricas promedio de los sensores registradas hasta "
        "la fecha."
    )
    story.append(Paragraph(resumen_text, styles['Justify']))
    story.append(Spacer(1, 20))

    story.append(Paragraph(f"<b>Ubicación de los sensores desplegados</b>", styles['Heading2']))
    story.append(Image(str(img_map), width=doc.width, height=doc.width * 0.6))
    story.append(Spacer(1, 20))

    #story.append(PageBreak())

    story.append(Paragraph(f"<b>Temperatura (°C) promedio en {month_words_root}</b>", styles['Heading2']))
    #story.append(Image(str(img_temp), width=480, height=288))
    story.append(Image(str(img_temp), width=480, height=270))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>Temperatura (°C) promedio en los últimos 7 días</b>", styles['Heading2']))
    #story.append(Image(str(img_temp7), width=480, height=288))
    story.append(Image(str(img_temp7), width=480, height=270))

    story.append(PageBreak())

    story.append(Paragraph(f"<b>Horas Frío promedio en {month_words_root}</b>", styles['Heading2']))
    story.append(Image(str(img_hf), width=480, height=288))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>Porciones de Frío promedio en {month_words_root}</b>", styles['Heading2']))
    story.append(Image(str(img_pf), width=480, height=288))

    daily_pf_table = create_daily_pf_table(df_raw, 5)  # 5 = Mayo
    style_table(daily_pf_table)
    story.append(Paragraph("<b>Acumulación diaria de Porciones de Frío - Mayo</b>", styles['Heading2']))
    story.append(daily_pf_table)

    story.append(PageBreak())

    weekly_table = create_weekly_table(df_raw, f"{current_year_label}-05-01", end_date_root, style_centered)
    style_table(weekly_table)
    story.append(Paragraph("<b>Acumulación semanal de Horas Frío y Porciones de Frío</b>", styles['Heading2']))
    story.append(weekly_table)


    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)

    img_temp.unlink()
    img_temp7.unlink()
    img_hf.unlink()
    img_pf.unlink()
    img_map.unlink()

    print(f"PDF generado exitosamente: {output_file}")

if __name__ == "__main__":
    # Ruta a la carpeta
    folder = "../reports/2025/"
    current_base_path_reports = "../reports/2025/temp_process_2025_may-jun_output_"
    current_start_date_root  = "2025-06-01"
    current_end_date_root    = "2025-06-30 23:59:59"
    current_last_7_days_root = "2025-06-23"
    current_month_root       = "2025-07"
    current_month_words_root = "Junio 2025"

    # Listar archivos
    files = os.listdir(folder)

    # Filtrar y extraer desde 'fic' hasta antes de '.csv'
    names = []
    for f in files:
        if f.endswith(".csv") and "fic2" in f:
            start = f.find("fic")
            end = f.rfind(".csv")
            names.append([f[start:end], f[start+5:end]])

    # Mostrar resultado
    for fic_name, dataset_key in names:
        print(fic_name, dataset_key)

        main(current_base_path_reports, fic_name, dataset_key, 
            current_month_root, current_month_words_root, current_start_date_root, current_end_date_root, current_last_7_days_root)
        #break
