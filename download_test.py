# import requests
# import json
# import os
# from urllib.parse import urlencode
# import logging
# import concurrent.futures

# # Konfiguracja logowania
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# def get_base_station_info(base_station_id):
#     """
#     Pobiera informacje o nadajniku na podstawie jego ID.
#     """
#     url = f"https://si2pem.gov.pl/api/public/base_station?search={base_station_id}"
#     try:
#         response = requests.get(url)
#         response.raise_for_status()
#         data = response.json()
#         if isinstance(data, list) and len(data) > 0:
#             return data[0]
#         else:
#             logging.error(f"Nie znaleziono nadajnika o ID: {base_station_id}")
#             return None
#     except requests.exceptions.RequestException as e:
#         logging.error(f"Błąd podczas pobierania informacji o nadajniku: {e}")
#         return None

# def construct_wfs_getfeature_url(bbox, feature_type='public:measures_all', output_format='application/json'):
#     """
#     Konstrukcja URL do zapytania WFS GetFeature z filtrem BBOX.
#     """
#     base_url = "https://si2pem.gov.pl/geoserver/public/wfs"
#     params = {
#         'service': 'WFS',
#         'version': '1.0.0',
#         'request': 'GetFeature',
#         'typeName': feature_type,
#         'outputFormat': output_format,
#         'bbox': f"{bbox[2]},{bbox[0]},{bbox[3]},{bbox[1]},EPSG:4326"  # minx,miny,maxx,maxy,CRS
#     }
#     query_string = urlencode(params)
#     return f"{base_url}?{query_string}"

# def get_feature_data(wfs_url):
#     """
#     Wysyła zapytanie WFS GetFeature i zwraca dane GeoJSON.
#     """
#     try:
#         response = requests.get(wfs_url)
#         response.raise_for_status()
#         data = response.json()
#         return data
#     except requests.exceptions.RequestException as e:
#         logging.error(f"Błąd podczas pobierania danych WFS: {e}")
#         return None

# def extract_pdf_urls(geojson_data):
#     """
#     Ekstrahuje URL-e do PDF z danych GeoJSON.
#     Zakładam, że URL do PDF znajduje się w polu 'url' w properties.
#     """
#     pdf_urls = set()
#     features = geojson_data.get('features', [])
#     for feature in features:
#         properties = feature.get('properties', {})
#         # Debugging: Wyświetl właściwości, aby zidentyfikować klucz z URL do PDF
#         # print(json.dumps(properties, indent=4, ensure_ascii=False))  # Odkomentuj dla debugowania
#         pdf_url = properties.get('url')  # Dostosuj, jeśli URL jest w innym polu
#         if pdf_url:
#             pdf_urls.add(pdf_url)
#     return pdf_urls

# def download_pdf(pdf_url, save_directory='pdfs'):
#     """
#     Pobiera plik PDF z podanego URL i zapisuje go w określonym katalogu.
#     """
#     try:
#         response = requests.get(pdf_url)
#         response.raise_for_status()
#         filename = pdf_url.split('/')[-1]
#         save_path = os.path.join(save_directory, filename)
#         with open(save_path, 'wb') as f:
#             f.write(response.content)
#         logging.info(f"PDF zapisany jako: {save_path}")
#     except requests.exceptions.RequestException as e:
#         logging.error(f"Błąd podczas pobierania PDF z {pdf_url}: {e}")

# def process_feature_type(bbox, feature_type):
#     """
#     Przetwarza jedną warstwę WFS GetFeature, zwraca zebrane URL-e do PDF.
#     """
#     wfs_url = construct_wfs_getfeature_url(bbox, feature_type=feature_type)
#     logging.info(f"Wysyłanie zapytania WFS GetFeature dla warstwy '{feature_type}': {wfs_url}")
    
#     geojson_data = get_feature_data(wfs_url)
#     if not geojson_data:
#         logging.error(f"Nie udało się pobrać danych dla warstwy '{feature_type}'.")
#         return set()
    
#     pdf_urls = extract_pdf_urls(geojson_data)
#     if pdf_urls:
#         logging.info(f"Znaleziono {len(pdf_urls)} PDF-ów w warstwie '{feature_type}'.")
#     else:
#         logging.info(f"Nie znaleziono PDF-ów w warstwie '{feature_type}'.")
    
#     return pdf_urls

# def main():
#     base_station_id = input("Podaj ID nadajnika: ").strip()
    
#     # Krok 1: Pobierz informacje o nadajniku
#     base_station = get_base_station_info(base_station_id)
#     if not base_station:
#         return
    
#     # Pobierz bounding box
#     bbox = base_station.get('boundingbox', [])
#     if len(bbox) != 4:
#         logging.error("Nieprawidłowy bounding box.")
#         return
#     min_lat, max_lat, min_lon, max_lon = bbox
#     logging.info(f"Bounding box: {bbox}")
    
#     # Lista warstw do przeszukania
#     feature_types = [
#         'public:measures_all',
#         'public:measures_14_21',
#         'public:measures_21_28',
#         'public:measures_28',
#         'public:measures_7',
#         'public:measures_7_14'
#     ]
    
#     all_pdf_urls = set()
    
#     # Krok 2: Iteruj przez warstwy i zbieraj PDF URL
#     for feature_type in feature_types:
#         pdf_urls = process_feature_type(bbox, feature_type)
#         all_pdf_urls.update(pdf_urls)
    
#     if not all_pdf_urls:
#         logging.info("Nie znaleziono żadnych PDF-ów dla tego nadajnika.")
#         return
    
#     logging.info(f"Łączna liczba unikalnych PDF-ów: {len(all_pdf_urls)}")
    
#     # Krok 3: Pobierz wszystkie PDF-y równolegle
#     os.makedirs("pdfs", exist_ok=True)
#     with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#         futures = [executor.submit(download_pdf, url) for url in all_pdf_urls]
#         concurrent.futures.wait(futures)
    
#     logging.info("Wszystkie PDF-y zostały pobrane.")

# if __name__ == "__main__":
#     main()
import requests
import json
import os
from urllib.parse import urlencode
import logging
import concurrent.futures
from PyPDF2 import PdfReader
import csv

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_base_station_info(base_station_id):
    """
    Pobiera informacje o nadajniku na podstawie jego ID.
    """
    url = f"https://si2pem.gov.pl/api/public/base_station?search={base_station_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        else:
            logging.error(f"Nie znaleziono nadajnika o ID: {base_station_id}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Błąd podczas pobierania informacji o nadajniku: {e}")
        return None

def construct_wfs_getfeature_url(bbox, feature_type='public:measures_all', output_format='application/json'):
    """
    Konstrukcja URL do zapytania WFS GetFeature z filtrem BBOX.
    """
    base_url = "https://si2pem.gov.pl/geoserver/public/wfs"
    params = {
        'service': 'WFS',
        'version': '1.0.0',
        'request': 'GetFeature',
        'typeName': feature_type,
        'outputFormat': output_format,
        'bbox': f"{bbox[2]},{bbox[0]},{bbox[3]},{bbox[1]},EPSG:4326"  # minx,miny,maxx,maxy,CRS
    }
    query_string = urlencode(params)
    return f"{base_url}?{query_string}"

def get_feature_data(wfs_url):
    """
    Wysyła zapytanie WFS GetFeature i zwraca dane GeoJSON.
    """
    try:
        response = requests.get(wfs_url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Błąd podczas pobierania danych WFS: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Błąd dekodowania JSON: {e}")
        return None

def extract_pdf_urls(geojson_data):
    """
    Ekstrahuje URL-e do PDF z danych GeoJSON.
    Zakładam, że URL do PDF znajduje się w polu 'url' w properties.
    """
    pdf_urls = set()
    features = geojson_data.get('features', [])
    for feature in features:
        properties = feature.get('properties', {})
        # Debugging: Wyświetl właściwości, aby zidentyfikować klucz z URL do PDF
        # print(json.dumps(properties, indent=4, ensure_ascii=False))  # Odkomentuj dla debugowania
        pdf_url = properties.get('url')  # Dostosuj, jeśli URL jest w innym polu
        if pdf_url:
            pdf_urls.add(pdf_url)
    return pdf_urls

def download_pdf(pdf_url, save_directory='pdfs'):
    """
    Pobiera plik PDF z podanego URL i zapisuje go w określonym katalogu.
    """
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
        filename = pdf_url.split('/')[-1]
        save_path = os.path.join(save_directory, filename)
        with open(save_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"PDF zapisany jako: {save_path}")
        return save_path  # Return the path for further processing
    except requests.exceptions.RequestException as e:
        logging.error(f"Błąd podczas pobierania PDF z {pdf_url}: {e}")
        return None

def extract_information_from_pdf(pdf_path, expected_station_id):
    """
    Ekstrahuje informacje o azymutach z pliku PDF.
    Zakłada, że na pierwszej stronie znajduje się ID stacji,
    a azymuty są wymienione w określonym formacie.
    """
    try:
        reader = PdfReader(pdf_path)
        first_page = reader.pages[0]
        text = first_page.extract_text()
        if not text:
            logging.error(f"Brak tekstu w PDF: {pdf_path}")
            return None

        # Sprawdź, czy ID stacji jest obecne
        if expected_station_id not in text:
            logging.error(f"ID stacji {expected_station_id} nie znaleziono w PDF: {pdf_path}")
            return None

        # Przykładowa metoda ekstrakcji azymutów
        # Zakładam, że azymuty są zapisane w formacie "Azymut: <wartość>"
        # Możesz dostosować poniższy kod do rzeczywistego formatu PDF
        azimuths = []
        lines = text.split('\n')
        for line in lines:
            if 'Azymut' in line:
                parts = line.split(':')
                if len(parts) == 2:
                    azimuth_value = parts[1].strip()
                    azimuths.append(azimuth_value)

        if not azimuths:
            logging.warning(f"Nie znaleziono azymutów w PDF: {pdf_path}")
            return {
                'Station ID': expected_station_id,
                'PDF File': os.path.basename(pdf_path),
                'Azymuts': 'Nie znaleziono azymutów'
            }

        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': azimuths
        }

    except Exception as e:
        logging.error(f"Błąd podczas przetwarzania PDF {pdf_path}: {e}")
        return None

def process_feature_type(bbox, feature_type):
    """
    Przetwarza jedną warstwę WFS GetFeature, zwraca zebrane URL-e do PDF.
    """
    wfs_url = construct_wfs_getfeature_url(bbox, feature_type=feature_type)
    logging.info(f"Wysyłanie zapytania WFS GetFeature dla warstwy '{feature_type}': {wfs_url}")
    
    geojson_data = get_feature_data(wfs_url)
    if not geojson_data:
        logging.error(f"Nie udało się pobrać danych dla warstwy '{feature_type}'.")
        return set()
    
    pdf_urls = extract_pdf_urls(geojson_data)
    if pdf_urls:
        logging.info(f"Znaleziono {len(pdf_urls)} PDF-ów w warstwie '{feature_type}'.")
    else:
        logging.info(f"Nie znaleziono PDF-ów w warstwie '{feature_type}'.")
    
    return pdf_urls

def export_to_csv(data, filename='antenna_data.csv'):
    """
    Eksportuje wyekstrahowane dane do pliku CSV.
    
    Args:
        data (list): Lista słowników zawierających wyekstrahowane informacje.
        filename (str): Nazwa pliku CSV.
    """
    if not data:
        logging.info("Brak danych do eksportu.")
        return

    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Station ID', 'PDF File', 'Azymuts'])
        for entry in data:
            azimuths = ', '.join(entry['Azymuts']) if isinstance(entry['Azymuts'], list) else entry['Azymuts']
            writer.writerow([entry['Station ID'], entry['PDF File'], azimuths])
    logging.info(f"\nDane zostały wyeksportowane do {filename}")

def main():
    base_station_id = input("Podaj ID nadajnika: ").strip()
    
    if not base_station_id:
        logging.error("ID nadajnika nie może być puste.")
        return
    
    # Krok 1: Pobierz informacje o nadajniku
    base_station = get_base_station_info(base_station_id)
    if not base_station:
        return
    
    # Pobierz bounding box
    bbox = base_station.get('boundingbox', [])
    if len(bbox) != 4:
        logging.error("Nieprawidłowy bounding box.")
        return
    min_lat, max_lat, min_lon, max_lon = bbox
    logging.info(f"Bounding box: {bbox}")
    
    # Lista warstw do przeszukania
    feature_types = [
        'public:measures_all',
        'public:measures_14_21',
        'public:measures_21_28',
        'public:measures_28',
        'public:measures_7',
        'public:measures_7_14'
    ]
    
    all_pdf_urls = set()
    
    # Krok 2: Iteruj przez warstwy i zbieraj PDF URL
    for feature_type in feature_types:
        pdf_urls = process_feature_type(bbox, feature_type)
        all_pdf_urls.update(pdf_urls)
    
    if not all_pdf_urls:
        logging.info("Nie znaleziono żadnych PDF-ów dla tego nadajnika.")
        return
    
    logging.info(f"Łączna liczba unikalnych PDF-ów: {len(all_pdf_urls)}")
    
    # Krok 3: Pobierz wszystkie PDF-y równolegle
    os.makedirs("pdfs", exist_ok=True)
    downloaded_pdfs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(download_pdf, url): url for url in all_pdf_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            pdf_path = future.result()
            if pdf_path:
                downloaded_pdfs.append(pdf_path)
    
    if not downloaded_pdfs:
        logging.info("Żaden PDF nie został pomyślnie pobrany.")
        return
    
    # Krok 4: Ekstrahuj informacje z PDF-ów
    extracted_data = []
    for pdf_path in downloaded_pdfs:
        info = extract_information_from_pdf(pdf_path, base_station_id)
        if info:
            extracted_data.append(info)
    
    if not extracted_data:
        logging.info("Nie udało się wyekstrahować żadnych informacji z PDF-ów.")
        return
    
    # Wyświetl wyekstrahowane informacje
    logging.info("\n=== Wyekstrahowane Informacje z PDF-ów ===")
    for entry in extracted_data:
        print(f"\nStation ID: {entry['Station ID']}")
        print(f"PDF File: {entry['PDF File']}")
        print("Azymuts:")
        if isinstance(entry['Azymuts'], list):
            for az in entry['Azymuts']:
                print(f"  - {az}")
        else:
            print(f"  {entry['Azymuts']}")
    
    # Krok 5: Eksportuj dane do pliku CSV
    export_to_csv(extracted_data)

    logging.info("Wszystkie operacje zostały zakończone.")

if __name__ == "__main__":
    main()
