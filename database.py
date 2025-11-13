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
    """Get all routes that pass through both origin and destination cities."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Find routes that have both cities as stops, with origin before destination
    c.execute('''SELECT DISTINCT r.* FROM routes r
                 INNER JOIN stops s1 ON r.id = s1.route_id
                 INNER JOIN stops s2 ON r.id = s2.route_id
                 WHERE s1.city_name = ? AND s2.city_name = ?
                 AND s1.stop_number < s2.stop_number
                 ORDER BY r.departure_time''', (origin, destination))
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

def get_stops_between_cities(route_id, from_city, to_city):
    """Get stops from from_city to to_city (inclusive) on a specific route."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Find the stop numbers for both cities
    c.execute('''SELECT stop_number FROM stops 
                 WHERE route_id = ? AND city_name = ?''', (route_id, from_city))
    from_result = c.fetchone()
    
    c.execute('''SELECT stop_number FROM stops 
                 WHERE route_id = ? AND city_name = ?''', (route_id, to_city))
    to_result = c.fetchone()
    
    if not from_result or not to_result:
        conn.close()
        return []
    
    from_stop_number = from_result['stop_number']
    to_stop_number = to_result['stop_number']
    
    # Get all stops between from and to (inclusive)
    c.execute('''SELECT * FROM stops 
                 WHERE route_id = ? AND stop_number >= ? AND stop_number <= ?
                 ORDER BY stop_number''', (route_id, from_stop_number, to_stop_number))
    stops = [dict(row) for row in c.fetchall()]
    conn.close()
    return stops

def find_connection_paths(origin_city, destination_city, max_hops=3):
    """
    Find all possible connection paths from origin to destination.
    Returns a list of paths, each path being a list of (hub_city, route_id) tuples.
    Each path represents: origin --(route1)--> hub1 --(route2)--> hub2 ... --(routeN)--> destination
    
    Uses BFS to find shortest paths first.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get all routes and their stops for quick lookup
    c.execute('SELECT id, origin_city, destination_city, route_name FROM routes')
    all_routes = {row['id']: {
        'name': row['route_name'],
        'origin': row['origin_city'],
        'destination': row['destination_city']
    } for row in c.fetchall()}
    
    c.execute('SELECT route_id, city_name, stop_number FROM stops ORDER BY route_id, stop_number')
    route_stops = {}
    for row in c.fetchall():
        if row['route_id'] not in route_stops:
            route_stops[row['route_id']] = []
        route_stops[row['route_id']].append({
            'city': row['city_name'],
            'stop_num': row['stop_number']
        })
    
    def get_routes_between(from_city, to_city):
        """Find all routes that go from from_city to to_city."""
        routes = []
        for route_id, stops in route_stops.items():
            cities = [s['city'] for s in stops]
            if from_city in cities and to_city in cities:
                from_idx = cities.index(from_city)
                to_idx = cities.index(to_city)
                if from_idx < to_idx:  # Must be in order
                    routes.append(route_id)
        return routes
    
    # BFS to find paths
    from collections import deque
    queue = deque([
        (origin_city, [])  # (current_city, path_so_far)
    ])
    
    found_paths = []
    visited_states = set()  # Prevent infinite loops: (current_city, path_length)
    
    while queue:
        current_city, path = queue.popleft()
        
        # Prevent revisiting same city with same path length
        state = (current_city, len(path))
        if state in visited_states:
            continue
        visited_states.add(state)
        
        # If we reached destination, save this path
        if current_city == destination_city and len(path) > 0:
            found_paths.append(path)
            continue
        
        # Don't exceed max hops
        if len(path) >= max_hops:
            continue
        
        # Find all routes from current city
        routes_from_here = get_routes_between(current_city, destination_city)
        
        # Also find routes to intermediate cities
        all_destinations = set()
        for route_id in route_stops.keys():
            stops = route_stops[route_id]
            cities = [s['city'] for s in stops]
            try:
                curr_idx = cities.index(current_city)
                for i in range(curr_idx + 1, len(cities)):
                    all_destinations.add(cities[i])
            except ValueError:
                pass
        
        for next_city in all_destinations:
            # Check if there's a route from current to next
            routes = get_routes_between(current_city, next_city)
            for route_id in routes:
                new_path = path + [(next_city, route_id)]
                queue.append((next_city, new_path))
    
    conn.close()
    
    # Return paths sorted by length (shortest first)
    return sorted(found_paths, key=len)


def find_connection_hubs(origin_city, destination_city):
    """
    Find all connection paths from origin to destination.
    Supports both 2-hop (single hub) and N-hop (multiple hubs) connections.
    
    Returns:
        List of dicts, where each dict represents a connection path with:
        - 'hubs': List of hub cities (intermediate connection points)
        - 'route_ids': List of route IDs making up this path
        - 'route_names': List of route names
        - 'path_length': Number of hops (len(route_ids))
    """
    paths = find_connection_paths(origin_city, destination_city)
    
    if not paths:
        return []
    
    connections = []
    for path in paths:
        # path is a list of (hub_city, route_id) tuples
        if not path:
            continue
        
        route_ids = [route_id for hub_city, route_id in path]
        hubs = [hub_city for hub_city, route_id in path[:-1]]  # Exclude final destination
        
        # Get route names
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        route_names = []
        for route_id in route_ids:
            c.execute('SELECT route_name FROM routes WHERE id = ?', (route_id,))
            result = c.fetchone()
            if result:
                route_names.append(result['route_name'])
        
        conn.close()
        
        connections.append({
            'route_ids': route_ids,
            'hubs': hubs,
            'route_names': route_names,
            'path_length': len(route_ids)
        })
    
    # For backward compatibility, also support old-style format for 2-hop connections
    # (single hub) by extracting the hub and route1/route2 info
    backward_compatible = []
    for conn in connections:
        if conn['path_length'] == 2:
            # 2-hop connection: convert to old format for compatibility
            backward_compatible.append({
                'hub': conn['hubs'][0],
                'route1_id': conn['route_ids'][0],
                'route1_name': conn['route_names'][0],
                'route2_id': conn['route_ids'][1],
                'route2_name': conn['route_names'][1],
                # Also include new format
                'route_ids': conn['route_ids'],
                'hubs': conn['hubs'],
                'path_length': 2
            })
        else:
            # N-hop connection (3 or more): only new format
            backward_compatible.append(conn)
    
    return backward_compatible

def get_connection_route(origin_city, destination_city, hub_city, route1_id, route2_id):
    """Get the combined route information for a connection through a hub."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # If hub_city not provided, determine it from route endpoints
    if not hub_city:
        # Route 1's destination should be the hub (where connection happens)
        c.execute('SELECT destination_city FROM routes WHERE id = ?', (route1_id,))
        result = c.fetchone()
        if result:
            hub_city = result['destination_city']
    
    # Get stops from origin to hub on route 1
    c.execute('''SELECT * FROM stops
                 WHERE route_id = ?
                 AND stop_number >= (SELECT stop_number FROM stops WHERE route_id = ? AND city_name = ?)
                 AND stop_number <= (SELECT stop_number FROM stops WHERE route_id = ? AND city_name = ?)
                 ORDER BY stop_number''', (route1_id, route1_id, origin_city, route1_id, hub_city))
    segment1_stops = [dict(row) for row in c.fetchall()]
    
    # Get stops from hub to destination on route 2
    c.execute('''SELECT * FROM stops
                 WHERE route_id = ?
                 AND stop_number >= (SELECT stop_number FROM stops WHERE route_id = ? AND city_name = ?)
                 AND stop_number <= (SELECT stop_number FROM stops WHERE route_id = ? AND city_name = ?)
                 ORDER BY stop_number''', (route2_id, route2_id, hub_city, route2_id, destination_city))
    segment2_stops = [dict(row) for row in c.fetchall()]
    
    # Get route details
    c.execute('SELECT * FROM routes WHERE id = ?', (route1_id,))
    route1 = dict(c.fetchone())
    
    c.execute('SELECT * FROM routes WHERE id = ?', (route2_id,))
    route2 = dict(c.fetchone())
    
    conn.close()
    
    return {
        'segment1_stops': segment1_stops,
        'segment2_stops': segment2_stops,
        'route1': route1,
        'route2': route2,
        'hub': hub_city
    }

def get_multi_hop_connection_route(origin_city, destination_city, route_ids):
    """
    Get the combined route information for a multi-hop connection.
    
    Args:
        origin_city: Starting city
        destination_city: Ending city
        route_ids: List of route IDs representing the path [1, 2, 3, ...]
    
    Returns:
        Dict with:
        - 'segments': List of segment dicts, each containing:
          - 'route': The route object for this segment
          - 'stops': List of stops for this segment
          - 'start_city': City where this segment starts
          - 'end_city': City where this segment ends
        - 'hubs': List of hub cities (connection points)
        - 'route_ids': The list of route IDs
    """
    if len(route_ids) < 2:
        return None
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    segments = []
    hubs = []
    prev_end_city = origin_city
    
    for route_idx, route_id in enumerate(route_ids):
        is_first = route_idx == 0
        is_last = route_idx == len(route_ids) - 1
        
        # Get route info
        c.execute('SELECT * FROM routes WHERE id = ?', (route_id,))
        route = dict(c.fetchone())
        
        # Determine start and end city for this segment
        if is_first:
            start_city = origin_city
        else:
            start_city = prev_end_city
            hubs.append(prev_end_city)
        
        end_city = destination_city if is_last else None
        
        if end_city is None:
            # Need to find the end city by looking at next route
            if route_idx + 1 < len(route_ids):
                next_route_id = route_ids[route_idx + 1]
                c.execute('SELECT origin_city FROM routes WHERE id = ?', (next_route_id,))
                next_route_result = c.fetchone()
                if next_route_result:
                    end_city = next_route_result['origin_city']
        
        if not end_city:
            end_city = route['destination_city']
        
        # Get stops from start to end on this route
        c.execute('''SELECT * FROM stops
                     WHERE route_id = ?
                     AND stop_number >= (SELECT stop_number FROM stops WHERE route_id = ? AND city_name = ?)
                     AND stop_number <= (SELECT stop_number FROM stops WHERE route_id = ? AND city_name = ?)
                     ORDER BY stop_number''', (route_id, route_id, start_city, route_id, end_city))
        stops = [dict(row) for row in c.fetchall()]
        
        segments.append({
            'route': route,
            'stops': stops,
            'start_city': start_city,
            'end_city': end_city
        })
        
        prev_end_city = end_city
    
    conn.close()
    
    return {
        'segments': segments,
        'hubs': hubs,
        'route_ids': route_ids
    }


if __name__ == '__main__':
    init_database()
    print("Database initialized successfully!")
