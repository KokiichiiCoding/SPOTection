"""
Spotection Web API
FastAPI backend for the parking detection system
Provides REST endpoints and WebSocket for live updates
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
import asyncio
from datetime import datetime, timedelta
import uvicorn

# Import your detection system
from spotection_system import SpotectionSystem

app = FastAPI(title="Spotection API", version="1.0.0")

# Enable CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize detection system
detection_system = SpotectionSystem()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Remove broken connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Pydantic models
class SpotStatus(BaseModel):
    id: str
    status: str
    confidence: float
    timestamp: str
    vehicle: Optional[Dict] = None

class LotStatus(BaseModel):
    lot_id: str
    timestamp: str
    total_spots: int
    free_spots: int
    occupied_spots: int
    spots: List[SpotStatus]

class CalibrationPoint(BaseModel):
    x: int
    y: int

class SpotPolygon(BaseModel):
    id: str
    polygon: List[List[int]]

# API Routes
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "message": "Spotection API",
        "version": "1.0.0",
        "endpoints": {
            "status": "/api/status",
            "lots": "/api/lots",
            "detection": "/api/detect",
            "websocket": "/ws"
        }
    }

@app.get("/api/status")
async def get_api_status():
    """Get API health status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": hasattr(detection_system, 'model'),
        "active_connections": len(manager.active_connections)
    }

@app.get("/api/lots", response_model=List[Dict])
async def get_lots():
    """Get list of available parking lots"""
    # For MVP, return a single lot
    return [
        {
            "lot_id": "main_lot",
            "name": "Main Parking Lot",
            "description": "Primary campus parking area",
            "camera_status": "active",
            "last_update": datetime.now().isoformat()
        }
    ]

@app.get("/api/lots/{lot_id}/spots")
async def get_lot_spots(lot_id: str):
    """Get parking spot definitions for a lot"""
    try:
        spot_layout_path = detection_system.config.get("spot_layout_path", "data/spot_layout.json")
        
        if not os.path.exists(spot_layout_path):
            raise HTTPException(status_code=404, detail="Spot layout not found")
        
        with open(spot_layout_path, 'r') as f:
            spots = json.load(f)
        
        return {
            "lot_id": lot_id,
            "spots": spots,
            "total_spots": len(spots)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lots/{lot_id}/status", response_model=LotStatus)
async def get_lot_status(lot_id: str):
    """Get current occupancy status for a parking lot"""
    try:
        # Load spot layout
        spot_layout_path = detection_system.config.get("spot_layout_path", "data/spot_layout.json")
        
        if not os.path.exists(spot_layout_path):
            raise HTTPException(status_code=404, detail="Spot layout not found")
        
        with open(spot_layout_path, 'r') as f:
            spots_data = json.load(f)
        
        # Run detection
        image_path = detection_system.config.get("image_path", "data/test_image.jpg")
        results = detection_system.process_frame(image_path, spots_data)
        
        # Format response
        spot_statuses = []
        for result in results:
            spot_statuses.append(SpotStatus(
                id=result["id"],
                status=result["status"],
                confidence=result["confidence"],
                timestamp=result["timestamp"],
                vehicle=result.get("vehicle")
            ))
        
        occupied_count = sum(1 for s in spot_statuses if s.status == "OCCUPIED")
        
        return LotStatus(
            lot_id=lot_id,
            timestamp=datetime.now().isoformat(),
            total_spots=len(spot_statuses),
            free_spots=len(spot_statuses) - occupied_count,
            occupied_spots=occupied_count,
            spots=spot_statuses
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lots/{lot_id}/calibrate")
async def calibrate_lot(lot_id: str, spots: List[SpotPolygon]):
    """Update parking spot polygons for a lot (admin only)"""
    try:
        spot_layout_path = detection_system.config.get("spot_layout_path", "data/spot_layout.json")
        
        # Convert to format expected by detection system
        spot_data = []
        for spot in spots:
            spot_data.append({
                "id": spot.id,
                "polygon": spot.polygon
            })
        
        # Save to file
        with open(spot_layout_path, 'w') as f:
            json.dump(spot_data, f, indent=2)
        
        return {
            "message": f"Updated {len(spots)} spots for lot {lot_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lots/{lot_id}/spots/{spot_id}/override")
async def manual_override(lot_id: str, spot_id: str, status: str):
    """Manually override spot status (admin only)"""
    if status not in ["FREE", "OCCUPIED", "UNKNOWN"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    # In a full implementation, this would update the database
    # For MVP, we'll just broadcast the override
    override_message = {
        "type": "manual_override",
        "lot_id": lot_id,
        "spot_id": spot_id,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    
    await manager.broadcast(override_message)
    
    return {
        "message": f"Override applied to {spot_id}",
        "status": status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/lots/{lot_id}/image")
async def get_lot_image(lot_id: str, annotated: bool = True):
    """Get the latest parking lot image (annotated or raw)"""
    try:
        if annotated:
            # Find the most recent annotated image
            output_dir = detection_system.config.get("output_dir", "output/")
            if os.path.exists(output_dir):
                images = [f for f in os.listdir(output_dir) if f.startswith("annotated_") and f.endswith(".jpg")]
                if images:
                    latest_image = max(images)
                    return FileResponse(os.path.join(output_dir, latest_image))
        
        # Return raw image
        image_path = detection_system.config.get("image_path", "data/test_image.jpg")
        if os.path.exists(image_path):
            return FileResponse(image_path)
        else:
            raise HTTPException(status_code=404, detail="Image not found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for live updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time parking updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Send periodic updates (every 30 seconds in production)
            await asyncio.sleep(5)  # 5 seconds for demo
            
            try:
                # Get current status
                spot_layout_path = detection_system.config.get("spot_layout_path", "data/spot_layout.json")
                if os.path.exists(spot_layout_path):
                    with open(spot_layout_path, 'r') as f:
                        spots_data = json.load(f)
                    
                    image_path = detection_system.config.get("image_path", "data/test_image.jpg")
                    results = detection_system.process_frame(image_path, spots_data)
                    
                    update_message = {
                        "type": "status_update",
                        "lot_id": "main_lot",
                        "timestamp": datetime.now().isoformat(),
                        "spots": results
                    }
                    
                    await websocket.send_json(update_message)
                    
            except Exception as e:
                print(f"Error in WebSocket update: {e}")
                break
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Serve static files (for frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/admin")
async def admin_interface():
    """Simple admin interface for calibration"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spotection Admin</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .status { background: #f0f0f0; padding: 10px; border-radius: 5px; margin: 10px 0; }
            .spot { margin: 5px 0; padding: 5px; border: 1px solid #ccc; }
            .free { background-color: #d4edda; }
            .occupied { background-color: #f8d7da; }
            button { padding: 10px 20px; margin: 5px; background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Spotection Admin Panel</h1>
            
            <div class="status">
                <h3>System Status</h3>
                <div id="system-status">Loading...</div>
            </div>
            
            <div class="status">
                <h3>Current Parking Status</h3>
                <button onclick="refreshStatus()">Refresh</button>
                <div id="parking-status">Loading...</div>
            </div>
            
            <div class="status">
                <h3>Actions</h3>
                <button onclick="window.location.href='/api/lots/main_lot/image'">View Current Image</button>
                <button onclick="runDetection()">Run Detection</button>
            </div>
        </div>
        
        <script>
            async function refreshStatus() {
                try {
                    const response = await fetch('/api/lots/main_lot/status');
                    const data = await response.json();
                    
                    document.getElementById('parking-status').innerHTML = `
                        <p>Total Spots: ${data.total_spots}</p>
                        <p>Free: ${data.free_spots}</p>
                        <p>Occupied: ${data.occupied_spots}</p>
                        <p>Last Update: ${new Date(data.timestamp).toLocaleString()}</p>
                        <div>
                            ${data.spots.map(spot => `
                                <div class="spot ${spot.status.toLowerCase()}">
                                    ${spot.id}: ${spot.status} 
                                    ${spot.vehicle ? `(${spot.vehicle.class})` : ''}
                                    - Confidence: ${(spot.confidence * 100).toFixed(1)}%
                                </div>
                            `).join('')}
                        </div>
                    `;
                } catch (error) {
                    document.getElementById('parking-status').innerHTML = `Error: ${error.message}`;
                }
            }
            
            async function runDetection() {
                try {
                    const response = await fetch('/api/lots/main_lot/status');
                    if (response.ok) {
                        await refreshStatus();
                        alert('Detection completed!');
                    } else {
                        alert('Detection failed!');
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            }
            
            async function checkSystemStatus() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    document.getElementById('system-status').innerHTML = `
                        <p>Status: ${data.status}</p>
                        <p>Model Loaded: ${data.model_loaded ? 'Yes' : 'No'}</p>
                        <p>Active Connections: ${data.active_connections}</p>
                        <p>Last Check: ${new Date(data.timestamp).toLocaleString()}</p>
                    `;
                } catch (error) {
                    document.getElementById('system-status').innerHTML = `Error: ${error.message}`;
                }
            }
            
            // Initialize
            checkSystemStatus();
            refreshStatus();
            
            // Auto-refresh every 30 seconds
            setInterval(refreshStatus, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    print("Starting Spotection API server...")
    print("Admin interface available at: http://localhost:8000/admin")
    print("API documentation at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)