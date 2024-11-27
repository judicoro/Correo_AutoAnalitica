from flask import Flask
from pymongo import MongoClient
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import time
import threading
import schedule
import os
from datetime import datetime, timedelta

# Configuración de Flask
app = Flask(__name__)

# Conexión a MongoDB
uri = "mongodb+srv://jucoronel:AivF1YaQSkx3NV4Q@autoanalitica.wh5c6.mongodb.net/?retryWrites=true&w=majority&appName=AutoAnalitica"
client = MongoClient(uri)
db = client["autosanalitica_Limpios"]

# Colecciones en MongoDB
clientes_collection = db["Cliente"]
productos_collection = db["productos_limpios"]

# Diccionario para rastrear correos enviados recientemente
correos_enviados = {}

def formatear_precio(precio):
    """
    Convierte un precio a formato XXX.XXX sin decimales y con punto como separador de miles.
    Si el precio no es numérico, retorna "No disponible".
    """
    try:
        return f"{int(float(precio)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "No disponible"

def obtener_productos_baratos(marca, modelo):
    """
    Obtiene los 5 productos más baratos para una marca y modelo específicos.
    """
    print(f"Buscando productos para marca: {marca}, modelo: {modelo}")
    productos = productos_collection.find({"marca": marca, "modelo": modelo})
    productos_baratos = []

    for producto in productos:
        try:
            precio_actual = producto["precio_actual"]
            productos_baratos.append({
                "nombre": producto["nombre"],
                "precio_actual": precio_actual,
                "precio_formateado": formatear_precio(precio_actual),
                "link": producto.get("LinkPagina", "No disponible"),
                "imagenUrl": producto.get("imagenUrl", ""),
                "precio_original": producto.get("precio_original", "No disponible")
            })
        except Exception as e:
            print(f"Error procesando producto: {e}")

    productos_baratos.sort(key=lambda x: x["precio_actual"] if isinstance(x["precio_actual"], (int, float)) else float("inf"))
    return productos_baratos[:5]

def generar_html(cliente, productos):
    """
    Genera el contenido HTML del correo con la lista completa de productos.
    """
    logo_url = "https://s11.aconvert.com/convert/p3r68-cdx67/spx89-sv2e0.webp"
    footer_image_url = "https://s11.aconvert.com/convert/p3r68-cdx67/cx2p6-6m5c0.webp"

    lista_completa_html = ""
    for producto in productos:
        precio_original_formateado = formatear_precio(producto.get("precio_original", "No disponible"))
        lista_completa_html += f"""
        <tr>
            <td style="padding:10px; border:1px solid #ddd; text-align:center;">
                <img src="{producto['imagenUrl']}" alt="{producto['nombre']}" style="width:100px; height:auto;">
            </td>
            <td style="padding:10px; border:1px solid #ddd;">
                <p style="margin:0; font-size:14px; color:#333;"><strong>{producto['nombre']}</strong></p>
                <p style="margin:5px 0; font-size:14px; color:#f4b400;"><strong>${producto['precio_formateado']}</strong></p>
                <a href="{producto['link']}" style="font-size:14px; color:#007bff; text-decoration:none;">Ver Producto</a>
            </td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 0;
            }}
            .header {{
                text-align: center;
                background-color: #000;
                color: #f4b400;
                padding: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Ofertas Exclusivas para tu Auto</h1>
        </div>
        <h2>Hola, {cliente['correo']}!</h2>
        <p>Te presentamos las mejores ofertas para tu vehículo ({cliente['marca']} {cliente['modelo']}):</p>
        <table>
            {lista_completa_html}
        </table>
        <div class="footer">
            <img src="{footer_image_url}" alt="Footer AutoAnalitica">
        </div>
    </body>
    </html>
    """
    return html

def enviar_correo(cliente, productos):
    """
    Envía un correo electrónico al cliente con los productos más baratos.
    """
    remitente = "judicoro02@gmail.com"
    contraseña = "lrrh sorq qflk mwin"
    destinatario = cliente["correo"]

    ahora = datetime.now()
    if destinatario in correos_enviados:
        ultima_vez = correos_enviados[destinatario]
        if ahora - ultima_vez < timedelta(minutes=5):
            print(f"Correo ya enviado recientemente a {destinatario}. Ignorando...")
            return

    correos_enviados[destinatario] = ahora

    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = "¡Ofertas Exclusivas para tu Auto!"
    mensaje["From"] = remitente
    mensaje["To"] = destinatario

    contenido_html = generar_html(cliente, productos)
    mensaje.attach(MIMEText(contenido_html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(remitente, contraseña)
            server.sendmail(remitente, destinatario, mensaje.as_string())
            print(f"Correo enviado a {destinatario}")
    except Exception as e:
        print(f"Error al enviar correo a {destinatario}: {e}")

def procesar_clientes_existentes():
    """
    Envía correos a todos los clientes existentes.
    """
    print("Procesando clientes existentes para el envío de correos...")
    clientes = clientes_collection.find()

    for cliente in clientes:
        productos = obtener_productos_baratos(cliente["marca"], cliente["modelo"])
        if productos:
            enviar_correo(cliente, productos)
        else:
            print(f"No se encontraron productos para {cliente['marca']} {cliente['modelo']}.")

def escuchar_nuevos_clientes():
    """
    Escucha cambios en la colección Cliente y envía correos automáticamente a los nuevos clientes.
    """
    print("Esperando nuevos clientes...")

    with clientes_collection.watch([{"$match": {"operationType": "insert"}}]) as stream:
        for cambio in stream:
            cliente_nuevo = cambio["fullDocument"]
            print(f"Nuevo cliente detectado: {cliente_nuevo}")

            productos = obtener_productos_baratos(cliente_nuevo["marca"], cliente_nuevo["modelo"])
            if productos:
                enviar_correo(cliente_nuevo, productos)

def iniciar_programacion():
    """
    Configura el envío de correos a las 3 PM para clientes existentes.
    """
    schedule.every().day.at("15:00").do(procesar_clientes_existentes)

    while True:
        schedule.run_pending()
        time.sleep(1)

# Ruta raíz para verificar que la aplicación está activa
@app.route("/")
def home():
    return "OK"

if __name__ == "__main__":
    # Iniciar los hilos para las tareas en segundo plano
    threading.Thread(target=escuchar_nuevos_clientes).start()
    threading.Thread(target=iniciar_programacion).start()

    # Ejecutar el servidor Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
