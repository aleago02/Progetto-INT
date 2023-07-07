#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WifiClient.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <NTPClient.h>
#include <WiFiUdp.h>
#include <ESPAsyncTCP.h>
#include <ESP8266mDNS.h>

ESP8266WebServer server(80);

#define DHTPIN 5
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);

// WiFi
const char *ssid = "Lorenzo"; // Enter your WiFi name
const char *password = "123456789";  // Enter WiFi password

String hostname = "ESP_8266";
String hostnameToFind = "";

//String serverName = "http://DESKTOP-REM1UNP/";

const char index_html[] PROGMEM = R"rawliteral(
    <!DOCTYPE HTML><html><head>
    <title>ESP Input Form</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head><body>
    <form action="/reconnect">
        SSID: <input type="text" name="ssid">
        PWD: <input type="text" name="pwd">
        <input type="submit" value="Submit">
    </form><br>
    <form action="/search">
      CERCA DEVICE <input type="submit" value="Search">
    </form><br>
    </body></html>)rawliteral";
    
const char search_html[] PROGMEM = R"rawliteral(
  <!DOCTYPE HTML><html><head>
    <title>ESP Input Form</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style> 
      input[type=text] {
        width: 20%;
        padding: 5px 10px;
        margin: 5px 0;
        box-sizing: border-box;
      }
    </style>
    </head><body>
    <form action="/searchIp" method="post" data-result="form-result">
      <label for="hostnameToFind">Hostname to find: </label><input type="text" name="hostnameToFind"><br>
      <input type="submit" value="Submit">
    </form>
    <br><br>
    <p id="form-result"></p>
        
    <script>
      document.addEventListener("submit", (e) => {
        const form = e.target;        
        fetch(form.action, {          
          method: form.method,       
          body: new FormData(form),         
        })     
        .then(response => response.text())  
        .then(text => {                     
          console.log(text);
          const resEl = document.getElementById(form.dataset.result).innerHTML = text;
        });
        e.preventDefault();                 
      });
    </script>
  </body></html>)rawliteral";

WiFiUDP ntpUDP;

NTPClient timeClient(ntpUDP, "pool.ntp.org");

//Week Days
String weekDays[7]={"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"};

//Month names
String months[12]={"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"};

// MQTT Broker
const char *mqtt_broker = "broker.emqx.io";
const char *topic = "ESP8266_AL";
const char *mqtt_username = "emqx";
const char *mqtt_password = "public";
const int mqtt_port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long startMillis;
unsigned long currentMillis;
const unsigned long period = 86400000;



void callback(char *topic, byte *payload, unsigned int length) {
  Serial.print("Message arrived in topic: ");
  Serial.println(topic);
  Serial.print("Message:");
  for (int i = 0; i < length; i++) {
      Serial.print((char) payload[i]);
  }
  Serial.println();
  Serial.println("-----------------------");
}

/*
  se sto richiedendo la homepage semplicemente ritorno l'html definito sopra, con il codice 200
*/
void handleHome(){
  server.send(200, "text/html", index_html);
}

void handleSearch(){
  server.send(200, "text/html", search_html);
}

void notFound() {
  server.send(404, "text/plain", "Not found");
}

String searchHost(String hostnameToFind){
  IPAddress serverIp;
  int retry = 0;
  while (serverIp.toString() == "0.0.0.0") {
    delay(250);
    int n = MDNS.queryService(hostnameToFind.c_str(), "tcp");
    if (n > 0){
      serverIp = MDNS.IP(0);
    }
    if(retry == 5)
      return "Hostname not found!";
    retry ++;
  }
  Serial.print("HostIP: ");
  Serial.println(serverIp.toString());

  return serverIp.toString();
}

void searchIp() {
    if(server.arg("hostnameToFind")){
      Serial.print("Hostname to find: ");
      Serial.println(server.arg("hostnameToFind"));
        
      server.send(200, "text/plain", searchHost(server.arg("hostnameToFind")));
    }else{
      server.send(200, "text/plain", "NO CREDENTIAL FOUND");
    }
}

/*
  Funzione che permette di verificare se la connessione va a buon fine o meno, con un counter che permette di evitare loop infiniti
*/
bool tryToConnect(String ssid, String pwd){
    WiFi.begin(&ssid[0], &pwd[0]);
    int retryCounter = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        retryCounter ++;
        Serial.println("Waiting to connect…");
        if(retryCounter > 10)
            return false;
    }
    Serial.println();
    Serial.print("IP ADDRESS: ");
    Serial.println(WiFi.localIP());
    return true;
}

/*
  se ho fatto il submit del form dovrei aver inviato le credenziali per la connessione wifi, a questo punto:
   - controllo che le credenziali esistano 
   - se le credenziali esistono rispondo al client e provo a connettermi
   - se riesco a connettermi non faccio nulla e resto in attesa
   - se non riesco a connettermi e mi connetto alle credenziali vecchie
   - se le credenziali non esistono invio 200 ma con un altro messaggio di errore
*/
void handleCredential() {
    if(server.arg("ssid") != "" && server.arg("pwd") != ""){
        Serial.print("NEW SSID: ");
        Serial.println(server.arg("ssid"));
        Serial.print("NEW PWD: ");
        Serial.println(server.arg("pwd"));
        server.send(200, "text/html", "Credential Found");
        delay(1000);
        if(tryToConnect(server.arg("ssid"), server.arg("pwd"))){
                      
        }else{
            tryToConnect(ssid, password);
        }
    }else{
        server.send(200, "text/html", "NO CREDENTIAL FOUND");
    }
}

/*
  inizializza sul server tutti gli endpoint disponibili per le chiamate (nel nostro caso solo root e /reconnect)
*/
void setupRouting() {
    server.on("/reconnect", handleCredential);
    server.on("/", handleHome);
    server.on("/search", handleSearch);
    server.on("/searchIp", searchIp); 
    server.onNotFound(notFound);
    server.begin();
}

void initWiFi() {
  WiFi.disconnect(true);
  WiFi.begin(ssid, password);
  WiFi.setHostname(hostname.c_str()); 
  
  Serial.print("Connecting to WiFi ..");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print('.');
    delay(1000);
  }
  Serial.println("Connected to the WiFi network");
  Serial.println();
  Serial.print("IP ADDRESS: ");
  Serial.println(WiFi.localIP());

  while(!MDNS.begin(hostname.c_str())) {
     Serial.println("Starting mDNS...");
     delay(1000);
  }
}

void setup() {
  // Set software serial baud to 115200;
  Serial.begin(115200);
  // connecting to a WiFi network
  initWiFi();
  setupRouting();
  Serial.println("Server listening");
  //connecting to a mqtt broker
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);
  //inizializzo il sensore
  dht.begin();
  timeClient.begin();
  timeClient.setTimeOffset(-1);

}

void loop() {
  currentMillis = millis();
  server.handleClient();
  
  if(currentMillis - startMillis >= period){
    startMillis = millis();
    timeClient.update();
    
    time_t epochTime = timeClient.getEpochTime();
    struct tm *ptm = gmtime ((time_t *)&epochTime); 
    int monthDay = ptm->tm_mday;
    int currentMonth = ptm->tm_mon+1;
    String currentMonthName = months[currentMonth-1];
    int currentYear = ptm->tm_year+1900;
  
    //Print complete date:
    String currentDate = String(currentMonth) + "/" + String(monthDay) + "/" + String(currentYear);
    Serial.print("Current date: ");
    Serial.println(currentDate);
    //ritardo di 2 secondi affinchè il sensore si stabilizzi ed abbia tempo di effettuare la lettura
    delay(2000);
    float MaxT = 0;
    float MinT = 0;
    float RH1 = 0;
    float RH2 = 0;
    //leggo l' umidità
    float h = dht.readHumidity();
    if(h>RH1) {
      RH2 = RH1;
      RH1 = h;
    } else if(h<RH2) {
      RH2 = h;
    }
    //leggo la temperatura
    float t = dht.readTemperature();
      if(t>MaxT) {
      MinT = MaxT;
      MaxT = t;
    } else if(h<RH2) {
      MinT = t;
    }
    //stampo i dati
    Serial.print(F("Humidity: "));
    Serial.print(h);
    Serial.print(F("%  Temperature: "));
    Serial.print(t);
    Serial.print(F("°C "));
    client.loop();
    while (!client.connected()) {
      String client_id = "esp8266-client-";
      client_id += String(WiFi.macAddress());
      Serial.printf("The client %s connects to the public mqtt broker\n", client_id.c_str());
      if (client.connect(client_id.c_str(), mqtt_username, mqtt_password)) {
          Serial.println("Public emqx mqtt broker connected");
      } else {
          Serial.print("failed with state ");
          Serial.print(client.state());
          delay(2000);
      }
    }
    // publish and subscribe
    client.publish(topic, "ESP8266");
    client.publish(topic, String(currentDate).c_str());
    client.publish(topic, String(MaxT).c_str());
    client.publish(topic, String(MinT).c_str());
    client.publish(topic, String(RH1).c_str());
    client.publish(topic, String(RH2).c_str());
    client.subscribe(topic);
    //2 minuti
    //delay(30000);
    //10 minuti
    //delay(600000);
    //12 ore
    //delay(43200000);
    //24 ore
    //delay(86400000);
  }
} 