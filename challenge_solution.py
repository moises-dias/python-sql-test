import sqlite3
import json

def load_json_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def validate_json_structure(data):
    if not isinstance(data, list):
        return False

    for record in data:
        if not isinstance(record, dict) or set(record.keys()) != {"year", "country", "airports"}:
            return False

        if not isinstance(record["year"], int) or not isinstance(record["country"], str):
            return False

        if not isinstance(record["airports"], list):
            return False

        for airport in record["airports"]:
            if set(airport.keys()) != {"iata_code", "icao_code", "total_passengers"}:
                return False

            if not isinstance(airport["iata_code"], str) or \
               not isinstance(airport["icao_code"], str) or \
               not isinstance(airport["total_passengers"], str):
                return False

            try:
                total_passengers = int(airport["total_passengers"])
                if total_passengers < 0:
                    return False
            except ValueError:
                return False

    return True

def create_tables(cursor):
    cursor.execute('''CREATE TABLE DimYear (YearID INTEGER PRIMARY KEY AUTOINCREMENT, Year INTEGER UNIQUE)''')
    cursor.execute('''CREATE TABLE DimCountry (CountryID INTEGER PRIMARY KEY AUTOINCREMENT, CountryName TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE DimAirport (AirportID INTEGER PRIMARY KEY AUTOINCREMENT, IATACode TEXT, ICAOCode TEXT, CountryID INTEGER, UNIQUE(IATACode, ICAOCode), FOREIGN KEY(CountryID) REFERENCES DimCountry(CountryID))''')
    cursor.execute('''CREATE TABLE FactAirTraffic (YearID INTEGER, AirportID INTEGER, TotalPassengers INTEGER, FOREIGN KEY(YearID) REFERENCES DimYear(YearID), FOREIGN KEY(AirportID) REFERENCES DimAirport(AirportID))''')

def batch_insert(cursor, table, columns, values):
    placeholder = '(' + ', '.join(['?' for _ in columns.split(',')]) + ')'
    placeholders = ', '.join([placeholder for _ in values])
    query = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES {placeholders}"

    if all(isinstance(item, tuple) for item in values):
        values = [item for sublist in values for item in sublist]
    cursor.execute(query, values)

def get_id_mapping(cursor, table, columns, values):
    placeholder = '(' + ', '.join(['?' for _ in columns.split(',')]) + ')'
    placeholders = ', '.join([placeholder for _ in values])
    query = f"SELECT {columns}, rowid FROM {table} WHERE ({columns}) IN ({placeholders})"

    if all(isinstance(item, tuple) for item in values):
        values = [item for sublist in values for item in sublist]
        cursor.execute(query, values)
        return {(row[0], row[1]): row[2] for row in cursor.fetchall()}
    else:
        cursor.execute(query, values)
        return {row[0]: row[1] for row in cursor.fetchall()}

def extract_data_from_json(data):
    years = set()
    countries = set()
    airports = set()
    fact_data = []

    for record in data:
        year = record['year']
        country = record['country']
        years.add(year)
        countries.add(country)

        for airport in record['airports']:
            iata_code = airport['iata_code']
            icao_code = airport['icao_code']
            total_passengers = int(airport['total_passengers'])
            airports.add((iata_code, icao_code, country))
            fact_data.append((year, iata_code, icao_code, total_passengers))
    
    extracted_data = {
        'years': list(years),
        'countries': list(countries),
        'airports': list(airports),
        'fact_data': list(fact_data)
    }

    return extracted_data

def populate_tables(cursor, data):
    extracted_data = extract_data_from_json(data)

    batch_insert(cursor, 'DimYear', 'Year', extracted_data['years'])
    year_ids = get_id_mapping(cursor, 'DimYear', 'Year', extracted_data['years'])
    
    batch_insert(cursor, 'DimCountry', 'CountryName', extracted_data['countries'])
    country_ids = get_id_mapping(cursor, 'DimCountry', 'CountryName', extracted_data['countries'])

    airport_records = [(iata, icao, country_ids[country]) for iata, icao, country in extracted_data['airports']]
    batch_insert(cursor, 'DimAirport', 'IATACode, ICAOCode, CountryID', airport_records)
    airport_keys = [(iata, icao) for iata, icao, country in extracted_data['airports']]
    airport_ids = get_id_mapping(cursor, 'DimAirport', 'IATACode, ICAOCode', airport_keys)

    fact_records = [(year_ids[year], airport_ids[(iata, icao)], passengers) for year, iata, icao, passengers in extracted_data['fact_data']]
    batch_insert(cursor, 'FactAirTraffic', 'YearID, AirportID, TotalPassengers', fact_records)

def query_total_passengers_per_country(cursor):
    query = '''
        SELECT c.CountryName, SUM(f.TotalPassengers) AS TotalPassengers
        FROM FactAirTraffic f
        INNER JOIN DimAirport a ON f.AirportID = a.AirportID
        INNER JOIN DimCountry c ON a.CountryID = c.CountryID
        GROUP BY c.CountryName
    '''
    cursor.execute(query)
    results =  cursor.fetchall()

    for result in results:
        print(result)

def main(file_paths):
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    create_tables(cursor)

    for file_path in file_paths:
        data = load_json_data(file_path)

        if not validate_json_structure(data):
            raise Exception("JSON structure is invalid.")

        populate_tables(cursor, data)

    query_total_passengers_per_country(cursor)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    file_paths = ['data.json']

    # The code can handle multiples json files.
    # Uncommenting the line below will produce the same result.
    # file_paths = ['data_part_1.json', 'data_part_2.json']
    main(file_paths)