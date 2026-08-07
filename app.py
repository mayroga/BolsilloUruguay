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
    "BolsilloUruguay - ¿Qué necesidad resolvemos hoy?",
    "BolsilloUruguay - ¿En qué te puedo orientar?",
    "BolsilloUruguay - Cuéntame, ¿qué andas buscando resolver?",
    "BolsilloUruguay - ¿Qué dato o solución precisas?",
    "BolsilloUruguay - Adelante, ¿en qué te ayudamos?",
    "BolsilloUruguay - ¿Qué pago o ahorro revisamos?",
    "BolsilloUruguay - Escucho tu consulta, ¿qué necesitas?"
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
        return jsonify({"respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nSu acceso de asesoría ha concluido. Le sugerimos renovar su plan para continuar recibiendo orientación."}), 403

    data = request.get_json()
    consulta = data.get("mensaje", "").strip()
    lat = data.get("lat")
    lon = data.get("lon")

    if not consulta:
        return jsonify({"respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nIndíquenos qué trámite o necesidad desea resolver en Uruguay.", "pausa_voz": True})

    historial = session.get("historial", [])
    query_url = consulta.replace(" ", "+")
    texto_lower = consulta.lower()

    # DETECCIÓN INTELIGENTE DINÁMICA SEGÚN EL TIPO DE CONSULTA
    if any(p in texto_lower for p in ["salario", "sueldo", "pago", "cobro", "incompleto", "trabajo", "despido", "mtss", "recibo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría ante su consulta sobre '{consulta}':\n\n"
            "1. Reúna sus recibos de sueldo, constancias de horario y comunicaciones con la empresa.\n"
            "2. Presente su reclamo formal directamente ante el Ministerio de Trabajo y Seguridad Social (MTSS).\n"
            "3. Acérquese a la oficina del MTSS para gestionar una conciliación laboral."
        )
        botones = [
            {"texto": "Consultas MTSS", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"},
            {"texto": "Ver oficinas en el mapa", "url": f"https://www.google.com/maps/search/ministerio+de+trabajo+uruguay/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    elif any(p in texto_lower for p in ["bps", "jubilacion", "paro", "asignacion", "historia laboral", "desempleo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría ante su consulta sobre '{consulta}':\n\n"
            "1. Ingrese a los servicios en línea del BPS con su cédula de identidad digital.\n"
            "2. Verifique su historia laboral o el estado de sus trámites previsionales.\n"
            "3. Gestione su subsidio o prestación directamente en las plataformas oficiales habilitadas."
        )
        botones = [
            {"texto": "Servicios en Línea BPS", "url": "https://www.bps.gub.uy/"},
            {"texto": "Ver oficinas BPS en el mapa", "url": f"https://www.google.com/maps/search/bps+oficina+uruguay/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    elif any(p in texto_lower for p in ["patente", "multa", "sucive", "vehiculo", "auto", "moto", "padron"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría ante su consulta sobre '{consulta}':\n\n"
            "1. Tenga a mano el número de matrícula y padrón de su vehículo o bien.\n"
            "2. Consulte los estados de cuenta y opciones de pago en el portal unificado SUCIVE.\n"
            "3. Verifique normativas o multas directamente con la Intendencia correspondiente."
        )
        botones = [
            {"texto": "Portal SUCIVE", "url": "https://www.sucive.gub.uy/"},
            {"texto": "Congreso de Intendencias", "url": "https://congresodeintendentes.gub.uy/"}
        ]

    else:
        # RESPUESTA DIRECTA ÚTIL PARA CUALQUIER OTRA COSA (COMPRAS, PRECIOS, LUGARES, ETC.)
        cuerpo_respuesta = (
            f"Sugerencia de asesoría para resolver '{consulta}':\n\n"
            f"1. Evalúe las opciones de comercio, servicio o gestión disponibles en su zona en Uruguay.\n"
            f"2. Compare precios, presupuestos o condiciones antes de concretar su decisión.\n"
            f"3. Utilice el mapa interactivo para ubicar los locales o puntos de interés más cercanos."
        )
        botones = [
            {"texto": f"Buscar '{consulta}' en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
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
