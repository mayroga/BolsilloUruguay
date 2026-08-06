import os
import random
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-uruguay")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
DEV_USER = os.environ.get("DEV_USER", "admin")
DEV_PASS = os.environ.get("DEV_PASS", "secreto123")

SALUDOS_INICIALES = [
    "¿Qué necesidad resolvemos hoy?",
    "¿En qué te puedo orientar en este momento?",
    "Cuéntame, ¿qué andas buscando resolver?",
    "¿Qué dato o solución precisas ahora?",
    "Adelante, ¿en qué te ayudamos hoy?",
    "¿Qué gestión o ahorro revisamos?",
    "Escucho tu consulta, ¿qué necesitas?"
]

@app.route("/")
def index():
    if session.get("is_dev") or session.get("pagado"):
        saludo_actual = random.choice(SALUDOS_INICIALES)
        return render_template("app.html", saludo_dinamico=saludo_actual)
    return render_template("paywall.html")

@app.route("/crear-checkout", methods=["POST"])
def crear_checkout():
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="payment",
            success_url=request.host_url + "exito",
            cancel_url=request.host_url,
        )
        return jsonify({"url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/exito")
def exito():
    session["pagado"] = True
    return redirect(url_for("index"))

@app.route("/login-dev", methods=["POST"])
def login_dev():
    data = request.get_json()
    if data.get("usuario") == DEV_USER and data.get("clave") == DEV_PASS:
        session["is_dev"] = True
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route("/consultar", methods=["POST"])
def consultar():
    if not session.get("is_dev") and not session.get("pagado"):
        return jsonify({"respuesta": "Acceso restringido."}), 403

    data = request.get_json()
    consulta = data.get("mensaje", "").lower().strip()
    lat = data.get("lat")
    lon = data.get("lon")

    if not consulta:
        return jsonify({"respuesta": "Escribe o di qué necesitas resolver hoy."})

    query_url = consulta.replace(" ", "+")
    
    # El servidor procesa internamente el análisis de ahorro, opciones, costos de traslado y pasos exactos.
    if any(p in consulta for p in ["cafe", "café", "llave", "latino", "expreso"]):
        respuesta = (
            "• Opción más económica (Mayorista o Feria): Buscar en ferias vecinales o distribuidores directos (ahorro de hasta un 30%).\n"
            "• Opción comercial segura: Cadenas de descuento (Ta-Ta o reposiciones en supermercados aprovechando días de tarjeta bonificada).\n"
            "💡 Qué hacer: Revisa el folleto digital antes de trasladarte para evaluar si el costo de transporte justifica el viaje.\n"
            "⚙️ Por qué: Evita pagar de más por presentaciones pequeñas en comercios de cercanía."
        )
        botones = [
            {"texto": "🌐 Ver precios mayoristas y ferias en Mapa", "url": f"https://www.google.com/maps/search/mayoristas+ferias+cercanos/@{lat or -34.9011},{lon or -56.1645},14z"},
            {"texto": "🌐 Ver ofertas en Supermercados Ta-Ta", "url": "https://www.tata.com.uy/catalogue?query=cafe%20la%20llave"}
        ]
        
    elif any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo"]):
        respuesta = (
            "• Opción digital inmediata: Ingresa a tu cuenta de BPS o a la web del Ministerio de Trabajo (MTSS) para verificar aportes y liquidaciones legales.\n"
            "• Opción presencial guiada: Acércate a la oficina territorial si requieres asistencia directa con tus recibos de los últimos 6 meses.\n"
            "💡 Qué hacer: Ten a mano tu cédula de identidad para auditar que el cálculo de aguinaldo o salario vacacional sea exacto.\n"
            "⚙️ Por qué: Previene diferencias salariales no reclamadas y asegura el cumplimiento normativo."
        )
        botones = [
            {"texto": "🌐 Portal de Trámites MTSS", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"},
            {"texto": "🌐 Consultas y Usuario BPS", "url": "https://www.bps.gub.uy/"}
        ]
        
    elif any(p in consulta for p in ["dolar", "dólar", "cambio", "cotizacion"]):
        respuesta = (
            "• Opción oficial de referencia: Banco República (BROU), tasa segura sin comisiones ocultas para montos base.\n"
            "• Opción alternativa en plaza: Redes de cobranza y casas de cambio privadas si buscas cercanía geográfica.\n"
            "💡 Qué hacer: Revisa la cotización en pantalla antes de realizar la operación para elegir el mejor momento del día.\n"
            "⚙️ Por qué: Las fluctuaciones cambiarias impactan directamente en tu poder de compra."
        )
        botones = [
            {"texto": "🌐 Ver Pizarra Oficial BROU", "url": "https://www.brou.com.uy/cotizaciones"},
            {"texto": "🌐 Ubicar redes de cambio cercanas", "url": f"https://www.google.com/maps/search/casas+de+cambio+cercanas/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]
        
    elif any(p in consulta for p in ["nafta", "combustible", "gasoil"]):
        respuesta = (
            "• Opción unificada oficial: Estaciones ANCAP (precio regulado e idéntico en todo el territorio nacional).\n"
            "• Opción de optimización de ruta: Planifica cargas completas antes de ingresar a zonas alejadas o rurales donde no hay estaciones.\n"
            "💡 Qué hacer: Utiliza aplicaciones de fidelización para sumar beneficios o descuentos en cada carga.\n"
            "⚙️ Por qué: Evita desvíos innecesarios que consumen más combustible del que pretendes ahorrar."
        )
        botones = [
            {"texto": "🌐 Ver Estaciones ANCAP en el Mapa", "url": f"https://www.google.com/maps/search/estaciones+ancap/@{lat or -34.9011},{lon or -56.1645},13z"},
            {"texto": "🌐 Portal Oficial ANCAP", "url": "https://www.ancap.com.uy/"}
        ]
    
    else:
        respuesta = (
            f"• Opción principal sugerida: Evaluar proveedores locales y comercios barriales para evitar gastos excesivos de transporte.\n"
            f"• Opción alternativa digital: Comparar en plataformas de comercio electrónico de plaza para entrega a domicilio.\n"
            f"💡 Qué hacer: Revisa los requerimientos previos y compara al menos dos alternativas antes de decidir.\n"
            f"⚙️ Por qué: Una solución inteligente equilibra precio, distancia y accesibilidad real para tu bolsillo."
        )
        botones = [
            {"texto": "🌐 Buscar comercios y opciones en Mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"},
            {"texto": "🌐 Buscar alternativas en la Web", "url": f"https://www.google.com/search?q={query_url}+uruguay"}
        ]

    return jsonify({"respuesta": respuesta, "botones": botones})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
