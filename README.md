# 🚂 Train Trip Planner

A web-based application to help users plan multi-day Amtrak train trips between cities with the ability to select intermediate stops and generate comprehensive trip schedules.

## ✨ Features

- 🗺️ **Route Database**: SQLite database with train routes, schedules, and stops
- 🌐 **Web Interface**: User-friendly localhost interface (http://localhost:5000)
- 🏙️ **City Selection**: Dynamic dropdown menus for origin/destination cities
- 🛑 **Stop Selection**: Choose intermediate cities to visit
- 📅 **Schedule Generation**: Full trip itineraries with dates and times
- 💾 **CSV Export**: Download your schedule for offline reference
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- pip

### Setup & Run
```bash
# Clone and navigate to the project
cd train-trip-planner

# Option 1: Use the quick start script (macOS/Linux)
chmod +x run.sh
./run.sh

# Option 2: Manual setup
python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python database.py
python app.py
```

Then visit: **http://localhost:5000**

## 📋 How to Use

1. **Enter Trip Details:**
   - Select "From" city (origin)
   - Select "To" city (destination)
   - Pick your travel date

2. **Search Routes:**
   - Click "Search Routes"
   - View available train routes with times

3. **Select a Route:**
   - Click on a route card to select it
   - View all intermediate stops

4. **Choose Your Stops:**
   - Check boxes for cities where you want to stop
   - Origin and destination are always included

5. **Generate Schedule:**
   - Click "Generate Schedule"
   - View your complete itinerary

6. **Export (Optional):**
   - Click "Download Schedule" to save as CSV

## 📁 Project Structure

```
train-trip-planner/
├── app.py                      # Flask backend (130 lines)
├── database.py                 # Database & queries (220 lines)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git configuration
├── run.sh                      # Quick start script
├── templates/
│   └── index.html             # Web interface
└── static/
    ├── style.css              # Styling (380 lines)
    └── script.js              # Frontend logic (350 lines)
```

## 🏗️ Architecture

### Backend (Python/Flask)

**API Endpoints:**
- `GET /` - Main page
- `GET /api/cities` - All available cities
- `POST /api/routes` - Routes between two cities
- `GET /api/stops/<route_id>` - Stops for a route
- `POST /api/generate-schedule` - Generate trip itinerary

### Database (SQLite)

**Routes Table** - Train routes with times and duration
- `id`, `route_number`, `route_name`
- `origin_city`, `destination_city`
- `departure_time`, `arrival_time`, `duration_hours`

**Stops Table** - Intermediate stops for each route
- `id`, `route_id`, `stop_number`
- `city_name`, `arrival_time`, `departure_time`

**Cities Table** - All cities in the network
- `id`, `name`, `state`

### Frontend (HTML/CSS/JavaScript)

- **index.html**: Responsive web interface
- **style.css**: Modern gradient design with animations
- **script.js**: Client-side logic for fetching/displaying data

## 📊 Sample Data

Pre-populated with 10 routes and 29 major US cities:

| Route | From | To | Duration |
|-------|------|----|---------:|
| Northeast Regional | Boston | New York | 3h |
| Northeast Regional | New York | Philadelphia | 2h |
| Northeast Regional | Philadelphia | Washington DC | 2h |
| Northeast Regional | Washington DC | Richmond | 2h |
| Silver Star | New York | Miami | 29h |
| Lake Shore Limited | Boston | Chicago | 30h |
| Capitol Limited | Chicago | Washington DC | 19h |
| California Zephyr | Chicago | Denver | 28h |
| Southwest Chief | Denver | Los Angeles | 29h |
| Empire Builder | Chicago | Seattle | 45h |

## 🔧 Configuration

### Change Port
Edit `app.py`:
```python
app.run(debug=True, port=3000)  # Change to port 3000
```

### Add Routes
Edit `database.py` in the `init_database()` function:
```python
sample_routes = [
    ('route_num', 'name', 'origin', 'destination', 'dep', 'arr', hours),
    # Add more routes here
]
```

### Reset Database
```bash
rm train_routes.db
python database.py
```

## 📱 Browser Support

- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers

## 🐛 Troubleshooting

**Port 5000 already in use:**
```bash
# Change port in app.py or use lsof to find what's using it
lsof -i :5000
```

**Database errors:**
```bash
rm train_routes.db
./run.sh
```

**Module import errors:**
```bash
pip install --upgrade -r requirements.txt
```

**JavaScript console errors:**
- Open DevTools (F12 or Cmd+Option+I)
- Check the Console tab for error messages
- Refresh the page (Cmd+R or F5)

## 📚 API Reference

### Get All Cities
```bash
curl http://localhost:5000/api/cities
```
Response:
```json
{
  "cities": ["Boston", "New York", "Philadelphia", ...]
}
```

### Search Routes
```bash
curl -X POST http://localhost:5000/api/routes \
  -H "Content-Type: application/json" \
  -d '{"origin": "Boston", "destination": "New York"}'
```
Response:
```json
{
  "routes": [
    {
      "id": 1,
      "route_name": "Northeast Regional",
      "departure_time": "08:00",
      "arrival_time": "11:30",
      ...
    }
  ]
}
```

### Get Route Stops
```bash
curl http://localhost:5000/api/stops/1
```
Response:
```json
{
  "stops": [
    {
      "city_name": "Boston",
      "arrival_time": "08:00",
      "departure_time": "08:00"
    },
    ...
  ]
}
```

### Generate Schedule
```bash
curl -X POST http://localhost:5000/api/generate-schedule \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": 1,
    "selected_stops": ["Providence"],
    "start_date": "2025-11-15"
  }'
```
Response:
```json
{
  "schedule": [
    {
      "city": "Boston",
      "event": "Departure",
      "time": "08:00",
      "date": "2025-11-15"
    },
    ...
  ],
  "route_name": "Northeast Regional",
  "total_duration": "3 hours"
}
```

## 📋 Assumptions

- ✅ Trains run once per day, every day
- ✅ Times from database are consistent
- ✅ Routes are unidirectional
- ✅ All times in 24-hour format (HH:MM)

## 🔒 Technical Notes

- **No external dependencies** (except Flask & Werkzeug)
- **SQL injection safe** (parameterized queries)
- **XSS protected** (proper DOM manipulation)
- **Suitable for** 100+ routes, 1000+ cities
- **Database file** (~50KB) for sample data

## 🚀 Future Enhancements

- Multi-leg trip planning
- Fare information
- Seat availability
- User accounts & saved trips
- Real-time delays
- Booking integration
- Mobile app
- Seasonal schedules

## 📄 Requirements

```
Flask==2.3.3
Werkzeug==2.3.7
```

## 📝 License

Open source - available for educational and personal use.

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## ❓ Support

For issues or questions, please open an issue in the repository.