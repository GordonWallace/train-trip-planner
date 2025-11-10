"""
Database initialization and management for the train trip planner.
"""
import sqlite3
import os
import csv
from pathlib import Path

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'train_routes.db')
SCHEDULES_DIR = os.path.join(os.path.dirname(__file__), 'schedules')

def init_database():
    """Initialize the database with schema and load data from CSV files."""
    # Always delete and recreate the database to get fresh data from CSVs
    db_path = DATABASE_PATH
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # Create routes table
    c.execute('''CREATE TABLE IF NOT EXISTS routes
                 (id INTEGER PRIMARY KEY,
                  route_number TEXT UNIQUE,
                  route_name TEXT,
                  origin_city TEXT,
                  destination_city TEXT,
                  departure_time TEXT,
                  arrival_time TEXT,
                  duration_hours INTEGER)''')
    
    # Create stops table (intermediate stops for each route)
    c.execute('''CREATE TABLE IF NOT EXISTS stops
                 (id INTEGER PRIMARY KEY,
                  route_id INTEGER,
                  stop_number INTEGER,
                  city_name TEXT,
                  stop_time TEXT,
                  FOREIGN KEY(route_id) REFERENCES routes(id))''')
    
    # Create cities table (all cities in the network)
    c.execute('''CREATE TABLE IF NOT EXISTS cities
                 (id INTEGER PRIMARY KEY,
                  name TEXT UNIQUE,
                  state TEXT)''')
    
    # Load all CSV files from the schedules directory
    print("📥 Loading schedules from CSV files...")
    load_schedules_from_csv(c)
    conn.commit()
    conn.close()


def reload_schedules():
    """Force reload all schedules from CSV files (deletes and recreates database)."""
    db_path = DATABASE_PATH
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  Deleted database: {db_path}")
    init_database()
    print("✓ Database reloaded with all CSV schedules")


def load_schedules_from_csv(cursor):
    """Load all CSV files from the schedules directory into the database."""
    schedules_path = Path(SCHEDULES_DIR)
    
    if not schedules_path.exists():
        print(f"Warning: Schedules directory not found at {SCHEDULES_DIR}")
        return
    
    csv_files = sorted(schedules_path.glob('*.csv'))
    
    if not csv_files:
        print(f"Warning: No CSV files found in {SCHEDULES_DIR}")
        return
    
    route_number = 1
    
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                # Read first row to get route name
                first_row = next(reader, None)
                if not first_row or not first_row[0]:
                    print(f"Warning: {csv_file.name} has no route name in cell A1")
                    continue
                
                # Get route name from first column of first row (ignore any extra columns)
                route_name = first_row[0].strip()
                
                # Read all stop rows
                stops = []
                for row in reader:
                    if not row:  # Skip empty rows
                        continue
                    
                    # Get city (first column) and time (second column)
                    city = row[0].strip() if len(row) > 0 else None
                    stop_time = row[1].strip() if len(row) > 1 else None
                    
                    # Only add if both city and time exist and are not empty
                    if city and stop_time:
                        # Normalize time format to HH:MM
                        # Handle times like "1:07" or "0:03" by padding with zero
                        time_parts = stop_time.split(':')
                        if len(time_parts) == 2:
                            try:
                                hour = int(time_parts[0])
                                minute = int(time_parts[1])
                                stop_time = f"{hour:02d}:{minute:02d}"
                            except (ValueError, IndexError):
                                pass  # Keep original format if parsing fails
                        
                        # Extract just the city name if it has station info
                        # For entries like "New York, NY – Moynihan Train Hall (NYP)", 
                        # we want to extract just "New York"
                        city_name = city.split(',')[0].strip()
                        stops.append((city_name, stop_time))
                
                if not stops:
                    print(f"Warning: {csv_file.name} has no valid stops")
                    continue
                
                # Insert route
                origin_city = stops[0][0]
                destination_city = stops[-1][0]
                departure_time = stops[0][1]
                arrival_time = stops[-1][1]
                
                # Calculate duration (simple estimation)
                duration_hours = 1  # Default, will be more sophisticated later
                
                cursor.execute('''INSERT INTO routes 
                                 (route_number, route_name, origin_city, destination_city, 
                                  departure_time, arrival_time, duration_hours)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (str(route_number), route_name, origin_city, destination_city,
                               departure_time, arrival_time, duration_hours))
                
                route_id = cursor.lastrowid
                
                # Insert stops
                for stop_number, (city, stop_time) in enumerate(stops, 1):
                    cursor.execute('''INSERT INTO stops 
                                     (route_id, stop_number, city_name, stop_time)
                                     VALUES (?, ?, ?, ?)''',
                                  (route_id, stop_number, city, stop_time))
                    
                    # Add city to cities table if not already there
                    cursor.execute('INSERT OR IGNORE INTO cities (name) VALUES (?)', (city,))
                
                print(f"✓ Loaded route {route_number}: {route_name} from {csv_file.name} ({len(stops)} stops)")
                route_number += 1
        
        except Exception as e:
            print(f"Error loading {csv_file.name}: {e}")
            import traceback
            traceback.print_exc()
            continue

def get_all_cities():
    """Get all cities in the network."""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('SELECT DISTINCT name FROM cities ORDER BY name')
    cities = [row[0] for row in c.fetchall()]
    conn.close()
    return cities

def get_routes_between_cities(origin, destination):
    """Get all routes between two cities."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''SELECT * FROM routes 
                 WHERE origin_city = ? AND destination_city = ?
                 ORDER BY departure_time''', (origin, destination))
    routes = [dict(row) for row in c.fetchall()]
    conn.close()
    return routes

def get_intermediate_stops(route_id):
    """Get all intermediate stops for a specific route."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''SELECT * FROM stops 
                 WHERE route_id = ? 
                 ORDER BY stop_number''', (route_id,))
    stops = [dict(row) for row in c.fetchall()]
    conn.close()
    return stops

def get_route_by_id(route_id):
    """Get a specific route by ID."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM routes WHERE id = ?', (route_id,))
    row = c.fetchone()
    route = dict(row) if row else None
    conn.close()
    return route

def get_all_routes_from_city(city):
    """Get all routes that pass through a specific city as a stop."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get all routes that have this city as a stop
    c.execute('''SELECT DISTINCT r.* FROM routes r
                 INNER JOIN stops s ON r.id = s.route_id
                 WHERE s.city_name = ?
                 ORDER BY r.departure_time''', (city,))
    routes = [dict(row) for row in c.fetchall()]
    conn.close()
    return routes

def get_routes_through_city_to_destination(from_city, to_city):
    """Get all routes that pass through from_city and continue to to_city."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get routes that have both cities as stops, with from_city before to_city
    c.execute('''SELECT DISTINCT r.* FROM routes r
                 INNER JOIN stops s1 ON r.id = s1.route_id
                 INNER JOIN stops s2 ON r.id = s2.route_id
                 WHERE s1.city_name = ? AND s2.city_name = ?
                 AND s1.stop_number < s2.stop_number
                 ORDER BY r.departure_time''', (from_city, to_city))
    routes = [dict(row) for row in c.fetchall()]
    conn.close()
    return routes

def get_stops_from_city(route_id, from_city):
    """Get all stops from a specific city onwards on a route."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Find the stop number for the from_city
    c.execute('''SELECT stop_number FROM stops 
                 WHERE route_id = ? AND city_name = ?''', (route_id, from_city))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return []
    
    from_stop_number = result['stop_number']
    
    # Get all stops from that point onwards
    c.execute('''SELECT * FROM stops 
                 WHERE route_id = ? AND stop_number >= ?
                 ORDER BY stop_number''', (route_id, from_stop_number))
    stops = [dict(row) for row in c.fetchall()]
    conn.close()
    return stops

if __name__ == '__main__':
    init_database()
    print("Database initialized successfully!")
