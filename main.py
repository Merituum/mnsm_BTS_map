import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QProgressBar
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QThread, pyqtSignal
import folium
import pandas as pd
import io
import requests
from geopy.distance import geodesic

OPENCAGE_API_KEY = '329efb3e6b1d4291b7559e2409deb4d4'
RADIUS_KM = 10  # Radius to filter transmitters

class Worker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(pd.DataFrame)
    
    def __init__(self, location):
        super().__init__()
        self.location = location

    def run(self):
        try:
            df = pd.read_csv('test_lomza.csv', delimiter=';', usecols=['siec_id', 'LONGuke', 'LATIuke', 'StationId'])

            # df = pd.read_csv('output.csv', delimiter=';', usecols=['siec_id', 'LONGuke', 'LATIuke', 'StationId'])
            # Filter data to include only transmitters within a certain radius
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
            self.progress.emit(int((i / total) * 100))
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
        
        self.show_map_button = QPushButton("Show Map", self)
        self.show_map_button.clicked.connect(self.show_map)
        self.layout.addWidget(self.show_map_button)
        
        self.map_view = QWebEngineView(self)
        self.layout.addWidget(self.map_view)

        self.progress_bar = QProgressBar(self)
        self.layout.addWidget(self.progress_bar)

    def show_map(self):
        address = self.address_input.text()
        if address:
            location = self.get_location_from_address(address)
            if location:
                self.start_worker(location)
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

    def start_worker(self, location):
        self.worker = Worker(location)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.display_map)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_map(self, filtered_df):
        self.progress_bar.setValue(100)  # Ensure the progress bar is full

        if filtered_df.empty:
            print("No data to display.")
            return

        lat, lon = filtered_df.iloc[0]['LATIuke'], filtered_df.iloc[0]['LONGuke']
        map_ = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker([lat, lon], tooltip='Location').add_to(map_)

        operator_colors = {
            'T-Mobile': 'pink',
            'Orange': 'orange',
            'Play': 'violet',
        }

        # Filter out operators other than Orange, Play, and T-Mobile
        filtered_df = filtered_df[filtered_df['siec_id'].isin(operator_colors.keys())]

        # Group by coordinates and create multi-colored markers
        grouped = filtered_df.groupby(['LATIuke', 'LONGuke'])

        for (lat, lon), group in grouped:
            operators = group['siec_id'].unique()
            if len(operators) > 1:
                # Create a multi-color marker
                colors = [operator_colors[op] for op in operators if op in operator_colors]
                html = self.create_multi_color_marker(colors)
            else:
                operator = operators[0]
                color = operator_colors.get(operator, 'blue')
                html = f'<div style="width: 20px; height: 20px; background-color: {color}; border-radius: 50%; border: 2px solid #000;"></div>'
            
            icon = folium.DivIcon(html=html)
            folium.Marker([lat, lon], icon=icon).add_to(map_)

        # Save map with transmitters and display in QWebEngineView
        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())
        self.progress_bar.setValue(0)  # Reset the progress bar for the next use

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
