# Importo il pacchetto necessario per la connessione al DB ed 
# instanzio l'oggetto "myDb" con tutti i parametri necessari
# alla connessione 
import mysql.connector

myDb = mysql.connector.connect(
    host="localhost",
    user="pythonUser",
    password="pythonPWD",
    database="tuoDB"
)

# Creo un oggetto "cursor", questo oggetto mi permette di lanciare
# i comandi, come se fossi nella CLI del DB server
myCursor = myDb.cursor()

# Cerco le tabelle nominate "Datas", per non far lanciare eccezioni
# nel caso in cui la tabella sia già presente, controllo quindi il risultato
# e se non esiste allora creo una nuova tabella "Datas"
# myCursor.execute("SHOW TABLES LIKE 'Datas'")
#if not myCursor.fetchone():
 #   print("Nessuna tabella rilevata, la creo")
  #  myCursor.execute("CREATE TABLE Datas (id INT NOT NULL AUTO_INCREMENT, value DOUBLE NOT NULL, PRIMARY KEY (id))")

# Visualizzo l'elenco di tutte le tabelle presenti nel mio DB,
# attualmente 1, quella appena creata
myCursor.execute("SHOW TABLES")
for table in myCursor:
    print(table)

myCursor.execute("LOAD DATA LOCAL INFILE 'data.sql'")
myDb.commit()

# Inserisco un dato all'interno della tabella
#myCursor.execute("INSERT INTO datas (value) VALUES (%f)" % (10.3))
#myDb.commit()

# Eseguo una query per estrapolare tutti i dati contenuti dentro alla tabella,
# quindi li stampo
#myCursor.execute("SELECT * FROM datas")
#for result in myCursor.fetchall():
#    print("id: ", result[0], " value: ", result[1])