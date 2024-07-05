import sys
import folium
import io
import pandas as pd
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLineEdit, QPushButton, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Ustawienia okna
        self.setWindowTitle("Mapa z lokalizacją")
        self.setGeometry(100, 100, 800, 600)

        # Inicjalizacja geolokatora
        self.geolocator = Nominatim(user_agent="geoapiExercises")

        # Wczytaj dane z pliku Excel
        self.df = pd.read_excel(r'C:\Users\Bartosz\Desktop\kod\Map network analyzer\nadajniki')

        # Przefiltruj nadajniki znajdujące się w Warszawie
        self.df_warszawa = self.df[self.df['Miasto'].str.contains('Warszawa', na=False, case=False)]

        # Tworzenie głównego widgetu
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Tworzenie układu
        self.layout = QVBoxLayout(self.central_widget)

        # Tworzenie pola do wpisywania miejscowości
        self.location_input = QLineEdit(self)
        self.location_input.setPlaceholderText("Wpisz nazwę miejscowości")
        self.layout.addWidget(self.location_input)

        # Tworzenie przycisku do wyszukiwania
        self.search_button = QPushButton("Znajdź", self)
        self.search_button.clicked.connect(self.update_map)
        self.layout.addWidget(self.search_button)

        # Tworzenie widoku WebEngineView
        self.browser = QWebEngineView(self)
        self.layout.addWidget(self.browser)

        # Początkowa mapa
        self.update_map(initial=True)

    def update_map(self, initial=False):
        if initial:
            latitude, longitude = 52.2297, 21.0122  # Warszawa
            location_name = 'Warszawa'
        else:
            location_name = self.location_input.text()
            location = None
            try:
                location = self.geolocator.geocode(location_name)
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"Geocoding error: {e}")

            if location:
                latitude, longitude = location.latitude, location.longitude
            else:
                latitude, longitude = 52.2297, 21.0122  # Domyślna lokalizacja: Warszawa
                location_name = 'Warszawa'

        # Tworzenie mapy z nową lokalizacją
        mapa = folium.Map(location=[latitude, longitude], zoom_start=12)

        # Dodanie znaczników dla nadajników w Warszawie
        for _, row in self.df_warszawa.iterrows():
            folium.Marker([row['Latitude'], row['Longitude']], popup=row['Nazwa']).add_to(mapa)

        # Zapisanie mapy do obiektu bytes
        data = io.BytesIO()
        mapa.save(data, close_file=False)

        # Konwersja bytes do HTML string
        html = data.getvalue().decode()

        # Wczytanie mapy do widoku
        self.browser.setHtml(html, QUrl(""))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MapWindow()
    window.show()
    sys.exit(app.exec_())
