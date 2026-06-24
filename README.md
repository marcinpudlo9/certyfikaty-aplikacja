# Generator certyfikatow - aplikacja webowa

Aplikacja webowa do generowania certyfikatow PDF z grafiki szablonu i listy uczestnikow z Excela.

## Funkcje

- upload grafiki certyfikatu: PNG/JPG lub pierwsza strona PDF,
- upload listy uczestnikow z Excela XLSX,
- upload wlasnej czcionki TTF/OTF,
- wybor kolumn z Excela dla imienia, nazwiska, NPWZ i dodatkowego pola,
- ustawianie pozycji tekstu X/Y, rozmiaru, koloru i wyrownania,
- podglad certyfikatu przed generowaniem,
- generowanie pojedynczych PDF oraz paczki ZIP,
- dziala lokalnie albo online na Streamlit Community Cloud.

## Uruchomienie lokalne

1. Zainstaluj Python 3.11 lub nowszy.
2. W folderze aplikacji uruchom:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Uruchomienie online

Wrzuć pliki do repozytorium GitHub i uruchom przez Streamlit Community Cloud.
Glowny plik aplikacji: `app.py`.

## Excel

Minimalne kolumny przykladowe:

| Imie | Nazwisko | NPWZ |
|---|---|---|
| Jan | Kowalski | 1234567 |
| Anna | Nowak | 7654321 |

Nazwy kolumn moga byc inne - wybierzesz je w aplikacji.
