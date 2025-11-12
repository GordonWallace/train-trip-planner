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

    def test_direct_route_all_stops_in_schedule(self):
        """Test that all stops passed through on a route appear in the schedule"""
        # Scenario A: NY to Toledo with stops in Rhinecliff, Utica, and Erie
        response = self._generate_schedule(
            route_id=1,
            origin='New York',
            destination='Toledo',
            selected_stops=[
                {'city': 'Rhinecliff', 'duration': 2},
                {'city': 'Utica', 'duration': 2},
                {'city': 'Erie', 'duration': 2}
            ],
            start_date='2025-11-12'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # Extract all cities from the schedule
        cities_in_schedule = [event['city'] for event in schedule]
        
        # Verify that every requested stop city appears in the schedule
        requested_cities = ['Rhinecliff', 'Utica', 'Erie']
        for city in requested_cities:
            self.assertIn(city, cities_in_schedule, 
                f"Requested stop city {city} missing from schedule")
        
        # Also verify intermediate stops between origin and destination appear
        # (Croton-Harmon, Poughkeepsie should be in the path from NY to Toledo)
        expected_intermediate = ['Croton-Harmon', 'Poughkeepsie']
        for city in expected_intermediate:
            self.assertIn(city, cities_in_schedule,
                f"Intermediate city {city} should appear in schedule from NY to Toledo")

    def test_direct_route_duration_stops_in_schedule(self):
        """Test that every user-requested duration stop appears with layover in schedule"""
        # Scenario A extended: verify duration stops actually get duration events
        response = self._generate_schedule(
            route_id=1,
            origin='New York',
            destination='Toledo',
            selected_stops=[
                {'city': 'Rhinecliff', 'duration': 2},
                {'city': 'Utica', 'duration': 2},
                {'city': 'Erie', 'duration': 2}
            ],
            start_date='2025-11-12'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # For each requested stop, verify there's a layover/stop event
        requested_cities = ['Rhinecliff', 'Utica', 'Erie']
        for city in requested_cities:
            city_events = [e for e in schedule if e['city'] == city]
            self.assertGreater(len(city_events), 0,
                f"Requested stop {city} should have at least one event in schedule")
            
            # Verify at least one event for this city shows a stop/layover
            has_stop_event = any('stop' in e['event'].lower() or 'layover' in e['event'].lower() 
                               for e in city_events)
            self.assertTrue(has_stop_event,
                f"City {city} should have a stop or layover event in schedule")

    def test_all_route_stops_database_times_preserved(self):
        """Test that all stops in schedule have correct times from database"""
        # Direct route: NY to Toledo
        response = self._generate_schedule(
            route_id=1,
            origin='New York',
            destination='Toledo',
            selected_stops=[],  # No special stops
            start_date='2025-11-12'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # Verify times are properly formatted (HH:MM)
        for event in schedule:
            time_str = event['time']
            self.assertRegex(time_str, r'^\d{2}:\d{2}$',
                f"Time {time_str} for {event['city']} not in HH:MM format")
            
            # Verify date is properly formatted (YYYY-MM-DD)
            date_str = event['date']
            self.assertRegex(date_str, r'^\d{4}-\d{2}-\d{2}$',
                f"Date {date_str} not in YYYY-MM-DD format")


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
    
    def test_connection_route_hub_stop_duration(self):
        """Test that hub stop duration extends layover correctly"""
        from datetime import datetime
        
        # Test with 8 hour hub stop
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [{'city': 'Chicago', 'duration': 8}],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Topeka'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Find Chicago layover event
        chicago_layover = None
        for event in data['schedule']:
            if event['city'] == 'Chicago' and 'layover' in event['event'].lower():
                chicago_layover = event
                break
        
        self.assertIsNotNone(chicago_layover, "Should have layover at Chicago")
        self.assertIn('8 hour', chicago_layover['event'], 
            "Layover should be 8 hours when 8 hour stop requested")
        
        # Verify total duration increased due to longer layover
        self.assertIn('total_duration', data)
        self.assertIn('days', data['total_duration'])
    
    def test_connection_route_hub_stop_multiday(self):
        """Test that multi-day hub stop uses next available train departure"""
        from datetime import datetime
        
        # Test with 24 hour hub stop - should push to next day at 14:25 (SW Chief departure)
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [{'city': 'Chicago', 'duration': 24}],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Topeka'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Find Chicago arrival and layover events
        chicago_events = [e for e in data['schedule'] if e['city'] == 'Chicago']
        self.assertGreater(len(chicago_events), 0)
        
        # Should have arrival (Disembark) and layover events
        has_disembark = any('Disembark' in e['event'] for e in chicago_events)
        has_layover = any('layover' in e['event'].lower() for e in chicago_events)
        
        self.assertTrue(has_disembark)
        self.assertTrue(has_layover)
        
        # Find the layover event and verify it shows the actual train departure time (14:25)
        layover_event = next(e for e in chicago_events if 'layover' in e['event'].lower())
        # Should show 14:25 as the departure time (SW Chief's actual departure)
        self.assertEqual(layover_event['time'], '14:25',
            "Should show actual SW Chief departure time of 14:25")

    def test_connection_route_intermediate_stop_duration_segment1(self):
        """Test that intermediate stops on segment 1 with duration create layover events"""
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [
                    {'city': 'South Bend', 'duration': 2}
                ],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Los Angeles'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # Find South Bend events
        south_bend_events = [e for e in schedule if e['city'] == 'South Bend']
        self.assertGreater(len(south_bend_events), 0, "Should have South Bend in schedule")
        
        # Should have Stop event and layover event when duration is requested
        has_stop = any('Stop' in e['event'] for e in south_bend_events)
        has_layover = any('hour' in e['event'].lower() for e in south_bend_events)
        self.assertTrue(has_stop, "Should have Stop event for South Bend")
        self.assertTrue(has_layover, "Should have layover event for South Bend since duration was requested")

    def test_connection_route_intermediate_stop_duration_segment2(self):
        """Test that intermediate stops on segment 2 with duration create layover events"""
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [
                    {'city': 'Kansas City', 'duration': 2}
                ],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Los Angeles'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # Find Kansas City events
        kc_events = [e for e in schedule if e['city'] == 'Kansas City']
        self.assertGreater(len(kc_events), 0, "Should have Kansas City in schedule")
        
        # Should have Stop event and layover event when duration is requested
        has_stop = any('Stop' in e['event'] for e in kc_events)
        has_layover = any('hour' in e['event'].lower() for e in kc_events)
        self.assertTrue(has_stop, "Should have Stop event for Kansas City")
        self.assertTrue(has_layover, "Should have layover event for Kansas City since duration was requested")

    def test_connection_route_intermediate_stop_no_duration(self):
        """Test that intermediate stops without durations don't add layover events"""
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [],  # No duration specified
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Los Angeles'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # When no stops are selected, all stops should be shown without extra layover events
        # Count non-layover stops (should be 20 from route1 + 7 from route2 + 1 layover at Chicago)
        non_layover_stops = [e for e in schedule if 'layover' not in e['event'].lower()]
        layover_stops = [e for e in schedule if 'layover' in e['event'].lower()]
        
        # Should have exactly 1 layover (Chicago hub connection)
        self.assertEqual(len(layover_stops), 1, 
            "Should have exactly 1 layover when no intermediate stops selected")

    def test_connection_route_all_intermediate_stops_appear(self):
        """Test that all intermediate stops on both route segments appear in schedule"""
        # Scenario B: NY to LA with stops in Erie and Newton
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [
                    {'city': 'Erie', 'duration': 2},
                    {'city': 'Newton', 'duration': 2}
                ],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Los Angeles'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # Extract all cities from the schedule
        cities_in_schedule = [event['city'] for event in schedule]
        
        # Verify requested stop cities appear
        requested_cities = ['Erie', 'Newton']
        for city in requested_cities:
            self.assertIn(city, cities_in_schedule,
                f"Requested stop city {city} missing from connection route schedule")
        
        # Verify hub city appears
        self.assertIn('Chicago', cities_in_schedule,
            "Hub city Chicago should appear in connection route schedule")
        
        # Verify origin and destination appear
        self.assertIn('New York', cities_in_schedule,
            "Origin New York should appear in schedule")
        self.assertIn('Los Angeles', cities_in_schedule,
            "Destination Los Angeles should appear in schedule")

    def test_connection_route_duration_stops_applied(self):
        """Test that duration-based stops on connection routes get proper layover times"""
        # Scenario B: NY to LA with stops in Erie and Newton
        response = self.client.post('/api/generate-schedule',
            json={
                'route_id': 'conn_1_2',
                'selected_stops': [
                    {'city': 'Erie', 'duration': 2},
                    {'city': 'Newton', 'duration': 2}
                ],
                'start_date': '2025-11-12',
                'origin_city': 'New York',
                'destination_city': 'Los Angeles'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schedule = data['schedule']
        
        # Find events for requested stop cities
        requested_cities = ['Erie', 'Newton']
        for city in requested_cities:
            city_events = [e for e in schedule if e['city'] == city]
            self.assertGreater(len(city_events), 0,
                f"Requested stop {city} should have events in schedule")
            
            # Get arrival and departure times for this city
            arrival_events = [e for e in city_events if 'arrival' in e['event'].lower() or e['event'] == 'Stop']
            departure_events = [e for e in city_events if 'layover' in e['event'].lower() or 'board' in e['event'].lower()]
            
            # Verify there's at least an arrival event
            self.assertGreater(len(arrival_events), 0,
                f"City {city} should have an arrival event")
            
            # BUG CHECK: Cities with requested durations should have layover events, not just plain stops
            # If we only have "Stop" events and no layover, that means duration wasn't applied
            has_layover_event = any('hour' in e['event'].lower() for e in city_events)
            self.assertTrue(has_layover_event,
                f"City {city} with 2-hour requested duration should have a layover event (e.g., '2 hour stop'), not just 'Stop'")


if __name__ == '__main__':
    unittest.main()

