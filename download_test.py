import requests
import json
import os
from urllib.parse import urlencode
import logging
import concurrent.futures
import pdfplumber
import re
import csv

# Konfiguracja logowania
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Lista możliwych nagłówków kolumn zawierających azymuty
AZIMUTH_HEADERS = [
    'Azymut H', 'Azimuth H', 'Kierunek H', 'Direction H',
    'Azymut', 'Azimuth', 'Kierunek', 'Direction'
]

def get_base_station_info(base_station_id):
    """
    Pobiera informacje o nadajniku na podstawie jego ID.
    """
    url = f"https://si2pem.gov.pl/api/public/base_station?search={base_station_id}"
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Błąd HTTP {response.status_code} podczas pobierania informacji o nadajniku.")
        return None
    data = response.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    else:
        logging.error(f"Nie znaleziono nadajnika o ID: {base_station_id}")
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
    response = requests.get(wfs_url)
    if response.status_code != 200:
        logging.error(f"Błąd HTTP {response.status_code} podczas pobierania danych WFS.")
        return None
    try:
        data = response.json()
        return data
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
        # Możliwe, że URL do PDF znajduje się pod innym kluczem
        pdf_url = properties.get('url') or properties.get('pdf_url') or properties.get('PDF_URL')
        if pdf_url:
            pdf_urls.add(pdf_url)
    return pdf_urls

def download_pdf(pdf_url, save_directory='pdfs'):
    """
    Pobiera plik PDF z podanego URL i zapisuje go w określonym katalogu.
    """
    response = requests.get(pdf_url)
    if response.status_code != 200:
        logging.error(f"Błąd HTTP {response.status_code} podczas pobierania PDF z {pdf_url}.")
        return None
    filename = pdf_url.split('/')[-1]
    save_path = os.path.join(save_directory, filename)
    os.makedirs(save_directory, exist_ok=True)
    with open(save_path, 'wb') as f:
        f.write(response.content)
    logging.info(f"PDF zapisany jako: {save_path}")
    return save_path  # Return the path for further processing

def extract_information_from_pdf(pdf_path, expected_station_id):
    """
    Ekstrahuje informacje o azymutach z pliku PDF.
    Zakłada, że tabela z azymutami znajduje się na trzeciej stronie PDF-a.
    """
    if not os.path.exists(pdf_path):
        logging.error(f"Plik PDF {pdf_path} nie istnieje.")
        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': 'Plik nie istnieje'
        }

    pdf = pdfplumber.open(pdf_path)
    
    # Sprawdź, czy PDF ma co najmniej 3 strony
    if len(pdf.pages) < 3:
        logging.warning(f"PDF {pdf_path} ma mniej niż 3 strony.")
        pdf.close()
        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': 'Nie znaleziono tabel'
        }

    # Przetwarzaj tylko trzecią stronę
    page_number = 3
    page = pdf.pages[2]  # Indeksowanie od 0
    text = page.extract_text()
    if not text:
        logging.error(f"Brak tekstu na stronie {page_number} w PDF: {pdf_path}")
        pdf.close()
        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': 'Brak tekstu'
        }

    # Zapisz wyciągnięty tekst do pliku dla debugowania
    text_save_path = os.path.join('extracted_texts', f"{os.path.basename(pdf_path)}_page_{page_number}.txt")
    os.makedirs('extracted_texts', exist_ok=True)
    with open(text_save_path, 'w', encoding='utf-8') as f:
        f.write(text)
    logging.debug(f"Zapisano wyciągnięty tekst ze strony {page_number} w PDF: {pdf_path} do {text_save_path}")

    # Sprawdź, czy ID stacji jest obecne na trzeciej stronie
    if expected_station_id not in text:
        logging.error(f"ID stacji {expected_station_id} nie znaleziono na trzeciej stronie PDF: {pdf_path}")
        pdf.close()
        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': 'ID stacji nie znaleziono'
        }

    # Ekstrakcja tabeli
    tables = page.extract_tables()
    if not tables:
        logging.warning(f"Nie znaleziono tabel na stronie {page_number} w PDF: {pdf_path}")
        pdf.close()
        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': 'Nie znaleziono tabel'
        }

    # Zakładam, że interesująca tabela jest pierwszą tabelą na stronie
    table = tables[0]
    headers = table[0]
    normalized_headers = [header.strip().lower() if header else '' for header in headers]
    azimuth_col_indices = [
        i for i, header in enumerate(normalized_headers)
        if any(re.search(r'\b{}\b'.format(re.escape(h.lower())), header) for h in AZIMUTH_HEADERS)
    ]

    if not azimuth_col_indices:
        logging.warning(f"Nie znaleziono kolumny z azymutami w tabeli na stronie {page_number} w PDF: {pdf_path}")
        pdf.close()
        return {
            'Station ID': expected_station_id,
            'PDF File': os.path.basename(pdf_path),
            'Azymuts': 'Nie znaleziono kolumny z azymutami'
        }

    logging.debug(f"Znalezione nagłówki tabeli: {headers}")
    logging.debug(f"Indeksy kolumn z azymutami: {azimuth_col_indices}")

    azimuths = []
    for row in table[1:]:  # Pomijam nagłówki
        for index in azimuth_col_indices:
            if index < len(row):
                azimuth_value = row[index].strip() if row[index] else ''
                if azimuth_value:
                    # Walidacja formatu azymutu (np. 180°)
                    match = re.match(r'(\d{1,3})\s*°', azimuth_value)
                    if match:
                        az_value = int(match.group(1))
                        if 0 <= az_value <= 360:
                            azimuths.append(str(az_value) + '°')
                        else:
                            logging.warning(f"Niewłaściwa wartość azymutu: {azimuth_value} w PDF: {pdf_path}")
                    else:
                        azimuths.append(azimuth_value)  # Zachowaj oryginalną wartość, jeśli nie pasuje

    pdf.close()

    if not azimuths:
        logging.warning(f"Nie znaleziono azymutów w tabeli PDF: {pdf_path}")
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
