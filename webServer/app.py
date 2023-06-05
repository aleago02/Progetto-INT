from flask import Flask
from flask_mqtt import Mqtt
from mqtt import mqtt_client
from views import views
from database import mysql

app = Flask(__name__)

app.register_blueprint(views, url_prefix="/")
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'pythonUser'
app.config['MYSQL_PASSWORD'] = 'pythonPWD'
app.config['MYSQL_DB'] = 'ICRISAT'
mysql.init_app(app)

app.config['MQTT_BROKER_URL'] = 'broker.emqx.io'
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_USERNAME'] = ''  # Set this item when you need to verify username and password
app.config['MQTT_PASSWORD'] = ''  # Set this item when you need to verify username and password
app.config['MQTT_KEEPALIVE'] = 5  # Set KeepAlive time in seconds
app.config['MQTT_TLS_ENABLED'] = False  # If your server supports TLS, set it True

mqtt_client.init_app(app)


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=8001)