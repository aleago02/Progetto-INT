import torch
import torch.nn as nn
import numpy as np

class LSTMnetwork(nn.Module):
    """
    Rete costituita di celle LSTM.
    """

    def __init__(self, input_size : int = 1, hidden_size : int = 100, output_size : int = 1) -> None:
        """
        Inizializza la rete.

        Args:
            input_size (int, optional): Numero di features attese per l'input LSTM. Defaults to 1.
            hidden_size (int, optional): Numero di features generate dall'output LSTM. Defaults to 100.
            output_size (int, optional): Dimensione dell'output. Defaults to 1.
        """     
        super(LSTMnetwork, self).__init__()

        self.hidden_size = hidden_size
        
        # Aggiungo strato costituito di celle LSTM:
        # - Indico la dimensione dell'input atteso.
        # - Indico la dimensione dell'output ptodotto.
        self.lstm = nn.LSTM(input_size, hidden_size)
        
        # Aggiungo uno strato fully-connected.
        self.linear = nn.Linear(hidden_size, output_size)
        
        # Inizializzo hidden e cell state iniziale: h0 e c0.
        self.hidden = (torch.zeros( 1, 1, self.hidden_size ), 
                       torch.zeros( 1, 1, self.hidden_size ))

    def forward(self, sequence : torch.Tensor) -> torch.Tensor:
        """
        Esegue il passaggio della sequenza dati nel modello.

        Args:
            sequence (torch.Tensor): Sequenza dati in ingresso.

        Returns:
            torch.Tensor: Tensore di output.
        """
        sequence = torch.from_numpy(sequence)
        lstm_out, self.hidden = self.lstm(sequence.view(len(sequence), 1, -1), self.hidden)
        prediction = self.linear( lstm_out.view( len(sequence), -1 ) )
        
        return prediction[-1]