from flask import Blueprint, render_template 
from flask import request, jsonify, redirect, url_for
from database import mysql
from flask_mqtt import Mqtt
from mqtt import mqtt_client
from sklearn.metrics import r2_score
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import json
import plotly
import plotly.express as px
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
import datetime as dt
from net_runner import NetRunner


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

# # defenisco il grafico e l'accuratezza della prvisione per la previsione dei dati passandogli il valore che voglio prevedre l'andamento
def get_previsione(SQLP, name):
    cursor = mysql.connection.cursor()
    cursor.execute(SQLP)
    row_headers=[x[0] for x in cursor.description]
    json_data=[]
    for result in cursor.fetchall():
        json_data.append(dict(zip(row_headers, result)))
    #print(json_data)
    data = pd.DataFrame(json_data)
    data['Date'] = pd.to_datetime(data['Date'])
    data['Date']=data['Date'].map(dt.datetime.toordinal)
    # split data into X and y
    X = data["Date"].to_numpy()
    X = X.reshape(-1, 1)
    y = data[name].to_numpy()


    X_train, X_test, y_train, y_test = train_test_split(X, y,test_size=0.2,random_state=0)

    # bulid and fit the model
    model = LinearRegression()
    model.fit(X_train, y_train)

    # prediction for the testing dataset
    test_pre = model.predict(X_test)
    test_score = r2_score(y_test, test_pre)
    fig = px.scatter(data, y_test, test_pre)
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    test_score = test_score * 100
    test_score = round(test_score, 2)
    return graphJSON, test_score

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

topic = 'message'
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
    if 'cfhj' in msg :
        msg.remove('hello')
        
    print('Received message on topic: {topic} with payload: {payload}'.format(**data))

views = Blueprint(__name__, "views")

# Visualizza il template "index.html" passandogli il 
# parametro "Pippo" tramite la renderizzazione
@views.route("/")
def home():
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
   return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, MaxT FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023' LIMIT 1460"), name=name)

@views.route("/MinT")
def MinT():
    name = 'MinT'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, MinT FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023' LIMIT 1460"), name=name)

@views.route("/RH1")
def RH1():
    name = 'RH1'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, RH1 FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023' LIMIT 1460"),name=name)

@views.route("/RH2")
def RH2():
    name = 'RH2'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, RH2 FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023' LIMIT 1460"), name=name)

@views.route("/Wind")
def Wind():
    name = 'Wind'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, Wind FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023' LIMIT 1460"),name=name)

@views.route("/Rain")
def Rain():
    name = 'Rain'
    return render_template("grafico.html", graphJSON=get_grafico("SELECT Date, Rain FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023' LIMIT 1460"), name=name)

# rotta per far vedere la tabella con gli ultimi dieci valori del mio DB 
@views.route("/table")
def get_table():
    cursor = mysql.connection.cursor()
    num = cursor.execute("SELECT * FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'")
    return render_template("table.html", number=num)


#  gestisco le varie rotte per la previsione dei dati

@views.route("/MaxT-Previsione")
def MaxTP():
    name = 'MaxT'
    # graphJSON, testScore=get_previsione("SELECT Date, MaxT FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'", name)
    runner = NetRunner("SELECT Date, MaxT FROM Sheet1 ", name)
    graphJSON=runner.fit()

    return redirect('http://localhost:6006')

    # return render_template("previsione.html", graphJSON = graphJSON,testScore = 10, name=name)

@views.route("/MinT-Previsione")
def MinTP():
    name = 'MinT'
    graphJSON, testScore=get_previsione("SELECT Date, MinT FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'", name)
    return render_template("previsione.html", graphJSON = graphJSON,testScore = testScore, name=name)

@views.route("/RH1-Previsione")
def RH1P():
    name = 'RH1'
    graphJSON, testScore=get_previsione("SELECT Date, RH1 FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'", name)
    return render_template("previsione.html", graphJSON = graphJSON,testScore = testScore, name=name)

@views.route("/RH2-Previsione")
def RH2P():
    name = 'RH2'
    graphJSON, testScore=get_previsione("SELECT Date, RH2 FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'", name)
    return render_template("previsione.html", graphJSON = graphJSON,testScore = testScore, name=name)

@views.route("/Wind-Previsione")
def WindP():
    name = 'Wind'
    graphJSON, testScore=get_previsione("SELECT Date, Wind FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'", name)
    return render_template("previsione.html", graphJSON = graphJSON,testScore = testScore, name=name)

@views.route("/Rain-Previsione")
def RainP():
    name = 'Rain'
    graphJSON, testScore=get_previsione("SELECT Date, Rain FROM Sheet1 WHERE Date != '%/%/2022' OR Date != '%/%/2023'", name)
    return render_template("previsione.html", graphJSON = graphJSON,testScore = testScore, name=name)