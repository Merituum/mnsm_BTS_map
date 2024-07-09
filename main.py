import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
import pandas as pd
import io
import requests

OPENCAGE_API_KEY = '329efb3e6b1d4291b7559e2409deb4d4'

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
                print("Could not retrieve location.")
        else:
            print("No address entered.")

    def get_location_from_address(self, address):
        # Use OpenCageData API to convert address to latitude and longitude
        url = f'https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_API_KEY}'
        response = requests.get(url).json()
        if response and response['results']:
            lat = response['results'][0]['geometry']['lat']
            lon = response['results'][0]['geometry']['lng']
            return float(lat), float(lon)
        return None

    def display_map(self, location):
        lat, lon = location
        map_ = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker([lat, lon], tooltip='Location').add_to(map_)

        # Save and display initial map
        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())

        # Load data from CSV file
        try:
            df = pd.read_csv('test_lomza.csv', delimiter=';', usecols=['siec_id', 'LONGuke', 'LATIuke', 'StationId'])
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return

        # Add markers for each transmitter in the specified town
        for index, row in df.iterrows():
            operator = row['siec_id']
            trans_lat = row['LATIuke']
            trans_lon = row['LONGuke']
            station_id = row['StationId']
            transmitter_location = (trans_lat, trans_lon)

            # Create HTML content for tooltip
            tooltip_html = f"<b>Operator:</b> {operator}<br><b>Station ID:</b> {station_id}"
            # Add marker to the map
            print(trans_lat, trans_lon)
            folium.Marker([trans_lat, trans_lon], tooltip=tooltip_html).add_to(map_)

        # Save map with transmitters and display in QWebEngineView
        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
