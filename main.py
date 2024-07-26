import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QProgressBar, QRadioButton, QButtonGroup, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QThread, pyqtSignal
import folium
import pandas as pd
import io
import requests
from geopy.distance import geodesic
from datetime import datetime, timedelta

DEMO_LAST_USED = None
RADIUS_KM = 10  # Radius to filter transmitters

class Worker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(pd.DataFrame)
    
    def __init__(self, location, wojewodztwo):
        super().__init__()
        self.location = location
        self.wojewodztwo = wojewodztwo

    def run(self):
        try:
            df = pd.read_csv('output.csv', delimiter=';', usecols=['siec_id', 'LONGuke', 'LATIuke', 'StationId', 'wojewodztwo_id'])
            # Filter by wojewodztwo
            df = df[df['wojewodztwo_id'] == self.wojewodztwo]
            filtered_df = self.filter_transmitters_by_location(df, self.location, RADIUS_KM)
            self.result.emit(filtered_df)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            self.result.emit(pd.DataFrame())  # Emit empty dataframe in case of error

    def filter_transmitters_by_location(self, df, location, radius_km):
        total = len(df)
        filtered_rows = []
        for i, row in df.iterrows():
            if geodesic(location, (row['LATIuke'], row['LONGuke'])).km <= radius_km:
                filtered_rows.append(row)
            self.progress.emit(int(((i + 1) / total) * 100))  # Update progress bar
        return pd.DataFrame(filtered_rows)

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

        self.api_key_input = QLineEdit(self)
        self.api_key_input.setPlaceholderText("Enter API key (for full version)")
        self.layout.addWidget(self.api_key_input)

        self.demo_radio = QRadioButton("Demo version (OpenStreetMap, 1 request per 24 hours)")
        self.full_radio = QRadioButton("Full version (OpenCageData)")
        self.layout.addWidget(self.demo_radio)
        self.layout.addWidget(self.full_radio)
        
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.demo_radio)
        self.button_group.addButton(self.full_radio)
        self.full_radio.setChecked(True)

        self.show_map_button = QPushButton("Show Map", self)
        self.show_map_button.clicked.connect(self.show_map)
        self.layout.addWidget(self.show_map_button)
        
        self.map_view = QWebEngineView(self)
        self.layout.addWidget(self.map_view)

        self.progress_bar = QProgressBar(self)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self)
        self.layout.addWidget(self.status_label)

    def show_map(self):
        address = self.address_input.text()
        if self.demo_radio.isChecked():
            if self.check_demo_limit():
                self.status_label.setText("Demo version: You can make 1 request per 24 hours.")
                location, wojewodztwo = self.get_location_from_osm(address)
            else:
                self.status_label.setText("Demo limit reached. Please try again later or use the full version.")
                return
        else:
            api_key = self.api_key_input.text()
            if not api_key:
                self.status_label.setText("Please enter a valid API key for the full version.")
                return
            location, wojewodztwo = self.get_location_from_opencage(address, api_key)
        
        if location and wojewodztwo:
            self.start_worker(location, wojewodztwo)
        else:
            self.status_label.setText("Could not retrieve location.")
    
    def check_demo_limit(self):
        global DEMO_LAST_USED
        now = datetime.now()
        if DEMO_LAST_USED is None or now - DEMO_LAST_USED >= timedelta(hours=24):
            DEMO_LAST_USED = now
            return True
        return False

    def get_location_from_osm(self, address):
        url = f'https://nominatim.openstreetmap.org/search?q={address}&format=json'
        response = requests.get(url).json()
        if response and len(response) > 0:
            lat = float(response[0]['lat'])
            lon = float(response[0]['lon'])
            # Get wojewodztwo from OSM reverse geocoding
            reverse_url = f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json'
            reverse_response = requests.get(reverse_url).json()
            if reverse_response and 'address' in reverse_response:
                wojewodztwo = reverse_response['address'].get('state', None)
                return (lat, lon), wojewodztwo
        return None, None

    def get_location_from_opencage(self, address, api_key):
        url = f'https://api.opencagedata.com/geocode/v1/json?q={address}&key={api_key}'
        response = requests.get(url).json()
        if response and response['results']:
            lat = float(response['results'][0]['geometry']['lat'])
            lon = float(response['results'][0]['geometry']['lng'])
            # Get wojewodztwo from OpenCageData reverse geocoding
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
        self.progress_bar.setValue(100)  # Ensure the progress bar is full

        if filtered_df.empty:
            self.status_label.setText("No data to display.")
            return

        lat, lon = filtered_df.iloc[0]['LATIuke'], filtered_df.iloc[0]['LONGuke']
        map_ = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker([lat, lon], tooltip='Location').add_to(map_)

        operator_colors = {
            'T-Mobile': 'pink',
            'Orange': 'orange',
            'Play': 'violet',
        }

        filtered_df = filtered_df[filtered_df['siec_id'].isin(operator_colors.keys())]

        grouped = filtered_df.groupby(['LATIuke', 'LONGuke'])

        for (lat, lon), group in grouped:
            operators = group['siec_id'].unique()
            if len(operators) > 1:
                colors = [operator_colors[op] for op in operators if op in operator_colors]
                html = self.create_multi_color_marker(colors)
            else:
                operator = operators[0]
                color = operator_colors.get(operator, 'blue')
                html = f'<div style="width: 20px; height: 20px; background-color: {color}; border-radius: 50%; border: 2px solid #000;"></div>'
            
            icon = folium.DivIcon(html=html)
            folium.Marker([lat, lon], icon=icon).add_to(map_)

        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())
        self.progress_bar.setValue(0)  # Reset the progress bar for the next use
        self.status_label.setText("")

    def create_multi_color_marker(self, colors):
        color_width = 100 / len(colors)
        color_blocks = ''.join([f'<div style="width: {color_width}%; height: 100%; background-color: {color};"></div>' for color in colors])
        html = f'<div style="width: 30px; height: 30px; display: flex; border-radius: 50%; border: 2px solid #000;">{color_blocks}</div>'
        return html

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())