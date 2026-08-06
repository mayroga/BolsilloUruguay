import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-uruguay")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
DEV_USER = os.environ.get("DEV_USER", "admin")
DEV_PASS = os.environ.get("DEV_PASS", "secreto123")

@app.route("/")
def index():
    if session.get("is_dev") or session.get("pagado"):
        return render_template("app.html")
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
        return jsonify({"respuesta": "Escribe o di qué necesitas resolver hoy para darte la guía exacta."})

    ubicacion_txt = f" (Zona: {lat}, {lon})" if lat and lon else ""

    # Blindaje legal estricto: Cero afirmaciones absolutas sobre salarios, cobros o leyes para evitar demandas o multas
    if any(p in consulta for p in ["sueldo", "salario", "cobro", "pago", "aguinaldo", "descuento", "ley laboral", "ministerio de trabajo"]):
        respuesta = f"Orientación general sobre gestiones{ubicacion_txt}: Se sugiere verificar los recibos de sueldo y consultar directamente los canales formales del MTSS o BPS para confirmar cálculos y normativas vigentes de forma segura."
    elif any(p in consulta for p in ["super", "precio", "comida", "carne", "pan", "feria", "comprar"]):
        respuesta = f"Ahorro sugerido{ubicacion_txt}: Se sugiere comparar ferias vecinales y comercios locales de cercanía. Comprar en días de descuento con redes de cobranza o tarjetas habituales reduce el gasto diario sin riesgos."
    elif any(p in consulta for p in ["tramite", "cedula", "bps", "intendencia", "pasaporte", "documento"]):
        respuesta = f"Gestión sugerida{ubicacion_txt}: Se sugiere verificar los requisitos mínimos en la web oficial correspondiente y agendarse previamente para evitar filas o traslados innecesarios."
    elif any(p in consulta for p in ["bondi", "transporte", "fletero", "viaje", "omnibus", "combi"]):
        respuesta = f"Movilidad sugerida{ubicacion_txt}: Se sugiere consultar líneas locales o combinar horarios vecinales para optimizar el costo del traslado diario."
    else:
        respuesta = f"Orientación general{ubicacion_txt}: Se sugiere verificar los canales directos y formales de la localidad para resolver esta necesidad de forma segura y económica."

    return jsonify({"respuesta": respuesta})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
