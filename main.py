import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QProgressBar, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QThread, pyqtSignal
import folium
import pandas as pd
import io
import requests
from geopy.distance import geodesic

RADIUS_KM = 1  # Radius to filter transmitters
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

# Import funkcji do pobierania danych na podstawie StationId
from download_test import get_base_station_info  # Dopasuj nazwę pliku/funkcji

class Worker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(pd.DataFrame)

    def __init__(self, location, wojewodztwo):
        super().__init__()
        self.location = location
        self.wojewodztwo = wojewodztwo
        self.filtered_df = pd.DataFrame()

    def run(self):
        try:
            df = pd.read_csv('output.csv', delimiter=';', usecols=['siec_id', 'LONGuke', 'LATIuke', 'StationId', 'wojewodztwo_id', 'pasmo', 'standard'])
            mapped_wojewodztwo = WOJEWODZTW_MAP.get(self.wojewodztwo, self.wojewodztwo)
            df = df[df['wojewodztwo_id'] == mapped_wojewodztwo]
            self.filtered_df = self.filter_transmitters_by_location(df, self.location, RADIUS_KM)
            self.result.emit(self.filtered_df)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            self.result.emit(pd.DataFrame())

    def filter_transmitters_by_location(self, df, location, radius_km):
        total = len(df)
        filtered_rows = []
        for i, row in df.iterrows():
            if geodesic(location, (row['LATIuke'], row['LONGuke'])).km <= radius_km:
                filtered_rows.append(row)
            self.progress.emit(int(((i + 1) / total) * 100))
        return pd.DataFrame(filtered_rows)


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

        self.fetch_data_button = QPushButton("Pobierz dane na podstawie ID", self)
        self.fetch_data_button.clicked.connect(self.fetch_data)
        self.layout.addWidget(self.fetch_data_button)

        self.map_view = QWebEngineView(self)
        self.layout.addWidget(self.map_view, 3)

        self.progress_bar = QProgressBar(self)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self)
        self.layout.addWidget(self.status_label)

    def fetch_data(self):
        """
        Pobiera szczegółowe dane z API na podstawie ID nadajników wyświetlonych na mapie.
        """
        try:
            # Pobierz dane przefiltrowane w promieniu 7 km
            filtered_df = self.worker.filtered_df
            if filtered_df.empty:
                self.status_label.setText("Brak nadajników w promieniu.")
                return

            # Pobierz StationId dla wyświetlonych nadajników
            station_ids = filtered_df['StationId'].unique()

            # Pobierz dane z API dla każdego ID
            for station_id in station_ids:
                print(f"Pobieram dane dla StationId: {station_id}")
                station_data = get_base_station_info(station_id)
                if station_data:
                    print(f"Dane dla {station_id}: {station_data}")
                else:
                    print(f"Nie znaleziono danych dla {station_id}")
        except Exception as e:
            self.status_label.setText(f"Błąd podczas pobierania danych: {e}")

    def show_map(self):
        address = self.address_input.text()
        api_key = self.api_key_input.text()
        if not api_key:
            self.status_label.setText("Klucz API, który został podany jest niepoprawny.")
            return
        location, wojewodztwo = self.get_location_from_opencage(address, api_key)
        if location and wojewodztwo:
            self.start_worker(location, wojewodztwo)
        else:
            self.status_label.setText("Could not retrieve location.")

    def get_location_from_opencage(self, address, api_key):
        url = f'https://api.opencagedata.com/geocode/v1/json?q={address}&key={api_key}'
        response = requests.get(url).json()
        if response and response['results']:
            lat = float(response['results'][0]['geometry']['lat'])
            lon = float(response['results'][0]['geometry']['lng'])
            components = response['results'][0]['components']
            wojewodztwo = components.get('state', None)
            return (lat, lon), wojewodztwo
        return None, None

    def start_worker(self, location, wojewodztwo):
        self.worker = Worker(location, wojewodztwo)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.display_map)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_map(self, filtered_df):
        """
        Wyświetla mapę z zaznaczonymi nadajnikami i zapisuje przefiltrowane dane w Worker.
        """
        self.progress_bar.setValue(100)
        if filtered_df.empty:
            self.status_label.setText("Brak danych, spróbój ponownie później.")
            return

        # Przypisz przefiltrowane dane do atrybutu Worker
        self.worker.filtered_df = filtered_df

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
            for operator, sub_group in group.groupby('siec_id'):
                pasma_technologie = sub_group.groupby('pasmo')['standard'].apply(lambda x: ', '.join(x.unique()))
                details = [f"{pasmo} ({technologie})" for pasmo, technologie in pasma_technologie.items()]
                operator_info.append(f"{operator}: " + '; '.join(details))
                color = operator_colors.get(operator, 'blue')
                color_blocks.append(f'<div style="flex: 1; background-color: {color};"></div>')
            tooltip_text = '<br>'.join(operator_info)
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
        self.status_label.setText("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
