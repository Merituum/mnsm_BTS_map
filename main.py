import sys
import os  # Dodany import modułu os
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QProgressBar, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QThread, pyqtSignal
import folium
import pandas as pd
import io
import requests
from geopy.distance import geodesic
from geopy.point import Point
from geopy import distance
from urllib.parse import urlencode
import logging
import concurrent.futures
from PyPDF2 import PdfReader
import re
import math

RADIUS_KM = 7  # Radius to filter transmitters

WOJEWODZTW_MAP = {
    "Podlaskie Voivodeship": "Podlaskie",
    "West Pomeranian Voivodeship": "Zachodniopomorskie",
    "Greater Poland Voivodeship": "Wielkopolskie",
    "Warmian-Masurian Voivodeship": "Warmińsko-Mazurskie",
    "Lesser Poland Voivodeship": "Małopolskie",
    "Lubin Voivodeship": "Lubuskie",
    "Holy Cross Voivodeship": "Świętokrzyskie",
    "Masovian Voivodeship": "Mazowieckie",
    "Opole Voivodeship": "Opolskie",
    "Silesian Voivodeship": "Śląskie",
    "Lower Silesian Voivodeship": "Dolnośląskie",
    "Lubusz Voivodeship": "Lubuskie",
    "Kuyavian-Pomeranian Voivodeship": "Kujawsko-Pomorskie",
    "Łódź Voivodeship": "Łódzkie",
    "Subcarpathian Voivodeship": "Podkarpackie",
    "Pomeranian Voivodeship": "Pomorskie",
}

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Worker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(pd.DataFrame)

    def __init__(self, location, wojewodztwo, api_key):
        super().__init__()
        self.location = location
        self.wojewodztwo = wojewodztwo
        self.api_key = api_key  # Dodatkowy klucz API, jeśli potrzebny

    def run(self):
        try:
            # Krok 1: Pobierz dane nadajników z CSV
            df = pd.read_csv(
                'output.csv',
                delimiter=';',
                usecols=['siec_id', 'LONGuke', 'LATIuke', 'StationId', 'wojewodztwo_id', 'pasmo', 'standard'],
                low_memory=False  # Dodane aby uniknąć DtypeWarning
            )
            mapped_wojewodztwo = WOJEWODZTW_MAP.get(self.wojewodztwo, self.wojewodztwo)
            df = df[df['wojewodztwo_id'] == mapped_wojewodztwo]

            # Krok 2: Filtruj nadajniki według lokalizacji
            filtered_df = self.filter_transmitters_by_location(df, self.location, RADIUS_KM)

            # Krok 3: Pobierz URL-e do PDF-ów z WFS GetFeature
            if not filtered_df.empty:
                # Oblicz BBOX wokół lokalizacji użytkownika
                min_lat, min_lon, max_lat, max_lon = self.calculate_bbox(self.location, RADIUS_KM)

                # Pobierz dane z WFS GetFeature
                wfs_features = self.fetch_wfs_features(min_lat, min_lon, max_lat, max_lon)

                # Stwórz DataFrame z WFS features
                wfs_df = self.parse_wfs_features(wfs_features)

                # Merge filtered_df z wfs_df na podstawie lat i lon
                merged_df = pd.merge(
                    filtered_df,
                    wfs_df,
                    left_on=['LATIuke', 'LONGuke'],
                    right_on=['latitude', 'longitude'],
                    how='left'
                )

                # Krok 4: Pobierz i przetwórz PDF dla każdego nadajnika
                azimuth_tilt_data = self.fetch_azimuth_tilt_from_pdfs(merged_df['url'].dropna().unique().tolist())
                if not azimuth_tilt_data.empty:
                    # Merge azimuth and tilt data into the merged_df
                    merged_df = merged_df.merge(azimuth_tilt_data, on='url', how='left')

                self.result.emit(merged_df)
            else:
                self.result.emit(filtered_df)
        except Exception as e:
            logging.error(f"Error processing data: {e}")
            self.result.emit(pd.DataFrame())

    def filter_transmitters_by_location(self, df, location, radius_km):
        total = len(df)
        filtered_rows = []
        for i, row in df.iterrows():
            distance_km = geodesic(location, (row['LATIuke'], row['LONGuke'])).km
            if distance_km <= radius_km:
                filtered_rows.append(row)
            self.progress.emit(int(((i + 1) / total) * 100))
        return pd.DataFrame(filtered_rows)

    def calculate_bbox(self, location, radius_km):
        """
        Oblicza BBOX wokół danej lokalizacji na podstawie promienia w km.
        """
        origin = Point(location[0], location[1])
        destination_north = distance.distance(kilometers=radius_km).destination(origin, 0)
        destination_east = distance.distance(kilometers=radius_km).destination(origin, 90)
        destination_south = distance.distance(kilometers=radius_km).destination(origin, 180)
        destination_west = distance.distance(kilometers=radius_km).destination(origin, 270)

        min_lat = destination_south.latitude
        min_lon = destination_west.longitude
        max_lat = destination_north.latitude
        max_lon = destination_east.longitude

        logging.info(f"Calculated BBOX: min_lat={min_lat}, min_lon={min_lon}, max_lat={max_lat}, max_lon={max_lon}")

        return min_lat, min_lon, max_lat, max_lon

    def fetch_wfs_features(self, min_lat, min_lon, max_lat, max_lon):
        """
        Pobiera dane z WFS GetFeature w określonym BBOX.
        """
        base_wfs_url = "https://si2pem.gov.pl/geoserver/public/wfs"
        cql_filter = f"BBOX(geom, {min_lon}, {min_lat}, {max_lon}, {max_lat})"
        params = {
            'service': 'WFS',
            'version': '1.0.0',
            'request': 'GetFeature',
            'typeName': 'public:measures_all',  # Dostosuj do rzeczywistej warstwy
            'outputFormat': 'application/json',
            'CQL_FILTER': cql_filter
        }
        query_string = urlencode(params)
        wfs_url = f"{base_wfs_url}?{query_string}"
        logging.info(f"Fetching WFS features from URL: {wfs_url}")

        try:
            response = requests.get(wfs_url)
            response.raise_for_status()
            data = response.json()
            features = data.get('features', [])
            logging.info(f"Fetched {len(features)} features from WFS.")
            return features
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch WFS features: {e}")
            return []

    def parse_wfs_features(self, features):
        """
        Parsuje features z WFS do DataFrame.
        """
        records = []
        for feature in features:
            properties = feature.get('properties', {})
            latitude = properties.get('latitude')
            longitude = properties.get('longitude')
            url = properties.get('url')
            if latitude and longitude and url:
                records.append({'latitude': float(latitude), 'longitude': float(longitude), 'url': url})
        wfs_df = pd.DataFrame(records)
        logging.info(f"Parsed {len(wfs_df)} WFS features with URLs.")
        return wfs_df

    def fetch_azimuth_tilt_from_pdfs(self, pdf_urls):
        """
        Pobiera PDF-y z podanych URL-i i wyodrębnia z nich azymuty oraz tilty.
        Zwraca DataFrame z kolumnami ['url', 'azimuth', 'tilt']
        """
        azimuth_tilt_records = []

        # Tworzenie folderu na pobrane PDF-y
        os.makedirs("pdfs_downloaded", exist_ok=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(self.download_and_parse_pdf, url): url for url in pdf_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    azimuth, tilt = future.result()
                    azimuth_tilt_records.append({'url': url, 'azimuth': azimuth, 'tilt': tilt})
                    logging.info(f"Parsed PDF from URL {url}: Azimuth={azimuth}, Tilt={tilt}")
                except Exception as e:
                    logging.error(f"Error processing PDF from URL {url}: {e}")

        return pd.DataFrame(azimuth_tilt_records)

    def download_and_parse_pdf(self, url):
        """
        Pobiera PDF z podanego URL i parsuje azymut oraz tilt.
        Zwraca tuple (azimuth, tilt)
        """
        pdf_filename = os.path.basename(url)
        pdf_path = os.path.join("pdfs_downloaded", pdf_filename)

        # Pobieranie PDF
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Downloaded PDF from {url} to {pdf_path}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download PDF from {url}: {e}")
            return ('N/A', 'N/A')

        # Parsowanie PDF
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text + "\n"

            # Wyodrębnienie azymutów i tiltów z tekstu
            # Zakładam, że azymuty są oznaczone jako "az. 190°" lub "Azymut: 190°"
            # Tilty jako "Tilt: 7°" lub "Tilt 7°"

            # Wyrażenia regularne do znalezienia azymutów i tiltów
            azimuth_pattern = re.compile(r'az(?:ymut)?\.?\s*[:\-]?\s*(\d{1,3})°', re.IGNORECASE)
            tilt_pattern = re.compile(r'Tilt\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)°', re.IGNORECASE)

            # Znajdowanie wszystkich azymutów i tiltów
            azimuths = azimuth_pattern.findall(text)
            tilts = tilt_pattern.findall(text)

            # Logowanie znalezionych wartości
            logging.debug(f"PDF {pdf_filename}: Found azimuths: {azimuths}, tilts: {tilts}")

            # Przykład: Przyjmuję pierwszy znaleziony azymut i tilt
            azimuth = ', '.join(azimuths) if azimuths else 'N/A'
            tilt = ', '.join(tilts) if tilts else 'N/A'

            return (azimuth, tilt)
        except Exception as e:
            logging.error(f"Failed to parse PDF {pdf_path}: {e}")
            return ('N/A', 'N/A')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MNSM by Merituum")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.address_input = QLineEdit(self)
        self.address_input.setPlaceholderText("Podaj adres: ")
        self.layout.addWidget(self.address_input)

        self.api_key_input = QLineEdit(self)
        self.api_key_input.setPlaceholderText("Podaj klucz API (OpenCage)")
        self.layout.addWidget(self.api_key_input)

        self.show_map_button = QPushButton("Wyświetl mapę", self)
        self.show_map_button.clicked.connect(self.show_map)
        self.layout.addWidget(self.show_map_button)

        self.map_view = QWebEngineView(self)
        self.layout.addWidget(self.map_view, 3)

        self.progress_bar = QProgressBar(self)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self)
        self.layout.addWidget(self.status_label)

    def show_map(self):
        address = self.address_input.text()
        api_key = self.api_key_input.text()
        if not api_key:
            self.status_label.setText("Klucz API jest niepoprawny lub nie został podany.")
            return
        location, wojewodztwo = self.get_location_from_opencage(address, api_key)

        if location and wojewodztwo:
            self.start_worker(location, wojewodztwo, api_key)
        else:
            self.status_label.setText("Nie udało się pobrać lokalizacji.")

    def get_location_from_opencage(self, address, api_key):
        url = f'https://api.opencagedata.com/geocode/v1/json?q={address}&key={api_key}'
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if data and data['results']:
                lat = float(data['results'][0]['geometry']['lat'])
                lon = float(data['results'][0]['geometry']['lng'])
                components = data['results'][0]['components']
                wojewodztwo = components.get('state', None)
                return (lat, lon), wojewodztwo
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd podczas geokodowania adresu: {e}")
        return None, None

    def start_worker(self, location, wojewodztwo, api_key):
        self.worker = Worker(location, wojewodztwo, api_key)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.display_map)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_map(self, filtered_df):
        self.progress_bar.setValue(100)

        if filtered_df.empty:
            self.status_label.setText("Brak danych, spróbuj ponownie później.")
            return

        user_lat, user_lon = self.worker.location
        map_ = folium.Map(location=[user_lat, user_lon], zoom_start=12)

        folium.Marker(
            [user_lat, user_lon],
            tooltip="Podany adres",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(map_)

        operator_colors = {
            'T-Mobile': 'pink',
            'Orange': 'orange',
            'Play': 'purple',
            'Plus': 'green'
        }

        grouped = filtered_df.groupby(['LATIuke', 'LONGuke'])

        for (lat, lon), group in grouped:
            operator_info = []
            color_blocks = []
            azimuth_info = []
            tilt_info = []
            for operator, sub_group in group.groupby('siec_id'):
                pasma_technologie = sub_group.groupby('pasmo')['standard'].apply(lambda x: ', '.join(x.unique()))
                details = [f"{pasmo} ({technologie})" for pasmo, technologie in pasma_technologie.items()]
                operator_info.append(f"{operator}: " + '; '.join(details))
                color = operator_colors.get(operator, 'blue')
                color_blocks.append(f'<div style="flex: 1; background-color: {color};"></div>')

            # Dodatkowe informacje o azymutach i tiltach
            for _, row in group.iterrows():
                azimuth = row.get('azimuth', 'N/A')
                tilt = row.get('tilt', 'N/A')
                azimuth_info.append(f"Azymut: {azimuth}°")
                tilt_info.append(f"Tilt: {tilt}°")

            tooltip_text = '<br>'.join(operator_info + azimuth_info + tilt_info)

            html = f'''
                <div style="width: 30px; height: 30px; display: flex; border-radius: 50%; border: 2px solid #000;">
                    {''.join(color_blocks)}
                </div>
            '''
            icon = folium.DivIcon(html=html)

            folium.Marker(
                [lat, lon],
                tooltip=tooltip_text,
                icon=icon
            ).add_to(map_)

        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())
        self.progress_bar.setValue(0)
        self.status_label.setText("Mapy zostały zaktualizowane.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
