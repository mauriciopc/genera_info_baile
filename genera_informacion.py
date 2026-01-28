from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from botocore.exceptions import NoCredentialsError
from datetime import datetime
from dotenv import load_dotenv

import re
import locale
import tempfile
import boto3
import os
import time
import json
import gc

load_dotenv()

PROD = os.getenv("PROD")

def inicializa_driver():

    # Configuración del navegador
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    if(PROD):
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
		# 👇 usar un directorio temporal único
        temp_profile = tempfile.mkdtemp(prefix="selenium_")
        options.add_argument(f"--user-data-dir={temp_profile}")
        
		# Define tamaño de ventana para evitar que se oculte contenido
        options.add_argument("--window-size=1920,1080")

        options.binary_location = "/opt/google/chrome/google-chrome"

        service = Service()

        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    return driver

def obtiene_informacion(driver,infoUrl):

    url = infoUrl["url"]
    driver.get(url)

    #Se coloca sleep para esperar a que cargue la pagina
    time.sleep(5)

    #Se valida que existen eventos proximos para la pagina
    if(PROD):
        validaEventos = driver.find_elements(By.XPATH, "//a[.//span[text()='Upcoming']]")
    else:
        validaEventos = driver.find_elements(By.XPATH, "//a[.//span[text()='Próximos']]")

    if(not(validaEventos)):
        print("No se encontraron eventos para: ",url, flush=True)
        # 🖼️ Captura de pantalla para depuración
        driver.save_screenshot(f"captura_{infoUrl['id']}.png")
        return {}
    
    #Se incializa variable para guardar informacion de los eventos
    infoPagina = {
        "id": infoUrl["id"],
        "url": infoUrl["url"],
        "eventos": []
    }

    # Extraer los enlaces a eventos
    eventos = driver.find_elements(By.XPATH, '//a[contains(@href, "/events/") and not(contains(@href, "create"))]')

    # Eliminar duplicados
    enlaces = set()
    for evento in eventos:
        href = evento.get_attribute("href")
        if href and "/events/" in href:
            enlaces.add(href.split("?")[0])  # limpiar parámetros

    # Mostrar resultados
    print("________Eventos encontrados para",url,":_______", flush=True)
    for enlace in enlaces:
        driver.get(enlace)
        time.sleep(5)
        
        try:
            try:
                # Obtener título del evento (h1 suele ser el nombre del evento)
                titulo = driver.find_element(By.XPATH, '//span[contains(@class, "html-span")]').text
            except:
                titulo = ""

            try:
                # Obtener fecha/hora (Facebook cambia a veces la estructura)
                if(PROD):
                    fecha = driver.find_elements(By.XPATH, '//span[contains(text(), " at")]')[0].text
                    fecha_f = formatear_fecha_en(fecha)
                    fecha = traducir_fecha(fecha)
                else:
                    fecha = driver.find_elements(By.XPATH, '//span[contains(text(), " a ")]')[0].text
                    fecha_f = formatear_fecha_es(fecha)
            except Exception as e:
                print("Existio un problema en obtener la fecha:",e,flush=True)
                fecha = ""
                fecha_f = ""

            try:
                # Obtener domicilio
                domicilio = driver.find_element(By.XPATH, '//div[contains(@class, "x78zum5 xdt5ytf x1wsgfga x9otpla")]//div[3]//span//span').text
                print("Esto es lo que tiene el domicilio:",domicilio )
            except Exception as e:
                print("Existio un problema al obtener el domicilio,",e,flush=True)
                domicilio = ""
          
            # Obtener imagen del evento
            img = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.XPATH, '//img[@data-imgperflogname="profileCoverPhoto"]'))
            )

            imagen_url = img.get_attribute("src")

            print(f"🔹 Evento: {titulo}",flush=True)
            print(f"📅 Fecha: {fecha}",flush=True)
            print(f"📅 Fecha Formateada: {fecha_f}",flush=True)
            print(f"🚗 Domicilio: {domicilio}",flush=True)
            print(f"📷 Img: {imagen_url}",flush=True)
            print(f"🔗 Link: {enlace}\n",flush=True)

            #Se genera variable en donde se guarda la info del evento
            evento = {
                "link":enlace,
                "titulo":titulo,
                "fecha":fecha,
                "fecha_f":fecha_f,
                "domicilio": domicilio,
                "img":imagen_url
            }

            # Se reivsa que no existan eventos repetidos
            if infoPagina["eventos"]:
                listaEventos = [p["titulo"] for p in infoPagina["eventos"]]

                if evento["titulo"] in listaEventos:
                    continue

            
            #Se guarda en el hash que contendra la informacion de todos los eventos de la pagina
            infoPagina["eventos"].append(evento)
        except Exception as e:
            print(f"⚠️ Error en {enlace}: {e}")
        
    return infoPagina

def subir_archivo_a_s3(nombre_local, nombre_remoto):
    
    try:
        AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
        AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        BUCKET_NAME = os.getenv("BUCKET_NAME")

        s3 = boto3.client('s3',
                          aws_access_key_id=AWS_ACCESS_KEY,
                          aws_secret_access_key=AWS_SECRET_KEY)

        s3.upload_file(nombre_local, BUCKET_NAME, nombre_remoto)
        print(f"✅ Archivo '{nombre_local}' subido como '{nombre_remoto}' en el bucket '{BUCKET_NAME}'")
    except FileNotFoundError:
        print("❌ El archivo no se encontró.")
    except NoCredentialsError:
        print("❌ No se encontraron las credenciales de AWS.")

def formatear_fecha_en(fecha_str):
    # Establecer el locale en inglés para que reconozca el mes en inglés
    try:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'C')  # Opción alternativa en algunos sistemas

    # Extraer solo la parte de la fecha antes de "at"
    fecha_solamente = fecha_str.split(" at")[0].strip()

    # Parsear el string al objeto datetime
    fecha = datetime.strptime(fecha_solamente, "%A, %B %d, %Y")

    # Retornar la fecha en el formato deseado
    return fecha.strftime("%d/%m/%Y")

def formatear_fecha_es(fecha_str):
    # Normaliza espacios invisibles
    fecha_str = fecha_str.replace('\u202f', ' ')  # narrow no-break space

    # Extraer solo: "2 de julio de 2025"
    match = re.search(r'\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b', fecha_str)
    if not match:
        raise ValueError("❌ No se pudo extraer la parte de la fecha")

    solo_fecha = match.group(0)

    # Intentar establecer locale español
    try:
        locale.setlocale(locale.LC_TIME, 'es_MX.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except:
            locale.setlocale(locale.LC_TIME, '')

    # Parsear sin el día de la semana
    fecha_dt = datetime.strptime(solo_fecha, "%d de %B de %Y")

    return fecha_dt.strftime("%d/%m/%Y")


def traducir_fecha(fecha_str):
    # Establecer locale en inglés para poder parsear
    try:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'C')

    # Quitar cualquier texto después del primer "at HH:MM", incluyendo rangos como "– 2:30 AM CST"
    match = re.search(r"^(.*? at [0-9]{1,2}:[0-9]{2}\s?[APMapm\.]{2,4})", fecha_str)
    if not match:
        raise ValueError("No se pudo interpretar la fecha")

    fecha_limpia = match.group(1)

    # Convertir a datetime
    fecha_dt = datetime.strptime(fecha_limpia, "%A, %B %d, %Y at %I:%M %p")

    # Traducciones
    dias = {
        "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
        "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"
    }
    meses = {
        "January": "Enero", "February": "Febrero", "March": "Marzo",
        "April": "Abril", "May": "Mayo", "June": "Junio", "July": "Julio",
        "August": "Agosto", "September": "Septiembre", "October": "Octubre",
        "November": "Noviembre", "December": "Diciembre"
    }

    # Obtener partes
    dia_en = fecha_dt.strftime("%A")
    mes_en = fecha_dt.strftime("%B")
    hora_es = fecha_dt.strftime("%H:%M")

    return f"{dias[dia_en]}, {fecha_dt.day} de {meses[mes_en]} de {fecha_dt.year} a las {hora_es} hrs"

# URLs de la páginas de eventos
urls = [{
            "id":1,
            "url":"https://www.facebook.com/mauricio.diaz.984991/events"
        },
        {
            "id":2,
            "url":"https://www.facebook.com/EsenciaBachataSocial/events"
        },
        {
            "id":3,
            "url":"https://www.facebook.com/Adondevamosabailarsociales/events/"
        },
        {
            "id":4,
            "url": "https://www.facebook.com/people/MasBachata/61550724543435/?sk=events"
        },
        {
            "id":5,
            "url":"https://www.facebook.com/people/Copacabana-Salsa-Bachata-Social/61553941332839/?sk=events"
        },
        {
            "id":6,
            "url":"https://www.facebook.com/PalladiumSalsaSocial/events"
        },
        {
            "id":7,
            "url":"https://www.facebook.com/SecretDanceMexico/events"  
        },
        {
            "id":8,
            "url":"https://www.facebook.com/elbabalu/events"  
        },
        {
            "id":9,
            "url":"https://www.facebook.com/people/Sensual-Sunset-BKS-Social/61560097226587/?sk=events"
        },
        {
            "id":10,
            "url":"https://www.facebook.com/profile.php?id=61572426942742&sk=events"
        },
        {
            "id":11,
            "url":"https://www.facebook.com/TardeadaBachaSalsa/events"
        },
        {
            "id":12,
            "url":"https://www.facebook.com/SAIztacalco/events"
        },
    ]

infoPaginas=[]

print("valor de prod",PROD)

for infoUrl in urls:
    #Se inicializa driver que controlara la navegacion 
    driver = inicializa_driver()
    infPagunaAux = obtiene_informacion(driver,infoUrl)
    if(infPagunaAux):
        infoPaginas.append(infPagunaAux)
    #Se cierra driver
    driver.quit()
    gc.collect()
    time.sleep(5)


nombre_archivo = "info_paginas.json"

try:
    with open(nombre_archivo, "w") as archivo:
        json.dump(infoPaginas, archivo, indent=4)
    subir_archivo_a_s3(nombre_archivo,nombre_archivo)
except Exception as e:
    print(f"❌ Error al guardar archivo: {e}")
