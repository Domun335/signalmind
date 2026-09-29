# OutOfBlack // Tactical Command & Reconnaissance Dashboard

Nowoczesny interfejs taktyczny (Tactical Command & Ground Control Dashboard) dla systemu **OutOfBlack**, zbudowany w oparciu o **Next.js 16 (App Router)**, **Tailwind CSS v4** oraz **shadcn/ui**.

Aplikacja łączy się w czasie rzeczywistym z backendem symulacji przez **WebSocket** (`ws://localhost:8000/ws/telemetry`) oraz **REST API** (`http://localhost:8000`).

---

## Główne Funkcjonalności

1. **Cyber-Tactical Dark Ops UI**:
   - Domyślny, spójny tryb ciemny o wysokim kontraście.
   - Kolorystyka taktyczna: neonowy cyjan (Mesh & Trajektorie), bursztyn (Łącze dosyłowe C2 Gateway), szmaragd (GPS & Stan Online), karmazyn (Wykryte Ofiary & Alarmy).
2. **Centralna Interaktywna Mapa GIS (Leaflet)**:
   - Dynamiczny import po stronie klienta (SSR-safe).
   - Przełącznik kafelków podkładowych: **CARTO Dark Matter** (z autoryzacją API Key), **Esri Dark Canvas**, **Esri Satelita**.
   - Warstwy operacyjne:
     - 🛸 **Pozycje dronów**: Animowane obroty według kąta kursu (`heading`), identyfikatory callsign, oznaczenie drona-bramy (Gateway).
     - 🛣️ **Trasy planowane**: Pasy przeszukiwań Boustrophedon z punktami zwrotnymi.
     - ⚡ **Siatka P2P Mesh**: Błękitne łącza Air-to-Air oraz pogrubione złote łącze C2 Gateway Backhaul ze wskaźnikami jakości (LQI %) i poziomem RSSI w dBm.
     - ⭕ **Okręgi zasięgów**: Zasięg stacji bazowej GCS (5.0 km) oraz zasięg P2P drona (2.5 km).
     - 🎯 **Wykryte sygnały poszkodowanych**: Koncentryczne radary beaconowe oraz geometryczne okręgi niepewności CEP ($\pm R_{unc}\text{ m}$) kurczące się wraz z kolejnymi pakietami.
     - 📶 **Gradient blackoutu GSM**: Wizualizacja zaniku sygnału komórkowego w epicentrum kataklizmu.
3. **Pasek Kontroli Misji & Metryk (TopNav)**:
   - Przyciski operacyjne: `START ROJU`, `WSTRZYMAJ`, `WZNÓW`, `RESET`.
   - Przełącznik przyspieszenia czasu (WARP): `1x`, `2x`, `5x`, `10x`.
   - Wstrzykiwanie ofiar (`+ OFIARA`).
   - Metryki na żywo: Czas misji, Pokrycie strefy %, Aktywne łącza mesh, Wykryte ofiary.
4. **Panele Taktyczne**:
   - **Rój UAV**: Monitoring baterii LiPo (z ostrzeżeniami procedury powrotu RTL), pułapu, prędkości, sniffowanych pakietów oraz trasy wieloskokowej do bazy (np. `UAV-06 ➔ UAV-05 ➔ UAV-01 ➔ GCS-BASE`). Kliknięcie drona centruje mapę.
   - **Wykryte Sygnały**: Zanonimizowane ID (SHA-256), typ sygnału (Wi-Fi Probe / LTE Uplink), poziom pewności %, błąd CEP ($\pm X\text{ m}$), ostatnie RSSI. Kliknięcie karty przybliża widok mapy do ofiary.
   - **Siatka MANET Mesh**: Macierz połączeń P2P, wskaźniki odległości i tłumienia.
   - **Konfigurator Misji (ConfigModal)**: Edycja parametrów w locie i bezpośredni zapis do `simulation_config.json`.

---

## Uruchomienie

1. Upewnij się, że backend symulacji działa na porcie `8000`:
   ```bash
   cd Backend
   source .venv/bin/activate
   python app.py
   ```

2. Uruchom serwer deweloperski frontendu:
   ```bash
   cd Frontend/outofblack
   npm run dev
   ```

3. Otwórz dashboard w przeglądarce pod adresem:
   **[http://localhost:3000](http://localhost:3000)**
