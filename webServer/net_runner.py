import time
import torch
import shutil
import numpy as np
import pandas as pd
import torch.nn as nn
import matplotlib.pyplot as plt
from database import mysql
import plotly
import plotly.express as px
import json
from pathlib import Path
from net import LSTMnetwork
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
import datetime as dt


class NetRunner():

    def __init__(self, SQL, name) -> None:
        self.net = LSTMnetwork()
        self.learning_rate = 0.01
         # Definisco: ottimizzatore e loss.
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr = self.learning_rate)
        self.criterion = nn.MSELoss()
        self.window_size = 12
        self.test_size = 12
        # Inizializzo lo scaler che usero' per preprocessare il dataset.
        self.scaler = MinMaxScaler(feature_range=(-1, 1))
        self.epochs = 200
        self.SQL = SQL
        self.name = name
        self.load_data()
  
    def load_data(self):
        cursor = mysql.connection.cursor()
        cursor.execute(self.SQL)
        row_headers=[x[0] for x in cursor.description]
        json_data=[]
        for result in cursor.fetchall():
            json_data.append(dict(zip(row_headers, result)))
        #print(json_data)
        data = pd.DataFrame(json_data)
        data['Date'] = pd.to_datetime(data['Date'])
        data['Date']=data['Date'].map(dt.datetime.toordinal)

        # Inizializzo lo scaler che usero' per preprocessare il dataset.
        scaler = MinMaxScaler(feature_range=(-1, 1))

        y = data[self.name].to_numpy()

        train_set, test_set = y[ : -self.test_size], y[-self.test_size : ]
        # Normalizzazione dei dati.
        train_norm = scaler.fit_transform(train_set.reshape(-1, 1))
        test_norm = scaler.transform(test_set.reshape(-1, 1))

        # Conversione in tensori.
        self.train_norm = torch.FloatTensor(train_norm).view(-1)
        self.test_norm = torch.FloatTensor(test_norm).view(-1)

        # Crea le coppie dati per l'addestramento: <finestra valore, prossimo valore atteso>
        self.train_data = []
        for i in range(len(train_norm) - self.window_size):
            windowed_data = train_norm[i : i + self.window_size]
            windowed_labels = train_norm[i + self.window_size : i + self.window_size + 1]
            self.train_data.append((windowed_data, windowed_labels))
            
        print(f'Sequence length --> training: {len(train_norm)}, test: {len(test_norm)}')
        print(f'Training data length: {len(self.train_data)} with windows size of {self.window_size}')

    def fit(self):
            """
            Esegue l'addestramento della rete e lo step di validazione per ogni epoca.
            """

            min_tr_loss = 10000
            min_va_loss = 10000

            # Ciclo per il numero di epoche configurate
            for epoch in range(self.epochs):
                self.net.train()

                # Ciclo per ogni finestra dati.
                for window_data, windows_labels in self.train_data:

                    # Inizializzo h0 e c0
                    self.net.hidden = (torch.zeros(1, 1, self.net.hidden_size),
                                    torch.zeros(1, 1, self.net.hidden_size))
                    
                    # Eseguo la predizione sulla sequeneza col modello
                    window_predictions = self.net(torch.from_numpy(window_data))
                    
                    # Calcolo la loss ed eseguo la back-propagation
                    loss = self.criterion(window_predictions, windows_labels)
                    loss.backward()

                    # Aggiorno i pesi ed azzero i gradienti per lo step successivo.
                    self.optimizer.step()
                    self.optimizer.zero_grad()

                # Prendo gli ultimi window_size campioni del training
                test_predictions = self.train_norm[-self.window_size : ].tolist()

                # Setto il modello in modalità eval
                self.net.eval()

                # Trovo i valori successivi:
                # - Predico un valore alla volta spostando la finestra.
                for _ in range(self.test_size):
                    window_data = torch.FloatTensor(test_predictions[-self.window_size:])
                    with torch.no_grad():
                        self.net.hidden = (torch.zeros(1, 1, self.net.hidden_size),
                                        torch.zeros(1, 1, self.net.hidden_size))
                        test_predictions.append(self.net(window_data).item())

                # Calcolo la loss.
                loss_va = self.criterion(torch.tensor(test_predictions[self.window_size:]), self.test_norm)
                
                upgraded = min_tr_loss > loss and min_va_loss > loss_va

                if min_tr_loss > loss:
                    min_tr_loss = loss

                if min_va_loss > loss_va:
                    min_va_loss = loss_va

            # Applico l'inverse scaler per tornare ai valori originali
            true_predictions = self.scaler.inverse_transform(np.array(test_predictions[self.window_size:]).reshape(-1, 1))

            return self.plot_full_data_predictions(true_predictions, epoch)

    def plot_full_data_predictions(self, predictions : np.ndarray, epoch : int):
        # Args:
        #     predictions (np.ndarray): Predizioni.
        #     epoch (int): Epoca associata al plot.
        x = np.arange('2018-02-01', '2019-02-01', dtype='datetime64[M]').astype('datetime64[D]')
        
        fig = px.line(x, x="Date", y=predictions, title='Andamento {0} durante gli anni'.format(predictions))
        #  converte una stringa  in json
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        return graphJSON