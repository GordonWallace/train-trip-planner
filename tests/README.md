# Test Suite

The Train Trip Planner uses a comprehensive test suite organized into logical test modules.

## Test Organization

### `test_database.py`
Tests for database functionality including:
- **TestDatabaseBasics**: Basic database queries
  - `test_get_route_by_id`: Verify route retrieval
  - `test_get_intermediate_stops`: Verify stop data retrieval
  - `test_get_routes_between_cities_direct`: Verify direct route queries

- **TestConnectionRoutes**: Connection route functionality
  - `test_find_connection_hubs_ny_to_topeka`: Verify hub city detection
  - `test_get_connection_route_data`: Verify complete connection data retrieval
  - `test_hub_city_auto_detection`: Verify automatic hub city determination

### `test_schedules.py`
Tests for schedule generation API:
- **TestDirectRouteSchedules**: Direct route schedule generation
  - `test_direct_route_no_stops`: Basic route without intermediate stops
  - `test_direct_route_with_single_stop`: Route with one intermediate stop
  - `test_direct_route_with_multiple_stops`: Route with multiple intermediate stops
  - `test_direct_route_with_long_layover`: Route with extended layover
  - `test_schedule_chronological_order`: Verify events are chronologically ordered
  - Validates that no duplicate stops appear in schedules

- **TestConnectionRouteSchedules**: Multi-train connection schedule generation
  - `test_connection_route_ny_to_topeka`: Full connection route (NY → Chicago → Topeka)
  - `test_connection_route_has_layover`: Verify layover information is included
  - `test_connection_route_two_routes_in_schedule`: Verify both train names appear

## Running Tests

### Run all tests:
```bash
python3 tests/run_tests.py
```

### Run specific test file:
```bash
python3 -m unittest tests.test_database -v
python3 -m unittest tests.test_schedules -v
```

### Run specific test class:
```bash
python3 -m unittest tests.test_database.TestDatabaseBasics -v
python3 -m unittest tests.test_schedules.TestDirectRouteSchedules -v
```

### Run specific test:
```bash
python3 -m unittest tests.test_database.TestDatabaseBasics.test_get_route_by_id -v
```

## Test Coverage

- ✅ Database queries (routes, stops, connections)
- ✅ Connection hub discovery
- ✅ Schedule generation for direct routes
- ✅ Schedule generation for multi-train connections
- ✅ Layover calculation
- ✅ Duplicate stop prevention
- ✅ Chronological ordering of events
- ✅ Multi-day date tracking

## Adding New Tests

1. Create a test method in the appropriate test class
2. Use descriptive names starting with `test_`
3. Include a docstring explaining what is tested
4. Use assertions to validate expected behavior
5. Run tests to ensure they pass before committing

Example:
```python
def test_new_feature(self):
    """Test that new feature works correctly"""
    result = some_function()
    self.assertEqual(result, expected_value)
```
