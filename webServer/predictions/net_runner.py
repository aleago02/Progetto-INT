import os
import time
from database import mysql
import torch
import shutil
import numpy as np
import pandas as pd
import torch.nn as nn
import matplotlib.pyplot as plt

from pathlib import Path
from net import LSTMnetwork
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

from torch.utils.tensorboard import SummaryWriter

torch.manual_seed(42)


class NetRunner():
    """
    Gestisce addestramento e test della rete.
    """ 

    def __init__(self, SQL, name, cfg_obj: object) -> None:

        # Raccolgo gli iper-parametri definiti nel config.
        self.epochs = cfg_obj.hyper_parameters.epochs
        self.window_size = cfg_obj.hyper_parameters.window_size
        self.test_size = cfg_obj.hyper_parameters.test_size
        self.learning_rate = cfg_obj.hyper_parameters.learning_rate
        
        self.SQL = SQL
        self.name = name
        
        self.runs_path = Path('./runs')
        existing_files = [f for f in os.listdir('./runs') if f.startswith(f'rnn_{self.name}')]
        print(existing_files)
        if existing_files and self.runs_path.is_dir():
            print('Clearing older runs...')
            filepath = './runs/' + existing_files[0]
            shutil.rmtree(filepath)

            time.sleep(5)

            print('Runs cleared!')

        # Creo un writer dedicato a tenere traccia della rete, degli esperimenti, degli artefatti...
        run_name = f'rnn_{self.name + datetime.fromtimestamp(time.time()).strftime("%d-%m-%Y_%H-%M")}'
        self.writer = SummaryWriter(f'runs/{run_name}')

        # Definisco la rete.
        self.net = LSTMnetwork()

        # Definisco: ottimizzatore e loss.
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr = self.learning_rate)
        self.criterion = nn.MSELoss()

        # Inizializzo lo scaler che usero' per preprocessare il dataset.
        self.scaler = MinMaxScaler(feature_range=(-1, 1))
        
        # Procedo al caricamento dei dati in un dataset e, di conseguenza, nel dataloader.
        self.load_data()

    def load_data(self):      
        cursor = mysql.connection.cursor()
        cursor.execute(self.SQL)
        row_headers=[x[0] for x in cursor.description]
        json_data=[]
        for result in cursor.fetchall():
            json_data.append(dict(zip(row_headers, result)))
        #print(json_data)
        self.df = pd.DataFrame(json_data)
        # Estraggo i valori della sequenza temporale
        data_sequence = self.df[self.name].values.astype(float) 

        # Creo il training e il test:
        # - La sequenza di test e' una porzione finale della sequenza.
        # - La restante parte e' per il training.
        train_set, test_set = data_sequence[ : -self.test_size], data_sequence[-self.test_size : ]

        # Normalizzazione dei dati.
        train_norm = self.scaler.fit_transform(train_set.reshape(-1, 1))
        test_norm = self.scaler.transform(test_set.reshape(-1, 1))

        # Conversione in tensori.
        self.train_norm = torch.FloatTensor(train_norm).view(-1)
        self.test_norm = torch.FloatTensor(test_norm).view(-1)

        # Crea le coppie dati per l'addestramento: <finestra valore, prossimo valore atteso>
        self.train_data = []
        for i in range(len(self.train_norm) - self.window_size):
            windowed_data = self.train_norm[i : i + self.window_size]
            windowed_labels = self.train_norm[i + self.window_size : i + self.window_size + 1]
            self.train_data.append((windowed_data, windowed_labels))
        
        print(f'Sequence length --> training: {len(self.train_norm)}, test: {len(self.test_norm)}')
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
                window_predictions = self.net(window_data)
                
                # Calcolo la loss ed eseguo la back-propagation
                loss = self.criterion(window_predictions, windows_labels)
                loss.backward()

                # Aggiorno i pesi ed azzero i gradienti per lo step successivo.
                self.optimizer.step()
                self.optimizer.zero_grad()
            
            #imposto il numero di predizioni
            num_predictions = self.test_size
            # Prendo gli ultimi window_size campioni del training
            test_predictions = self.train_norm[-self.window_size : ].tolist() * num_predictions

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
            loss_va = self.criterion(torch.tensor(test_predictions[-self.window_size:]), self.test_norm)
            
            upgraded = min_tr_loss > loss and min_va_loss > loss_va

            if min_tr_loss > loss:
                min_tr_loss = loss

            if min_va_loss > loss_va:
                min_va_loss = loss_va

            if upgraded:

                # Aggiungo la loss del training e validation alla tensorboard
                self.writer.add_scalars('Losses', {'train/loss': loss.item(), 'train/val_loss': loss_va.item()}, epoch)

                # Applico l'inverse scaler per tornare ai valori originali
                true_predictions = self.scaler.inverse_transform(np.array(test_predictions[self.window_size:]).reshape(-1, 1))

                self.plot_full_data_predictions(true_predictions[:num_predictions], epoch)
                

            # Stampo:
            # - la loss ottenuta alla fine di ogni epoca sui dati di training    
            # - la loss ottenuta alla fine di ogni epoca sui dati di test    
            print(f'Epoch: {epoch:2} Loss: {loss.item():10.8f} --- Loss_va: {loss_va.item():10.8f} {"*** Upgraded ***" if upgraded else ""}')

    def plot_full_data_predictions(self, predictions : np.ndarray, epoch : int):
        """
        Salva su tensorboard un grafico completo di dati e predizioni.

        Args:
            predictions (np.ndarray): Predizioni.
            epoch (int): Epoca associata al plot.
        """

        x = np.arange('1988-01-02', '1992-01-01', dtype='datetime64[D]').astype('datetime64[D]')[-len(predictions):]

        
        self.fig = plt.figure(figsize=(12,4))
        plt.title(self.name + 'previsione')
        plt.ylabel(self.name)
        plt.grid(True)
        plt.autoscale(axis='x',tight=True)
        plt.plot(self.df[self.name], color='#8000ff')
        plt.plot(x, predictions, color='#ff8000')
        
        self.plot_to_tensorboard(self.name + 'predizione', epoch)


    def plot_to_tensorboard(self, prefix : str, epoch : int) -> None:
        """
        Salva l'immagine matplotlib sulla tensorboard.

        Args:
            prefix (str): Nome immagine.
            epoch (int): Epoca.
        """

        self.writer.add_figure(prefix, self.fig, epoch)
        plt.close()