from flask import Blueprint, render_template 
from flask import request, jsonify, redirect, url_for
from database import mysql
from flask_mqtt import Mqtt
from mqtt import mqtt_client
import json
import plotly
import plotly.express as px
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
import datetime as dt
from predictions.net_runner import NetRunner
from predictions.config_helper import check_and_get_configuration
import subprocess

cfg_obj = check_and_get_configuration('webServer/predictions/config.json', 'webServer/predictions/config_schema.json')

# definisco la funzione per ritornare il grafico dopo avergli passato SQL del valore che voglio plottare 
def get_grafico(SQL):
    cursor = mysql.connection.cursor()
    cursor.execute(SQL)
    row_headers=[x[0] for x in cursor.description]
    json_data=[]
    for result in cursor.fetchall():
        json_data.append(dict(zip(row_headers, result)))
    #print(json_data)
    data = pd.DataFrame(json_data)
    data['Date'] = pd.to_datetime(data['Date'])
    fig = px.line(data, x="Date", y=data.columns[1], title='Andamento {0} durante gli anni'.format(data.columns[1]))
    #  converte una stringa  in json
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

def add_data(data):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM sheet1 ORDER BY STR_TO_DATE(Date,'%m/%g/%Y') DESC LIMIT 10")
    row_headers=[x[0] for x in cursor.description]
    json_data=[]

    for result in cursor.fetchall():
        json_data.append(dict(zip(row_headers, result)))
    
    df = pd.DataFrame(json_data)
        
    mean_wind = df['Wind'].mean()
    mean_wind = round(mean_wind,2)
    mean_rain = df['Rain'].mean()
    mean_rain = round(mean_rain,2)
    mean_RH2 = df['RH2'].mean()
    mean_RH2 = round(mean_RH2,2)
    mean_MinT = df['MinT'].mean()
    mean_MinT = round(mean_MinT,2)
    
    Station = data[0]
    Date = data[1]
    MaxT = data[2]
    MinT = data[3]
    if (MinT == 0):
        MinT = str(mean_MinT)
    RH1 = data[4]
    RH2 = data[5]
    if (RH2 == 0):
        RH2 = str(mean_RH2)
    Wind = (str(mean_wind))
    Rain = (str(mean_rain))    
    
    cursor = mysql.connection.cursor()
    query = """INSERT INTO sheet1(Station, Date, MaxT, MinT, RH1, RH2, Wind, Rain) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
    record = (Station, Date, MaxT, MinT, RH1, RH2, Wind, Rain)
    cursor.execute(query, record)
    mysql.connection.commit()
    print("caricati")

topic = 'ESP8266_AL'
msg = []

@mqtt_client.on_connect()
def handle_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected successfully')
        mqtt_client.subscribe(topic) # subscribe topic
    else:
        print('Bad connection. Code:', rc)

@mqtt_client.on_message()
def handle_mqtt_message(client, userdata, message):
    data = dict(
        topic=message.topic,
        payload=message.payload.decode()
    )
    if (len(msg)==6):
        msg.clear()  
      
    msg.append('{payload}'.format(**data))
        
    print('Received message on topic: {topic} with payload: {payload}'.format(**data))

views = Blueprint(__name__, "views")

# Visualizza il template "index.html" passandogli il 
@views.route("/")
def home():
    logdir = './runs'
    subprocess.Popen(['tensorboard', '--logdir', logdir])
    return render_template("index.html")

@views.route('/publish', methods=['GET','POST'])
def publish_message():
    if(len(msg)==6):
        print(msg)
    return jsonify(message=msg)

# Visualizza i dati prelevati dal DB, eseguendo 
# la query vista negli esercizi precedenti,
# formattando i dati come un json
@views.route("/data")
def get_data():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM sheet1 ORDER BY STR_TO_DATE(Date,'%m/%g/%Y') DESC LIMIT 10")
    row_headers=[x[0] for x in cursor.description]
    json_data=[]

    for result in cursor.fetchall():
        json_data.append(dict(zip(row_headers, result)))
    #print(json_data)
    
    if(len(msg)==6):
        add_data(msg)
        print(msg)

    return jsonify({"dati" : json_data})
    
# Effettua un redirect verso la pagina json 
# NB: nel redirect occorre inserire il nome della
# funzione, non il link completo
@views.route("/goToGetJson")
def goToGetJson():
    return redirect(url_for("views.get_json"))

# gestisco le varie rotte per i grafici
@views.route("/MaxT")
def MaxT():
   name = 'MaxT'
   return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, MaxT FROM Sheet1"), name=name)

@views.route("/MinT")
def MinT():
    name = 'MinT'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, MinT FROM Sheet1"), name=name)

@views.route("/RH1")
def RH1():
    name = 'RH1'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, RH1 FROM Sheet1"),name=name)

@views.route("/RH2")
def RH2():
    name = 'RH2'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, RH2 FROM Sheet1"), name=name)

@views.route("/Wind")
def Wind():
    name = 'Wind'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, Wind FROM Sheet1"),name=name)

@views.route("/Rain")
def Rain():
    name = 'Rain'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, Rain FROM Sheet1"), name=name)

# rotta per far vedere la tabella con gli ultimi dieci valori del mio DB 
@views.route("/table")
def get_table():
    cursor = mysql.connection.cursor()
    num = cursor.execute("SELECT * FROM Sheet1")
    return render_template("table.html", number=num)


#  gestisco le varie rotte per la previsione dei dati

@views.route("/MaxT-Previsione")
def MaxTP():
    name = 'MaxT'
    runner = NetRunner("SELECT Date, MaxT FROM Sheet1 ", name, cfg_obj )
    runner.fit()
    return redirect('http://localhost:6006')

@views.route("/MinT-Previsione")
def MinTP():
    name = 'MinT'
    runner = NetRunner("SELECT Date, MinT FROM Sheet1 ", name, cfg_obj)
    runner.fit()
    return redirect('http://localhost:6006')

@views.route("/RH1-Previsione")
def RH1P():
    name = 'RH1'
    runner = NetRunner("SELECT Date, RH1 FROM Sheet1 ", name, cfg_obj)
    runner.fit()
    return redirect('http://localhost:6006')

@views.route("/RH2-Previsione")
def RH2P():
    name = 'RH2'
    runner = NetRunner("SELECT Date, RH2 FROM Sheet1 ", name, cfg_obj)
    runner.fit()
    return redirect('http://localhost:6006')

@views.route("/Wind-Previsione")
def WindP():
    name = 'Wind'
    runner = NetRunner("SELECT Date, Wind FROM Sheet1 ", name, cfg_obj)
    runner.fit()
    return redirect('http://localhost:6006')

@views.route("/Rain-Previsione")
def RainP():
    name = 'Rain'
    runner = NetRunner("SELECT Date, Rain FROM Sheet1 ", name, cfg_obj)
    runner.fit()
    return redirect('http://localhost:6006')