import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
import io
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LTE/5G Network Analyzer")
        self.setGeometry(100, 100, 800, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        
        self.address_input = QLineEdit(self)
        self.address_input.setPlaceholderText("Enter address")
        self.layout.addWidget(self.address_input)
        
        self.show_map_button = QPushButton("Show Map", self)
        self.show_map_button.clicked.connect(self.show_map)
        self.layout.addWidget(self.show_map_button)
        
        self.map_view = QWebEngineView(self)
        self.layout.addWidget(self.map_view)

    def show_map(self):
        address = self.address_input.text()
        if address:
            location = self.get_location_from_address(address)
            if location:
                self.display_map(location)
            else:
                print("Location not found")

    def get_location_from_address(self, address):
        geolocator = Nominatim(user_agent="myGeocoder")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        return None

    def dms_to_decimal(self, dms_str):
        """
        Convert DMS (Degrees, Minutes, Seconds) to decimal format.
        Example input: '19E48\'22"'
        """
        import re
        parts = re.split('[^\d\w]+', dms_str)
        degrees = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        direction = parts[3]

        decimal = degrees + minutes / 60 + seconds / 3600
        if direction in ['S', 'W']:
            decimal *= -1
        return decimal

    def display_map(self, location):
        lat, lon = location
        map_ = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker([lat, lon], tooltip='Location').add_to(map_)

        # Load data from Excel file
        try:
            df = pd.read_excel('nadajniki/5g3600_-_stan_na_2024-06-25.xlsx')
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            return

        # Filter transmitters within 15 km radius
        for index, row in df.iterrows():
            try:
                station_lat = self.dms_to_decimal(row['Dł geogr stacji'])
                station_lon = self.dms_to_decimal(row['Lokalizacja'])
            except Exception as e:
                print(f"Error converting coordinates: {e}")
                continue

            station_location = (station_lat, station_lon)
            distance = geodesic((lat, lon), station_location).km

            if distance <= 15:
                operator = row['Nazwa operatora']
                station_id = row['IdStacji']

                # Create HTML content for tooltip
                tooltip_html = f"<b>Operator:</b> {operator}<br><b>Station ID:</b> {station_id}<br><b>Distance:</b> {distance:.2f} km"

                # Add marker to the map
                folium.Marker([station_lat, station_lon], tooltip=tooltip_html).add_to(map_)

        # Save map to bytes and display in QWebEngineView
        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
