import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify, request
from src.models.db import db  # Updated import
from src.models.parcel import Parcel
from src.models.annotation import Annotation
import random

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'village_mapper.db')}" # Using SQLite for simplicity
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all() # Create database tables
    # Add some sample parcel data if the parcels table is empty
    if not Parcel.query.first():
        # Example: Create 10 random 5km x 5km parcels around a central point in China (e.g., Xi'an)
        # Approximate center: 34.3416° N, 108.9398° E
        # 5km is roughly 0.045 degrees latitude and 0.045 / cos(latitude) degrees longitude
        center_lat = 34.3416
        center_lon = 108.9398
        lat_offset = 0.045
        lon_offset_at_equator = 0.045

        for i in range(10):
            # Create somewhat separated parcels for initial testing
            parcel_center_lat = center_lat + (random.random() - 0.5) * 0.5 # Spread them out a bit
            parcel_center_lon = center_lon + (random.random() - 0.5) * 0.5 # Spread them out a bit
            
            # Calculate lon_offset based on current latitude
            import math
            lon_offset = lon_offset_at_equator / math.cos(math.radians(parcel_center_lat))

            min_lat = parcel_center_lat - lat_offset / 2
            max_lat = parcel_center_lat + lat_offset / 2
            min_lon = parcel_center_lon - lon_offset / 2
            max_lon = parcel_center_lon + lon_offset / 2
            
            parcel = Parcel(min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon, status='pending')
            db.session.add(parcel)
        db.session.commit()

# API for getting a task (a 5x5km parcel)
@app.route('/api/task', methods=['GET'])
def get_task():
    # Find a pending parcel, assign it (conceptually, for now status change can be more complex)
    # For simplicity, pick a random pending parcel
    pending_parcels = Parcel.query.filter_by(status='pending').all()
    if not pending_parcels:
        return jsonify({'message': 'No pending tasks available'}), 404
    
    task_parcel = random.choice(pending_parcels)
    # task_parcel.status = 'assigned' # In a real system, you'd assign it to a user and change status
    # db.session.commit()
    return jsonify({
        'parcel_id': task_parcel.id,
        'min_lat': task_parcel.min_lat,
        'min_lon': task_parcel.min_lon,
        'max_lat': task_parcel.max_lat,
        'max_lon': task_parcel.max_lon
    })

# API for submitting annotations for a parcel
@app.route('/api/annotation', methods=['POST'])
def submit_annotation():
    data = request.get_json()
    if not data or 'parcel_id' not in data or 'annotations' not in data:
        return jsonify({'message': 'Invalid data format'}), 400

    parcel_id = data['parcel_id']
    annotations_data = data['annotations']

    parcel = Parcel.query.get(parcel_id)
    if not parcel:
        return jsonify({'message': 'Parcel not found'}), 404

    for ann_data in annotations_data:
        if not all(k in ann_data for k in ('latitude', 'longitude', 'classification_type')):
            return jsonify({'message': 'Invalid annotation data'}), 400
        
        annotation = Annotation(
            parcel_id=parcel_id,
            latitude=ann_data['latitude'],
            longitude=ann_data['longitude'],
            classification_type=ann_data['classification_type']
        )
        db.session.add(annotation)
    
    # Optionally, update parcel status
    # parcel.status = 'completed' # Or 'in_review' etc.
    db.session.commit()
    return jsonify({'message': 'Annotations submitted successfully'}), 201

# API for exporting point data (example: all annotations as CSV-like structure)
@app.route('/api/export/points', methods=['GET'])
def export_points():
    annotations = Annotation.query.all()
    output = []
    # Header for CSV
    # output.append('annotation_id,parcel_id,latitude,longitude,classification_type,timestamp')
    for ann in annotations:
        output.append({
            'annotation_id': ann.id,
            'parcel_id': ann.parcel_id,
            'latitude': ann.latitude,
            'longitude': ann.longitude,
            'classification_type': ann.classification_type,
            'timestamp': ann.timestamp.isoformat()
        })
    # For actual CSV download, you'd use Flask's send_file or create a Response with CSV content-type
    return jsonify(output)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            # A simple API list for now if index.html is not present
            return jsonify({
                'message': 'Welcome to Village Mapper API. No frontend index.html found.',
                'available_endpoints': {
                    'get_task': '/api/task (GET)',
                    'submit_annotation': '/api/annotation (POST)',
                    'export_points': '/api/export/points (GET)'
                }
            })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

