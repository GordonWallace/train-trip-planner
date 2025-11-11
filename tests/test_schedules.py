"""Tests for schedule generation API"""
import unittest
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


class TestDirectRouteSchedules(unittest.TestCase):
    """Test schedule generation for direct routes"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test client"""
        cls.client = app.test_client()
    
    def _generate_schedule(self, route_id, origin, destination, selected_stops=None, start_date='2025-11-12'):
        """Helper to generate schedule"""
        if selected_stops is None:
            selected_stops = []
        
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': route_id,
                'selected_stops': selected_stops,
                'start_date': start_date,
                'origin_city': origin,
                'destination_city': destination
            },
            content_type='application/json'
        )
        return response
    
    def _check_no_duplicates(self, schedule):
        """Check that schedule has no duplicate stops at same time"""
        seen = set()
        for event in schedule:
            event_key = (event['date'], event['time'], event['city'])
            self.assertNotIn(event_key, seen, f"Duplicate event found: {event}")
            seen.add(event_key)
    
    def test_direct_route_no_stops(self):
        """Test direct route from Chicago to Topeka without intermediate stops"""
        response = self._generate_schedule(
            route_id=2,
            origin='Chicago',
            destination='Topeka'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertIn('schedule', data)
        self.assertIn('route_name', data)
        self.assertGreater(len(data['schedule']), 0)
        
        # Verify no duplicates
        self._check_no_duplicates(data['schedule'])
        
        # Should have at least 2 events (departure and arrival)
        self.assertGreaterEqual(len(data['schedule']), 2)
    
    def test_direct_route_with_single_stop(self):
        """Test direct route generation with request for intermediate stop"""
        response = self._generate_schedule(
            route_id=2,
            origin='Chicago',
            destination='Topeka',
            selected_stops=[{'city': 'Princeton', 'duration': 0}]
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify no duplicates
        self._check_no_duplicates(data['schedule'])
        
        # Should have events
        self.assertGreater(len(data['schedule']), 0)
        
        # Verify route name is correct
        self.assertIn('Southwest Chief', data['route_name'])
    
    def test_direct_route_with_multiple_stops(self):
        """Test direct route generation with multiple stop requests"""
        response = self._generate_schedule(
            route_id=2,
            origin='Chicago',
            destination='Topeka',
            selected_stops=[
                {'city': 'Naperville', 'duration': 0},
                {'city': 'Princeton', 'duration': 0},
                {'city': 'Galesburg', 'duration': 0}
            ]
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify no duplicates
        self._check_no_duplicates(data['schedule'])
        
        # Should have events
        self.assertGreater(len(data['schedule']), 0)
        
        # Verify route name is correct
        self.assertIn('Southwest Chief', data['route_name'])
    
    def test_direct_route_with_long_layover(self):
        """Test direct route with a long layover at intermediate stop"""
        response = self._generate_schedule(
            route_id=2,
            origin='Chicago',
            destination='Topeka',
            selected_stops=[{'city': 'Princeton', 'duration': 24}]  # 24 hour layover
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify no duplicates
        self._check_no_duplicates(data['schedule'])
        
        # Verify duration is calculated
        self.assertIn('total_duration', data)
        self.assertNotEqual(data['total_duration'], 'Unknown')
    
    def test_schedule_chronological_order(self):
        """Test that schedule events are in chronological order"""
        response = self._generate_schedule(
            route_id=1,
            origin='New York',
            destination='Chicago'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        schedule = data['schedule']
        from datetime import datetime
        
        # Convert to datetime objects and verify ordering
        prev_dt = None
        for event in schedule:
            event_dt = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M')
            if prev_dt is not None:
                self.assertGreaterEqual(event_dt, prev_dt, 
                    f"Events not in chronological order: {prev_dt} -> {event_dt}")
            prev_dt = event_dt


class TestConnectionRouteSchedules(unittest.TestCase):
    """Test schedule generation for connection routes"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test client"""
        cls.client = app.test_client()
    
    def test_connection_route_ny_to_topeka(self):
        """Test multi-train connection from New York to Topeka"""
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',  # Lake Shore Limited → Southwest Chief
                'selected_stops': [],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Topeka'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertIn('schedule', data)
        self.assertIn('route_name', data)
        self.assertIn('total_duration', data)
        
        # Should have substantial number of events (both routes + layover)
        self.assertGreater(len(data['schedule']), 20)
        
        # Verify no duplicate stops
        seen = set()
        for event in data['schedule']:
            event_key = (event['date'], event['time'], event['city'])
            self.assertNotIn(event_key, seen, f"Duplicate event in connection route: {event}")
            seen.add(event_key)
    
    def test_connection_route_has_layover(self):
        """Test that connection route includes layover information"""
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Topeka'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Check for layover event
        has_layover = False
        for event in data['schedule']:
            if 'layover' in event['event'].lower():
                has_layover = True
                break
        
        self.assertTrue(has_layover, "Connection route should include layover information")
    
    def test_connection_route_two_routes_in_schedule(self):
        """Test that connection route shows both train names"""
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Topeka'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Collect unique route names in schedule
        route_names = set()
        for event in data['schedule']:
            if 'route_name' in event:
                route_names.add(event['route_name'])
        
        # Should have both route names represented
        self.assertGreater(len(route_names), 1, 
            "Connection route should show multiple train names in schedule")


if __name__ == '__main__':
    unittest.main()
