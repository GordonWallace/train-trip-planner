#!/usr/bin/env python3
"""Quick test of database queries"""
import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'train_routes.db')

conn = sqlite3.connect(DATABASE_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check what routes we have
print("All routes:")
c.execute('SELECT id, route_name, origin_city, destination_city, departure_time FROM routes ORDER BY id')
for row in c.fetchall():
    print(f"  Route {row['id']}: {row['route_name']} {row['origin_city']} -> {row['destination_city']} departs {row['departure_time']}")

print("\n\nAll stops:")
c.execute('SELECT route_id, stop_number, city_name FROM stops ORDER BY route_id, stop_number')
current_route = None
for row in c.fetchall():
    if row['route_id'] != current_route:
        print(f"\nRoute {row['route_id']}:")
        current_route = row['route_id']
    print(f"  Stop {row['stop_number']}: {row['city_name']}")

print("\n\nTesting get_routes_through_city_to_destination('Providence', 'New York'):")
c.execute('''SELECT DISTINCT r.* FROM routes r
             INNER JOIN stops s1 ON r.id = s1.route_id
             INNER JOIN stops s2 ON r.id = s2.route_id
             WHERE s1.city_name = 'Providence' AND s2.city_name = 'New York'
             AND s1.stop_number < s2.stop_number
             ORDER BY r.departure_time''')
for row in c.fetchall():
    print(f"  Route {row['id']}: {row['route_name']}")

print("\n\nTesting get_stops_from_city(1, 'Providence'):")
c.execute('SELECT stop_number FROM stops WHERE route_id = 1 AND city_name = "Providence"')
result = c.fetchone()
if result:
    from_stop_number = result['stop_number']
    print(f"  Providence is at stop {from_stop_number}")
    c.execute('SELECT * FROM stops WHERE route_id = 1 AND stop_number >= ? ORDER BY stop_number', (from_stop_number,))
    for row in c.fetchall():
        print(f"    Stop {row['stop_number']}: {row['city_name']} arrival {row['arrival_time']} departure {row['departure_time']}")
else:
    print("  Providence not found on route 1")

conn.close()
