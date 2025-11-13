"""
Flask backend for the train trip planner application.
"""
from flask import Flask, render_template, jsonify, request
from database import init_database, get_all_cities, get_routes_between_cities, get_intermediate_stops, get_route_by_id, get_all_routes_from_city, get_routes_through_city_to_destination, get_stops_from_city, get_stops_between_cities
from datetime import datetime, timedelta

app = Flask(__name__)

def calculate_base_schedule_duration(route_id, origin_city, destination_city, start_date):
    """
    Calculate the base route duration by generating a schedule with no user-selected stops.
    This gives us the true duration of the route without any user-added layovers.
    """
    try:
        # Create a fake request context to call generate_schedule internally
        # We'll build the schedule with empty selected_stops
        from flask import Request
        from werkzeug.datastructures import ImmutableMultiDict
        
        # Manually invoke the schedule generation logic without going through Flask routing
        is_connection = isinstance(route_id, str) and route_id.startswith('conn_')
        
        if is_connection:
            parts = route_id.split('_')[1:]  # Skip 'conn' prefix
            route_ids = [int(r) for r in parts]
            
            # Use appropriate function based on number of hops
            if len(route_ids) == 2:
                from database import get_connection_route
                connection_data = get_connection_route(origin_city, destination_city, None, route_ids[0], route_ids[1])
            else:
                from database import get_multi_hop_connection_route
                connection_data = get_multi_hop_connection_route(origin_city, destination_city, route_ids)
            
            schedule = _build_connection_schedule(connection_data, origin_city, destination_city, start_date, {})
        else:
            schedule = _build_direct_schedule(route_id, origin_city, destination_city, start_date, {})
        
        return _calculate_schedule_duration_string(schedule)
    except Exception as e:
        print(f"Error calculating base duration: {e}")
        return 'Unknown'

def _calculate_schedule_duration_string(schedule):
    """Helper to calculate duration string from a schedule."""
    if schedule and len(schedule) > 0:
        first_event = schedule[0]
        last_event = schedule[-1]
        if first_event.get('time') and first_event.get('date') and last_event.get('time') and last_event.get('date'):
            try:
                start_dt = datetime.strptime(f"{first_event['date']} {first_event['time']}", '%Y-%m-%d %H:%M')
                end_dt = datetime.strptime(f"{last_event['date']} {last_event['time']}", '%Y-%m-%d %H:%M')
                total_duration = end_dt - start_dt
                hours = int(total_duration.total_seconds() // 3600)
                days = hours // 24
                hours = hours % 24
                return f"{days} days {hours} hours" if days > 0 else f"{hours} hours"
            except:
                return 'Unknown'
    return 'Unknown'

def _build_connection_schedule(connection_data, origin_city, destination_city, start_date, stop_durations):
    """
    Build a connection route schedule supporting N-hops.
    
    connection_data format:
    - For 2-hop (backward compat): {'segment1_stops': [...], 'segment2_stops': [...], 'route1': {...}, 'route2': {...}}
    - For N-hop: {'segments': [{'stops': [...], 'route': {...}}, ...], 'hubs': [...]}
    """
    # Handle both old and new format
    if 'segments' in connection_data:
        # New format: N-hop support
        segments = connection_data['segments']
    else:
        # Old format: Convert to new format for backward compatibility
        segments = [
            {'stops': connection_data['segment1_stops'], 'route': connection_data['route1']},
            {'stops': connection_data['segment2_stops'], 'route': connection_data['route2']}
        ]
    
    schedule = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    prev_stop_time = None
    
    # Process each segment
    for segment_idx, segment in enumerate(segments):
        is_first_segment = segment_idx == 0
        is_last_segment = segment_idx == len(segments) - 1
        stops = segment['stops']
        route = segment['route']
        
        # Add segment header for non-first segments
        if not is_first_segment:
            schedule.append({
                'city': '',
                'event': f"🚆 {route['route_name']}",
                'time': '',
                'date': '',
                'route_name': '',
                'is_segment_header': True
            })
        
        # Process stops in this segment
        for stop_idx, stop in enumerate(stops):
            if not stop.get('stop_time'):
                continue
            
            stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
            city_name = stop['city_name']
            is_origin = is_first_segment and stop_idx == 0
            is_hub = stop_idx == len(stops) - 1
            is_destination = is_last_segment and is_hub
            
            # Handle day wrap-around
            if prev_stop_time is not None and stop_time < prev_stop_time:
                current_date = current_date + timedelta(days=1)
            
            # Check if this stop has user-requested duration
            is_selected_with_duration = city_name in stop_durations and not is_hub
            
            if is_selected_with_duration:
                stop_dt = datetime.combine(current_date, stop_time)
                duration = stop_durations[city_name]
                desired_departure_dt = stop_dt + timedelta(hours=duration)
                
                # Find next available departure from this city
                next_city = destination_city if is_last_segment else (segments[segment_idx + 1]['stops'][0]['city_name'] if segment_idx + 1 < len(segments) else destination_city)
                next_available = find_next_departure(city_name, desired_departure_dt, next_city)
                
                if next_available:
                    depart_time, depart_date, connecting_stops = next_available
                    actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                    actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                    
                    if actual_duration_hours > 0:
                        schedule.append({
                            'city': city_name,
                            'event': f'{actual_duration_hours} hour stop' if actual_duration_hours != 1 else '1 hour stop',
                            'time': stop_time.strftime('%H:%M'),
                            'date': current_date.strftime('%Y-%m-%d'),
                            'route_name': route['route_name']
                        })
                        
                        schedule.append({
                            'city': city_name,
                            'event': 'Board',
                            'time': depart_time,
                            'date': depart_date,
                            'route_name': route['route_name']
                        })
                        
                        current_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
            else:
                # Regular stop (no user-requested duration)
                if not is_hub:
                    schedule.append({
                        'city': city_name,
                        'event': 'Board' if is_origin else 'Stop',
                        'time': stop_time.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d'),
                        'route_name': route['route_name']
                    })
                elif is_hub and not is_destination:
                    # This is a hub (connection point), not the final destination
                    # Will be handled as a layover below
                    pass
            
            prev_stop_time = stop_time
        
        # Handle layover at hub (for non-last segments)
        if not is_last_segment:
            hub_city = stops[-1]['city_name']
            hub_arrival_time = datetime.strptime(stops[-1]['stop_time'], '%H:%M').time()
            hub_arrival_dt = datetime.combine(current_date, hub_arrival_time)
            
            # Get departure info from next segment
            next_segment_stops = segments[segment_idx + 1]['stops']
            next_segment_departure_time = datetime.strptime(next_segment_stops[0]['stop_time'], '%H:%M').time()
            next_segment_departure_dt = datetime.combine(current_date, next_segment_departure_time)
            
            # Handle day wrap
            if next_segment_departure_dt < hub_arrival_dt:
                next_segment_departure_dt = next_segment_departure_dt + timedelta(days=1)
            
            hub_departure_dt = next_segment_departure_dt
            
            # Handle user-requested layover duration
            if hub_city in stop_durations:
                user_requested_duration = stop_durations[hub_city]
                if user_requested_duration > 0:
                    desired_earliest_departure = hub_arrival_dt + timedelta(hours=user_requested_duration)
                    if next_segment_departure_dt >= desired_earliest_departure:
                        hub_departure_dt = next_segment_departure_dt
                    else:
                        hub_departure_dt = next_segment_departure_dt + timedelta(days=1)
                        if hub_departure_dt < desired_earliest_departure:
                            hub_departure_dt = desired_earliest_departure
            
            # Add layover event
            layover_minutes = int((hub_departure_dt - hub_arrival_dt).total_seconds() / 60)
            schedule.append({
                'city': hub_city,
                'event': f'Disembark - {layover_minutes // 60} hour layover',
                'time': hub_arrival_time.strftime('%H:%M'),
                'date': current_date.strftime('%Y-%m-%d'),
                'route_name': route['route_name']
            })
            
            # Add boarding event for next segment
            next_route_name = segments[segment_idx + 1]['route']['route_name']
            schedule.append({
                'city': hub_city,
                'event': 'Board',
                'time': hub_departure_dt.time().strftime('%H:%M'),
                'date': hub_departure_dt.strftime('%Y-%m-%d'),
                'route_name': next_route_name
            })
            
            current_date = hub_departure_dt.date()
        else:
            # Last segment: add final disembark
            last_stop = stops[-1]
            if last_stop.get('stop_time'):
                last_stop_time = datetime.strptime(last_stop['stop_time'], '%H:%M').time()
                schedule.append({
                    'city': last_stop['city_name'],
                    'event': 'Disembark',
                    'time': last_stop_time.strftime('%H:%M'),
                    'date': current_date.strftime('%Y-%m-%d'),
                    'route_name': route['route_name']
                })
    
    return schedule

def _build_direct_schedule(route_id, origin_city, destination_city, start_date, stop_durations):
    """Build a direct route schedule and return it."""
    route = get_route_by_id(route_id)
    if not route:
        return []
    
    actual_origin = origin_city if origin_city else route['origin_city']
    actual_destination = destination_city if destination_city else route['destination_city']
    
    trip_date = datetime.strptime(start_date, '%Y-%m-%d')
    schedule = []
    current_date = trip_date
    
    stops = get_intermediate_stops(route_id)
    
    start_idx = None
    end_idx = None
    for i, stop in enumerate(stops):
        if stop['city_name'] == actual_origin:
            start_idx = i
        if stop['city_name'] == actual_destination:
            end_idx = i
    
    if start_idx is None or end_idx is None or start_idx >= end_idx:
        return []
    
    i = start_idx
    prev_stop_time = None
    current_date = trip_date
    consumed_cities = set()
    
    while i <= end_idx:
        stop = stops[i]
        
        if stop['city_name'] in consumed_cities:
            i += 1
            continue
        
        if not stop.get('stop_time'):
            i += 1
            continue
        
        is_selected = stop['city_name'] in stop_durations
        is_destination = stop['city_name'] == actual_destination
        is_origin = stop['city_name'] == actual_origin
        
        stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
        
        if is_origin:
            schedule.append({
                'city': stop['city_name'],
                'event': 'Board',
                'time': stop_time.strftime('%H:%M'),
                'date': current_date.strftime('%Y-%m-%d')
            })
            consumed_cities.add(stop['city_name'])
            prev_stop_time = stop_time
            i += 1
            continue
        
        if is_selected and stop['city_name'] in stop_durations:
            duration = stop_durations[stop['city_name']]
            
            stop_dt = datetime.combine(current_date, stop_time)
            desired_departure_dt = stop_dt + timedelta(hours=duration)
            
            next_available_departure = find_next_departure(
                stop['city_name'],
                desired_departure_dt,
                actual_destination
            )
            
            if next_available_departure:
                depart_time, depart_date, connecting_stops = next_available_departure
                
                actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                
                if actual_duration_hours > 0:
                    schedule.append({
                        'city': stop['city_name'],
                        'event': f'{actual_duration_hours} hour stop' if actual_duration_hours != 1 else '1 hour stop',
                        'time': stop_time.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
                    
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Board',
                        'time': depart_time,
                        'date': depart_date
                    })
                
                connecting_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
                connecting_prev_time = None
                
                if connecting_stops and connecting_stops[0].get('stop_time'):
                    connecting_prev_time = datetime.strptime(connecting_stops[0]['stop_time'], '%H:%M').time()
                
                for next_stop in connecting_stops[1:]:
                    if not next_stop.get('stop_time'):
                        continue
                        
                    next_is_destination = next_stop['city_name'] == actual_destination
                    next_is_selected = next_stop['city_name'] in stop_durations
                    next_time = datetime.strptime(next_stop['stop_time'], '%H:%M').time()
                    
                    if connecting_prev_time is not None and next_time < connecting_prev_time:
                        connecting_date = connecting_date + timedelta(days=1)
                    
                    next_dt = datetime.combine(connecting_date, next_time)
                    
                    if next_is_selected and not next_is_destination:
                        pass
                    else:
                        schedule.append({
                            'city': next_stop['city_name'],
                            'event': 'Disembark' if next_is_destination else 'Stop',
                            'time': next_time.strftime('%H:%M'),
                            'date': next_dt.strftime('%Y-%m-%d')
                        })
                        consumed_cities.add(next_stop['city_name'])
                    
                    connecting_prev_time = next_time
                    
                    if next_is_destination:
                        break
                    
                    if next_is_selected:
                        break
                
                current_date = connecting_date
                consumed_cities.add(stop['city_name'])
                
                i += 1
                while i <= end_idx and stops[i]['city_name'] in consumed_cities:
                    i += 1
                continue
        
        if not is_selected:
            if prev_stop_time is not None and stop_time < prev_stop_time:
                current_date = current_date + timedelta(days=1)
            
            schedule.append({
                'city': stop['city_name'],
                'event': 'Disembark' if is_destination else 'Stop',
                'time': stop_time.strftime('%H:%M'),
                'date': current_date.strftime('%Y-%m-%d')
            })
            consumed_cities.add(stop['city_name'])
            prev_stop_time = stop_time
        
        i += 1
    
    return schedule


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
    """Get routes between two cities, including connecting routes."""
    data = request.json
    origin = data.get('origin')
    destination = data.get('destination')
    
    if not origin or not destination:
        return jsonify({'error': 'Origin and destination required'}), 400
    
    all_routes = []
    
    # First, try to find direct routes
    direct_routes = get_routes_between_cities(origin, destination)
    
    for route in direct_routes:
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
                dest_dt = dest_dt + timedelta(days=1)
            
            duration = dest_dt - origin_dt
            total_seconds = duration.total_seconds()
            total_hours = round(total_seconds / 3600)
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
            
            # Update departure and arrival times to reflect the actual origin/destination
            route['departure_time'] = origin_time
            route['arrival_time'] = destination_time
            route['is_connection'] = False
            all_routes.append(route)
    
    # If no direct routes, try to find connecting routes
    if not all_routes:
        from database import find_connection_hubs, get_connection_route, get_multi_hop_connection_route
        
        connections = find_connection_hubs(origin, destination)
        
        for conn_info in connections:
            # Handle both 2-hop and N-hop connections
            route_ids = conn_info.get('route_ids', [])
            path_length = conn_info.get('path_length', 2)
            
            if path_length == 2:
                # 2-hop connection: use old format for backward compatibility
                connection_route = get_connection_route(
                    origin, 
                    destination, 
                    conn_info['hub'],
                    conn_info['route1_id'],
                    conn_info['route2_id']
                )
                
                seg1_stops = connection_route['segment1_stops']
                seg2_stops = connection_route['segment2_stops']
                
                # Get times
                origin_time = seg1_stops[0]['stop_time'] if seg1_stops else None
                hub_arrival_time = seg1_stops[-1]['stop_time'] if seg1_stops else None
                hub_departure_time = seg2_stops[0]['stop_time'] if seg2_stops else None
                destination_time = seg2_stops[-1]['stop_time'] if seg2_stops else None
                
                if origin_time and destination_time:
                    # Calculate actual duration by generating a base schedule
                    # Use today's date as a reference for schedule generation
                    reference_date = datetime.now().strftime('%Y-%m-%d')
                    route_id_str = f"conn_{connection_route['route1']['id']}_{connection_route['route2']['id']}"
                    duration_str = calculate_base_schedule_duration(
                        route_id_str,
                        origin,
                        destination,
                        reference_date
                    )
                    
                    route_info = {
                        'id': route_id_str,
                        'route_name': f"{connection_route['route1']['route_name']} → {connection_route['route2']['route_name']}",
                        'origin_city': origin,
                        'destination_city': destination,
                        'departure_time': origin_time,
                        'arrival_time': destination_time,
                        'duration_hours': duration_str,
                        'is_connection': True,
                        'connection_hub': conn_info['hub'],
                        'route1_id': connection_route['route1']['id'],
                        'route2_id': connection_route['route2']['id']
                    }
                    all_routes.append(route_info)
            else:
                # N-hop connection (3+ hops)
                connection_route = get_multi_hop_connection_route(origin, destination, route_ids)
                
                if connection_route and 'segments' in connection_route:
                    segments = connection_route['segments']
                    hubs = connection_route['hubs']
                    
                    # Get times from first and last segment
                    first_segment_stops = segments[0]['stops']
                    last_segment_stops = segments[-1]['stops']
                    
                    origin_time = first_segment_stops[0]['stop_time'] if first_segment_stops else None
                    destination_time = last_segment_stops[-1]['stop_time'] if last_segment_stops else None
                    
                    if origin_time and destination_time:
                        # Calculate actual duration by generating a base schedule
                        reference_date = datetime.now().strftime('%Y-%m-%d')
                        route_id_str = 'conn_' + '_'.join(str(rid) for rid in route_ids)
                        duration_str = calculate_base_schedule_duration(
                            route_id_str,
                            origin,
                            destination,
                            reference_date
                        )
                        
                        # Build route names for all segments
                        route_names = [seg['route']['route_name'] for seg in segments]
                        route_name = ' → '.join(route_names)
                        
                        route_info = {
                            'id': route_id_str,
                            'route_name': route_name,
                            'origin_city': origin,
                            'destination_city': destination,
                            'departure_time': origin_time,
                            'arrival_time': destination_time,
                            'duration_hours': duration_str,
                            'is_connection': True,
                            'hubs': hubs,
                            'route_ids': route_ids,
                            'path_length': path_length
                        }
                        all_routes.append(route_info)
    
    return jsonify({'routes': all_routes})

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
        # Check if this is a connection route
        is_connection = isinstance(route_id, str) and route_id.startswith('conn_')
        
        if is_connection:
            # Parse connection route ID (format: conn_route1_id_route2_id or conn_route1_id_route2_id_route3_id, etc.)
            parts = route_id.split('_')[1:]  # Skip 'conn' prefix
            route_ids = [int(r) for r in parts]
            
            # Use appropriate function based on number of hops
            if len(route_ids) == 2:
                from database import get_connection_route
                connection_data = get_connection_route(origin_city, destination_city, None, route_ids[0], route_ids[1])
            else:
                from database import get_multi_hop_connection_route
                connection_data = get_multi_hop_connection_route(origin_city, destination_city, route_ids)
            
            # Parse stop durations (for hub stop layovers)
            stop_durations = {}
            if selected_stops and isinstance(selected_stops[0], dict):
                for stop_data in selected_stops:
                    stop_durations[stop_data['city']] = stop_data.get('duration', 0)
            else:
                # Old format: just city names
                for stop_city in selected_stops:
                    stop_durations[stop_city] = 0
            
            # Generate schedule using generalized connection schedule builder
            schedule_data = _build_connection_schedule(connection_data, origin_city, destination_city, start_date, stop_durations)
            
            # Build route_name from all segments
            if 'segments' in connection_data:
                route_names = [seg['route']['route_name'] for seg in connection_data['segments']]
                route_name = ' → '.join(route_names)
            else:
                # Old format
                route_name = f"{connection_data['route1']['route_name']} → {connection_data['route2']['route_name']}"
            
            # Build the schedule using the generalized connection schedule builder
            schedule_data = _build_connection_schedule(connection_data, origin_city, destination_city, start_date, stop_durations)
            
            # Calculate total duration
            
            # Use the generalized schedule builder which handles N-hops
            schedule = _build_connection_schedule(connection_data, origin_city, destination_city, start_date, stop_durations)
            
            # Calculate total duration
            if schedule:
                # Filter out empty/header rows that don't have valid times
                valid_events = [e for e in schedule if e.get('time') and e.get('date')]
                if len(valid_events) >= 2:
                    first_event = valid_events[0]
                    last_event = valid_events[-1]
                    start_dt = datetime.strptime(f"{first_event['date']} {first_event['time']}", '%Y-%m-%d %H:%M')
                    end_dt = datetime.strptime(f"{last_event['date']} {last_event['time']}", '%Y-%m-%d %H:%M')
                    total_duration = end_dt - start_dt
                    hours = int(total_duration.total_seconds() // 3600)
                    days = hours // 24
                    hours = hours % 24
                    duration_str = f"{days} days {hours} hours" if days > 0 else f"{hours} hours"
                else:
                    duration_str = "Unknown"
            else:
                duration_str = "Unknown"
            
            return jsonify({
                'schedule': schedule,
                'route_name': route_name,
                'total_duration': duration_str
            })
        
        # Handle regular (non-connection) routes
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
        
        # Build complete journey with stops between origin and destination
        i = start_idx
        prev_stop_time = None
        current_date = trip_date
        
        while i <= end_idx:
            stop = stops[i]
            
            if not stop.get('stop_time'):
                i += 1
                continue
            
            stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
            
            # Handle day wrap-around
            if prev_stop_time is not None and stop_time < prev_stop_time:
                current_date = current_date + timedelta(days=1)
            
            is_origin = (i == start_idx)
            is_destination = (i == end_idx)
            city_name = stop['city_name']
            
            # Check if this is a selected stop with duration (but not origin or destination)
            is_selected_with_duration = city_name in stop_durations and not is_origin and not is_destination
            
            if is_selected_with_duration:
                # User wants to stop here for a specific duration
                stop_dt = datetime.combine(current_date, stop_time)
                duration = stop_durations[city_name]
                desired_departure_dt = stop_dt + timedelta(hours=duration)
                
                # Find next departure after requested duration
                next_available = find_next_departure(city_name, desired_departure_dt, actual_destination)
                
                if next_available:
                    depart_time, depart_date, connecting_stops = next_available
                    actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                    actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                    
                    if actual_duration_hours > 0:
                        # Add duration row
                        schedule.append({
                            'city': city_name,
                            'event': f'{actual_duration_hours} hour stop' if actual_duration_hours != 1 else '1 hour stop',
                            'time': stop_time.strftime('%H:%M'),
                            'date': current_date.strftime('%Y-%m-%d'),
                            'route_name': route['route_name']
                        })
                        
                        # Add board event (may be with next connecting train)
                        schedule.append({
                            'city': city_name,
                            'event': 'Board',
                            'time': depart_time,
                            'date': depart_date,
                            'route_name': route['route_name']
                        })
                        
                        current_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
            else:
                # Normal stop without user-requested duration
                if is_origin:
                    event = 'Board'
                elif is_destination:
                    event = 'Disembark'
                else:
                    event = 'Stop'
                
                schedule.append({
                    'city': city_name,
                    'event': event,
                    'time': stop_time.strftime('%H:%M'),
                    'date': current_date.strftime('%Y-%m-%d'),
                    'route_name': route['route_name']
                })
            
            prev_stop_time = stop_time
            i += 1
                if not stop.get('stop_time'):
                    continue  # Skip stops with no time data
                    
                stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
                is_origin = i == 0
                is_hub = i == len(stops1) - 1
                city_name = stop['city_name']
                
                if prev_stop_time is not None and stop_time < prev_stop_time:
                    current_date = current_date + timedelta(days=1)
                
                # Check if this is a selected stop with duration (but not the hub)
                is_selected_with_duration = city_name in stop_durations and not is_hub
                
                if is_selected_with_duration:
                    # Find next departure after requested duration
                    stop_dt = datetime.combine(current_date, stop_time)
                    duration = stop_durations[city_name]
                    desired_departure_dt = stop_dt + timedelta(hours=duration)
                    
                    # For intermediate stops on segment 1, find next train to the hub
                    next_available = find_next_departure(city_name, desired_departure_dt, hub_city)
                    
                    if next_available:
                        depart_time, depart_date, connecting_stops = next_available
                        actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                        actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                        
                        if actual_duration_hours > 0:
                            # Add duration row (replaces the regular Stop event)
                            schedule.append({
                                'city': city_name,
                                'event': f'{actual_duration_hours} hour stop' if actual_duration_hours != 1 else '1 hour stop',
                                'time': stop_time.strftime('%H:%M'),
                                'date': current_date.strftime('%Y-%m-%d'),
                                'route_name': connection_data['route1']['route_name']
                            })
                            
                            # Add board event
                            schedule.append({
                                'city': city_name,
                                'event': 'Board',
                                'time': depart_time,
                                'date': depart_date,
                                'route_name': connection_data['route1']['route_name']
                            })
                            
                            current_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
                else:
                    # Regular stop (not selected with duration)
                    # Skip hub city - it will be handled separately with the layover info
                    if not is_hub:
                        schedule.append({
                            'city': city_name,
                            'event': 'Board' if is_origin else 'Stop',
                            'time': stop_time.strftime('%H:%M'),
                            'date': current_date.strftime('%Y-%m-%d'),
                            'route_name': connection_data['route1']['route_name']
                        })
                
                prev_stop_time = stop_time
            
            # Add layover info at hub
            hub_departure_dt = None
            hub_departure_time = None
            
            if prev_stop_time and stops2 and stops2[0].get('stop_time'):
                hub_arrival_dt = datetime.combine(current_date, prev_stop_time)
                
                # Get the next train's departure time from segment 2
                next_train_departure_time = datetime.strptime(stops2[0]['stop_time'], '%H:%M').time()
                next_train_departure_dt = datetime.combine(current_date, next_train_departure_time)
                
                # If this departure is earlier than arrival, it's the next day
                if next_train_departure_dt < hub_arrival_dt:
                    next_train_departure_dt = next_train_departure_dt + timedelta(days=1)
                
                # Default: depart on the next available train
                hub_departure_dt = next_train_departure_dt
                
                # Check if user wants to stop at the hub for additional time
                if hub_city in stop_durations:
                    user_requested_duration = stop_durations[hub_city]
                    if user_requested_duration > 0:
                        # User wants to stay longer at the hub
                        desired_earliest_departure = hub_arrival_dt + timedelta(hours=user_requested_duration)
                        
                        # Check if next train departs after user's desired departure time
                        if next_train_departure_dt >= desired_earliest_departure:
                            # Take the next train (it departs after user wants to leave anyway)
                            hub_departure_dt = next_train_departure_dt
                        else:
                            # Next train is too early, so check the train the next day
                            # (assume same time the next day for this simple logic)
                            hub_departure_dt = next_train_departure_dt + timedelta(days=1)
                            # If that's still before desired departure, push to desired time
                            if hub_departure_dt < desired_earliest_departure:
                                hub_departure_dt = desired_earliest_departure
                
                layover_minutes = int((hub_departure_dt - hub_arrival_dt).total_seconds() / 60)
                
                # Add combined disembark + layover event with arrival time
                schedule.append({
                    'city': hub_city,
                    'event': f'Disembark - {layover_minutes // 60} hour layover',
                    'time': prev_stop_time.strftime('%H:%M'),
                    'date': current_date.strftime('%Y-%m-%d'),
                    'route_name': connection_data['route1']['route_name']
                })
                
                current_date = hub_departure_dt.date()
                prev_stop_time = hub_departure_time
            else:
                # If we can't calculate layover, just get the departure time
                if stops2 and stops2[0].get('stop_time'):
                    hub_departure_time = datetime.strptime(stops2[0]['stop_time'], '%H:%M').time()
                    hub_departure_dt = datetime.combine(current_date, hub_departure_time)
                    prev_stop_time = hub_departure_time
                else:
                    # No valid departure time available
                    prev_stop_time = None
            
            # Add segment header and boarding event for segment 2
            if hub_departure_dt:
                current_date = hub_departure_dt.date()
                
                # Add segment header
                schedule.append({
                    'city': '',
                    'event': f"🚆 {connection_data['route2']['route_name']}",
                    'time': '',
                    'date': '',
                    'route_name': '',
                    'is_segment_header': True
                })
                
                # Add boarding event at hub with departure time
                schedule.append({
                    'city': hub_city,
                    'event': 'Board',
                    'time': hub_departure_dt.time().strftime('%H:%M'),
                    'date': hub_departure_dt.strftime('%Y-%m-%d'),
                    'route_name': connection_data['route2']['route_name']
                })
            else:
                current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            for i, stop in enumerate(stops2[1:], 1):
                if not stop.get('stop_time'):
                    continue  # Skip stops with no time data
                    
                stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
                is_destination = i == len(stops2) - 1
                city_name = stop['city_name']
                
                if prev_stop_time is not None and stop_time < prev_stop_time:
                    current_date = current_date + timedelta(days=1)
                
                # Check if this is a selected stop with duration (but not the destination)
                is_selected_with_duration = city_name in stop_durations and not is_destination
                
                if is_selected_with_duration:
                    # Find next departure after requested duration
                    stop_dt = datetime.combine(current_date, stop_time)
                    duration = stop_durations[city_name]
                    desired_departure_dt = stop_dt + timedelta(hours=duration)
                    
                    # For intermediate stops on segment 2, find next train to final destination
                    next_available = find_next_departure(city_name, desired_departure_dt, destination_city)
                    
                    if next_available:
                        depart_time, depart_date, connecting_stops = next_available
                        actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                        actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                        
                        if actual_duration_hours > 0:
                            # Add duration row (replaces the regular Stop event)
                            schedule.append({
                                'city': city_name,
                                'event': f'{actual_duration_hours} hour stop' if actual_duration_hours != 1 else '1 hour stop',
                                'time': stop_time.strftime('%H:%M'),
                                'date': current_date.strftime('%Y-%m-%d'),
                                'route_name': connection_data['route2']['route_name']
                            })
                            
                            # Add board event
                            schedule.append({
                                'city': city_name,
                                'event': 'Board',
                                'time': depart_time,
                                'date': depart_date,
                                'route_name': connection_data['route2']['route_name']
                            })
                            
                            current_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
                else:
                    # Regular stop (not selected with duration)
                    schedule.append({
                        'city': city_name,
                        'event': 'Disembark' if is_destination else 'Stop',
                        'time': stop_time.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d'),
                        'route_name': connection_data['route2']['route_name']
                    })
                
                prev_stop_time = stop_time
            
            # Calculate total duration
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
                duration_str = "Unknown"
            
            return jsonify({
                'schedule': schedule,
                'route_name': route_name,
                'total_duration': duration_str
            })
        
        # Handle regular (non-connection) routes
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
        
        # Build complete journey with stops between origin and destination
        i = start_idx
        prev_stop_time = None
        current_date = trip_date
        consumed_cities = set()  # Track cities already added to schedule
        
        while i <= end_idx:
            stop = stops[i]
            
            # Skip cities that were already added from a connecting segment
            if stop['city_name'] in consumed_cities:
                i += 1
                continue
            
            # Skip stops with no time data
            if not stop.get('stop_time'):
                i += 1
                continue
            
            # Check if this is a selected stop or the destination
            is_selected = stop['city_name'] in stop_durations
            is_destination = stop['city_name'] == actual_destination
            is_origin = stop['city_name'] == actual_origin
            
            stop_time = datetime.strptime(stop['stop_time'], '%H:%M').time()
            
            # Always add the origin stop
            if is_origin:
                schedule.append({
                    'city': stop['city_name'],
                    'event': 'Board',
                    'time': stop_time.strftime('%H:%M'),
                    'date': current_date.strftime('%Y-%m-%d')
                })
                consumed_cities.add(stop['city_name'])
                prev_stop_time = stop_time
                i += 1
                continue
            
            # Handle selected intermediate stops with duration
            if is_selected and stop['city_name'] in stop_durations:
                duration = stop_durations[stop['city_name']]
                
                # Calculate when user wants to leave
                stop_dt = datetime.combine(current_date, stop_time)
                desired_departure_dt = stop_dt + timedelta(hours=duration)
                
                # Find next available train departing from this city at or after desired time
                next_available_departure = find_next_departure(
                    stop['city_name'],
                    desired_departure_dt,
                    actual_destination
                )
                
                if next_available_departure:
                    depart_time, depart_date, connecting_stops = next_available_departure
                    
                    # Calculate actual stop duration (from arrival to actual departure)
                    actual_depart_dt = datetime.strptime(f"{depart_date} {depart_time}", '%Y-%m-%d %H:%M')
                    actual_duration_hours = round((actual_depart_dt - stop_dt).total_seconds() / 3600)
                    
                    # Only add duration row if actual duration > 0
                    if actual_duration_hours > 0:
                        # Add duration row showing ACTUAL stop duration with START date (arrival date)
                        # This replaces the regular Stop event
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
                    else:
                        # If no actual duration (immediate departure), just add a regular Stop
                        schedule.append({
                            'city': stop['city_name'],
                            'event': 'Stop',
                            'time': stop_time.strftime('%H:%M'),
                            'date': current_date.strftime('%Y-%m-%d')
                        })
                    
                    # Add all stops from this new segment until we reach the destination or another selected stop
                    connecting_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
                    connecting_prev_time = None
                    
                    # Get first stop's time if it exists
                    if connecting_stops and connecting_stops[0].get('stop_time'):
                        connecting_prev_time = datetime.strptime(connecting_stops[0]['stop_time'], '%H:%M').time()
                    
                    for next_stop in connecting_stops[1:]:  # Skip first stop (same as current city)
                        if not next_stop.get('stop_time'):
                            continue  # Skip stops with no time data
                            
                        next_is_destination = next_stop['city_name'] == actual_destination
                        next_is_selected = next_stop['city_name'] in stop_durations
                        next_time = datetime.strptime(next_stop['stop_time'], '%H:%M').time()
                        
                        # Track day changes within connecting stops
                        if connecting_prev_time is not None and next_time < connecting_prev_time:
                            connecting_date = connecting_date + timedelta(days=1)
                        
                        next_dt = datetime.combine(connecting_date, next_time)
                        
                        # Add all stops except those that are selected intermediate stops (not destination)
                        # Selected intermediate stops will be processed by main loop with their own duration logic
                        if next_is_selected and not next_is_destination:
                            # Don't add selected intermediate stops or mark them consumed
                            # Let main loop process them with their duration logic
                            pass
                        else:
                            # Add non-selected stops and the destination
                            schedule.append({
                                'city': next_stop['city_name'],
                                'event': 'Disembark' if next_is_destination else 'Stop',
                                'time': next_time.strftime('%H:%M'),
                                'date': next_dt.strftime('%Y-%m-%d')
                            })
                            consumed_cities.add(next_stop['city_name'])
                        
                        connecting_prev_time = next_time
                        
                        # If we hit the destination, stop adding
                        if next_is_destination:
                            break
                        
                        # If we hit a selected stop (not destination), still stop but don't mark consumed
                        if next_is_selected:
                            break
                    
                    # Update current_date for next iteration
                    current_date = connecting_date
                    consumed_cities.add(stop['city_name'])
                    
                    # Skip ahead in the main loop to the next stop after all consumed cities
                    # Find the next stop that hasn't been consumed
                    i += 1
                    while i <= end_idx and stops[i]['city_name'] in consumed_cities:
                        i += 1
                    continue
            
            # Handle destination or non-selected stops
            if not is_selected:
                # Check if we need to update current_date for day boundaries
                if prev_stop_time is not None and stop_time < prev_stop_time:
                    current_date = current_date + timedelta(days=1)
                
                schedule.append({
                    'city': stop['city_name'],
                    'event': 'Disembark' if is_destination else 'Stop',
                    'time': stop_time.strftime('%H:%M'),
                    'date': current_date.strftime('%Y-%m-%d')
                })
                consumed_cities.add(stop['city_name'])
                prev_stop_time = stop_time
            
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
