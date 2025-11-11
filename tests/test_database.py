"""Tests for database functionality"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (
    init_database,
    get_routes_between_cities,
    find_connection_hubs,
    get_connection_route,
    get_route_by_id,
    get_intermediate_stops
)


class TestDatabaseBasics(unittest.TestCase):
    """Test basic database queries"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize database before tests"""
        init_database()
    
    def test_get_route_by_id(self):
        """Test retrieving a route by ID"""
        route = get_route_by_id(1)
        self.assertIsNotNone(route)
        self.assertEqual(route['id'], 1)
        self.assertIn('route_name', route)
        self.assertIn('origin_city', route)
        self.assertIn('destination_city', route)
    
    def test_get_intermediate_stops(self):
        """Test retrieving intermediate stops for a route"""
        stops = get_intermediate_stops(1)
        self.assertGreater(len(stops), 0)
        # Should have stop data
        for stop in stops:
            self.assertIn('city_name', stop)
    
    def test_get_routes_between_cities_direct(self):
        """Test finding direct routes between two cities"""
        routes = get_routes_between_cities("New York", "Chicago")
        self.assertGreater(len(routes), 0)
        # All returned routes should go from origin to destination
        for route in routes:
            self.assertEqual(route['origin_city'], "New York")
            self.assertEqual(route['destination_city'], "Chicago")


class TestConnectionRoutes(unittest.TestCase):
    """Test connection route functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize database before tests"""
        init_database()
    
    def test_find_connection_hubs_ny_to_topeka(self):
        """Test finding hub cities between New York and Topeka"""
        hubs = find_connection_hubs("New York", "Topeka")
        self.assertGreater(len(hubs), 0)
        
        # Verify structure of hub data
        hub = hubs[0]
        self.assertIn('hub', hub)
        self.assertIn('route1_id', hub)
        self.assertIn('route2_id', hub)
        self.assertIn('route1_name', hub)
        self.assertIn('route2_name', hub)
    
    def test_get_connection_route_data(self):
        """Test retrieving complete connection route data"""
        hubs = find_connection_hubs("New York", "Topeka")
        self.assertGreater(len(hubs), 0)
        
        hub = hubs[0]
        connection_data = get_connection_route(
            "New York",
            "Topeka",
            None,  # hub_city should be auto-detected
            hub['route1_id'],
            hub['route2_id']
        )
        
        # Verify structure
        self.assertIn('segment1_stops', connection_data)
        self.assertIn('segment2_stops', connection_data)
        self.assertIn('route1', connection_data)
        self.assertIn('route2', connection_data)
        self.assertIn('hub', connection_data)
        
        # Verify segments have stops
        self.assertGreater(len(connection_data['segment1_stops']), 0)
        self.assertGreater(len(connection_data['segment2_stops']), 0)
        
        # Verify all stops have required fields
        for stop in connection_data['segment1_stops']:
            self.assertIn('city_name', stop)
            self.assertIn('stop_time', stop)
        
        for stop in connection_data['segment2_stops']:
            self.assertIn('city_name', stop)
            self.assertIn('stop_time', stop)
    
    def test_hub_city_auto_detection(self):
        """Test that hub city is correctly auto-detected"""
        hubs = find_connection_hubs("New York", "Topeka")
        hub = hubs[0]
        
        connection_data = get_connection_route(
            "New York",
            "Topeka",
            None,  # Let it auto-detect
            hub['route1_id'],
            hub['route2_id']
        )
        
        # Hub should be the destination of route1
        route1 = get_route_by_id(hub['route1_id'])
        self.assertEqual(connection_data['hub'], route1['destination_city'])


if __name__ == '__main__':
    unittest.main()
