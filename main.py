import sys
import csv
import io
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QPushButton
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
from opencage.geocoder import OpenCageGeocode

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 800, 600)

        # User input field
        self.location_input = QLineEdit(self)
        self.location_input.move(10, 10)
        self.location_input.resize(200, 40)

        # Search button
        self.search_button = QPushButton('Search', self)
        self.search_button.move(220, 10)
        self.search_button.clicked.connect(self.find_and_display_stations)

        # Map view
        self.map_view = QWebEngineView(self)
        self.map_view.move(10, 60)
        self.map_view.resize(780, 530)

    def find_and_display_stations(self):
        user_location = self.location_input.text()
        
        # Initialize OpenCageGeocode with your API key
        key = '329efb3e6b1d4291b7559e2409deb4d4'
        geocoder = OpenCageGeocode(key)
        
        # Geocode user input to get latitude and longitude
        result = geocoder.geocode(user_location, no_annotations='1')
        if result and len(result):
            lat = result[0]['geometry']['lat']
            lon = result[0]['geometry']['lng']
            map_ = folium.Map(location=[lat, lon], zoom_start=12)
        else:
            # Default to a global view if geocoding fails
            map_ = folium.Map(location=[20, 0], zoom_start=2)
        
        with open('baza.csv', mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            for row in reader:
                if row['miejscowosc'].lower() == user_location.lower():
                    # station_lat, station_lon = float(row['LATIuke']), float(row['LONGuke'])
                    station_lat, station_lon = self.convert_to_decimal_degrees(row['LATIuke']), self.convert_to_decimal_degrees(row['LONGuke'])
                    # Use a custom icon for the marker to make it a big red dot
                    folium.CircleMarker(
                        location=[station_lat, station_lon],
                        radius=9, # Adjust the size of the dot
                        color='red',
                        fill=True,
                        fill_color='red',
                        popup=row['miejscowosc']
                    ).add_to(map_)

        # Save map with transmitters and display in QWebEngineView
        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())
    # def convert_to_decimal_degrees(self,coord):
    #     if 'N' in coord:
    #         parts = coord.split('N')
    #         degrees = float(parts[0])
    #         decimal = float(parts[1]) / 10000
    #         return degrees + decimal
    #     elif 'W' in coord:
    #         parts = coord.split('W')
    #         degrees = float(parts[0])
    #         decimal = float(parts[1]) / 10000
    #         return -(degrees + decimal)
    #     else:
    #         # If the format does not match, return None or raise an error
    #         return None
    #     # Usage example:
    #     # Assuming row['LATIuke'] is '53N0944' and row['LONGuke'] is a similar format
    #     try:
    #         station_lat = convert_to_decimal_degrees(row['LATIuke'])
    #         station_lon = convert_to_decimal_degrees(row['LONGuke'])
    #     except ValueError:
    #         # Handle the error, e.g., by skipping this row or logging an error message
    #         print(f"Could not convert {row['LATIuke']} or {row['LONGuke']} to float.")
    def convert_to_decimal_degrees(self, coord):
        direction = coord[-1]  # Get the last character (direction)
        parts = coord[:-1].split('.')  # Split the coordinate into degrees and minutes without the direction
        degrees = float(parts[0])
        minutes = float(parts[1]) / 60 if len(parts) > 1 else 0  # Convert minutes to decimal if present

        # Convert to decimal degrees
        decimal_degrees = degrees + minutes

        # Adjust based on direction
        if direction in ['S', 'W']:
            decimal_degrees *= -1  # South and West are negative
        elif direction not in ['N', 'E']:
            raise ValueError(f"Unexpected coordinate direction: {direction}")

        return decimal_degrees

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())