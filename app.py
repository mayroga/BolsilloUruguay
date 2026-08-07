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
        return jsonify({"respuesta": f"BolsilloUruguay - {URL_BASE_OFICIAL}\n\nIndíquenos qué trámite o gestión en Uruguay desea que le orientemos a resolver.", "pausa_voz": True})

    historial = session.get("historial", [])
    query_url = consulta.replace(" ", "+")
    texto = consulta

    # 1. BPS (JUBILACIONES, HISTORIA LABORAL, ASIGNACIONES, SEGURO DE PARO)
    if any(p in texto for p in ["bps", "jubilacion", "jubilación", "paro", "asignacion", "asignación", "historia laboral", "subsidio", "apuntes"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para gestiones en el BPS:\n\n"
            "1. Acceda a 'Servicios en Línea del BPS' utilizando su identidad digital.\n"
            "2. Revise su historia laboral para corroborar el registro correcto de aportes.\n"
            "3. Canalice solicitudes de subsidios o asignaciones directamente en la plataforma oficial."
        )
        botones = [
            {"texto": "Servicios en Línea BPS", "url": "https://www.bps.gub.uy/"},
            {"texto": "Oficinas BPS en mapa", "url": f"https://www.google.com/maps/search/bps+oficina+uruguay/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 2. SUCIVE, PATENTE Y MULTAS (INTENDENCIAS DE TODO EL PAÍS)
    elif any(p in texto for p in ["patente", "multa", "sucive", "contribucion", "contribución", "intendencia", "imm", "vehiculo", "padron", "departamento", "interior"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para tributos y vehículos en todo el país:\n\n"
            "1. Tenga disponible el número de padrón o matrícula de su vehículo o bien inmueble.\n"
            "2. Verifique estados de cuenta y convenios vigentes en el portal unificado SUCIVE.\n"
            "3. Consulte la Intendencia departamental correspondiente ante dudas normativas locales."
        )
        botones = [
            {"texto": "Portal SUCIVE", "url": "https://www.sucive.gub.uy/"},
            {"texto": "Congreso de Intendencias", "url": "https://congresodeintendentes.gub.uy/"}
        ]

    # 3. EMPLEO, TRABAJO Y SUBSIDIOS (MTSS / INEFOP)
    elif any(p in texto for p in ["empleo", "trabajo", "curriculum", "vacante", "oferta", "mtss", "inefop", "capacitacion", "capacitación", "curp"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para inserción laboral y capacitación:\n\n"
            "1. Postúlese a través de la bolsa oficial de empleo dependiente del MTSS.\n"
            "2. Explore programas de formación y actualización profesional certificados por INEFOP.\n"
            "3. Mantenga su perfil actualizado para maximizar opciones de contratación formal."
        )
        botones = [
            {"texto": "Bolsa de Empleo MTSS", "url": "https://www.empleos.gub.uy/"},
            {"texto": "Cursos y Becas INEFOP", "url": "https://www.inefop.org.uy/"}
        ]

    # 4. DGI, MONOTRIBUTO Y FACTURACIÓN
    elif any(p in texto for p in ["dgi", "monotributo", "factura", "impuesto", "ruc", "empresa", "aportes", "literal e"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para obligaciones tributarias:\n\n"
            "1. Ingrese con sus credenciales autorizadas a los servicios digitales de la DGI.\n"
            "2. Compruebe las fechas límite de pago para regímenes de Monotributo o Literal E.\n"
            "3. Emita sus documentos fiscales electrónicos cumpliendo con la normativa vigente."
        )
        botones = [
            {"texto": "Portal Oficial DGI", "url": "https://www.dgi.gub.uy/"},
            {"texto": "Oficinas DGI en mapa", "url": f"https://www.google.com/maps/search/dgi+oficina/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 5. SALUD, ASSE, POLICLÍNICAS Y FARMACIAS DE TURNO
    elif any(p in texto for p in ["clinica", "salud", "medico", "policlinica", "hospital", "doctor", "farmacia", "remedio", "asse", "urgencia", "emergencia"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para atención sanitaria:\n\n"
            "1. Diríjase a la policlínica de ASSE o centro asistencial habilitado en su zona.\n"
            "2. Utilice la línea telefónica 105 ante situaciones de urgencia médica pública.\n"
            "3. Consulte los establecimientos farmacéuticos de turno operativos en su localidad."
        )
        botones = [
            {"texto": "Portal ASSE Uruguay", "url": "https://www.asse.com.uy/"},
            {"texto": "Farmacias y centros de salud cerca", "url": f"https://www.google.com/maps/search/farmacia+hospital+policlinica/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 6. COTIZACIÓN DE DÓLARES Y BANCOS (BROU)
    elif any(p in texto for p in ["dolar", "dólar", "cambio", "cotizacion", "banco", "brou", "pesos", "cajero", "prestamo", "tarjeta"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para transacciones y divisas:\n\n"
            "1. Valide los valores de referencia en la pizarra oficial del Banco República (BROU).\n"
            "2. Efectúe operaciones cambiarias a través de entidades formalmente habilitadas.\n"
            "3. Localice cajeros automáticos o sucursales bancarias seguras en su entorno."
        )
        botones = [
            {"texto": "Cotizaciones BROU", "url": "https://www.brou.com.uy/cotizaciones"},
            {"texto": "Cajeros y bancos cerca", "url": f"https://www.google.com/maps/search/banco+cajero+automatico/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 7. TRANSPORTE, STM Y TRES CRUCES
    elif any(p in texto for p in ["transporte", "bondi", "bus", "pasaje", "viaje", "boleto", "nafta", "combustible", "stm", "tres cruces"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para movilidad urbana e interdepartamental:\n\n"
            "1. Consulte líneas, frecuencias y saldos mediante el sistema STM.\n"
            "2. Verifique itinerarios de transporte de larga distancia en Tres Cruces.\n"
            "3. Compare precios en estaciones de servicio autorizadas."
        )
        botones = [
            {"texto": "Consulta STM Montevideo", "url": "https://montevideo.gub.uy/stm"},
            {"texto": "Terminal Tres Cruces", "url": "https://www.trescruces.com.uy/"},
            {"texto": "Estaciones de servicio en mapa", "url": f"https://www.google.com/maps/search/estacion+de+servicio+ancap/@{lat or -34.9011},{lon or -56.1645},14z"}
        ]

    # 8. MIGRACIONES Y RESIDENCIAS EN URUGUAY
    elif any(p in texto for p in ["residencia", "inmigrante", "extranjero", "migraciones", "papeles", "cedula", "cédula", "pasaporte", "visa"]):
        cuerpo_respuesta = (
            "Sugerencia de asesoría para radicación legal y documentación:\n\n"
            "1. Prepare su pasaporte en regla junto al certificado de antecedentes debidamente legalizado.\n"
            "2. Presente su solicitud de residencia ante la Dirección Nacional de Migraciones.\n"
            "3. Gestione su documento de identidad ante la Dirección Nacional de Identificación Civil."
        )
        botones = [
            {"texto": "Dirección Nacional de Migraciones", "url": "https://www.gub.uy/ministerio-interior/institucion/direccion-nacional-migraciones"},
            {"texto": "Identificación Civil", "url": "https://www.gub.uy/ministerio-interior/institucion/direccion-nacional-identificacion-civil"}
        ]

    # RESPUESTA DIRECTA DE ASESORÍA PARA CUALQUIER OTRA GESTIÓN
    else:
        cuerpo_respuesta = (
            f"Sugerencia de asesoría para resolver '{consulta}':\n\n"
            "1. Evite intermediarios innecesarios y acuda directamente al canal institucional correspondiente.\n"
            "2. Reúna y organice sus respaldos documentales antes de iniciar la gestión.\n"
            "3. Emplee el mapa interactivo para ubicar la dependencia o comercio más próximo."
        )
        botones = [
            {"texto": "Buscar ubicación en mapa", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}
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
