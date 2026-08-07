import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import stripe
from google import genai
from google.genai import types
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-uruguay")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
DEV_USER = os.environ.get("DEV_USER", "admin")
DEV_PASS = os.environ.get("DEV_PASS", "secreto123")

URL_BASE_OFICIAL = "https://bolsillouruguay.onrender.com"

# Configuración de Clientes (Principal Gemini y Respaldo OpenAI / ChatGPT)
api_key_gemini = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=api_key_gemini) if api_key_gemini else None

api_key_openai = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=api_key_openai) if api_key_openai else None

SALUDOS_INICIALES = [
    "BolsilloUruguay - Qué necesidad resolvemos hoy?",
    "BolsilloUruguay - En qué te puedo orientar?",
    "BolsilloUruguay - Cuéntame, qué andas buscando resolver?",
    "BolsilloUruguay - Qué dato o solución precisas?",
    "BolsilloUruguay - Adelante, en qué te ayudamos?",
    "BolsilloUruguay - Qué pago o ahorro revisamos?",
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

def verificar_limite_diario():
    """
    Controla que el usuario no pase de 10 consultas al día.
    Se resetea automáticamente si cambia el día.
    """
    if session.get("is_dev"):
        return True # El modo desarrollador no tiene límite diario

    hoy_str = datetime.utcnow().strftime("%Y-%m-%d")
    ultimo_dia = session.get("ultimo_dia_consulta")
    
    if ultimo_dia != hoy_str:
        session["ultimo_dia_consulta"] = hoy_str
        session["consultas_hoy"] = 0

    consultas_actuales = session.get("consultas_hoy", 0)
    if consultas_actuales >= 10:
        return False
        
    return True

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
    session["consultas_hoy"] = 0
    session["ultimo_dia_consulta"] = datetime.utcnow().strftime("%Y-%m-%d")
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

    if not verificar_limite_diario():
        return jsonify({
            "respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nHa alcanzado el límite de 10 consultas permitidas para el día de hoy. Le invitamos a continuar mañana aprovechando sus días vigentes de servicio."
        }), 200

    data = request.get_json()
    consulta = data.get("mensaje", "").lower().strip()
    lat = data.get("lat")
    lon = data.get("lon")

    if not consulta:
        return jsonify({"respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nIndíquenos qué trámite, compra, servicio o gestión desea resolver en Uruguay.", "pausa_voz": True})

    # Incrementamos el contador de uso diario exitoso
    if not session.get("is_dev"):
        session["consultas_hoy"] = session.get("consultas_hoy", 0) + 1

    historial = session.get("historial", [])
    query_url = consulta.replace(" ", "+")

    # PROPOSITO AMPLIO, COMERCIAL Y DE GUÍA DIRECTA PARA MAY ROGA LLC
    system_instruction = (
        "Eres el asesor experto de la aplicación BolsilloUruguay, operada por MAY ROGA LLC. "
        "BolsilloUruguay se creó para romper con el laberinto burocrático del Estado y frenar el abuso de intermediarios y gestores caros que cobran por trámites que son gratuitos. "
        "ALCANCE TOTAL DE LA APLICACIÓN:\n"
        "1. AMPLIO Y COMERCIAL: No te limites solo a trámites públicos. Guía al usuario en todo lo que necesite en Uruguay: economía diaria, costos de vida, precios (desde opciones más económicas hasta las más premium), ubicación de hospitales, clínicas, farmacias, comercios, profesionales, abogados o servicios particulares.\n"
        "2. ORIENTACIÓN DE PRECIOS Y OPCIONES: Si consultan por salud, clínicas, servicios o compras, detalla rangos de precios (económicos hasta caros), ubicaciones y cómo encontrarlos.\n"
        "3. RUTA HASTA LA PUERTA: Tu único objetivo es guiar, dar la información que normalmente ocultan o cobran, y llevar al usuario hasta la puerta de la institución, comercio, profesional o servicio mediante 3 pasos claros y un enlace directo. Lo que ocurra después de llegar ya depende enteramente del cliente y del prestador, sin responsabilidad para la app.\n"
        "REGLAS CRÍTICAS DE VERDAD Y SEGURIDAD LEGAL:\n"
        "1. SOLO DI LA REALIDAD ESTRICTA: Está terminantemente prohibido inventar datos, precios falsos o direcciones inexistentes. Basate en la realidad de Uruguay.\n"
        "2. CERO DIAGNÓSTICOS MÉDICOS: Si preguntan por salud, indica dónde están los centros y rangos de precios de clínicas u hospitales, pero jamás emitas diagnósticos ni recetes.\n"
        "3. CERO ASTERISCOS, NEGRITAS O MARKDOWN: Escribe texto plano y conversacional puro para que la lectura de voz sea fluida y humana.\n"
        "4. LENGUAJE DE ASESOR PRUDENTE: Usa frases como 'Sugerencia de asesoría' o 'Le sugerimos'. No actúes como autoridad estatal.\n"
        "5. No menciones IA ni tecnologías internas.\n"
        "6. Encabeza siempre la respuesta con: BolsilloUruguay - https://bolsillouruguay.onrender.com\n\n"
    )

    cuerpo_respuesta = None

    # INTENTO 1: USAR GEMINI (PRINCIPAL)
    try:
        if gemini_client:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=consulta,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                ),
            )
            cuerpo_respuesta = response.text.replace("*", "").replace("#", "")
    except Exception as e:
        cuerpo_respuesta = None

    # INTENTO 2: RESPALDO CON OPENAI (CHATGPT) SI GEMINI FALLA
    if not cuerpo_respuesta and openai_client:
        try:
            response_openai = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": consulta}
                ],
                temperature=0.2
            )
            cuerpo_respuesta = response_openai.choices[0].message.content.replace("*", "").replace("#", "")
        except Exception as e:
            cuerpo_respuesta = None

    # RESPALDO FINAL DE EMERGENCIA SI AMBOS FALLAN
    if not cuerpo_respuesta:
        cuerpo_respuesta = (
            f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\n"
            f"Sugerencia de asesoría para su consulta sobre {consulta}:\n\n"
            "1. Identifique las opciones de mercado, comercio o servicio disponibles en su zona de Uruguay.\n"
            "2. Compare precios, rangos de costos y requisitos antes de avanzar con su gestión.\n"
            "3. Utilice el mapa interactivo para ubicar la alternativa exacta más próxima."
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
