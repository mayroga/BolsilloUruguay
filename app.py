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
    
    # Respuestas enfocadas 100% en la esencia, claras, sin rodeos, con su botón opcional al final
    if any(p in consulta for p in ["cafe", "café", "llave", "latino", "expreso"]):
        respuesta = "El Café La Llave se consigue al mejor precio en cadenas de supermercados grandes (como Ta-Ta, Devoto, Disco, Geant) o en importadores directos por mayor. Revisa las ofertas semanales de stock en línea."
        boton = {"texto": "🌐 Ver disponibilidad y precios exactos", "url": "https://www.tata.com.uy/catalogue?query=cafe%20la%20llave"}
        
    elif any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo"]):
        respuesta = "Tus liquidaciones, cálculos de haberes y reclamos formales se gestionan directamente a través del Ministerio de Trabajo (MTSS) o tu historial en el BPS."
        boton = {"texto": "🌐 Ir al portal oficial del MTSS", "url": "https://www.gub.uy/ministerio-trabajo-seguridad-social"}
        
    elif any(p in consulta for p in ["dolar", "dólar", "cambio", "cotizacion"]):
        respuesta = "La cotización oficial de referencia en plaza para compra y venta la fija el Banco República (BROU) y la red de cambios."
        boton = {"texto": "🌐 Ver pizarra actual del BROU", "url": "https://www.brou.com.uy/cotizaciones"}
        
    elif any(p in consulta for p in ["nafta", "combustible", "gasoil"]):
        respuesta = "Los precios de los combustibles son regulados y únicos a nivel nacional en todas las estaciones de servicio ANCAP."
        boton = {"texto": "🌐 Ver estaciones cercanas en Mapa", "url": f"https://www.google.com/maps/search/estaciones+ancap/@{lat or -34.9011},{lon or -56.1645},13z"}
    
    else:
        respuesta = f"Para resolver tu búsqueda sobre '{consulta}', la opción más directa y efectiva es revisar los puntos de comercio o prestadores especializados en la zona."
        boton = {"texto": "🌐 Buscar ubicación y sitios exactos", "url": f"https://www.google.com/maps/search/{query_url}/@{lat or -34.9011},{lon or -56.1645},14z"}

    return jsonify({"respuesta": respuesta, "boton": boton})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
