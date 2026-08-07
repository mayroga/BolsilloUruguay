import os
import random
import re
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

# Configuración de Clientes corregida para evitar NameError en Render
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
        return True

    hoy_str = datetime.utcnow().strftime("%Y-%m-%d")
    ultimo_dia = session.get("ultimo_dia_consulta")
    
    if ultimo_dia != hoy_str:
        session["ultimo_dia_consulta"] = hoy_str
        session["consultas_hoy"] = 0

    consultas_actuales = session.get("consultas_hoy", 0)
    if consultas_actuales >= 10:
        return False
        
    return True

def limpiar_texto_para_voz(texto):
    """
    Elimina URLs, enlaces web y menciones de dominios para que el lector de voz 
    nunca lea direcciones web en voz alta.
    """
    if not texto:
        return ""
    texto_limpio = re.sub(r'https?://\S+|www\.\S+', '', texto)
    texto_limpio = re.sub(r'\b[a-zA-Z0-9-]+\.(com|org|net|uy|edu|gov|mil|biz|info|mobi|name|aero|jobs|museum)\b', '', texto_limpio, flags=re.IGNORECASE)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    return texto_limpio

def extraer_lugar_para_mapa(consulta):
    """
    Traduce la consulta del usuario a una categoría o lugar físico real de Google Maps
    para evitar enviar frases de síntomas o textos largos al mapa.
    """
    c = consulta.lower()
    
    if any(k in c for k in ["dolor", "orino", "ardor", "fiebre", "hospital", "clínica", "medico", "médico", "doctor", "emergencia", "salud", "enfermo", "farmacia", "pastilla", "receta"]):
        if "farmacia" in c:
            return "farmacia"
        return "hospital clinica centro de salud"
    
    if "bps" in c or "jubilacion" in c or "pension" in c:
        return "BPS oficina"
    if "dgi" in c or "impuesto" in c or "rut" in c:
        return "DGI oficina tributaria"
    if "asse" in c or "hospital militar" in c or "hospital policial" in c:
        return "hospital publico ASSE"
    if "intendencia" in c or "imm" in c or "patente" in c or "multa" in c:
        return "Intendencia departamental oficina"
    
    if "supermercado" in c or "comida" in c or "feria" in c or "abastos" in c:
        return "supermercado feria"
    if "gas" in c or "supergas" in c or "combustible" in c or "ancap" in c:
        return "estacion de servicio ANCAP"
    if "banco" in c or "BROU" in c or "dinero" in c:
        return "banco BROU"
        
    return "hospital farmacia centro comercial"

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

    if not session.get("is_dev"):
        session["consultas_hoy"] = session.get("consultas_hoy", 0) + 1

    historial = session.get("historial", [])
    
    lugar_mapa = extraer_lugar_para_mapa(consulta)
    query_mapa_url = lugar_mapa.replace(" ", "+")

    # Instrucciones del sistema optimizadas: Cobertura universal de clases con foco en supervivencia económica diaria
    system_instruction = (
        "ROL Y IDENTIDAD:\n"
        "Eres el asesor experto de la aplicación BolsilloUruguay, operada por MAY ROGA LLC. "
        "Tu tono es el de un asesor prudente, empático, altamente resolutivo y muy profesional. Usa frases como 'Sugerencia de asesoría' o 'Le sugerimos'. "
        "No actúes como una autoridad estatal y jamás menciones que eres una IA ni tecnologías internas.\n\n"

        "MISIÓN CRÍTICA Y ENFOQUE SOCIAL UNIVERESAL:\n"
        "La aplicación debe IDENTIFICAR Y RESOLVER el problema del cliente directamente. Está prohibido mandarlo a investigar por su cuenta o responder con generalidades genéricas. "
        "Si te piden un producto, servicio o trámite, tú debes darle la respuesta con datos concretos de Uruguay.\n"
        "1. ENFOQUE PRINCIPAL (SUPERVIVENCIA DIARIA): Resuelve necesidades cotidianas de todas las clases sociales (precios de alimentos, marcas locales, combustibles, alquileres, casas y transporte). Debes ofrecer SIEMPRE un mínimo de 3 opciones o alternativas físicas reales (ejemplo: grandes superficies, distribuidoras mayoristas, ferias vecinales de Montevideo o almacenes locales) indicando rangos de precios estimados o zonas clave de abasto.\n"
        "2. ENFOQUE PREMIUM: Si un usuario con recursos económicos elevados consulta por opciones costosas o zonas exclusivas, guíalo de igual manera dándole las 3 mejores opciones de alta gama sin escatimar información ni forzar el ahorro.\n"
        "3. TRÁMITES Y GESTIONES: Guía paso a paso al usuario para resolver trámites gratuitos en BPS, DGI, Intendencias, ASSE y ministerios, evitando intermediarios costosos.\n"
        "Tu objetivo es guiar con claridad, con geografía social real de Uruguay y llevar al usuario hasta la puerta de la solución. Lo que ocurra después de llegar ya depende del cliente y del prestador, sin responsabilidad para la app.\n\n"

        "REGLAS CRÍTICAS DE SEGURIDAD LEGAL:\n"
        "- SOLO REALIDAD ESTRICTA: Prohibido inventar comercios o direcciones inexistentes. Usa tu conocimiento del mercado uruguayo real. Si no posees el precio exacto del día de un artículo específico, ofrece el rango de costo estimado actual en el mercado uruguayo (por ejemplo, en pesos uruguayos) y menciona los puntos de venta o cadenas más económicas donde se distribuye.\n"
        "- CERO DIAGNÓSTICOS MÉDICOS: Indica dónde están los centros médicos o farmacias, pero JAMÁS emitas diagnósticos, opiniones médicas ni recetes medicamentos.\n\n"

        "REGLAS ESTRICTAS DE FORMATO (CRÍTICO PARA LECTOR DE VOZ):\n"
        "- ENCABEZADO OBLIGATORIO: Comienza siempre la primera línea de tu respuesta únicamente con la palabra: BolsilloUruguay\n"
        "- PROHIBIDO ENLACES O URLS: No incluyas NINGUNA dirección web, enlaces HTTP ni textos de dominios en tu respuesta. El usuario solo debe recibir texto limpio.\n"
        "- TEXTO PLANO PURO: Está TERMINANTEMENTE PROHIBIDO el uso de asteriscos (*), almohadillas (#), guiones de lista (- ) o cualquier formato Markdown. Escribe exclusivamente en párrafos limpios, directos y conversacionales para que el lector de voz digital de la app lea el texto de forma fluida, natural, humana y sin tropiezos.\n"
    )
    cuerpo_respuesta = None

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

    if not cuerpo_respuesta:
        cuerpo_respuesta = (
            f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\n"
            f"Sugerencia de asesoría para su consulta sobre {consulta}:\n\n"
            "1. Identifique las opciones de mercado, comercio o servicio disponibles en su zona de Uruguay.\n"
            "2. Compare precios, rangos de costos y requisitos antes de avanzar con su gestión.\n"
            "3. Utilice el mapa interactivo para ubicar la alternativa exacta más próxima."
        )

    voz_texto_limpio = limpiar_texto_para_voz(cuerpo_respuesta)

    botones = [
        {"texto": f"Ubicar centros en el mapa", "url": f"https://www.google.com/maps/search/{query_mapa_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
    ]

    historial.append({"usuario": consulta, "asesor": cuerpo_respuesta})
    if len(historial) > 10:
        historial.pop(0)
    session["historial"] = historial

    return jsonify({
        "respuesta": cuerpo_respuesta, 
        "voz_texto": voz_texto_limpio, 
        "botones": botones, 
        "pausa_voz": True
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
