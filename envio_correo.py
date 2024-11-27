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
