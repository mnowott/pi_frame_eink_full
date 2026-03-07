# Intro

Diese App bereitet Bilder für deine **800×480 eInk-Bilderrahmen** vor, verwaltet sie
und synchronisiert sie mit den Rahmen auf dem Raspberry Pi.

So stellst du sicher, dass **alle Bilder immer exakt zur Auflösung des Displays passen** 
und der Rahmen automatisch auf neue Bilder reagiert.
---

## Pipeline-Überblick

1. Du wählst und/oder beschneidest Bilder hier in der App.
2. Die bearbeiteten Bilder werden in einem geteiltem Ordner in der Cloud geschrieben.
3. Auf dem Bilderrahmen überwacht der Pi den Ordner und synchronisiert regelmäßig

## WIFI einstellungen

Im tab **Downloads** kannst du eine wifi.json datei runterladen. Wenn diese Datei mit deinem
WLAN namen und deinem WLAN password auf der micro-sd Karte (oberste ebene, nicht in ordner verpacken)
abgelegt wird, verbindet sich der Pi automatisch mit dem wifi.

```json
{
  "wifi_name": "YourSSID",
  "wifi_password": "YourWifiPassword"
}
```

## Bilder downloads

Die gesammeltern Bilder können auf der Downloadseite als zip-Datei heruntergeladen werden.


## Lokale Bilder

Neben den Bildern in der Cloud können auch lokale Bilder (png, jpg) in der MicroSD karte abgelegt werden, am
besten einfach auf der obersten Ebene, aber Unterordner werden auch erkannt.

Der Bilderrahmen erlaubt in den Einstellungen zwischen lokal/cloud zu wechseln (siehe unten).
## SD-Karten-Struktur & Bildmodi

## Settings.

Falls der Pi mit dem Wlan verbunden ist wird im Wlan eine Settings app bereitgeselt, die URL git der Bilderrahmen beim start aus.

Der Pi verwendet einen konfigurierbaren *picture_mode* aus den settings (siehe local app auf dem Boot-Screen der Bilderrahmen).
Beachte: der ordner s3_folder in der Micro-SD Karte ist besonders und sollte nicht vom Nutzer angefasst werden.

- `local`  – nur Bilder **außerhalb** des Ordners `s3_folder`
- `online` – nur Bilder **innerhalb** von `s3_folder`
- `both`   – **alle** Bilder auf der SD-Karte

Typische SD-Karten-Struktur:

```text
/ (Root der SD-Karte)
├── my_photos/         # lokale Bilder
├── holidays/          # lokale Bilder
└── s3_folder/         # „Online“-Bilder (z.B. von S3 synchronisiert)
