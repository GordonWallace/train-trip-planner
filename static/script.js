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
    document.getElementById('editBtn').addEventListener('click', editSchedule);
    document.getElementById('saveBtn').addEventListener('click', saveSchedule);
    document.getElementById('loadBtn').addEventListener('click', loadScheduleModal);
    document.getElementById('loadLandingBtn').addEventListener('click', loadScheduleModal);
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

// Helper function to get route-specific styling class
function getRouteClass(routeId, segmentIndex) {
    if (routeId === 1) return 'route1';
    if (routeId === 2) return 'route2';
    return `route${segmentIndex + 1}`;
}

// Unified function to render stops for both new routes and editing
// For new routes, pass an array with 1-2 items: [{stops: [...], route_id: 1}, {stops: [...], route_id: 2}]
// For editing, pass the same format from the edit function
function renderSegmentStops(segmentStopsArray, route, searchOrigin, searchDestination, isEditing = false) {
    const stopsList = document.getElementById('stopsList');
    stopsList.innerHTML = '';
    const connectionHub = route.connection_hub;
    
    segmentStopsArray.forEach((segment, segmentIndex) => {
        const stops = segment.stops;
        const isLastSegment = segmentIndex === segmentStopsArray.length - 1;
        const routeClass = getRouteClass(segment.route_id, segmentIndex);
        
        // Add segment header with route-specific styling
        const header = document.createElement('div');
        header.className = `segment-header ${routeClass}-header`;
        
        // Determine route name based on route_id
        let headerText = `Segment ${segmentIndex + 1}`;
        if (segment.route_id === 1) {
            headerText = 'Lake Shore Limited';
        } else if (segment.route_id === 2) {
            headerText = 'Southwest Chief';
        }
        
        header.innerHTML = `<strong>🚆 ${headerText}</strong>`;
        stopsList.appendChild(header);
        
        // Find origin and destination indices for this segment
        let originIndex = -1;
        let destinationIndex = stops.length - 1;
        
        const segmentOrigin = segmentIndex === 0 ? searchOrigin : connectionHub;
        const segmentDestination = isLastSegment ? searchDestination : connectionHub;
        
        stops.forEach((stop, index) => {
            if (stop.city_name === segmentOrigin && originIndex === -1) {
                originIndex = index;
            }
            if (stop.city_name === segmentDestination) {
                destinationIndex = index;
            }
        });
        
        // Add origin stop (non-selectable)
        if (originIndex >= 0 && originIndex < stops.length) {
            const originItem = document.createElement('div');
            originItem.className = `stop-item checked ${routeClass}-stop`;
            const stopLabel = segmentIndex === 0 ? 'Origin' : 'Connection Hub';
            originItem.innerHTML = `
                <div class="stop-checkbox-container">
                    <label>${stops[originIndex].city_name} - <strong>${stopLabel} (Departure: ${stops[originIndex].stop_time})</strong></label>
                </div>
            `;
            stopsList.appendChild(originItem);
        }
        
        // Add intermediate stops (selectable)
        for (let i = originIndex + 1; i < destinationIndex && i < stops.length; i++) {
            const stop = stops[i];
            const stopItem = document.createElement('div');
            stopItem.className = `stop-item ${routeClass}-stop`;
            const stopId = isEditing ? `stop-${segmentIndex}-${stop.id}` : `stop${segment.route_id}-${stop.id}`;
            
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
        
        // Add hub departure info (only for non-last segments in new routes)
        if (!isEditing && !isLastSegment) {
            const hubDepartureInfo = document.createElement('div');
            hubDepartureInfo.className = `stop-item hub-departure-info`;
            
            let hubDepartureTime = null;
            if (segmentIndex + 1 < segmentStopsArray.length) {
                const nextSegment = segmentStopsArray[segmentIndex + 1];
                nextSegment.stops.forEach((stop) => {
                    if (stop.city_name === connectionHub && !hubDepartureTime) {
                        hubDepartureTime = stop.stop_time;
                    }
                });
            }
            
            hubDepartureInfo.innerHTML = `
                <div class="stop-checkbox-container">
                    <label>${connectionHub} - <strong>Departure: ${hubDepartureTime}</strong></label>
                </div>
            `;
            stopsList.appendChild(hubDepartureInfo);
        }
        
        // Add destination stop (non-selectable)
        if (destinationIndex >= 0 && destinationIndex < stops.length) {
            const destItem = document.createElement('div');
            const destLabel = isLastSegment ? 'Destination' : 'Connection Hub';
            const arrivalTime = isLastSegment ? (isEditing ? route.arrival_time : route.arrival_time) : stops[destinationIndex].stop_time;
            destItem.className = `stop-item checked ${routeClass}-stop`;
            destItem.innerHTML = `
                <div class="stop-checkbox-container">
                    <label>${stops[destinationIndex].city_name} - <strong>${destLabel} (${isLastSegment ? 'Arrival' : 'Arrival'}: ${arrivalTime})</strong></label>
                </div>
            `;
            stopsList.appendChild(destItem);
        }
    });
}

// Display stops for connection routes (two segments) - now uses unified renderer
function displayConnectionStops(stops1, stops2, route, searchOrigin, searchDestination) {
    const segmentStopsArray = [
        { route_id: 1, stops: stops1 },
        { route_id: 2, stops: stops2 }
    ];
    renderSegmentStops(segmentStopsArray, route, searchOrigin, searchDestination, false);
}

// Display stops for connection routes during edit - now uses unified renderer
function displayConnectionStopsForEdit(segmentStopsArray, route, searchOrigin, searchDestination) {
    renderSegmentStops(segmentStopsArray, route, searchOrigin, searchDestination, true);
}

// Generate the trip schedule
async function generateSchedule() {
    const selectedStopsData = [];
    
    // Get origin and destination from form inputs
    const originCity = document.getElementById('origin').value;
    const destinationCity = document.getElementById('destination').value;
    
    // Check if we have a saved state from localStorage (e.g., from loading a schedule)
    // But only use it if the stops section is visible (meaning we just loaded and haven't edited yet)
    const stopsSection = document.getElementById('stopsSection');
    const savedState = localStorage.getItem('currentSchedule');
    let selectedStops = null;
    
    if (savedState && stopsSection.style.display === 'none') {
        // We're using a saved state and haven't shown the stops section for editing yet
        try {
            const state = JSON.parse(savedState);
            if (state.selected_stops && state.selected_stops.length > 0) {
                // Use the saved selected stops instead of reading from checkboxes
                selectedStops = state.selected_stops;
            }
        } catch (e) {
            console.error('Error parsing saved state:', e);
        }
    }
    
    // If we have saved stops to use (fresh from loading), use them; otherwise read from checked checkboxes
    if (selectedStops) {
        selectedStopsData.push(...selectedStops);
        // Clear localStorage so we don't reuse this state on the next schedule generation
        localStorage.removeItem('currentSchedule');
    } else {
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
    }
    
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
            displaySchedule(data, selectedStopsData);
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
function displaySchedule(data, selectedStopsData = null) {
    document.getElementById('scheduleTitleRoute').textContent = `Trip Schedule - ${data.route_name} (${data.total_duration})`;
    
    const scheduleBody = document.getElementById('scheduleBody');
    scheduleBody.innerHTML = '';
    
    let currentRouteName = null;
    let routeIndex = 0;
    let hasBackendHeaders = false;
    
    // First pass: check if backend provided segment headers
    hasBackendHeaders = data.schedule.some(event => event.is_segment_header);
    
    data.schedule.forEach((event) => {
        // Handle explicit segment headers from backend (for connections)
        if (event.is_segment_header) {
            const headerRow = document.createElement('tr');
            headerRow.className = 'segment-header-row';
            headerRow.innerHTML = `
                <td colspan="4"><strong>${event.event}</strong></td>
            `;
            scheduleBody.appendChild(headerRow);
            // Extract and update the current route name from the header
            currentRouteName = event.event.replace('🚆 ', '');
            
            // Apply route-specific styling to header
            if (currentRouteName.includes('Lake Shore')) {
                headerRow.classList.add('route1-header-row');
            } else if (currentRouteName.includes('Southwest')) {
                headerRow.classList.add('route2-header-row');
            } else if (routeIndex >= 3) {
                headerRow.classList.add('route3-header-row');
            }
            
            routeIndex++;
            return;
        }
        
        // For direct routes without backend headers, add a header on first event
        if (!hasBackendHeaders && event.route_name && event.route_name !== currentRouteName) {
            const headerRow = document.createElement('tr');
            headerRow.className = 'segment-header-row';
            headerRow.innerHTML = `
                <td colspan="4"><strong>🚆 ${event.route_name}</strong></td>
            `;
            scheduleBody.appendChild(headerRow);
            currentRouteName = event.route_name;
            
            // Apply route-specific styling to header
            if (currentRouteName.includes('Lake Shore')) {
                headerRow.classList.add('route1-header-row');
            } else if (currentRouteName.includes('Southwest')) {
                headerRow.classList.add('route2-header-row');
            } else if (routeIndex >= 3) {
                headerRow.classList.add('route3-header-row');
            }
            
            routeIndex++;
        }
        
        const row = document.createElement('tr');
        
        // Apply route-specific styling class based on current route name
        if (currentRouteName && currentRouteName.includes('Lake Shore')) {
            row.classList.add('route1-row');
        } else if (currentRouteName && currentRouteName.includes('Southwest')) {
            row.classList.add('route2-row');
        } else if (routeIndex >= 3) {
            row.classList.add('route3-row');
        }
        
        // Check if this is a stop duration row or layover row
        if (event.event.includes('hour stop') || event.event.includes('layover')) {
            row.classList.add('duration-row');
        }
        
        row.innerHTML = `
            <td>${event.date}</td>
            <td>${event.time}</td>
            <td><strong>${event.city}</strong></td>
            <td>${event.event}</td>
        `;
        scheduleBody.appendChild(row);
    });
    
    // Save the current schedule state for editing, passing the selected stops
    saveScheduleState(data, selectedStopsData);
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

// ==================== EDIT/SAVE/LOAD FUNCTIONALITY ====================

// Save the current schedule state to localStorage
function saveScheduleState(scheduleData, selectedStopsData = null) {
    let selectedStops = [];
    
    // If selectedStopsData is provided (e.g., from a loaded schedule), use it
    if (selectedStopsData && Array.isArray(selectedStopsData)) {
        selectedStops = selectedStopsData;
    } else {
        // Otherwise, read from the DOM checkboxes (for newly generated schedules)
        document.querySelectorAll('.stop-item input[type="checkbox"]:checked:not(:disabled)').forEach(checkbox => {
            const city = checkbox.getAttribute('data-city');
            if (city) {
                const stopId = checkbox.id;
                const durationInput = document.querySelector(`#duration-input-${stopId}`);
                const duration = durationInput ? parseFloat(durationInput.value) : 0;
                selectedStops.push({ city, duration });
            }
        });
    }
    
    const state = {
        route_id: currentRoute.id,
        origin: document.getElementById('origin').value,
        destination: document.getElementById('destination').value,
        start_date: document.getElementById('startDate').value,
        selected_stops: selectedStops,
        schedule_data: scheduleData,
        route: currentRoute  // Store the full route object
    };
    
    localStorage.setItem('currentSchedule', JSON.stringify(state));
}

// Edit the current schedule (go back to stops selection with previous choices)
async function editSchedule() {
    const state = JSON.parse(localStorage.getItem('currentSchedule'));
    if (!state) {
        showError('No schedule to edit');
        return;
    }
    
    // Restore form values
    document.getElementById('origin').value = state.origin;
    document.getElementById('destination').value = state.destination;
    document.getElementById('startDate').value = state.start_date;
    
    // Restore currentRoute
    currentRoute = state.route || { id: state.route_id };
    
    showLoading(true);
    
    try {
        // Check if this is a connection route (contains 'conn_' in the ID)
        const routeId = currentRoute.id;
        const isConnection = String(routeId).includes('conn_');
        
        if (isConnection) {
            // For connection routes, we need to parse the route IDs and fetch stops for each segment
            // Route ID format: 'conn_1_2' means routes 1 and 2, 'conn_1_2_3' means routes 1, 2, and 3
            const routeParts = String(routeId).split('_').slice(1).map(Number);
            
            try {
                // Fetch stops for each route segment
                const allSegmentStops = [];
                for (const rid of routeParts) {
                    const response = await fetch(`/api/stops/${rid}`);
                    if (!response.ok) {
                        throw new Error(`Failed to fetch stops for route ${rid}`);
                    }
                    const data = await response.json();
                    allSegmentStops.push({
                        route_id: rid,
                        stops: data.stops || []
                    });
                }
                
                // Display connection stops with all segments
                displayConnectionStopsForEdit(allSegmentStops, currentRoute, state.origin, state.destination);
            } catch (error) {
                console.error('Error fetching connection route stops:', error);
                showError('Error loading connection route stops');
                showLoading(false);
                return;
            }
        } else {
            // For direct routes, fetch the stops from the backend
            const response = await fetch(`/api/stops/${routeId}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch stops: ${response.status}`);
            }
            const data = await response.json();
            
            // Display stops with previous selections
            displayStops(data.stops || [], currentRoute, state.origin, state.destination);
        }
        
        // Re-select the previous stops
        // Use setTimeout to ensure DOM is updated before trying to select checkboxes
        setTimeout(() => {
            state.selected_stops.forEach(stop => {
                const checkbox = document.querySelector(`input[data-city="${stop.city}"]:not(:disabled)`);
                if (checkbox) {
                    checkbox.checked = true;
                    const stopId = checkbox.id;
                    const durationInput = document.querySelector(`#duration-input-${stopId}`);
                    if (durationInput) {
                        durationInput.value = stop.duration;
                    }
                    // Trigger the change event to show the duration input
                    checkbox.dispatchEvent(new Event('change'));
                }
            });
        }, 0);
        
        // Hide schedule, show stops
        document.getElementById('scheduleSection').style.display = 'none';
        document.getElementById('stopsSection').style.display = 'block';
        document.getElementById('stopsSection').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error loading stops for edit:', error);
        showError('Error loading stops for editing');
    } finally {
        showLoading(false);
    }
}

// Save the current schedule to a file
async function saveSchedule() {
    const state = JSON.parse(localStorage.getItem('currentSchedule'));
    if (!state) {
        showError('No schedule to save');
        return;
    }
    
    // Prompt for schedule name
    const scheduleName = prompt('Enter a name for this schedule:', `Schedule-${new Date().toLocaleDateString()}`);
    if (!scheduleName) return;
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/save-schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: scheduleName,
                schedule_data: state
            })
        });
        
        if (response.ok) {
            showError(`Schedule "${scheduleName}" saved successfully!`);
        } else {
            const data = await response.json();
            showError(data.error || 'Error saving schedule');
        }
    } catch (error) {
        console.error('Error saving schedule:', error);
        showError('Error saving schedule');
    } finally {
        showLoading(false);
    }
}

// Load a saved schedule
async function loadScheduleModal() {
    showLoading(true);
    
    try {
        const response = await fetch('/api/load-schedules');
        const data = await response.json();
        
        if (!data.schedules || data.schedules.length === 0) {
            showError('No saved schedules found');
            showLoading(false);
            return;
        }
        
        // Create a modal to select a schedule
        const modal = document.createElement('div');
        modal.className = 'schedule-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>Load Saved Schedule</h3>
                <div class="schedules-list"></div>
                <div class="modal-actions">
                    <button class="btn btn-secondary modal-close">Cancel</button>
                </div>
            </div>
        `;
        
        const schedulesList = modal.querySelector('.schedules-list');
        data.schedules.forEach(schedule => {
            const item = document.createElement('div');
            item.className = 'schedule-item';
            item.innerHTML = `
                <div class="schedule-info">
                    <strong>${schedule.name}</strong>
                    <p>${schedule.origin} → ${schedule.destination} (${schedule.date})</p>
                </div>
                <button class="btn btn-sm btn-primary load-schedule-btn" data-id="${schedule.id}">Load</button>
                <button class="btn btn-sm btn-danger delete-schedule-btn" data-id="${schedule.id}">Delete</button>
            `;
            schedulesList.appendChild(item);
        });
        
        // Add close button handler
        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.remove();
            showLoading(false);
        });
        
        // Add load handlers
        modal.querySelectorAll('.load-schedule-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const scheduleId = e.target.getAttribute('data-id');
                await loadScheduleById(scheduleId);
                modal.remove();
            });
        });
        
        // Add delete handlers
        modal.querySelectorAll('.delete-schedule-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const scheduleId = e.target.getAttribute('data-id');
                if (confirm('Are you sure you want to delete this schedule?')) {
                    await deleteScheduleById(scheduleId);
                    location.reload();
                }
            });
        });
        
        document.body.appendChild(modal);
        showLoading(false);
    } catch (error) {
        console.error('Error loading schedules:', error);
        showError('Error loading schedules');
        showLoading(false);
    }
}

// Load a specific schedule by ID
async function loadScheduleById(scheduleId) {
    showLoading(true);
    
    try {
        const response = await fetch(`/api/load-schedule/${scheduleId}`);
        const data = await response.json();
        
        const state = data.schedule_data;
        
        // Clear any previous selections from the DOM
        document.getElementById('stopsList').innerHTML = '';
        document.getElementById('stopsSection').style.display = 'none';
        document.getElementById('routesSection').style.display = 'none';
        
        // Restore form values
        document.getElementById('origin').value = state.origin;
        document.getElementById('destination').value = state.destination;
        document.getElementById('startDate').value = state.start_date;
        
        // Restore currentRoute
        currentRoute = { id: state.route_id };
        
        // Save to localStorage
        localStorage.setItem('currentSchedule', JSON.stringify(state));
        
        // Generate the schedule
        await generateSchedule();
        
    } catch (error) {
        console.error('Error loading schedule:', error);
        showError('Error loading schedule');
    } finally {
        showLoading(false);
    }
}

// Delete a schedule
async function deleteScheduleById(scheduleId) {
    try {
        const response = await fetch(`/api/delete-schedule/${scheduleId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showError('Schedule deleted successfully');
        } else {
            showError('Error deleting schedule');
        }
    } catch (error) {
        console.error('Error deleting schedule:', error);
        showError('Error deleting schedule');
    }
}

