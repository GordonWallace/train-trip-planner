// Global state
let currentRoute = null;
let allCities = [];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadCities();
    setupEventListeners();
    setMinDate();
});

// Set minimum date to today
function setMinDate() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('startDate').setAttribute('min', today);
}

// Setup event listeners
function setupEventListeners() {
    document.getElementById('searchBtn').addEventListener('click', searchRoutes);
    document.getElementById('generateBtn').addEventListener('click', generateSchedule);
    document.getElementById('newTripBtn').addEventListener('click', resetForm);
    document.getElementById('backBtn').addEventListener('click', goBack);
    document.getElementById('downloadBtn').addEventListener('click', downloadSchedule);
}

// Load all cities
async function loadCities() {
    try {
        const response = await fetch('/api/cities');
        const data = await response.json();
        allCities = data.cities;
        populateCitySelects();
    } catch (error) {
        console.error('Error loading cities:', error);
        showError('Failed to load cities');
    }
}

// Populate city dropdown selects
function populateCitySelects() {
    const originSelect = document.getElementById('origin');
    const destinationSelect = document.getElementById('destination');
    
    allCities.forEach(city => {
        const option1 = document.createElement('option');
        option1.value = city;
        option1.textContent = city;
        originSelect.appendChild(option1);
        
        const option2 = document.createElement('option');
        option2.value = city;
        option2.textContent = city;
        destinationSelect.appendChild(option2);
    });
}

// Search for routes
async function searchRoutes() {
    const origin = document.getElementById('origin').value;
    const destination = document.getElementById('destination').value;
    const startDate = document.getElementById('startDate').value;
    
    if (!origin || !destination || !startDate) {
        showError('Please fill in all fields');
        return;
    }
    
    if (origin === destination) {
        showError('Origin and destination must be different');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/routes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ origin, destination })
        });
        
        const data = await response.json();
        
        if (!data.routes || data.routes.length === 0) {
            showError('No routes found between these cities');
            showLoading(false);
            return;
        }
        
        displayRoutes(data.routes);
        document.getElementById('routesSection').style.display = 'block';
        document.querySelector('.planning-section').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error searching routes:', error);
        showError('Error searching for routes');
    } finally {
        showLoading(false);
    }
}

// Display available routes
function displayRoutes(routes) {
    const routesList = document.getElementById('routesList');
    routesList.innerHTML = '';
    
    routes.forEach(route => {
        const card = document.createElement('div');
        card.className = 'route-card';
        card.innerHTML = `
            <h3>${route.route_name}</h3>
            <div class="route-info">
                <div class="route-info-item">
                    <span class="route-label">Departure:</span> ${route.departure_time}
                </div>
                <div class="route-info-item">
                    <span class="route-label">Arrival:</span> ${route.arrival_time}
                </div>
                <div class="route-info-item">
                    <span class="route-label">Duration:</span> ${route.duration_hours} hours
                </div>
                <div class="route-info-item">
                    <span class="route-label">Route #:</span> ${route.route_number}
                </div>
            </div>
        `;
        
        card.addEventListener('click', () => selectRoute(route));
        routesList.appendChild(card);
    });
}

// Select a route and load its stops
async function selectRoute(route) {
    currentRoute = route;
    
    // Update UI to show selected route
    document.querySelectorAll('.route-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/stops/${route.id}`);
        const data = await response.json();
        
        displayStops(data.stops, route);
        document.getElementById('stopsSection').style.display = 'block';
        document.getElementById('stopsSection').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error loading stops:', error);
        showError('Error loading stops');
    } finally {
        showLoading(false);
    }
}

// Display stops for selection
function displayStops(stops, route) {
    const stopsList = document.getElementById('stopsList');
    stopsList.innerHTML = `
        <div class="stop-item checked">
            <input type="checkbox" id="stop-origin" checked disabled data-city="${route.origin_city}">
            <label for="stop-origin">${route.origin_city} - <strong>Origin (Departure: ${route.departure_time})</strong></label>
        </div>
    `;
    
    stops.forEach(stop => {
        const stopItem = document.createElement('div');
        stopItem.className = 'stop-item';
        const stopId = `stop-${stop.id}`;
        
        stopItem.innerHTML = `
            <div class="stop-checkbox-container">
                <input type="checkbox" id="${stopId}" data-city="${stop.city_name}">
                <label for="${stopId}">${stop.city_name} - Arrival: ${stop.stop_time}</label>
            </div>
            <div class="stop-duration-container" id="duration-${stopId}" style="display: none;">
                <label for="duration-input-${stopId}">Stop duration (hours):</label>
                <input type="number" id="duration-input-${stopId}" min="0" max="24" step="0.5" value="2" class="duration-input">
            </div>
        `;
        
        const checkbox = stopItem.querySelector('input[type="checkbox"]');
        const durationContainer = stopItem.querySelector(`#duration-${stopId}`);
        const durationInput = stopItem.querySelector(`.duration-input`);
        
        checkbox.addEventListener('change', function() {
            if (this.checked) {
                stopItem.classList.add('checked');
                durationContainer.style.display = 'flex';
            } else {
                stopItem.classList.remove('checked');
                durationContainer.style.display = 'none';
            }
        });
        
        stopsList.appendChild(stopItem);
    });
    
    // Add destination if not already in stops
    const lastStop = stops[stops.length - 1];
    if (lastStop && lastStop.city_name !== route.destination_city) {
        const destItem = document.createElement('div');
        destItem.className = 'stop-item checked';
        destItem.innerHTML = `
            <div class="stop-checkbox-container">
                <input type="checkbox" id="stop-dest" checked disabled data-city="${route.destination_city}">
                <label for="stop-dest">${route.destination_city} - <strong>Destination (Arrival: ${route.arrival_time})</strong></label>
            </div>
        `;
        stopsList.appendChild(destItem);
    }
}

// Generate the trip schedule
async function generateSchedule() {
    const selectedStopsData = [];
    
    // Get all checked stops with their durations
    document.querySelectorAll('.stop-item input[type="checkbox"]:checked:not(:disabled)').forEach(checkbox => {
        const city = checkbox.getAttribute('data-city');
        if (city) {
            // Find the duration input for this stop
            const stopId = checkbox.id;
            const durationInput = document.querySelector(`#duration-input-${stopId}`);
            const duration = durationInput ? parseFloat(durationInput.value) : 0;
            
            selectedStopsData.push({
                city: city,
                duration: duration
            });
        }
    });
    
    const startDate = document.getElementById('startDate').value;
    
    if (!currentRoute || !startDate) {
        showError('Please select a route and date');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/generate-schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                route_id: currentRoute.id,
                selected_stops: selectedStopsData,
                start_date: startDate
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displaySchedule(data);
            document.getElementById('stopsSection').style.display = 'none';
            document.getElementById('routesSection').style.display = 'none';
            document.getElementById('scheduleSection').style.display = 'block';
            document.getElementById('scheduleSection').scrollIntoView({ behavior: 'smooth' });
        } else {
            showError(data.error || 'Error generating schedule');
        }
    } catch (error) {
        console.error('Error generating schedule:', error);
        showError('Error generating schedule');
    } finally {
        showLoading(false);
    }
}

// Display the generated schedule
function displaySchedule(data) {
    document.getElementById('scheduleTitleRoute').textContent = `Trip Schedule - ${data.route_name} (${data.total_duration})`;
    
    const scheduleBody = document.getElementById('scheduleBody');
    scheduleBody.innerHTML = '';
    
    // Get selected stops with durations for reference
    const selectedStopsMap = {};
    document.querySelectorAll('.stop-item input[type="checkbox"]:checked:not(:disabled)').forEach(checkbox => {
        const city = checkbox.getAttribute('data-city');
        if (city) {
            const stopId = checkbox.id;
            const durationInput = document.querySelector(`#duration-input-${stopId}`);
            const duration = durationInput ? parseFloat(durationInput.value) : 0;
            selectedStopsMap[city] = duration;
        }
    });
    
    // Track which selected stops have already had their duration rows added
    const durationRowsAdded = new Set();
    
    data.schedule.forEach((event, index) => {
        // Check if the next event is a reboarding event (same city, both Stop events)
        const nextEvent = index + 1 < data.schedule.length ? data.schedule[index + 1] : null;
        const isBeforeReboarding = nextEvent && nextEvent.city === event.city && event.event === 'Stop' && nextEvent.event === 'Stop';
        
        // If this is a Stop event at a selected stop with duration, and the next event is reboarding,
        // add the duration row BEFORE adding the reboarding event
        if (isBeforeReboarding && selectedStopsMap.hasOwnProperty(event.city) && selectedStopsMap[event.city] > 0 && !durationRowsAdded.has(event.city)) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${event.date}</td>
                <td>${event.time}</td>
                <td><strong>${event.city}</strong></td>
                <td>${event.event}</td>
            `;
            scheduleBody.appendChild(row);
            
            // Add duration row
            const durationRow = document.createElement('tr');
            durationRow.className = 'duration-row';
            const stopDuration = selectedStopsMap[event.city];
            const arrivalTime = new Date(`${event.date}T${event.time}`);
            const departureTime = new Date(arrivalTime.getTime() + stopDuration * 60 * 60 * 1000);
            const departureTimeStr = departureTime.toTimeString().slice(0, 5);
            
            durationRow.innerHTML = `
                <td>${departureTime.toISOString().split('T')[0]}</td>
                <td>${departureTimeStr}</td>
                <td><em>${event.city} - Stop Duration</em></td>
                <td>${stopDuration} hour(s)</td>
            `;
            scheduleBody.appendChild(durationRow);
            durationRowsAdded.add(event.city);
            
            // Skip adding this event again, move to next
            return;
        }
        
        // Add the normal event row
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${event.date}</td>
            <td>${event.time}</td>
            <td><strong>${event.city}</strong></td>
            <td>${event.event}</td>
        `;
        scheduleBody.appendChild(row);
    });
}

// Download schedule as CSV
function downloadSchedule() {
    const rows = [];
    const table = document.getElementById('scheduleTable');
    
    // Add headers
    const headers = [];
    table.querySelectorAll('th').forEach(th => {
        headers.push(th.textContent);
    });
    rows.push(headers.join(','));
    
    // Add data rows
    table.querySelectorAll('tbody tr').forEach(tr => {
        const cells = [];
        tr.querySelectorAll('td').forEach(td => {
            cells.push(`"${td.textContent}"`);
        });
        rows.push(cells.join(','));
    });
    
    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `train-schedule-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// Go back to stops selection
function goBack() {
    document.getElementById('stopsSection').style.display = 'block';
    document.getElementById('scheduleSection').style.display = 'none';
    document.getElementById('stopsSection').scrollIntoView({ behavior: 'smooth' });
}

// Reset the form and start over
function resetForm() {
    currentRoute = null;
    document.getElementById('origin').value = '';
    document.getElementById('destination').value = '';
    document.getElementById('startDate').value = '';
    document.getElementById('routesSection').style.display = 'none';
    document.getElementById('stopsSection').style.display = 'none';
    document.getElementById('scheduleSection').style.display = 'none';
    document.querySelector('.planning-section').scrollIntoView({ behavior: 'smooth' });
}

// Show/hide loading spinner
function showLoading(show) {
    const spinner = document.getElementById('loadingSpinner');
    if (show) {
        spinner.style.display = 'flex';
    } else {
        spinner.style.display = 'none';
    }
}

// Show error message
function showError(message) {
    const existingError = document.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
    
    const error = document.createElement('div');
    error.className = 'error-message';
    error.textContent = message;
    
    document.querySelector('main').insertBefore(error, document.querySelector('main').firstChild);
    
    setTimeout(() => {
        error.remove();
    }, 5000);
}
