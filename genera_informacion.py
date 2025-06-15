from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError

import tempfile
import boto3
import os
import time
import json

def inicializa_driver():

    # Configuración del navegador
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # 👇 usar un directorio temporal único
    temp_profile = tempfile.mkdtemp(prefix="selenium_")
    options.add_argument(f"--user-data-dir={temp_profile}")

    options.binary_location = "/usr/bin/google-chrome"

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)

    return driver

def obtiene_informacion(driver,infoUrl):

    url = infoUrl["url"];
    driver.get(url)

    # Esperar a que cargue
    time.sleep(5)

    #Se valida que existen eventos proximos para la pagina
    validaEventos = driver.find_elements(By.XPATH, "//a[.//span[text()='Upcoming']]")
    if(not(validaEventos)):
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
                fecha = driver.find_elements(By.XPATH, '//span[contains(text(), " at ")]')[0].text
            except:
                fecha = ""

            try:
                # Obtener domicilio
                domicilio = driver.find_element(By.XPATH, '//span[contains(@class, "x193iq5w xeuugli x13faqbe x1vvkbs x1xmvt09 x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x xudqn12 x3x7a5m x1lkfr7t x1lbecb7 xo1l8bm xi81zsa x1yc453h")]//span').text
                print("Esto es lo que tiene el domicilio:",domicilio )
            except e:
                print("Existio un problema al obtener el domicilio,",e)
                domicilio = ""
          
            # Obtener imagen del evento
            img = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.XPATH, '//img[@data-imgperflogname="profileCoverPhoto"]'))
            )

            imagen_url = img.get_attribute("src")

            print(f"🔹 Evento: {titulo}",flush=True)
            print(f"📅 Fecha: {fecha}",flush=True)
            print(f"🚗 Domicilio: {domicilio}",flush=True)
            print(f"📷 Img: {imagen_url}",flush=True)
            print(f"🔗 Link: {enlace}\n",flush=True)

            #Se genera variable en donde se guarda la info del evento
            evento = {
                "link":enlace,
                "titulo": titulo,
                "fecha": fecha,
                "domicilio": domicilio,
                "img":imagen_url
            }

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
        }
    ]

infoPaginas=[]

#Se inicializa driver que controlara la navegacion 
driver = inicializa_driver()

for infoUrl in urls:
   infPagunaAux = obtiene_informacion(driver, infoUrl)
   if(infPagunaAux):
       infoPaginas.append(infPagunaAux)

#Se cierra driver
driver.quit()


nombre_archivo = "info_paginas.json"

try:
    with open(nombre_archivo, "w") as archivo:
        json.dump(infoPaginas, archivo, indent=4)
    subir_archivo_a_s3(nombre_archivo,nombre_archivo)
except Exception as e:
    print(f"❌ Error al guardar archivo: {e}")