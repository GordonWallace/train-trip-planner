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
        card.className = 'route-card' + (route.is_connection ? ' connection-route' : '');
        
        // Build the connection info if this is a connection route
        const connectionInfo = route.is_connection ? 
            `<div class="connection-info">
                <span class="connection-badge">🔗 Connection via ${route.connection_hub}</span>
            </div>` : '';
        
        card.innerHTML = `
            <h3>${route.route_name}</h3>
            ${connectionInfo}
            <div class="route-info">
                <div class="route-info-item">
                    <span class="route-label">Departure:</span> ${route.departure_time}
                </div>
                <div class="route-info-item">
                    <span class="route-label">Arrival:</span> ${route.arrival_time}
                </div>
                <div class="route-info-item">
                    <span class="route-label">Duration:</span> ${route.duration_hours}
                </div>
                <div class="route-info-item">
                    <span class="route-label">Route #:</span> ${route.id}
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
    
    // Get search origin and destination
    const searchOrigin = document.getElementById('origin').value;
    const searchDestination = document.getElementById('destination').value;
    
    // Update UI to show selected route
    document.querySelectorAll('.route-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
    
    showLoading(true);
    
    try {
        // For connection routes, we need to load stops from both routes
        if (route.is_connection) {
            // For connections, just show a combined stops section
            // We'll handle stop selection for both routes
            const stops1Response = await fetch(`/api/stops/${route.route1_id}`);
            const stops1Data = await stops1Response.json();
            
            const stops2Response = await fetch(`/api/stops/${route.route2_id}`);
            const stops2Data = await stops2Response.json();
            
            // Display stops for connection route (show both segments)
            displayConnectionStops(stops1Data.stops, stops2Data.stops, route, searchOrigin, searchDestination);
        } else {
            // For regular routes, proceed normally
            const response = await fetch(`/api/stops/${route.id}`);
            const data = await response.json();
            
            displayStops(data.stops, route, searchOrigin, searchDestination);
        }
        
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
function displayStops(stops, route, searchOrigin, searchDestination) {
    const stopsList = document.getElementById('stopsList');
    stopsList.innerHTML = `
        <div class="stop-item checked">
            <input type="checkbox" id="stop-origin" checked disabled data-city="${searchOrigin}">
            <label for="stop-origin">${searchOrigin} - <strong>Origin (Departure: ${route.departure_time})</strong></label>
        </div>
    `;
    
    // Find the indices of origin and destination in the stops array
    let originIndex = -1;
    let destinationIndex = stops.length - 1;
    
    stops.forEach((stop, index) => {
        if (stop.city_name === searchOrigin && originIndex === -1) {
            originIndex = index;
        }
        if (stop.city_name === searchDestination) {
            destinationIndex = index;
        }
    });
    
    // Find the destination stop to get its arrival time
    let destinationArrivalTime = route.arrival_time;
    if (destinationIndex >= 0 && destinationIndex < stops.length) {
        destinationArrivalTime = stops[destinationIndex].stop_time;
    }
    
    // Display only stops between origin and destination (exclusive of both)
    for (let i = originIndex + 1; i < destinationIndex; i++) {
        if (i < stops.length) {
            const stop = stops[i];
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
        }
    }
    
    // Add destination (with correct arrival time)
    const destItem = document.createElement('div');
    destItem.className = 'stop-item checked';
    destItem.innerHTML = `
        <div class="stop-checkbox-container">
            <input type="checkbox" id="stop-dest" checked disabled data-city="${searchDestination}">
            <label for="stop-dest">${searchDestination} - <strong>Destination (Arrival: ${destinationArrivalTime})</strong></label>
        </div>
    `;
    stopsList.appendChild(destItem);
}

// Display stops for connection routes (two segments)
function displayConnectionStops(stops1, stops2, route, searchOrigin, searchDestination) {
    const stopsList = document.getElementById('stopsList');
    stopsList.innerHTML = '';
    
    // Add a header for the first route segment at the very beginning
    const header1 = document.createElement('div');
    header1.className = 'segment-header route1-header';
    header1.innerHTML = `<strong>🚆 ${route.route_name.split(' → ')[0]}</strong>`;
    stopsList.appendChild(header1);
    
    // Add origin stop (no checkbox, just like hub departure info)
    const originItem = document.createElement('div');
    originItem.className = 'stop-item route1-stop';
    originItem.innerHTML = `
        <div class="stop-checkbox-container">
            <label>${searchOrigin} - <strong>Origin (Departure: ${route.departure_time})</strong></label>
        </div>
    `;
    stopsList.appendChild(originItem);
    
    // Find indices for first route
    let originIndex = -1;
    let hubIndex = stops1.length - 1;
    
    stops1.forEach((stop, index) => {
        if (stop.city_name === searchOrigin && originIndex === -1) {
            originIndex = index;
        }
        if (stop.city_name === route.connection_hub) {
            hubIndex = index;
        }
    });
    
    // Display stops from origin to hub on first route (skip the origin since we already rendered it)
    for (let i = originIndex + 1; i <= hubIndex && i < stops1.length; i++) {
        const stop = stops1[i];
        const stopItem = document.createElement('div');
        stopItem.className = 'stop-item route1-stop';
        const stopId = `stop1-${stop.id}`;
        
        const isHub = stop.city_name === route.connection_hub;
        
        stopItem.innerHTML = `
            <div class="stop-checkbox-container">
                <input type="checkbox" id="${stopId}" data-city="${stop.city_name}">
                <label for="${stopId}">${stop.city_name}${isHub ? ' - <strong>Connection Hub</strong>' : ''} - Arrival: ${stop.stop_time}</label>
            </div>
            <div class="stop-duration-container" id="duration-${stopId}" style="display: none;">
                <label for="duration-input-${stopId}">Stop duration (hours):</label>
                <input type="number" id="duration-input-${stopId}" min="0" max="24" step="0.5" value="2" class="duration-input">
            </div>
        `;
        
        const checkbox = stopItem.querySelector('input[type="checkbox"]');
        const durationContainer = stopItem.querySelector(`#duration-${stopId}`);
        
        checkbox.addEventListener('change', function() {
            if (this.checked) {
                stopItem.classList.add('checked');
                if (durationContainer) durationContainer.style.display = 'flex';
            } else {
                stopItem.classList.remove('checked');
                if (durationContainer) durationContainer.style.display = 'none';
            }
        });
        
        stopsList.appendChild(stopItem);
    }
    
    // Add a header for the second route segment
    const header2 = document.createElement('div');
    header2.className = 'segment-header route2-header';
    header2.innerHTML = `<strong>🚆 ${route.route_name.split(' → ')[1]}</strong>`;
    stopsList.appendChild(header2);
    
    // Add connection hub departure info from second route (after header2)
    const hubDepartureInfo = document.createElement('div');
    hubDepartureInfo.className = 'stop-item hub-departure-info';
    
    // Find the departure time from the hub on route 2
    let hubDepartureTime = null;
    stops2.forEach((stop) => {
        if (stop.city_name === route.connection_hub && !hubDepartureTime) {
            hubDepartureTime = stop.stop_time;
        }
    });
    
    hubDepartureInfo.innerHTML = `
        <div class="stop-checkbox-container">
            <label>${route.connection_hub} - <strong>Departure: ${hubDepartureTime}</strong></label>
        </div>
    `;
    stopsList.appendChild(hubDepartureInfo);
    
    // Find indices for second route
    let hubIndex2 = -1;
    let destIndex2 = stops2.length - 1;
    
    stops2.forEach((stop, index) => {
        if (stop.city_name === route.connection_hub && hubIndex2 === -1) {
            hubIndex2 = index;
        }
        if (stop.city_name === searchDestination) {
            destIndex2 = index;
        }
    });
    
    // Display stops from hub to destination on second route (skip hub as it's shown in segment 1)
    for (let i = hubIndex2 + 1; i < destIndex2 && i < stops2.length; i++) {
        const stop = stops2[i];
        const stopItem = document.createElement('div');
        stopItem.className = 'stop-item route2-stop';
        const stopId = `stop2-${stop.id}`;
        
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
    }
    
    // Add destination (no checkbox, just like hub departure info)
    const destItem = document.createElement('div');
    destItem.className = 'stop-item route2-stop';
    destItem.innerHTML = `
        <div class="stop-checkbox-container">
            <label>${searchDestination} - <strong>Destination (Arrival: ${route.arrival_time})</strong></label>
        </div>
    `;
    stopsList.appendChild(destItem);
}

// Generate the trip schedule
async function generateSchedule() {
    const selectedStopsData = [];
    
    // Get origin from global variable
    const originCity = searchOrigin;
    
    // Get all checked intermediate stops with their durations (excluding disabled checkboxes)
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
    
    // Get destination from global variable
    const destinationCity = searchDestination;
    
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
                start_date: startDate,
                origin_city: originCity,
                destination_city: destinationCity
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
    
    let lastRouteName = null;
    
    data.schedule.forEach((event) => {
        // Add segment header if route changes
        const currentRouteName = event.route_name;
        if (lastRouteName !== null && lastRouteName !== currentRouteName && !currentRouteName.includes('Connecting')) {
            const headerRow = document.createElement('tr');
            headerRow.className = 'segment-header-row';
            headerRow.innerHTML = `
                <td colspan="4"><strong>🚆 ${currentRouteName}</strong></td>
            `;
            scheduleBody.appendChild(headerRow);
        }
        lastRouteName = currentRouteName;
        
        const row = document.createElement('tr');
        
        // Check if this is a stop duration row or layover row
        if (event.event.includes('hour stop') || event.event.includes('layover')) {
            row.className = 'duration-row';
        }
        
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
