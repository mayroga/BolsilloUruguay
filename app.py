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
    consulta = data.get("mensaje", "").lower().strip()
    lat = data.get("lat")
    lon = data.get("lon")

    if not consulta:
        return jsonify({"respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nIndíquenos qué trámite, problema o gestión en Uruguay desea que le orientemos a resolver con precisión.", "pausa_voz": True})

    historial = session.get("historial", [])
    query_url = consulta.replace(" ", "+")
    texto = consulta

    # 1. TRABAJO, SALARIOS, DESPIDOS Y RECLAMOS LABORALES (MTSS)
    if any(p in texto for p in ["salario", "sueldo", "pago", "cobro", "incompleto", "menos", "trabajo", "despido", "renuncia", "aguinaldo", "licencia", "mtss", "patron", "recibo", "despedido"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Reúna inmediatamente sus últimos recibos de sueldo, constancias de horarios y comunicaciones escritas con su empleador.\n"
            "2. Presente su reclamo formal por liquidación incorrecta o falta de pago en el Ministerio de Trabajo y Seguridad Social (MTSS).\n"
            "3. Acérquese a la dependencia del MTSS para una audiencia de conciliación laboral gratuita."
        )
        botones = [
            {"texto": "Reclamos y Consultas MTSS", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"},
            {"texto": "Oficinas del MTSS en el mapa", "url": f"https://www.google.com/maps/search/ministerio+de+trabajo+y+seguridad+social+montevideo/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 2. BPS (JUBILACIONES, HISTORIA LABORAL, ASIGNACIONES, SEGURO DE PARO)
    elif any(p in texto for p in ["bps", "jubilacion", "jubilación", "paro", "asignacion", "asignación", "historia laboral", "subsidio", "apuntes", "desempleo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Ingrese a los 'Servicios en Línea del BPS' utilizando su cédula de identidad y clave personal o identidad digital.\n"
            "2. Verifique en detalle su historia laboral para corroborar que los aportes patronales correspondan a los meses trabajados.\n"
            "3. Inicie o gestione el subsidio por desempleo, jubilación o asignación directamente en la plataforma digital oficial."
        )
        botones = [
            {"texto": "Servicios en Línea BPS", "url": "https://www.bps.gub.uy/"},
            {"texto": "Oficinas BPS en el mapa", "url": f"https://www.google.com/maps/search/bps+oficina+uruguay/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 3. SUCIVE, PATENTE Y MULTAS (INTENDENCIAS DE TODO EL PAÍS)
    elif any(p in texto for p in ["patente", "multa", "sucive", "contribucion", "contribución", "intendencia", "imm", "vehiculo", "padron", "departamento", "interior", "auto", "moto"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Tenga a mano el número de matrícula y padrón de su vehículo o el padrón catastral de su inmueble.\n"
            "2. Consulte estados de cuenta, adeudos y convenios vigentes en el portal unificado de SUCIVE.\n"
            "3. Diríjase a la Intendencia departamental correspondiente si requiere gestionar permisos locales o multas específicas."
        )
        botones = [
            {"texto": "Portal SUCIVE", "url": "https://www.sucive.gub.uy/"},
            {"texto": "Congreso de Intendencias", "url": "https://congresodeintendentes.gub.uy/"}
        ]

    # 4. EMPLEO, VACANTES Y CAPACITACIÓN (INEFOP)
    elif any(p in texto for p in ["empleo", "trabajo", "curriculum", "vacante", "oferta", "inefop", "capacitacion", "capacitación", "curp", "buscar trabajo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Postúlese de forma directa a las vacantes formales registradas en la bolsa oficial de empleo del MTSS.\n"
            "2. Inscríbase en los cursos de reconversión y capacitación profesional subvencionados por INEFOP.\n"
            "3. Actualice sus datos de contacto y antecedentes formativos para llamados públicos y privados."
        )
        botones = [
            {"texto": "Bolsa de Empleo MTSS", "url": "https://www.empleos.gub.uy/"},
            {"texto": "Cursos y Becas INEFOP", "url": "https://www.inefop.org.uy/"}
        ]

    # 5. DGI, MONOTRIBUTO Y FACTURACIÓN
    elif any(p in texto for p in ["dgi", "monotributo", "factura", "impuesto", "ruc", "empresa", "aportes", "literal e", "tributo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Acceda con su RUT y clave de acceso a los servicios digitales del portal de la DGI.\n"
            "2. Verifique el cumplimiento de sus pagos mensuales de Monotributo o régimen Literal E para evitar multas.\n"
            "3. Emita sus comprobantes fiscales electrónicos exigidos por la normativa fiscal vigente."
        )
        botones = [
            {"texto": "Portal Oficial DGI", "url": "https://www.dgi.gub.uy/"},
            {"texto": "Oficinas DGI en el mapa", "url": f"https://www.google.com/maps/search/dgi+oficina/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 6. SALUD, ASSE, POLICLÍNICAS Y FARMACIAS DE TURNO
    elif any(p in texto for p in ["clinica", "salud", "medico", "policlinica", "hospital", "doctor", "farmacia", "remedio", "asse", "urgencia", "emergencia", "enfermo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Acuda directamente a la policlínica de ASSE o centro asistencial habilitado más cercano a su domicilio.\n"
            "2. Comuníquese al número de emergencia pública 105 ante situaciones de urgencia sanitaria.\n"
            "3. Consulte los establecimientos farmacéuticos de turno operativos en su zona para adquirir medicamentos."
        )
        botones = [
            {"texto": "Portal ASSE Uruguay", "url": "https://www.asse.com.uy/"},
            {"texto": "Farmacias y centros de salud cerca", "url": f"https://www.google.com/maps/search/farmacia+hospital+policlinica/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 7. COTIZACIÓN DE DÓLARES Y BANCOS (BROU)
    elif any(p in texto for p in ["dolar", "dólar", "cambio", "cotizacion", "banco", "brou", "pesos", "cajero", "prestamo", "tarjeta", "efectivo"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Compruebe los valores oficiales de cotización en la pizarra del Banco República (BROU).\n"
            "2. Realice sus transacciones de cambio de moneda exclusivamente en redes autorizadas del sistema financiero.\n"
            "3. Ubique cajeros automáticos o sucursales bancarias seguras en su entorno inmediato."
        )
        botones = [
            {"texto": "Cotizaciones BROU", "url": "https://www.brou.com.uy/cotizaciones"},
            {"texto": "Cajeros y bancos cerca", "url": f"https://www.google.com/maps/search/banco+cajero+automatico/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 8. TRANSPORTE, STM Y TRES CRUCES
    elif any(p in texto for p in ["transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "stm", "tres cruces", "omnibus"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Consulte líneas, frecuencias, saldos y recargas a través del sistema metropolitano STM.\n"
            "2. Verifique horarios de salida y venta de pasajes interdepartamentales en la terminal Tres Cruces.\n"
            "3. Compare precios actualizados de combustibles en estaciones de servicio habilitadas."
        )
        botones = [
            {"texto": "Consulta STM Montevideo", "url": "https://montevideo.gub.uy/stm"},
            {"texto": "Terminal Tres Cruces", "url": "https://www.trescruces.com.uy/"},
            {"texto": "Estaciones de servicio en mapa", "url": f"https://www.google.com/maps/search/estacion+de+servicio+ancap/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 9. MIGRACIONES Y RESIDENCIAS EN URUGUAY
    elif any(p in texto for p in ["residencia", "inmigrante", "extranjero", "migraciones", "papeles", "cedula", "cédula", "pasaporte", "visa", "radicacion"]):
        cuerpo_respuesta = (
            f"Sugerencia de asesoría exacta para su caso sobre '{consulta}':\n\n"
            "1. Reúna su pasaporte vigente junto al certificado de antecedentes penales legalizado y apostillado.\n"
            "2. Presente formalmente su solicitud de radicación ante la Dirección Nacional de Migraciones.\n"
            "3. Gestione su cédula de identidad provisional o definitiva ante la Dirección Nacional de Identificación Civil."
        )
        botones = [
            {"texto": "Dirección Nacional de Migraciones", "url": "https://www.gub.uy/ministerio-interior/institucion/direccion-nacional-migraciones"},
            {"texto": "Identificación Civil", "url": "https://www.gub.uy/ministerio-interior/institucion/direccion-nacional-identificacion-civil"}
        ]

    # RESOLUCIÓN INTELIGENTE DIRECTA PARA CUALQUIER OTRA CONSULTA ESPECÍFICA
    else:
        cuerpo_respuesta = (
            f"Sugerencia de asesoría enfocada en resolver su planteo sobre '{consulta}':\n\n"
            f"1. Identifique la institución pública o privada competente directamente relacionada con esta gestión en Uruguay.\n"
            f"2. Prepare los documentos, recibos o datos concretos vinculados a su situación antes de iniciar el trámite.\n"
            f"3. Utilice la herramienta de mapas para localizar la dependencia u oficina de atención más próxima."
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
