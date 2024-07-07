#include <iostream>
#include <fstream>
#include <string>
#include <sstream>

using namespace std;

// Funkcja do zamiany współrzędnych
string zamienWspolrzedne(string wsp) {
    string noweWsp = wsp;
    
    // Zamiana "N" i "S"
    size_t poz = noweWsp.find("N");
    if (poz != string::npos) {
        noweWsp.replace(poz, 1, "");
    }
    poz = noweWsp.find("S");
    if (poz != string::npos) {
        noweWsp.replace(poz, 1, "-");
    }
    
    // Zamiana "E" i "W"
    poz = noweWsp.find("E");
    if (poz != string::npos) {
        noweWsp.replace(poz, 1, "");
    }
    poz = noweWsp.find("W");
    if (poz != string::npos) {
        noweWsp.replace(poz, 1, "-");
    }
    
    return noweWsp;
}

int main() {
    ifstream plik("test.csv"); // Załóżmy, że dane są w pliku CSV
    ofstream plikWyj("baza_nadajnikow_zaktualizowane.csv");
    
    if (!plik || !plikWyj) {
        cerr << "Nie można otworzyć pliku!" << endl;
        return 1;
    }
    
    string linia;
    bool pierwszaLinia = true; // Zmienna do pominięcia nagłówka
    
    while (getline(plik, linia)) {
        if (pierwszaLinia) {
            plikWyj << linia << endl; // Zapisz nagłówek do pliku wynikowego
            pierwszaLinia = false;
            continue;
        }
        
        istringstream ss(linia);
        string pole;
        string nowaLinia;
        bool pierwszePole = true;
        
        while (getline(ss, pole, ';')) {
            if (!pierwszePole) {
                nowaLinia += ';';
            }
            
            if (pole.find("N") != string::npos || pole.find("S") != string::npos ||
                pole.find("E") != string::npos || pole.find("W") != string::npos) {
                // Jeśli pole zawiera N, S, E, W, to zamień współrzędne
                nowaLinia += zamienWspolrzedne(pole);
            } else {
                nowaLinia += pole;
            }
            
            pierwszePole = false;
        }
        
        plikWyj << nowaLinia << endl;
    }
    
    plik.close();
    plikWyj.close();
    
    cout << "Konwersja zakończona pomyslnie!" << endl;
    
    return 0;
}
