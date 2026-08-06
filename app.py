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

# Tu URL fija oficial en Render
URL_BASE_OFICIAL = "https://bolsillouruguay.onrender.com"

SALUDOS_INICIALES = [
    "¿Qué necesidad resolvemos hoy?",
    "¿En qué te puedo orientar en este momento?",
    "Cuéntame, ¿qué andas buscando resolver?",
    "¿Qué dato o solución precisas ahora?",
    "Adelante, ¿en qué te ayudamos hoy?",
    "¿Qué gestión o ahorro revisamos?",
    "Escucho tu consulta, ¿qué necesitas?"
]

def verificar_acceso_pagado():
    """Verifica si el usuario es desarrollador o si su pago de 10 días sigue vigente."""
    if session.get("is_dev"):
        return True
    
    # Comprobar si tiene fecha de expiración y si aún no ha vencido
    expiracion = session.get("expiracion_pago")
    if expiracion:
        # Convertir texto guardado en fecha y comparar con el momento actual
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
        # Forzamos las URLs de retorno usando tu dominio exacto de Render para evitar fallos
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
    # Al pagarse con éxito, otorgamos el acceso exacto por 10 días a partir de este segundo
    tiempo_expiracion = datetime.utcnow() + timedelta(days=10)
    session["expiracion_pago"] = tiempo_expiracion.isoformat()
    session["historial"] = []
    return redirect(URL_BASE_OFICIAL)

@app.route("/login-dev", methods=["POST"])
def login_dev():
    data = request.get_json()
    if data.get("usuario"] == DEV_USER and data.get("clave"] == DEV_PASS:
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
        return jsonify({"respuesta": "Escribe o di qué necesidad de ahorro o trámite necesitas resolver hoy."})

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
        respuesta = (
            "Esta aplicación está especializada exclusivamente en asesoría de ahorro, compras inteligentes, movilidad, trámites laborales, salud accesible y soluciones económicas en plaza.\n\n"
            "Por favor, realiza una consulta orientada a resolver un problema de tu economía, gestiones de trabajo, costos o servicios para brindarte la solución exacta."
        )
        botones = []
    else:
        if any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley"]):
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

        elif any(p in consulta for p in ["abogado", "contrato", "incumplimiento", "demanda"]):
            respuesta = (
                "Para resolver un incumplimiento de contrato o situación legal buscando la opción más económica y protegiendo tu dinero:\n\n"
                "1. **Defensa gratuita inicial:** Antes de contratar un abogado particular costoso, acude a los centros de mediación o justicia de paz locales para conciliaciones de bajo costo o gratuitas.\n"
                "2. **Asistencia jurídica pública:** Si tus ingresos son limitados, verifica el acceso a consultorios jurídicos gratuitos o defensorías públicas para evaluar el contrato sin honorarios abusivos.\n"
                "3. **Si contratas abogado privado:** Exige un presupuesto cerrado por escrito (honorarios fijos por etapas) y evita porcentajes desmedidos.\n"
                "4. **Qué hacer:** Reúne el contrato original, comprobantes de pago y mensajes con el incumplimiento antes de iniciar gestiones."
            )
            botones = [
                {"texto": "🌐 Ver juzgados de paz y mediación en el Mapa", "url": f"https://www.google.com/maps/search/juzgado+de+paz+centros+de+mediacion/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["clinica", "salud", "medico", "policlinica", "hospital"]):
            respuesta = (
                f"Para encontrar la mejor opción de salud y optimizar tus gastos médicos:\n\n"
                "1. **Opción pública de referencia:** Red de atención primaria (ASSE) y policlínicas barriales de la zona para consultas y medicamentos bonificados.\n"
                "2. **Opción mutual de cercanía:** Compara cuotas sociales de instituciones médicas privadas locales si buscas cobertura extendida.\n"
                "3. **Qué hacer:** Verifica los costos de órdenes, timbres profesionales y recetas antes de trasladarte para evitar cobros sorpresa."
            )
            botones = [
                {"texto": "🌐 Ver policlínicas y centros de salud en el Mapa", "url": f"https://www.google.com/maps/search/clinica+policlinica+medico/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["carne", "asado", "carniceria", "san gregorio", "polanco"]):
            respuesta = (
                "Opciones directas de compra de carne en San Gregorio de Polanco según lo que busques gastar:\n\n"
                "• **Opción más económica y completa:** Autoservicio La Cadena (Gral. Artigas), ideal para surtidos generales y buenos precios en frescos.\n"
                "• **Opción de ahorro en congelados:** Cutti Congelados (Gral. Artigas 132), excelente variedad para stockear sin gastar de más.\n"
                "• **Opción tradicional de barrio:** Carnicería La Pampa (Gral. Artigas 136) o Autoservicio Vida Nueva (Arturo Mollo 147) para compras rápidas."
            )
            botones = [
                {"texto": "🌐 Ver ubicación exacta de los comercios", "url": f"https://www.google.com/maps/search/carnicerias+en+San+Gregorio+de+Polanco/@{lat or -32.6517},{lon or -55.5861},14z"}
            ]

        elif any(p in consulta for p in ["dolar", "dólar", "cambio", "cotizacion"]):
            respuesta = (
                "Para cambiar dinero al mejor valor y sin riesgos:\n\n"
                "• **Opción oficial de referencia:** Banco República (BROU), tasa segura sin comisiones ocultas para montos base.\n"
                "• **Opción alternativa en plaza:** Redes de cobranza y casas de cambio privadas si buscas cercanía geográfica.\n"
                "• **Qué hacer:** Revisa la cotización en pantalla antes de operar para elegir el mejor momento del día."
            )
            botones = [
                {"texto": "🌐 Ver pizarra actual del BROU", "url": "https://www.brou.com.uy/cotizaciones"},
                {"texto": "🌐 Ver casas de cambio cercanas", "url": f"https://www.google.com/maps/search/casas+de+cambio/@{lat or -34.9011},{lon or -56.1645},14z"}
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
                {"texto": "🌐 Buscar soluciones y sitios exactos en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

    historial.append({"usuario": consulta, "asesor": respuesta})
    if len(historial) > 10:
        historial.pop(0)
    session["historial"] = historial

    return jsonify({"respuesta": respuesta, "botones": botones})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
