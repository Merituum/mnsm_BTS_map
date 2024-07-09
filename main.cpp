#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <exception>

// Funkcja do konwersji DMS na dziesiętne
double dms_to_decimal(const std::string& dms, char direction) {
    try {
        // Upewnijmy się, że dms ma odpowiednią długość
        if (dms.length() < 6) {
            throw std::invalid_argument("Invalid DMS format");
        }

        // Parsowanie wartości DMS
        int degrees = std::stoi(dms.substr(0, 2));
        int minutes = std::stoi(dms.substr(2, 2));
        int seconds = std::stoi(dms.substr(4, 2));

        double decimal = degrees + minutes / 60.0 + seconds / 3600.0;

        // Ustawienie odpowiedniego znaku współrzędnych
        if (direction == 'S' || direction == 'W') {
            decimal = -decimal;
        }

        return decimal;
    }
    catch (const std::exception& e) {
        std::cerr << "Error converting DMS to decimal: " << e.what() << " for DMS: " << dms << std::endl;
        return 0.0; // Return a default value or handle the error as needed
    }
}

// Funkcja do przetwarzania pliku CSV
void process_csv(const std::string& input_file, const std::string& output_file) {
    std::ifstream infile;
    std::ofstream outfile;

    try {
        infile.open(input_file);
        if (!infile.is_open()) {
            throw std::ios_base::failure("Failed to open input file");
        }

        outfile.open(output_file);
        if (!outfile.is_open()) {
            throw std::ios_base::failure("Failed to open output file");
        }

        std::string line;

        // Nagłówki pliku
        if (std::getline(infile, line)) {
            outfile << line << "\n";
        }

        // Przetwarzanie linii
        while (std::getline(infile, line)) {
            try {
                std::stringstream ss(line);
                std::vector<std::string> tokens;
                std::string token;

                while (std::getline(ss, token, ';')) {
                    tokens.push_back(token);
                }

                if (tokens.size() < 27) {
                    throw std::runtime_error("Invalid line format");
                }

                // Konwersja współrzędnych
                std::string long_dms = tokens[24]; // 25. kolumna LONGuke
                std::string lat_dms = tokens[25];  // 26. kolumna LATIuke

                // Upewniamy się, że przetwarzamy współrzędne zgodnie z formatem
                char long_direction = long_dms[2];
                char lat_direction = lat_dms[2];
                long_dms.erase(2, 1); // Usunięcie litery oznaczającej kierunek
                lat_dms.erase(2, 1); // Usunięcie litery oznaczającej kierunek

                double longitude = dms_to_decimal(long_dms, long_direction);
                double latitude = dms_to_decimal(lat_dms, lat_direction);

                // Zamiana współrzędnych w wektorze
                tokens[24] = std::to_string(longitude);
                tokens[25] = std::to_string(latitude);

                // Zapis zmodyfikowanej linii do pliku wyjściowego
                for (size_t i = 0; i < tokens.size(); ++i) {
                    outfile << tokens[i];
                    if (i != tokens.size() - 1) {
                        outfile << ";";
                    }
                }
                outfile << "\n";
            }
            catch (const std::exception& e) {
                std::cerr << "Error processing line: " << e.what() << std::endl;
                continue; // Skip this line and proceed to the next one
            }
        }

    }
    catch (const std::ios_base::failure& e) {
        std::cerr << "File error: " << e.what() << std::endl;
    }
    catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }

    infile.close();
    outfile.close();
}

int main() {
    std::string input_file = "btsearch.csv";
    std::string output_file = "output.csv";

    process_csv(input_file, output_file);

    std::cout << "Konwersja zakończona. Wynik zapisano do " << output_file << std::endl;

    return 0;
}
