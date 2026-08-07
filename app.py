import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import stripe
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-uruguay")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
DEV_USER = os.environ.get("DEV_USER", "admin")
DEV_PASS = os.environ.get("DEV_PASS", "secreto123")

URL_BASE_OFICIAL = "https://bolsillouruguay.onrender.com"

# Configuración del cliente de Gemini
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SALUDOS_INICIALES = [
    "BolsilloUruguay - ¿Qué necesidad resolvemos hoy?",
    "BolsilloUruguay - ¿En qué te puedo orientar?",
    "BolsilloUruguay - Cuéntame, qué andas buscando resolver?",
    "BolsilloUruguay - ¿Qué dato o solución precisas?",
    "BolsilloUruguay - Adelante, ¿en qué te ayudamos?",
    "BolsilloUruguay - ¿Qué pago o ahorro revisamos?",
    "BolsilloUruguay - Escucho tu consulta, qué necesitas?"
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
    consulta = data.get("mensaje", "").lower().strip()
    lat = data.get("lat")
    lon = data.get("lon")

    if not consulta:
        return jsonify({"respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nIndíquenos qué trámite, compra o gestión desea resolver en Uruguay.", "pausa_voz": True})

    historial = session.get("historial", [])
    query_url = consulta.replace(" ", "+")

    # Prompt del Sistema estricto para que el modelo haga su trabajo real sin rodeos
    system_instruction = (
        "Eres el asesor experto de la aplicación 'BolsilloUruguay'. "
        "Tu única tarea es dar respuestas directas, exactas y resolutivas para resolver problemas cotidianos, trámites, compras, salarios, salud, transporte o servicios en Uruguay. "
        "REGLAS ESTRICTAS:\n"
        "1. Cero respuestas genéricas o plantillas vacías. Si te preguntan dónde comprar ropa barata, diles zonas, ferias o comercios reales de Montevideo o el interior. Si te preguntan por sueldos impagos, menciona el MTSS de forma directa. Adapta la respuesta 100% a lo que el usuario preguntó.\n"
        "2. Estructura la respuesta exactamente en 3 pasos directos y útiles.\n"
        "3. Usa un tono de asesor profesional y prudente (usa términos como 'Sugerencia de asesoría' o 'Le sugerimos'), sin sonar como autoridad gubernamental.\n"
        "4. No digas ni IA, ni ChatGPT, ni inteligencia artificial.\n"
        "5. Encabeza siempre tu respuesta con: BolsilloUruguay - https://bolsillouruguay.onrender.com\n\n"
    )

    try:
        # Llamada directa al modelo de Gemini para que analice y resuelva con total libertad
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=consulta,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            ),
        )
        cuerpo_respuesta = response.text
    except Exception as e:
        # Fallback de emergencia si la API demora o falla
        cuerpo_respuesta = (
            f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\n"
            f"Sugerencia de asesoría para su consulta sobre '{consulta}':\n\n"
            "1. Verifique los detalles y antecedentes específicos de su planteo.\n"
            "2. Contacte directamente a la entidad o comercio vinculado en su zona.\n"
            "3. Utilice el mapa interactivo para ubicar la solución más próxima."
        )

    botones = [
        {"texto": f"Buscar '{consulta}' en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
    ]

    historial.append({"usuario": consulta, "asesor": cuerpo_respuesta})
    if len(historial) > 10:
        historial.pop(0)
    session["historial"] = historial

    return jsonify({"respuesta": cuerpo_respuesta, "botones": botones, "pausa_voz": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
