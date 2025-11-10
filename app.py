"""
Flask backend for the train trip planner application.
"""
from flask import Flask, render_template, jsonify, request
from database import init_database, get_all_cities, get_routes_between_cities, get_intermediate_stops, get_route_by_id, get_all_routes_from_city, get_routes_through_city_to_destination, get_stops_from_city, get_stops_between_cities
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/api/cities', methods=['GET'])
def api_cities():
    """Get all available cities."""
    cities = get_all_cities()
    return jsonify({'cities': cities})

@app.route('/api/routes', methods=['POST'])
def api_routes():
    """Get routes between two cities."""
    data = request.json
    origin = data.get('origin')
    destination = data.get('destination')
    
    if not origin or not destination:
        return jsonify({'error': 'Origin and destination required'}), 400
    
    routes = get_routes_between_cities(origin, destination)
    
    # Calculate actual duration and arrival time for each route accounting for date boundaries
    for route in routes:
        # Get all stops for this route to find the actual origin and destination times
        all_stops = get_intermediate_stops(route['id'])
        
        # Find the times for the actual origin and destination cities
        origin_time = None
        destination_time = None
        
        for stop in all_stops:
            if stop['city_name'] == origin and origin_time is None:
                origin_time = stop['stop_time']
            if stop['city_name'] == destination:
                destination_time = stop['stop_time']
        
        # Calculate duration accounting for day boundary
        if origin_time and destination_time:
            origin_dt = datetime.strptime(origin_time, '%H:%M')
            dest_dt = datetime.strptime(destination_time, '%H:%M')
            
            # If destination time is earlier than origin time, it's the next day
            if dest_dt < origin_dt:
                # Add 24 hours to destination to account for day rollover
                dest_dt = dest_dt + timedelta(days=1)
            
            duration = dest_dt - origin_dt
            total_seconds = duration.total_seconds()
            total_hours = round(total_seconds / 3600)  # Round to nearest hour
            days = total_hours // 24
            remaining_hours = total_hours % 24
            
            # Format the duration string properly
            if days > 0:
                if remaining_hours > 0:
                    route['duration_hours'] = f"{days} day{'s' if days > 1 else ''} {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
                else:
                    route['duration_hours'] = f"{days} day{'s' if days > 1 else ''}"
            else:
                route['duration_hours'] = f"{total_hours} hour{'s' if total_hours != 1 else ''}"
            
            # Update arrival time to reflect the actual destination
            route['arrival_time'] = destination_time
    
    return jsonify({'routes': routes})

@app.route('/api/stops/<int:route_id>', methods=['GET'])
def api_stops(route_id):
    """Get intermediate stops for a route."""
    stops = get_intermediate_stops(route_id)
    return jsonify({'stops': stops})

@app.route('/api/generate-schedule', methods=['POST'])
def generate_schedule():
    """Generate a complete trip schedule."""
    data = request.json
    route_id = data.get('route_id')
    selected_stops = data.get('selected_stops', [])
    start_date = data.get('start_date')
    origin_city = data.get('origin_city')
    destination_city = data.get('destination_city')
    
    if not route_id or not start_date:
        return jsonify({'error': 'Route ID and start date required'}), 400
    
    try:
        route = get_route_by_id(route_id)
        if not route:
            return jsonify({'error': 'Route not found'}), 404
        
        # Parse stop data: handle both old format (list of city names) and new format (list of objects)
        stop_durations = {}
        if selected_stops and isinstance(selected_stops[0], dict):
            for stop_data in selected_stops:
                stop_durations[stop_data['city']] = stop_data.get('duration', 0)
        else:
            # Old format: just city names
            for stop_city in selected_stops:
                stop_durations[stop_city] = 0
        
        # Use provided origin/destination, or fall back to route defaults
        actual_origin = origin_city if origin_city else route['origin_city']
        actual_destination = destination_city if destination_city else route['destination_city']
        
        print(f"\n[DEBUG] generate_schedule called")
        print(f"  Route: {route['route_name']} (ID: {route_id})")
        print(f"  Actual origin: {actual_origin}")
        print(f"  Actual destination: {actual_destination}")
        print(f"  Stop durations: {stop_durations}")
        
        # Parse the start date
        trip_date = datetime.strptime(start_date, '%Y-%m-%d')
        
        # Build schedule
        schedule = []
        current_date = trip_date
        
        # Get all stops for this route (in order)
        stops = get_intermediate_stops(route_id)
        
        # Find the start and end stop indices
        start_idx = None
        end_idx = None
        for i, stop in enumerate(stops):
            if stop['city_name'] == actual_origin:
                start_idx = i
            if stop['city_name'] == actual_destination:
                end_idx = i
        
        if start_idx is None or end_idx is None or start_idx >= end_idx:
            return jsonify({'error': f'Cannot find route from {actual_origin} to {actual_destination}'}), 400
        
        print(f"  Start index: {start_idx} ({stops[start_idx]['city_name']})")
        print(f"  End index: {end_idx} ({stops[end_idx]['city_name']})")
        print(f"  Stops to process: {[s['city_name'] for s in stops[start_idx:end_idx+1]]}")
        
        # Build complete journey with stops between origin and destination
        i = start_idx
        prev_stop_time = None
        while i <= end_idx:
            stop = stops[i]
            
            # Check if this is a selected stop or the destination
            is_selected = stop['city_name'] in stop_durations
            is_destination = stop['city_name'] == actual_destination
            is_origin = stop['city_name'] == actual_origin
            
            stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
            
            # Always add the origin stop
            if is_origin:
                current_date = trip_date
                schedule.append({
                    'city': stop['city_name'],
                    'event': 'Board',
                    'time': stop_time.strftime('%H:%M'),
                    'date': current_date.strftime('%Y-%m-%d')
                })
                prev_stop_time = stop_time
                i += 1
                continue
            
            # For all other stops (intermediate and destination), add them to show the full route
            # Detect day boundary: if current time is earlier than previous time, we've crossed midnight
            if prev_stop_time is not None and stop_time < prev_stop_time:
                current_date = current_date + timedelta(days=1)
                print(f"  [DATE ADVANCE] {stop['city_name']}: {stop_time} < {prev_stop_time}, advancing to {current_date}")
            
            print(f"  Processing {stop['city_name']} at {stop_time} on {current_date}")
            
            # Determine the event type: Disembark if destination OR if this is a selected stop (getting off)
            event_type = 'Disembark' if (is_destination or is_selected) else 'Stop'
            
            schedule.append({
                'city': stop['city_name'],
                'event': event_type,
                'time': stop_time.strftime('%H:%M'),
                'date': current_date.strftime('%Y-%m-%d')
            })
            # Update prev_stop_time for all stops to track date correctly
            prev_stop_time = stop_time
            
            # If this is a selected stop with a duration, add a duration row and find next departure
            if is_selected and stop['city_name'] in stop_durations:
                duration = stop_durations[stop['city_name']]
                
                # Calculate when user wants to leave
                stop_dt = datetime.combine(current_date, stop_time)
                desired_departure_dt = stop_dt + timedelta(hours=duration)
                
                print(f"\n[DEBUG] Stop at {stop['city_name']}")
                print(f"  Stop time: {stop_dt}")
                print(f"  Stop duration: {duration} hours")
                print(f"  Desired departure: {desired_departure_dt}")
                
                # Find next available train departing from this city at or after desired time
                next_available_departure = find_next_departure(
                    stop['city_name'],
                    desired_departure_dt,
                    actual_destination
                )
                
                print(f"  Next departure found: {next_available_departure}")
                
                if next_available_departure:
                    depart_time, depart_date, connecting_stops = next_available_departure
                    
                    # Calculate actual stop duration (from arrival to actual departure)
                    actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                    actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                    
                    # Only add duration row if actual duration > 0
                    if actual_duration_hours > 0:
                        # Add duration row showing ACTUAL stop duration with START date (arrival date)
                        schedule.append({
                            'city': stop['city_name'],
                            'event': f'{actual_duration_hours} hour stop' if actual_duration_hours != 1 else '1 hour stop',
                            'time': stop_time.strftime('%H:%M'),
                            'date': current_date.strftime('%Y-%m-%d')
                        })
                        
                        # Add a Board event for reboarding at actual departure time
                        schedule.append({
                            'city': stop['city_name'],
                            'event': 'Board',
                            'time': depart_time,
                            'date': depart_date
                        })
                    # Add all stops from this new segment until we reach the destination
                    # Skip the first stop since it's the city we're departing from (already added above)
                    connecting_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
                    # Initialize prev_time to the departure city's time for proper date tracking
                    connecting_prev_time = datetime.strptime(connecting_stops[0]['stop_time'], '%H:%M').time() if connecting_stops else None
                    for next_stop in connecting_stops[1:]:  # Skip first stop (same as current city)
                        next_is_destination = next_stop['city_name'] == actual_destination
                        next_time = datetime.strptime(next_stop['stop_time'], '%H:%M').time()
                        
                        # Track day changes within connecting stops
                        if connecting_prev_time is not None and next_time < connecting_prev_time:
                            connecting_date = connecting_date + timedelta(days=1)
                        
                        next_dt = datetime.combine(connecting_date, next_time)
                        
                        schedule.append({
                            'city': next_stop['city_name'],
                            'event': 'Disembark' if next_is_destination else 'Stop',
                            'time': next_time.strftime('%H:%M'),
                            'date': next_dt.strftime('%Y-%m-%d')
                        })
                        
                        connecting_prev_time = next_time
                        
                        # Stop adding once we reach actual destination
                        if next_is_destination:
                            break
                    
                    # After processing connecting stops, we've reached the destination
                    # Calculate total duration from first to last event
                    first_event = schedule[0]
                    last_event = schedule[-1]
                    start_dt = datetime.strptime(f"{first_event['date']} {first_event['time']}", '%Y-%m-%d %H:%M')
                    end_dt = datetime.strptime(f"{last_event['date']} {last_event['time']}", '%Y-%m-%d %H:%M')
                    total_duration = end_dt - start_dt
                    hours = int(total_duration.total_seconds() // 3600)
                    days = hours // 24
                    hours = hours % 24
                    duration_str = f"{days} days {hours} hours" if days > 0 else f"{hours} hours"
                    
                    # Return early to avoid adding more stops from the main route
                    return jsonify({
                        'schedule': schedule,
                        'route_name': route['route_name'],
                        'total_duration': duration_str
                    })
            
            i += 1
        
        # Calculate total duration from first to last event
        if schedule:
            first_event = schedule[0]
            last_event = schedule[-1]
            start_dt = datetime.strptime(f"{first_event['date']} {first_event['time']}", '%Y-%m-%d %H:%M')
            end_dt = datetime.strptime(f"{last_event['date']} {last_event['time']}", '%Y-%m-%d %H:%M')
            total_duration = end_dt - start_dt
            hours = int(total_duration.total_seconds() // 3600)
            days = hours // 24
            hours = hours % 24
            duration_str = f"{days} days {hours} hours" if days > 0 else f"{hours} hours"
        else:
            duration_str = f"{route['duration_hours']} hours"
        
        return jsonify({
            'schedule': schedule,
            'route_name': route['route_name'],
            'total_duration': duration_str
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def find_next_departure(city, desired_departure_dt, destination):
    """
    Find the next available departure from a city at or after the desired time
    that reaches the destination.
    Returns (departure_time, departure_date, remaining_stops) or None
    """
    try:
        # Get all routes that pass through this city and reach the destination
        available_routes = get_routes_through_city_to_destination(city, destination)
        
        # Find routes that depart at or after the desired departure time
        for route_option in available_routes:
            route_id = route_option['id']
            stops = get_stops_between_cities(route_id, city, destination)
            
            if not stops:
                continue
            
            # Get the actual departure time from this city (first stop in the list)
            depart_time_str = stops[0]['stop_time']
            depart_time = datetime.strptime(depart_time_str, '%H:%M').time()
            desired_time_only = desired_departure_dt.time()
            
            # Create a full datetime to compare properly across day boundaries
            # Start by assuming the departure is on the same day as desired_departure_dt
            test_depart_dt = datetime.combine(desired_departure_dt.date(), depart_time)
            
            # If this time is before desired time on the same day, it must be the next day's train
            if test_depart_dt < desired_departure_dt:
                test_depart_dt = test_depart_dt + timedelta(days=1)
            
            # Check if this train departs at or after the desired departure time
            if test_depart_dt >= desired_departure_dt:
                # This train works! Return it with the correct date
                return (depart_time_str, test_depart_dt.strftime('%Y-%m-%d'), stops)
        
        # If no train found in the above list, try looking at all routes again
        # and return the first one from the day after desired departure
        if available_routes:
            for route_option in available_routes:
                route_id = route_option['id']
                stops = get_stops_between_cities(route_id, city, destination)
                if stops:
                    # Return with the next day's date and actual departure time from this city
                    first_depart_time = stops[0]['stop_time']
                    next_day = desired_departure_dt + timedelta(days=1)
                    return (first_depart_time, next_day.strftime('%Y-%m-%d'), stops)
        
        return None
    except Exception as e:
        print(f"Error in find_next_departure: {e}")
        return None



@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5000)
