import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-temporal")

# Configuración de Stripe (Credenciales seguras desde las variables de entorno de Render)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
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
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "BolsilloUruguay - Acceso Ilimitado"},
                    "unit_amount": 299, # $2.99 USD
                },
                "quantity": 1,
            }],
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
        return jsonify({"respuesta": "Acceso restringido. Debe realizar el pago correspondiente."}), 403

    data = request.get_json()
    consulta = data.get("mensaje", "").lower().strip()
    
    if not consulta:
        respuesta = "Por favor, escribe o di qué necesitas resolver hoy para darte una guía exacta."
    elif "super" in consulta or "comida" in consulta or "precio" in consulta or "canasta" in consulta:
        respuesta = "Se sugiere comparar ofertas semanales en ferias vecinales y comercios de barrio. Comprar en días de descuento con tarjetas locales reduce notablemente el gasto diario."
    elif "tramite" in consulta or "bps" in consulta or "cedula" in consulta or "intendencia" in consulta:
        respuesta = "Para trámites estatales, se sugiere agendarse previamente de forma digital o verificar requisitos en las sedes oficiales para evitar traslados innecesarios y perder tiempo en filas."
    elif "transporte" in consulta or "bondi" in consulta or "viaje" in consulta:
        respuesta = "Se sugiere consultar las aplicaciones oficiales de movilidad o líneas locales para coordinar combinaciones y evitar costos extra en traslados dentro de la ciudad o hacia el interior."
    else:
        respuesta = "Orientación general: Se sugiere verificar siempre los canales oficiales o locales correspondientes para resolver esta consulta de forma segura y sin gastos de más."

    return jsonify({"respuesta": respuesta})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
