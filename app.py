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
        return jsonify({"respuesta": "Escribe o di qué necesidad de ahorro o trámite necesitas resolver hoy."})

    query_url = consulta.replace(" ", "+")
    
    # Palabras clave permitidas dentro del alcance de la aplicación (Economía, compras, laboral, transporte, trámites)
    palabras_clave_validas = [
        "sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley",
        "comprar", "precio", "donde", "barato", "carne", "cafe", "supermercado", "feria", "alimento", "gas",
        "transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "auto",
        "tramite", "banco", "brou", "bps", "mtss", "comercio", "ahorro", "gasto", "mercado", "negocio"
    ]

    # Filtro de alcance estricto: Si la consulta no tiene relación con el servicio, se limita a explicar su propósito
    es_valida = any(palabra in consulta for palabra in palabras_clave_validas)

    if not es_valida:
        respuesta = (
            "Esta aplicación está especializada exclusivamente en asesoría de ahorro, compras inteligentes, movilidad, trámites laborales y soluciones económicas en plaza.\n\n"
            "Por favor, realiza una consulta orientada a resolver un problema de tu economía, gestiones de trabajo, costos de productos o transporte para brindarte la solución exacta."
        )
        botones = []

    elif any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley"]):
        respuesta = (
            f"Para resolver tu situación sobre '{consulta}' de forma efectiva y sin gastar en abogados:\n\n"
            "1. **Auditoría interna de tu caso:** Verifica tus recibos de sueldo y tu historia laboral digital en el BPS para contrastar los números reales frente a lo que te corresponde por ley.\n"
            "2. **Cálculo y base legal:** Si se trata de haberes impagos o cálculos de liquidación (como aguinaldo o salario vacacional), recuerda que se estructuran sobre los promedios y días trabajados exactos.\n"
            "3. **Paso a seguir:** Presenta un reclamo formal y por escrito ante la administración de la empresa exigiendo el desglose.\n"
            "4. **Defensa gratuita:** Si no hay respuesta favorable, agenda una audiencia de conciliación en el Ministerio de Trabajo (MTSS), donde un inspector interviene sin costo para hacer valer tus derechos."
        )
        botones = [
            {"texto": "🌐 Consultar BPS", "url": "https://www.bps.gub.uy/"},
            {"texto": "🌐 Agendar en MTSS", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"}
        ]

    elif any(p in consulta for p in ["comprar", "precio", "donde", "barato", "carne", "cafe", "supermercado", "feria", "alimento", "gas"]):
        respuesta = (
            f"Estrategia de ahorro y compra inteligente para '{consulta}':\n\n"
            "1. **Opción más económica (Mayorista / Feria / Productor):** Compara siempre en ferias vecinales o distribuidores de plaza para evitar el sobreprecio de los comercios de cercanía.\n"
            "2. **Opción comercial de apoyo:** Cadenas de descuento o supermercados medianos aprovechando promociones con tarjetas asociadas o días de rebaja en stock.\n"
            "3. **Análisis de traslado:** Valora la distancia; gastar de más en combustible o transporte público para buscar un producto lejano a veces anula el ahorro obtenido.\n"
            "4. **Qué hacer:** Revisa el costo por unidad de medida (kilo o litro) antes de decidir el punto de compra."
        )
        botones = [
            {"texto": "🌐 Buscar opciones y comercios cercanos en Mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    elif any(p in consulta for p in ["transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "auto"]):
        respuesta = (
            f"Optimización de movilidad y costos para '{consulta}':\n\n"
            "1. **Opción de menor costo:** Evalúa abonos mensuales, tarjetas recargables de transporte o escalas locales que reducen el impacto diario en el bolsillo.\n"
            "2. **Opción de eficiencia de tiempo:** Si el costo de oportunidad es alto, utiliza rutas directas para evitar demoras innecesarias.\n"
            "3. **Qué hacer:** Planifica los trayectos con anticipación y evita desvíos que disparen el consumo de combustible o pasajes adicionales."
        )
        botones = [
            {"texto": "🌐 Ver terminales, estaciones y rutas en Mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},13z"}
        ]

    else:
        respuesta = (
            f"Solución experta orientada a tu consulta sobre '{consulta}':\n\n"
            "1. **Análisis del problema:** Para resolver esta necesidad al menor costo y con el máximo rendimiento, evita intermediarios y acude directamente a los proveedores o fuentes oficiales de plaza.\n"
            "2. **Estrategia recomendada:** Compara al menos dos alternativas (la de menor costo operativo y la de referencia segura) antes de tomar una decisión financiera o de gestión.\n"
            "3. **Qué hacer:** Utiliza los canales directos habilitados para ejecutar la solución de forma inmediata y segura."
        )
        botones = [
            {"texto": "🌐 Buscar soluciones y sitios exactos en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"},
            {"texto": "🌐 Consultar referencias oficiales en la Web", "url": f"https://www.google.com/search?q={query_url}+uruguay"}
        ]

    return jsonify({"respuesta": respuesta, "botones": botones})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
