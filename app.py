import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-uruguay")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
DEV_USER = os.environ.get("DEV_USER", "admin")
DEV_PASS = os.environ.get("DEV_PASS", "secreto123")

URL_BASE_OFICIAL = "https://bolsillouruguay.onrender.com"

SALUDOS_INICIALES = [
    "¿Qué necesidad resolvemos hoy?",
    "¿En qué te puedo orientar?",
    "Cuéntame, ¿qué andas buscando resolver?",
    "¿Qué dato o solución precisas?",
    "Adelante, ¿en qué te ayudamos?",
    "¿Qué pago o ahorro revisamos?",
    "Escucho tu consulta, ¿qué necesitas?"
]

def verificar_acceso_pagado():
    if session.get("is_dev"):
        return True
    
    expiracion = session.get("expiracion_pago")
    if expiracion:
        if datetime.utcnow() < datetime.fromisoformat(expiracion):
            return True
            
    return False

@app.route("/")
def index():
    if verificar_acceso_pagado():
        saludo_actual = random.choice(SALUDOS_INICIALES)
        if "historial" not in session:
            session["historial"] = []
        return render_template("app.html", saludo_dinamico=saludo_actual)
    return render_template("paywall.html")

@app.route("/crear-checkout", methods=["POST"])
def crear_checkout():
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="payment",
            success_url=f"{URL_BASE_OFICIAL}/exito",
            cancel_url=URL_BASE_OFICIAL,
        )
        return jsonify({"url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/exito")
def exito():
    tiempo_expiracion = datetime.utcnow() + timedelta(days=10)
    session["expiracion_pago"] = tiempo_expiracion.isoformat()
    session["historial"] = []
    return redirect(URL_BASE_OFICIAL)

@app.route("/login-dev", methods=["POST"])
def login_dev():
    data = request.get_json()
    if data.get("usuario") == DEV_USER and data.get("clave") == DEV_PASS:
        session["is_dev"] = True
        session["historial"] = []
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route("/consultar", methods=["POST"])
def consultar():
    if not verificar_acceso_pagado():
        return jsonify({"respuesta": "El tiempo de su acceso ha expirado. Por favor, renueve su plan de asesoría."}), 403

    data = request.get_json()
    consulta = data.get("mensaje", "").lower().strip()
    lat = data.get("lat")
    lon = data.get("lon")

    if not consulta:
        return jsonify({"respuesta": "Dime qué quieres resolver hoy.", "pausa_voz": True})

    historial = session.get("historial", [])
    query_url = consulta.replace(" ", "+")
    
    # Análisis inteligente por intención global (idea o frase)
    texto = consulta

    # 1. TRÁMITES, DOCUMENTOS, IDENTIDAD E INMIGRACIÓN
    if any(p in texto for p in ["residencia", "inmigrante", "extranjero", "migraciones", "papeles", "cedula", "cédula", "documento", "pasaporte", "visa", "radicacion", "legalizar", "certificado", "antecedentes", "venir de afuera", "llegar al pais"]):
        cuerpo_respuesta = (
            "Para hacer tu residencia legal y tener tus papeles al día paso a paso:\n\n"
            "1. Junta tu pasaporte o documento de identidad y el certificado de antecedentes penales legalizado.\n"
            "2. Entra a la web oficial de Dirección Nacional de Migraciones para iniciar tu trámite sin intermediarios.\n"
            "3. Presenta todo para obtener tu residencia y la constancia que te permite sacar la cédula provisoria."
        )
        botones = [
            {"texto": "Ir a Migraciones Uruguay", "url": "https://www.gub.uy/ministerio-interior/institucion/direccion-nacional-migraciones"},
            {"texto": "Oficinas de Migraciones en el mapa", "url": f"https://www.google.com/maps/search/direccion+nacional+de+migraciones+montevideo/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 2. TRABAJO, SUELDOS, SALARIOS Y DERECHOS LABORALES
    elif any(p in texto for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley", "patron", "jefe", "empleo", "recibo", "horas", "aguinaldo", "licencia", "renuncia", "plata"]):
        cuerpo_respuesta = (
            "Para cobrar lo justo y defender tus derechos de trabajo:\n\n"
            "1. Revisa bien los números de tu recibo de sueldo en papel o en el celular.\n"
            "2. Si te pagaron de menos, habla tranquilo con el encargado o la empresa.\n"
            "3. Si no te quieren pagar lo que corresponde, ve al Ministerio de Trabajo a pedir ayuda gratis."
        )
        botones = [
            {"texto": "Consultar BPS", "url": "https://www.bps.gub.uy/"},
            {"texto": "Ir al Ministerio de Trabajo", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"}
        ]

    # 3. COMPRAS, ALIMENTOS, SUPERMERCADOS Y AHORRO DIARIO
    elif any(p in texto for p in ["comprar", "precio", "donde", "barato", "carne", "cafe", "supermercado", "feria", "alimento", "gas", "comida", "mercado", "comercio", "gasto", "ahorro", "almacen", "pan", "leche"]):
        cuerpo_respuesta = (
            "Para comprar comida y cosas del día gastando menos:\n\n"
            "1. Compara precios en dos o tres almacenes o ferias de tu barrio antes de cargar el carrito.\n"
            "2. Busca los comercios barriales que tienen ofertas directas sin marcas caras.\n"
            "3. Usa los accesos del mapa para ver los negocios más cercanos."
        )
        botones = [
            {"texto": "Ver comercios y ferias cerca", "url": f"https://www.google.com/maps/search/supermercado+feria+almacen/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 4. TRANSPORTE, MOVILIDAD Y PASAJES
    elif any(p in texto for p in ["transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "auto", "colectivo", "movilidad", "estacion", "terminal", "caminar"]):
        cuerpo_respuesta = (
            "Para moverte por la ciudad gastando lo menos posible:\n\n"
            "1. Usa tarjeta con descuento para el boleto o colectivo si está disponible.\n"
            "2. Pregunta por las líneas directas para no tomar dos transportes cuando puedes hacer un solo viaje.\n"
            "3. Revisa las paradas y rutas exactas en el mapa."
        )
        botones = [
            {"texto": "Ver paradas y rutas en mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},13z"}
        ]

    # 5. SALUD, MÉDICOS, POLICLÍNICAS Y FARMACIAS
    elif any(p in texto for p in ["clinica", "salud", "medico", "policlinica", "hospital", "doctor", "farmacia", "remedio", "enfermo", "atencion", "urgencia", "emergencia", "sanidad"]):
        cuerpo_respuesta = (
            "Para recibir atención médica rápida y cuidar tu salud sin gastar de más:\n\n"
            "1. Acércate a la policlínica barrial o al hospital público más cercano de tu zona.\n"
            "2. Pide tu número temprano en la mañana para asegurar atención sin pagar consultas caras.\n"
            "3. Consulta si tus medicamentos están en el listado bonificado."
        )
        botones = [
            {"texto": "Ver policlínicas y hospitales cerca", "url": f"https://www.google.com/maps/search/policlinica+hospital+medico/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 6. DINERO, BANCOS, DÓLARES Y CAMBIO
    elif any(p in texto for p in ["dolar", "dólar", "cambio", "cotizacion", "banco", "brou", "plata", "efectivo", "moneda", "pesos", "cajero", "prestamo", "tarjeta"]):
        cuerpo_respuesta = (
            "Para manejar tu dinero, pesos o dólares de forma segura:\n\n"
            "1. Consulta la pizarra oficial del Banco República (BROU) para evitar comisiones ocultas.\n"
            "2. Compara el valor en casas de cambio autorizadas antes de entregar tu efectivo.\n"
            "3. Ubica los cajeros automáticos o sucursales más seguras en el mapa."
        )
        botones = [
            {"texto": "Ver cotización en BROU", "url": "https://www.brou.com.uy/cotizaciones"},
            {"texto": "Ver cajeros y bancos cerca", "url": f"https://www.google.com/maps/search/banco+cajero+automatico/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 7. PROBLEMAS LEGALES, PAPELES Y JUZGADOS
    elif any(p in texto for p in ["abogado", "contrato", "incumplimiento", "demanda", "juzgado", "juez", "reclamo", "multa", "alquiler", "desalojo", "firma", "acuerdo"]):
        cuerpo_respuesta = (
            "Para resolver problemas legales o de contratos sin gastar una fortuna:\n\n"
            "1. No pagues abogados caros antes de intentar un acuerdo directo.\n"
            "2. Acude al Juzgado de Paz de tu zona para mediación gratuita.\n"
            "3. Guarda todos tus recibos, contratos y mensajes escritos."
        )
        botones = [
            {"texto": "Ver juzgados de paz cerca", "url": f"https://www.google.com/maps/search/juzgado+de+paz/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # RESPUESTA GENERAL INTELIGENTE (Cubre cualquier otra idea de trámite o solución)
    else:
        cuerpo_respuesta = (
            "Para resolver esta gestión de forma directa y económica:\n\n"
            "1. Evita intermediarios que te cobren de más y busca la oficina o canal oficial.\n"
            "2. Compara opciones y organiza tus papeles antes de hacer el trámite.\n"
            "3. Toca el botón de abajo para buscar el lugar exacto en el mapa."
        )
        botones = [
            {"texto": "Buscar solución en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    firma_app = f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\n"
    respuesta = firma_app + cuerpo_respuesta

    historial.append({"usuario": consulta, "asesor": respuesta})
    if len(historial) > 10:
        historial.pop(0)
    session["historial"] = historial

    return jsonify({"respuesta": respuesta, "botones": botones, "pausa_voz": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
