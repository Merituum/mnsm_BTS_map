import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
import pandas as pd
import io

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
        # Load data from Excel file
        try:
            df = pd.read_excel('nadajniki/5g3600_-_stan_na_2024-06-25.xlsx')
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            return

        # Create folium map centered on Poland
        map_ = folium.Map(location=[52.237049, 21.017532], zoom_start=6)

        # Add markers for each transmitter
        for index, row in df.iterrows():
            operator = row['Nazwa operatora']
            lat = row['Dł geogr stacji']
            lon = row['Lokalizacja']
            station_id = row['IdStacji']

            # Create HTML content for tooltip
            tooltip_html = f"<b>Operator:</b> {operator}<br><b>Station ID:</b> {station_id}"

            # Add marker to the map
            folium.Marker([lat, lon], tooltip=tooltip_html).add_to(map_)

        # Save map to bytes and display in QWebEngineView
        data = io.BytesIO()
        map_.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
