"""
Database initialization and management for the train trip planner.
"""
import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'train_routes.db')

def init_database():
    """Initialize the database with schema and sample data."""
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
                  arrival_time TEXT,
                  departure_time TEXT,
                  FOREIGN KEY(route_id) REFERENCES routes(id))''')
    
    # Create cities table (all cities in the network)
    c.execute('''CREATE TABLE IF NOT EXISTS cities
                 (id INTEGER PRIMARY KEY,
                  name TEXT UNIQUE,
                  state TEXT)''')
    
    # Check if we already have data
    c.execute('SELECT COUNT(*) FROM routes')
    if c.fetchone()[0] == 0:
        # Insert sample Amtrak-inspired routes
        sample_routes = [
            ('1', 'Northeast Regional', 'Boston', 'New York', '08:00', '11:30', 3),
            ('2', 'Northeast Regional', 'New York', 'Philadelphia', '12:00', '14:45', 2),
            ('3', 'Northeast Regional', 'Philadelphia', 'Washington DC', '15:15', '17:30', 2),
            ('4', 'Northeast Regional', 'Washington DC', 'Richmond', '18:00', '20:15', 2),
            ('5', 'Silver Star', 'New York', 'Miami', '07:00', '12:30', 29),
            ('6', 'Lake Shore Limited', 'Boston', 'Chicago', '09:00', '15:45', 30),
            ('7', 'Capitol Limited', 'Chicago', 'Washington DC', '14:30', '10:00', 19),
            ('8', 'California Zephyr', 'Chicago', 'Denver', '08:00', '12:00', 28),
            ('9', 'Southwest Chief', 'Denver', 'Los Angeles', '15:00', '20:00', 29),
            ('10', 'Empire Builder', 'Chicago', 'Seattle', '01:00', '20:15', 45),
        ]
        
        for route in sample_routes:
            c.execute('''INSERT INTO routes 
                         (route_number, route_name, origin_city, destination_city, 
                          departure_time, arrival_time, duration_hours)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', route)
        
        # Get route IDs for adding stops
        c.execute('SELECT id, origin_city, destination_city FROM routes')
        routes_data = c.fetchall()
        
        # Sample stops (intermediate stops on routes)
        stops_data = [
            # Northeast Regional stops (Boston to New York)
            (1, 1, 'Boston', '08:00', '08:00'),
            (1, 2, 'Providence', '08:45', '08:55'),
            (1, 3, 'New Haven', '09:30', '09:40'),
            (1, 4, 'New York', '11:30', '11:30'),
            
            (2, 1, 'New York', '12:00', '12:15'),
            (2, 2, 'New Brunswick', '12:45', '12:55'),
            (2, 3, 'Philadelphia', '14:45', '14:45'),
            
            (3, 1, 'Philadelphia', '15:15', '15:30'),
            (3, 2, 'Baltimore', '16:15', '16:30'),
            (3, 3, 'Washington DC', '17:30', '17:30'),
            
            (4, 1, 'Washington DC', '18:00', '18:15'),
            (4, 2, 'Petersburg', '19:30', '19:45'),
            (4, 3, 'Richmond', '20:15', '20:15'),
            
            # Silver Star stops
            (5, 1, 'New York', '07:00', '07:30'),
            (5, 2, 'Baltimore', '09:00', '09:15'),
            (5, 3, 'Washington DC', '10:30', '11:00'),
            (5, 4, 'Charlotte', '14:30', '15:00'),
            (5, 5, 'Savannah', '20:00', '20:30'),
            (5, 6, 'Jacksonville', '23:00', '23:30'),
            (5, 7, 'Miami', '12:30', '12:30'),
            
            # Lake Shore Limited stops
            (6, 1, 'Boston', '09:00', '09:30'),
            (6, 2, 'New York', '11:45', '12:30'),
            (6, 3, 'Buffalo', '18:00', '18:30'),
            (6, 4, 'Cleveland', '23:30', '00:00'),
            (6, 5, 'Chicago', '15:45', '15:45'),
            
            # Capitol Limited stops
            (7, 1, 'Chicago', '14:30', '15:00'),
            (7, 2, 'Indianapolis', '19:00', '19:30'),
            (7, 3, 'Cincinnati', '22:30', '23:00'),
            (7, 4, 'Washington DC', '10:00', '10:00'),
            
            # California Zephyr stops
            (8, 1, 'Chicago', '08:00', '08:30'),
            (8, 2, 'Milwaukee', '09:30', '10:00'),
            (8, 3, 'Des Moines', '14:00', '14:30'),
            (8, 4, 'Denver', '12:00', '12:00'),
            
            # Southwest Chief stops
            (9, 1, 'Denver', '15:00', '15:30'),
            (9, 2, 'Kansas City', '20:00', '20:30'),
            (9, 3, 'Albuquerque', '03:00', '03:30'),
            (9, 4, 'Los Angeles', '20:00', '20:00'),
            
            # Empire Builder stops
            (10, 1, 'Chicago', '01:00', '01:30'),
            (10, 2, 'Minneapolis', '10:00', '10:30'),
            (10, 3, 'Fargo', '14:00', '14:30'),
            (10, 4, 'Spokane', '13:00', '13:30'),
            (10, 5, 'Seattle', '20:15', '20:15'),
        ]
        
        for stop in stops_data:
            c.execute('''INSERT INTO stops 
                         (route_id, stop_number, city_name, arrival_time, departure_time)
                         VALUES (?, ?, ?, ?, ?)''', stop)
        
        # Insert cities
        cities_data = [
            ('Boston', 'MA'),
            ('New York', 'NY'),
            ('Philadelphia', 'PA'),
            ('Washington DC', 'DC'),
            ('Richmond', 'VA'),
            ('Baltimore', 'MD'),
            ('Charlotte', 'NC'),
            ('Savannah', 'GA'),
            ('Jacksonville', 'FL'),
            ('Miami', 'FL'),
            ('New Haven', 'CT'),
            ('Providence', 'RI'),
            ('New Brunswick', 'NJ'),
            ('Petersburg', 'VA'),
            ('Chicago', 'IL'),
            ('Milwaukee', 'WI'),
            ('Des Moines', 'IA'),
            ('Denver', 'CO'),
            ('Kansas City', 'MO'),
            ('Albuquerque', 'NM'),
            ('Los Angeles', 'CA'),
            ('Minneapolis', 'MN'),
            ('Fargo', 'ND'),
            ('Spokane', 'WA'),
            ('Seattle', 'WA'),
            ('Cleveland', 'OH'),
            ('Cincinnati', 'OH'),
            ('Indianapolis', 'IN'),
            ('Buffalo', 'NY'),
        ]
        
        for city in cities_data:
            c.execute('INSERT OR IGNORE INTO cities (name, state) VALUES (?, ?)', city)
    
    conn.commit()
    conn.close()

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

if __name__ == '__main__':
    init_database()
    print("Database initialized successfully!")
