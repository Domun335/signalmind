# SignalMind // OutOfBlack

> **Dual-Use Swarm RF Reconnaissance & Crisis Management System**  
> _Autonomiczne pasywne rozpoznanie radiowe oparte na roju dronów połączonych w sieć P2P Mesh w strefach całkowitego blackoutu._

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Leaflet GIS](https://img.shields.io/badge/GIS-Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)

---

## Przegląd Projektu (Executive Summary)

**SignalMind (OutOfBlack)** to zaawansowana platforma podwójnego zastosowania (_dual-use_: poszukiwawczo-ratownicza SAR, zarządzanie kryzysowe i obronność), zaprojektowana do operowania w rejonach dotkniętych klęskami żywiołowymi, katastrofami przemysłowymi lub działaniami militarnymi, gdzie nastąpił **blackout** - zniszczenie naziemnych stacji bazowych GSM, sieci energetycznej i infrastruktury internetowej.

Zamiast polegać na łączności komórkowej czy aktywnym namierzaniu, system wysyła **rój autonomicznych bezzałogowców (UAV)**, które:

1. **Tworzą samokonfigurującą się sieć ad-hoc (P2P MANET Mesh)** w powietrzu, utrzymując łączność ze stacją bazową GCS nawet poza bezpośrednim horyzontem radiowym (_Multi-Hop Backhaul_).
2. **Pasywnie nasłuchują (sniffing RF)** impulsów wysyłanych przez telefony ofiar (ramki _Wi-Fi Probe Request_ oraz sygnały _LTE Uplink_), bez potrzeby logowania się urządzeń do sieci.
3. **Lokalizują źródła emisji w czasie rzeczywistym** za pomocą adaptacyjnej multilateracji ważonej (_WCL - Weighted Centroid Localization_) z precyzyjną oceną okręgu niepewności (_CEP - Circular Error Probable_).
4. **Zarządzają energią i misją roju** — automatyczna procedura powrotu do bazy (_RTL - Return to Land_) przy niskim stanie baterii, wymiana pakietów zasilających i ponowny start, a także inspekcja zidentyfikowanych celów (hovering).

---

## Architektura Monorepo

Repozytorium zorganizowane jest w podziale na niezależne moduły:

```
signalmind/
├── Backend/                      # Serwer symulacji taktycznej i silnik matematyczny (Python/FastAPI)
│   ├── core/                     # Geodezja ENU, propagacja RF, sieć Mesh, multilateracja WCL, planista Boustrophedon
│   ├── models/                   # Schematy Pydantic v2 (telemetria, komendy, stany misji)
│   ├── tests/                    # Zestaw testów jednostkowych i integracyjnych (pytest)
│   ├── simulation_engine.py      # Główny silnik symulacji i pętla zdarzeń
│   ├── simulation_config.json    # Aktywny plik konfiguracji parametrów misji i środowiska
│   └── main.py / app.py          # FastAPI WebSocket (1 Hz) & REST API
│
├── Frontend/
│   ├── outofblack/               # Główny interfejs taktyczny (Tactical Command Dashboard)
│   │   ├── components/setup/     # Simulation Studio (kreator parametrów misji i mapy)
│   │   ├── components/dashboard/ # Kokpit operacyjny (mapa GIS Leaflet, roje, sygnały, mesh)
│   │   └── hooks/                # Klient WebSocket z automatyczną retransmisją i buforowaniem
│   │
│   └── landing/                  # Landing page prezentacyjny projektu SignalMind
│       └── app/                  # Cyber-radar UI z animacjami i opisem technologii
│
└── README.md                     # Niniejszy dokument
```

---

## Szybki Start (Quick Start)

### Wymagania wstępne:

- **Python 3.11+** oraz wirtualne środowisko (`venv`)
- **Node.js 18+** i **npm**

---

### Krok 1: Uruchomienie Backend (Silnik Symulacji)

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Uruchomienie serwera FastAPI (port 8000)
python app.py
```

> Backend wystawia:
>
> - **REST API & Dokumentacja Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
> - **WebSocket Telemetrii:** `ws://localhost:8000/ws/telemetry` (częstotliwość 1 Hz)

---

### Krok 2: Uruchomienie Dashboardu Taktycznego (OutOfBlack)

W nowym oknie terminala:

```bash
cd Frontend/outofblack
npm install
npm run dev
```

> Otwórz w przeglądarce: **[http://localhost:3000](http://localhost:3000)**  
> Dostępne tryby:
>
> - 🛠️ **Simulation Studio:** Wizualny edytor strefy poszukiwań, pozycji GCS, masztów GSM i ofiar.
> - 🛰️ **Operator Console:** Interaktywna mapa taktyczna Leaflet na żywo, telemetria roju, stan baterii, zarządzanie prędkością (WARP 1x–25x), inspekcja celów i wstrzykiwanie ofiar.

---

### Krok 3: (Opcjonalnie) Uruchomienie Landing Page

W kolejnym terminalu:

```bash
cd Frontend/landing
npm install
npm run dev -- -p 3001
```

> Otwórz w przeglądarce: **[http://localhost:3001](http://localhost:3001)**

---

## Modele Matematyczne i Algorytmiczne

| Moduł                | Algorytm / Model                         | Opis działania                                                                                                                     |
| :------------------- | :--------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| **Geodezja**         | Płaska projekcja ENU (_East-North-Up_)   | Konwersja współrzędnych WGS84 na metryczny układ lokalny $(x,y,z)$ względem punktu odniesienia misji.                              |
| **Trajektorie Roju** | _Boustrophedon Search Pattern_           | Zsynchronizowane przeszukiwanie pasowe (tzw. kosiarka) z dynamicznym przydziałem korytarzy dla dronów.                             |
| **Propagacja RF**    | _Log-Distance Path Loss_ + _Shadowing_   | Modelowanie tłumienia sygnałów Wi-Fi (2.4 GHz) i LTE (700-1800 MHz) z losowym cieniowaniem wielodrogowym ($\sigma=2.0\text{ dB}$). |
| **Lokalizacja**      | _Weighted Centroid Localization (WCL)_   | Ważenie odległości na podstawie odwróconego równania strat ścieżki i wieku pakietu. Obliczanie błędu kołowego CEP.                 |
| **Topologia Sieci**  | _MANET Ad-Hoc Mesh_ + _Gateway Election_ | Dynamiczne krawędzie radiowe ($R \le 700\text{ m}$), elekcja bramy o najlepszym łączu do GCS i trasowanie wieloskokowe (BFS).      |
| **Blackout GSM**     | Gradientowe pole tłumienia               | Symulacja zniszczonych stacji bazowych (BTS) i strefy braku zasięgu komórkowego.                                                   |
| **Dual-Use Privacy** | Haszowanie kryptograficzne               | Sniffowane adresy MAC są nieodwracalnie haszowane: `SHA256(SALT + MAC)[0:8]`.                                                      |

---

## Możliwości Interfejsu

1. **Podgląd GIS**: Przełączanie kafelków podkładowych (_CARTO Dark Matter_, _Esri Dark Canvas_, _Esri Satellite_).
2. **Sterowanie Misją**: `START`, `WZNÓW`, `ABORT (RTL)`, `RESET`.
3. **Zarządzanie Czasem**: Akcelerator symulacji `1x`, `2x`, `5x`, `10x`, `25x`.
4. **Zarządzanie Energią Roju**: Alarmy niskiego stanu baterii, automatyczny powrót RTL, wymiana baterii (_Swap Battery_) i ponowny start (_Relaunch_).
5. **Inspekcja Celu**: Wysłanie najbliższego drona w tryb zawisu (_Hover / Inspect_) nad wykrytym punktem POI, a następnie powrót do przeszukiwania.
6. **Live Injection**: Dodawanie poszkodowanych na żywo z poziomu mapy lub formularza współrzędnych.

---

## Testy Jednostkowe

Wszystkie kluczowe moduły backendu posiadają dedykowany zestaw testów oparty o `pytest`:

```bash
cd Backend
pytest tests/ -v
```

Pokrywane obszary testowe:

- `test_coordinates.py`: Poprawność transformacji geodezyjnych WGS84 ↔ ENU.
- `test_flight_planner.py`: Algorytm Boustrophedon, separacja korytarzy i kinetyka lotu.
- `test_rf_propagation.py`: Straty propagacyjne, progi czułości RSSI i estymacja odległości.
- `test_mesh_network.py`: Graf połączeń, wskaźnik LQI, elekcja bramy i izolacja węzłów.
- `test_estimator.py`: Zbieżność algorytmu WCL i redukcja okręgu niepewności.
- `test_simulation_engine.py`: Pętla zdarzeń, zmiana stanów, obsługa baterii i RTL.
- `test_api.py`: Endpointy REST i poprawność schematów odpowiedzi.

---
