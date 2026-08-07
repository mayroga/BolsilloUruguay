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
    "Que necesidad resolvemos hoy",
    "En que te puedo orientar en este momento",
    "Cuéntame que andas buscando resolver",
    "Que dato o solución precisas ahora",
    "Adelante en que te ayudamos hoy",
    "Que gestión o ahorro revisamos",
    "Escucho tu consulta que necesitas"
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
        return jsonify({"respuesta": "Escribe o di que necesidad de ahorro o tramite necesitas resolver hoy."})

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
            "Esta aplicación esta especializada exclusivamente en asesoría de ahorro, compras inteligentes, movilidad, trámites laborales, salud accesible y soluciones económicas en plaza. "
            "Por favor, realiza una consulta orientada a resolver un problema de tu economía, gestiones de trabajo, costos o servicios para brindarte la solución exacta."
        )
        botones = []
    else:
        if any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "deuda", "trabajo", "despido", "ley"]):
            cuerpo_respuesta = (
                "Para resolver esta situación salarial y proteger tus ingresos:\n\n"
                "1. Entra a tu cuenta del BPS en el servicio de historia laboral para verificar que tus aportes y días trabajados estén registrados exactamente como corresponden.\n"
                "2. Revisa el desglose de tu recibo de sueldo frente a los laudos vigentes de tu categoría en los Consejos de Salarios.\n"
                "3. Presenta un reclamo escrito ante la administración o gerencia de la empresa exigiendo el ajuste o pago en plazo.\n"
                "4. Si no obtienes respuesta inmediata, agenda una audiencia de conciliación sin costo en el Ministerio de Trabajo y Seguridad Social."
            )
            botones = [
                {"texto": "Consultar BPS", "url": "https://www.bps.gub.uy/"},
                {"texto": "Agendar en MTSS", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"}
            ]

        elif any(p in consulta for p in ["abogado", "contrato", "incumplimiento", "demanda"]):
            cuerpo_respuesta = (
                "Para solucionar un conflicto contractual o legal al menor costo posible:\n\n"
                "1. Acude primero a un centro de mediación o juzgado de paz de tu zona para lograr un acuerdo directo y gratuito antes de iniciar juicios largos.\n"
                "2. Si precisas asistencia legal formal y tus ingresos son limitados, solicita orientación en los consultorios jurídicos públicos habilitados.\n"
                "3. Si contratas un profesional particular, pacta honorarios fijos por escrito y etapas cumplidas para evitar cobros desmedidos.\n"
                "4. Junta todos los comprobantes, mensajes y el contrato original para respaldar tu reclamo desde el primer minuto."
            )
            botones = [
                {"texto": "Ver juzgados de paz y mediación", "url": f"https://www.google.com/maps/search/juzgado+de+paz+centros+de+mediacion/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["clinica", "salud", "medico", "policlinica", "hospital"]):
            cuerpo_respuesta = (
                "Para encontrar atención médica rápida y optimizar tus gastos de salud:\n\n"
                "1. Dirígete a la policlínica barrial de ASSE o al centro de atención primaria más cercano de tu red para consultas generales y recetas bonificadas.\n"
                "2. Compara los costos de la orden médica y los timbres profesionales en tu institución de asistencia médica antes de concurrir.\n"
                "3. Verifica si los medicamentos recetados están incluidos en el formulario terapéutico de medicamentos para evitar sobrecostos en farmacias privadas."
            )
            botones = [
                {"texto": "Ver policlínicas y centros de salud", "url": f"https://www.google.com/maps/search/clinica+policlinica+medico/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["carne", "asado", "carniceria", "san gregorio", "polanco"]):
            cuerpo_respuesta = (
                "Para comprar carne y alimentos al mejor precio en San Gregorio de Polanco:\n\n"
                "• Visita el Autoservicio La Cadena sobre Gral. Artigas para encontrar ofertas en cortes y productos de almacén.\n"
                "• Revisa las opciones en Cutti Congelados en Gral. Artigas 132 para stockear mercadería a menor costo.\n"
                "• Compara precios con Carnicería La Pampa o Autoservicio Vida Nueva para elegir el corte más conveniente del día."
            )
            botones = [
                {"texto": "Ver ubicación exacta de los comercios", "url": f"https://www.google.com/maps/search/carnicerias+en+San+Gregorio+de+Polanco/@{lat or -32.6517},{lon or -55.5861},14z"}
            ]

        elif any(p in consulta for p in ["dolar", "dólar", "cambio", "cotizacion"]):
            cuerpo_respuesta = (
                "Para realizar operaciones de cambio de moneda de forma segura y conveniente:\n\n"
                "• Consulta la pizarra oficial del Banco República (BROU) para tener la referencia exacta sin comisiones ocultas.\n"
                "• Compara las tasas de compra y venta en las redes de cobranza y casas de cambio privadas de tu zona.\n"
                "• Realiza la operación en los horarios de mayor estabilidad cambiaria durante la jornada bancaria."
            )
            botones = [
                {"texto": "Ver pizarra actual del BROU", "url": "https://www.brou.com.uy/cotizaciones"},
                {"texto": "Ver casas de cambio cercanas", "url": f"https://www.google.com/maps/search/casas+de+cambio/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

        elif any(p in consulta for p in ["transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "auto"]):
            cuerpo_respuesta = (
                "Para optimizar tus traslados y reducir el gasto en movilidad:\n\n"
                "1. Utiliza tarjetas recargables o abonos de transporte para aprovechar tarifas bonificadas en tus recorridos frecuentes.\n"
                "2. Planifica los trayectos directos para evitar desvíos innecesarios que eleven el consumo de combustible o pasajes.\n"
                "3. Consulta los puntos de recarga y las terminales operativas antes de iniciar tu viaje."
            )
            botones = [
                {"texto": "Ver terminales y estaciones en mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},13z"}
            ]

        else:
            cuerpo_respuesta = (
                "Para resolver esta gestión de forma directa y económica:\n\n"
                "1. Evita intermediarios innecesarios y comunícate directamente con los canales oficiales de atención o proveedores autorizados.\n"
                "2. Compara al menos dos opciones de costo operativo antes de comprometer tu presupuesto.\n"
                "3. Ejecuta la solución mediante los accesos directos habilitados para completar el trámite de forma segura."
            )
            botones = [
                {"texto": "Buscar soluciones en el mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
            ]

    # Incorporar el enlace oficial y el nombre de la app al inicio para compartir por WhatsApp limpiamente
    firma_app = f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\n"
    respuesta = firma_app + cuerpo_respuesta

    historial.append({"usuario": consulta, "asesor": respuesta})
    if len(historial) > 10:
        historial.pop(0)
    session["historial"] = historial

    return jsonify({"respuesta": respuesta, "botones": botones})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
