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
    
    palabras_clave_validas = [
        "sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley",
        "comprar", "precio", "donde", "barato", "carne", "cafe", "supermercado", "feria", "alimento", "gas",
        "transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "auto",
        "tramite", "banco", "brou", "bps", "mtss", "comercio", "ahorro", "gasto", "mercado", "negocio",
        "clinica", "salud", "medico", "abogado", "contrato", "dolar", "cambio", "cotizacion"
    ]

    es_valida = any(palabra in consulta for palabra in palabras_clave_validas)
    if not es_valida and len(historial) > 0 and any(p in consulta for p in ["cuanto", "donde", "cual", "como", "y ", "ese", "esta", "ahi"]):
        es_valida = True

    if not es_valida:
        cuerpo_respuesta = (
            "Solo hablo de cosas para ahorrar dinero, compras, trabajo, salud y trámites sencillos. "
            "Cuéntame qué problema tienes para ayudarte con palabras muy fáciles."
        )
        botones = []
    else:
        if any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley"]):
            cuerpo_respuesta = (
                "Para cobrar lo justo y que no te falte plata:\n\n"
                "1. Mira bien tu recibo de sueldo en un papel o en el celular.\n"
                "2. Si te pagaron menos, anda a hablar tranquilo con el jefe o el que paga.\n"
                "3. Si no te quieren dar tu plata, ve al Ministerio de Trabajo a pedir ayuda gratis."
            )
            botones = [
                {"texto": "Ir al BPS", "url": "https://www.bps.gub.uy/"},
                {"texto": "Ir al Ministerio de Trabajo", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"}
            ]

        elif any(p in consulta for p in ["abogado", "contrato", "incumplimiento", "demanda"]):
            cuerpo_respuesta = (
                "Para solucionar un problema con papeles o plata sin gastar de más:\n\n"
                "1. No gastes en abogados caros de entrada.\n"
                "2. Ve al Juzgado de Paz de tu barrio y pide hablar con alguien para solucionar el problema hablando.\n"
                "3. Guarda siempre tus papeles y boletas."
            )
            botones = [
                {"texto": "Ver juzgados cerca", "url": f"https://www.google.com/maps/search/juzgado+de+paz/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["clinica", "salud", "medico", "policlinica", "hospital"]):
            cuerpo_respuesta = (
                "Para verte con un doctor sin gastar mucho:\n\n"
                "1. Ve a la policlínica de tu barrio o al hospital público más cercano.\n"
                "2. Pide turno temprano para que te atiendan sin pagar consulta cara.\n"
                "3. Lleva tu cédula."
            )
            botones = [
                {"texto": "Ver policlínicas cerca", "url": f"https://www.google.com/maps/search/policlinica+medico/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["carne", "asado", "carniceria", "san gregorio", "polanco"]):
            cuerpo_respuesta = (
                "Para comprar comida barata:\n\n"
                "• Ve al Autoservicio La Cadena en la calle General Artigas para buscar ofertas.\n"
                "• Mira también en Cutti Congelados si buscas pollo o carne a mejor precio.\n"
                "• Compara en dos almacenes antes de comprar."
            )
            botones = [
                {"texto": "Ver comercios en el mapa", "url": f"https://www.google.com/maps/search/carnicerias+en+San+Gregorio+de+Polanco/@{lat or -32.6517},{lon or -55.5861},14z"}
            ]

        elif any(p in consulta for p in ["dolar", "dólar", "cambio", "cotizacion"]):
            cuerpo_respuesta = (
                "Para cambiar tus pesos o dólares de forma segura:\n\n"
                "• Ve al Banco República (BROU) que es seguro y no cobra de más.\n"
                "• Mira bien el número en la pantalla antes de entregar tu plata."
            )
            botones = [
                {"texto": "Ver valor del dólar en BROU", "url": "https://www.brou.com.uy/cotizaciones"},
                {"texto": "Ver casas de cambio cerca", "url": f"https://www.google.com/maps/search/casas+de+cambio/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "auto"]):
            cuerpo_respuesta = (
                "Para moverte gastando menos:\n\n"
                "1. Usa la tarjeta de boleto si tiene descuento.\n"
                "2. Pregunta cuál es el colectivo o bondi directo para no dar vueltas de más."
            )
            botones = [
                {"texto": "Ver paradas y rutas", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},13z"}
            ]

        else:
            cuerpo_respuesta = (
                "Para resolver esto fácil y rápido:\n\n"
                "1. No pagues de más ni hables con intermediarios.\n"
                "2. Ve directo al lugar que te solucione el problema.\n"
                "3. Toca el botón de abajo para buscar el sitio exacto en el mapa."
            )
            botones = [
                {"texto": "Buscar en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
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
