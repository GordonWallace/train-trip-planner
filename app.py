"""
Flask backend for the train trip planner application.
"""
from flask import Flask, render_template, jsonify, request
from database import init_database, get_all_cities, get_routes_between_cities, get_intermediate_stops, get_route_by_id
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
        
        # Parse the start date
        trip_date = datetime.strptime(start_date, '%Y-%m-%d')
        
        # Build schedule
        schedule = []
        current_date = trip_date
        
        # Get all stops for this route (in order)
        stops = get_intermediate_stops(route_id)
        
        # Build complete journey with all stops
        for stop in stops:
            # Check if this is a selected stop or the destination
            is_selected = stop['city_name'] in selected_stops
            is_destination = stop['city_name'] == route['destination_city']
            is_origin = stop['city_name'] == route['origin_city']
            
            if is_origin or is_selected or is_destination:
                arrival = datetime.strptime(stop['arrival_time'], '%H:%M').time()
                departure = datetime.strptime(stop['departure_time'], '%H:%M').time()
                
                # Detect day boundary by comparing times
                departure_hour = int(route['departure_time'].split(':')[0])
                if arrival.hour < departure_hour and not is_origin:
                    current_date = trip_date + timedelta(days=1)
                elif is_origin:
                    current_date = trip_date
                
                # Add arrival (unless it's the origin)
                if not is_origin:
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Arrival',
                        'time': arrival.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
                else:
                    # For origin, show departure
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Departure',
                        'time': departure.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
                    continue
                
                # Add departure (unless it's the destination)
                if not is_destination:
                    schedule.append({
                        'city': stop['city_name'],
                        'event': 'Departure',
                        'time': departure.strftime('%H:%M'),
                        'date': current_date.strftime('%Y-%m-%d')
                    })
        
        return jsonify({
            'schedule': schedule,
            'route_name': route['route_name'],
            'total_duration': f"{route['duration_hours']} hours"
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5000)
