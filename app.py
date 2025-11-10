"""
Flask backend for the train trip planner application.
"""
from flask import Flask, render_template, jsonify, request
from database import init_database, get_all_cities, get_routes_between_cities, get_intermediate_stops, get_route_by_id, get_all_routes_from_city, get_routes_through_city_to_destination, get_stops_from_city
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
        
        # Parse the start date
        trip_date = datetime.strptime(start_date, '%Y-%m-%d')
        
        # Build schedule
        schedule = []
        current_date = trip_date
        
        # Get all stops for this route (in order)
        stops = get_intermediate_stops(route_id)
        
        # Build complete journey with all stops
        i = 0
        while i < len(stops):
            stop = stops[i]
            
            # Check if this is a selected stop or the destination
            is_selected = stop['city_name'] in stop_durations
            is_destination = stop['city_name'] == route['destination_city']
            is_origin = stop['city_name'] == route['origin_city']
            
            if is_origin or is_selected or is_destination:
                stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
                
                # Detect day boundary
                route_departure_hour = int(route['departure_time'].split(':')[0])
                if stop_time.hour < route_departure_hour and not is_origin:
                    current_date = trip_date + timedelta(days=1)
                elif is_origin:
                    current_date = trip_date
                
                # Add stop (unless it's the origin)
                if not is_origin:
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Stop',
                        'time': stop_time.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
                    
                    # If this stop has a duration, find the next available departure
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
                            route['destination_city']
                        )
                        
                        print(f"  Next departure found: {next_available_departure}")
                        
                        if next_available_departure:
                            depart_time, depart_date, connecting_stops = next_available_departure
                            # Use the stop_time from the first stop in connecting_stops
                            first_stop = connecting_stops[0]
                            schedule.append({
                                'city': first_stop['city_name'],
                                'event': 'Stop',
                                'time': first_stop['stop_time'],
                                'date': depart_date
                            })
                            # Add all remaining stops from this new segment (skip the first, already added)
                            for next_stop in connecting_stops[1:]:
                                next_is_selected = next_stop['city_name'] in stop_durations
                                next_is_destination = next_stop['city_name'] == route['destination_city']
                                next_time = datetime.strptime(next_stop['stop_time'], '%H:%M').time()
                                depart_date_obj = datetime.strptime(depart_date, '%Y-%m-%d').date()
                                next_dt = datetime.combine(depart_date_obj, next_time)
                                # If time < previous time, increment day
                                if next_time < datetime.strptime(first_stop['stop_time'], '%H:%M').time():
                                    next_dt = next_dt + timedelta(days=1)
                                schedule.append({
                                    'city': next_stop['city_name'],
                                    'event': 'Stop',
                                    'time': next_time.strftime('%H:%M'),
                                    'date': next_dt.strftime('%Y-%m-%d')
                                })
                            # Skip to end of stops since we've processed the rest
                            break
                        else:
                            # No more trains available, use current schedule time
                            schedule.append({
                                'city': stop['city_name'],
                                'event': 'Stop',
                                'time': stop_time.strftime('%H:%M'),
                                'date': current_date.strftime('%Y-%m-%d')
                            })
                else:
                    # For origin, show stop
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Stop',
                        'time': stop_time.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
                    i += 1
                    continue
                
                # Add stop for non-selected stops or destination
                if not is_selected and not is_destination:
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Stop',
                        'time': stop_time.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
            
            i += 1
        
        return jsonify({
            'schedule': schedule,
            'route_name': route['route_name'],
            'total_duration': f"{route['duration_hours']} hours"
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
            depart_time_str = route_option['departure_time']
            depart_time = datetime.strptime(depart_time_str, '%H:%M').time()
            
            # Check if this train departs at or after the desired departure time
            desired_time_only = desired_departure_dt.time()
            
            if depart_time >= desired_time_only:
                # This train works! Get its stops from the current city onwards
                stops = get_stops_from_city(route_option['id'], city)
                
                if stops:
                    # Return with the same date (it's the first train on or after desired time)
                    return (depart_time_str, desired_departure_dt.strftime('%Y-%m-%d'), stops)
        
        # If no train found at or after desired time on the same day, 
        # return the first train from the next day
        if available_routes:
            first_route = available_routes[0]
            first_depart_time = first_route['departure_time']
            stops = get_stops_from_city(first_route['id'], city)
            
            if stops:
                # Return with the next day's date
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
