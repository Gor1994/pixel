from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv
from uuid import uuid4
from flask_cors import CORS
from pymongo import MongoClient, UpdateOne, DeleteOne
from datetime import datetime, timedelta
import certifi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults
from threading import Thread
import threading
import time
import random
import secrets
import logging
import requests
import asyncio
from flask_session import Session
import json
from bson import ObjectId
from multiprocessing import Process
import math

# Load .env file
load_dotenv()

app = Flask(__name__)
# CORS(app, supports_credentials=True, resources={r"/*": {"origins": "http://195.133.146.186/"}})
#CORS(app)

# socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=25, ping_timeout=60)


#socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
#socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app, supports_credentials=True)
app.secret_key = "aaa"
import os
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

SESSION_FILE_DIR = './flask_session'
if not os.path.exists(SESSION_FILE_DIR):
    os.makedirs(SESSION_FILE_DIR)
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR


# MongoDB Configuration
MONGO_URI = 'mongodb+srv://nershakobyan:QkmcuOAhHba7C4q8@cluster0.1rwwk.mongodb.net/Grid_Game?retryWrites=true&w=majority'

client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
db = client["Grid_Game"]
cells_collection = db["owned_cells"]
forts_collection = db["forts"]
users_collection = db["users"]

print("Successfully connected to MongoDB")

app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = False  # Use True for HTTPS

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session/'  # Directory to store session files
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # For cross-origin requests
Session(app)


RECHARGE_INTERVAL_SECONDS = int(os.getenv("RECHARGE_INTERVAL_SECONDS"))
MAX_CLICK_PER_CHARGE = int(os.getenv("MAX_CLICK_PER_CHARGE"))
ENERGY_RECHARGE_PER_SEC = int(os.getenv("ENERGY_RECHARGE_PER_SEC"))
TOTAL_RECHARGABLE_ENERGY = int(os.getenv("TOTAL_RECHARGABLE_ENERGY"))
ENERGY_IN_ONE_CHARGE = int(os.getenv("ENERGY_IN_ONE_CHARGE"))

# Constants
FORT_MIN_SIZE = 3

########################################  TELEGRAM ########################################
# Telegram Bot Token
telegram_app_TOKEN = '8076325725:AAHqtb8Z7mJu56NEceWYtLTvD1h-2rI3_Wg'
# Correctly initialize the Telegram Bot Application
telegram_app = Application.builder().token(telegram_app_TOKEN).build()

# Constants
CODE_VALIDITY_MINUTES = 5  # Code expiration time


# Generate a random 6-digit login code
def generate_login_code():
    return f"{random.randint(100000, 999999)}"

def generate_random_color_hex():
    """Generate a random hex color code."""
    return f"#{random.randint(0, 0xFFFFFF):06x}"

# Send login code to Telegram
async def send_login_code_to_telegram(telegram_user_id, code):
    try:
        message = f"Your login code is: {code}\nIt is valid for {CODE_VALIDITY_MINUTES} minutes."
        await telegram_app.bot.send_message(chat_id=telegram_user_id, text=message)   

        print(f"✅ Login code sent to Telegram ID {telegram_user_id}")
    except Exception as e:
        print(f"❌ Failed to send login code: {e}")


# Determine if the identifier is Telegram ID (numeric) or username (alphanumeric)
def is_telegram_id(identifier):
    return identifier.isdigit()  # Check if the identifier consists of only digits

@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")
    emit("connected", {"message": "Welcome!"})


@app.route("/request-login-code", methods=["POST"])
def request_login_code():
    try:
        data = request.json
        identifier = data.get("identifier")  # Telegram ID or username
        if not identifier:
            return jsonify({"error": "Identifier (Telegram ID or username) is required"}), 400

        # Determine whether the identifier is Telegram ID or username
        query = (
            {"telegram_user_id": int(identifier)}
            if identifier.isdigit()
            else {"telegram_username": str(identifier)}
        )

        # Find user in the database
        user = users_collection.find_one(query)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Generate a random 6-digit login code
        generated_code = str(random.randint(100000, 999999))
        expiry_time = datetime.utcnow() + timedelta(minutes=CODE_VALIDITY_MINUTES)

        # Save the code and expiration time in the database
        users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"login_code": generated_code, "code_expires_at": expiry_time}},
        )

        # Fetch IP address and location info
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        location = "Unknown Location"
        try:
            ip_api_url = f"http://ip-api.com/json/{user_ip}"
            response = requests.get(ip_api_url)
            if response.status_code == 200:
                ip_data = response.json()
                city = ip_data.get("city", "")
                region = ip_data.get("regionName", "")
                country = ip_data.get("country", "")
                location = f"{city}, {region}, {country}"
        except Exception as ip_error:
            print(f"Error fetching location: {ip_error}")

        telegram_url = f'https://api.telegram.org/bot{telegram_app_TOKEN}/sendMessage'

        # Construct the message to send via Telegram
        message_text = (
            f"Login detected from IP address:\n"
            f"<a href='https://{user_ip}'>{user_ip}</a> ({location})\n\n"
            f"<b>Authorization Code:</b> <code>{generated_code}</code>\n\n"
            f"If you did not request this, please ignore this message."
        )

        payload = {
            'chat_id':user.get("telegram_user_id"),
            'text': message_text,
            'parse_mode': 'HTML'
        }

        response = requests.post(telegram_url, json=payload)

        if response.status_code != 200:
            return jsonify({'error': 'Failed to send password to Telegram'}), 500

        return jsonify({'message': 'Password sent to Telegram'}), 200

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({'error': 'An error occurred on the server'}), 500

server_sessions = {}

import jwt
JWT_SECRET = "your_secret_key"
JWT_ALGORITHM = "HS256"  # Hashing algorithm

# Generate JWT
def generate_jwt(user_id, username):
    expiration = datetime.utcnow() + timedelta(hours=1)  # Token valid for 1 hour
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": expiration,  # Expiry
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# Verify JWT
def verify_jwt(token):
    try:
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded_token
    except jwt.ExpiredSignatureError:
        print("Token expired.")
        return None
    except jwt.InvalidTokenError:
        print("Invalid token.")
        return None
    
@app.route("/verify-login-code", methods=["POST"])
def verify_login_code():
    data = request.json
    identifier = data.get("identifier")
    code = data.get("code")

    if  is_telegram_id(identifier):
    # Find user and validate code
        user = users_collection.find_one(
            {"telegram_user_id": int(identifier)}
        )
    else :
        user = users_collection.find_one(
            {"telegram_username": identifier}
        )

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.get("login_code") != code or datetime.utcnow() > user.get("code_expires_at"):
        return jsonify({"error": "Invalid or expired code"}), 400

    # Generate JWT
    token = generate_jwt(user_id=str(user["telegram_user_id"]), username=user.get("telegram_username"))

    return jsonify({
        "message": "Logged in successfully",
        "token": token,
        "user_id": str(user["telegram_user_id"]),
        "username": user.get("telegram_username"),
    })



@app.route("/check-login", methods=["GET"])
def check_login():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        print("No Authorization header or invalid format.")
        return jsonify({"message": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    decoded_token = verify_jwt(token)

    if not decoded_token:
        return jsonify({"message": "Unauthorized"}), 401

    return jsonify({
        "userId": decoded_token["user_id"],
        "username": decoded_token["username"],
    }), 200

@app.route("/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization")
    if token and token in server_sessions:
        del server_sessions[token]
    return jsonify({"message": "Logged out successfully"}), 200


def get_neighbors(row, col):
    """Get neighbors for a given cell."""
    return [
        (row - 1, col), (row + 1, col),  # Vertical neighbors
        (row, col - 1), (row, col + 1)   # Horizontal neighbors
    ]


def fetch_grid_as_dict():
    """Fetch the grid from MongoDB and return as a dictionary."""
    cells = cells_collection.find({}, {"_id": 0})
    grid = {}
    for cell in cells:
        row, col = map(int, cell["coordinates"].split("-"))
        grid[(row, col)] = cell
    return grid
def detect_and_mark_fort(start_cell, user_id):
    """
    Detect and mark forts (rectangles) with a minimum size, while handling overlapping or enclosed forts.
    Removes any inner cells belonging to other users.
    """
    grid = fetch_grid_as_dict()  # Fetch the current grid state from MongoDB
    visited = set()  # Track visited cells

    def dfs(row, col):
        """Depth-first search to find all connected cells."""
        stack = [(row, col)]
        component = set()

        while stack:
            r, c = stack.pop()
            if (r, c) in visited or (r, c) not in grid:
                continue
            visited.add((r, c))
            if grid[(r, c)].get("is_in_fort"):  # Skip cells already in a fort
                continue
            component.add((r, c))
            stack.extend(get_neighbors(r, c))

        return component

    def find_largest_rectangle(cells, owner_id):
        """
        Find the largest valid rectangle within a set of connected cells, ensuring that border cells form a proper boundary.
        """
        if not cells:
            return None

        # Convert cells to a sorted list of coordinates
        cells_list = sorted(list(cells))
        min_row = min(r for r, _ in cells_list)
        max_row = max(r for r, _ in cells_list)
        min_col = min(c for _, c in cells_list)
        max_col = max(c for _, c in cells_list)

        best_rectangle = None
        max_area = 0

        # Try all possible rectangles within the bounds
        for top in range(min_row, max_row + 1):
            for bottom in range(top, max_row + 1):
                for left in range(min_col, max_col + 1):
                    for right in range(left, max_col + 1):
                        # Track border and inner cells
                        border_cells = set()
                        inner_cells = set()
                        is_valid = True

                        # Validate all cells within the potential rectangle
                        for r in range(top, bottom + 1):
                            for c in range(left, right + 1):
                                cell = grid.get((r, c))

                                # Classify as border or inner
                                if r == top or r == bottom or c == left or c == right:
                                    # Border cells must exist and belong to the owner
                                    if not cell or cell.get("user_id") != owner_id:
                                        is_valid = False
                                        break
                                    border_cells.add((r, c))
                                else:
                                    # Inner cells can be gaps (empty), so no checks needed
                                    inner_cells.add((r, c))

                            if not is_valid:
                                break

                        # Ensure rectangle meets size requirements
                        if is_valid and (bottom - top + 1) >= FORT_MIN_SIZE and (right - left + 1) >= FORT_MIN_SIZE:
                            area = (bottom - top + 1) * (right - left + 1)
                            if area > max_area:
                                max_area = area
                                best_rectangle = {
                                    "top": top,
                                    "bottom": bottom,
                                    "left": left,
                                    "right": right,
                                    "border_cells": border_cells,
                                    "inner_cells": inner_cells,
                                }

        return best_rectangle


    # Start detection from the specified cell
    start_row, start_col = start_cell
    connected_cells = dfs(start_row, start_col)

    # Find the largest valid rectangle within connected cells
    rectangle = find_largest_rectangle(connected_cells, user_id)
    print(f"🚀 ~ rectangle:", rectangle)
    
    if not rectangle:
        return False

    # Convert coordinate tuples to string format for database
    border_cells = [f"{r}-{c}" for r, c in rectangle['border_cells']]
    print(f"🚀 ~ border_cells:", border_cells)
    inner_cells = [f"{r}-{c}" for r, c in rectangle['inner_cells']]

    # Validate ownership of all cells
    owner_ids = set(
        grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])), {}).get("user_id")
        for coord in border_cells
    )
     # Get the owner of the border cells (assuming all border cells belong to the same user)
    if len(owner_ids) == 1:
        border_owner_id = next(iter(owner_ids))  # Extract the single owner ID
    else:
        border_owner_id = None

    # Check ownership for inner cells
    inner_cells_owners = set(
        grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])), {}).get("user_id")
        for coord in inner_cells
    )

    # Ensure all inner cells are owned by the same user as the border cells
    if len(inner_cells_owners) > 1 or None in inner_cells_owners or (border_owner_id and border_owner_id not in inner_cells_owners):
        print(f"❌ Inner cells have different owners or are not owned by the border owner.")
        
        # Check if any inner cell is part of another fort
        for coord in inner_cells:
            cell = grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])))
            if cell and cell.get("is_in_fort"):
                print(f"🔍 Inner cell {coord} is part of a fort.")
                
                # Get the fort owner's user ID
                fort_owner_id = cell.get("user_id")
                if fort_owner_id:
                    # Fetch levels for the current user and the fort owner
                    current_user_level = calculate_user_level(user_id)
                    fort_owner_level = calculate_user_level(fort_owner_id)

                    # Compare levels
                    if current_user_level > fort_owner_level:
                        print(f"✅ Current user's level ({current_user_level}) is higher than the fort owner's level ({fort_owner_level}).")
                    else:
                        print(f"❌ Current user's level ({current_user_level}) is not higher than the fort owner's level ({fort_owner_level}).")
                        return False
            else:
                print(f"🔍 Inner cell {coord} is NOT part of a fort.")


    # Remove inner cells belonging to another user
    for coord in inner_cells:
        cell = grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])))
        if cell and cell.get("user_id") != user_id:
            print(f"❌ Removing inner cell belonging to another user: {coord}")
            cells_collection.delete_one({"coordinates": coord})
            socketio.emit("cell-deleted", {"coordinates": coord})

    # Generate a unique fort_id
    new_fort_id = str(uuid4())

    # Calculate fort level based on the minimum level of border cells
    fort_level = min(
        [grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])), {}).get("level", 1) for coord in border_cells]
    )

    # Generate the fort data
    fort_data = {
        "fort_id": new_fort_id,
        "user_id": list(owner_ids)[0],  # The single owner ID
        "border_cells": border_cells,
        "inner_cells": inner_cells,
        "level": fort_level,
        "created_at": datetime.utcnow()
    }

    # Proceed to store the fort in the `forts` collection
    forts_collection.insert_one(fort_data)

    # Prepare bulk operations for `owned_cells` update
    bulk_operations = []
    for cell in border_cells:
        bulk_operations.append(
            UpdateOne(
                {"coordinates": cell},
                {"$set": {"is_border": True, "is_inner": False, "is_in_fort": True, "fort_id": new_fort_id}},
                upsert=True
            )
        )
    for cell in inner_cells:
        bulk_operations.append(
            UpdateOne(
                {"coordinates": cell},
                {"$set": {"is_border": False, "is_inner": True, "is_in_fort": True, "fort_id": new_fort_id}},
                upsert=True
            )
        )
    if bulk_operations:
        cells_collection.bulk_write(bulk_operations)

    new_user_level = calculate_user_level(user_id)
    print(f"🚀 ~ new_user_level:", new_user_level)

    try:
        print(f"here")
        socketio.emit(
            "user-level-updated",
            {
                "user_id": user_id,
                "level": new_user_level,
            }
        )
        print(f"here")
    except Exception as e:
        app.logger.error(f"Error emitting user-level-updated: {e}")
    print(f"✅ Fort added to database: {fort_data}")

    try:
        socketio.emit("fort-detected", json.loads(json.dumps(fort_data, cls=CustomJSONEncoder)))
    except Exception as e:
        app.logger.error(f"Error emitting fort-detected: {e}")
    return True






@app.route("/get-grid", methods=["GET"])
def get_grid():
    """Return the current grid state with fort levels included."""
    cells = list(cells_collection.find({}, {"_id": 0}))
    forts = list(forts_collection.find({}, {"_id": 0, "fort_id": 1, "level": 1}))

    # Map fort_id to fort_level
    fort_levels = {fort["fort_id"]: fort["level"] for fort in forts}
    print(f"hereeeeeeeeeeeeeee")
    # Add fort_level to each cell if it belongs to a fort
    for cell in cells:
        if "fort_id" in cell and cell["fort_id"] in fort_levels:
            cell["fort_level"] = fort_levels[cell["fort_id"]]

    return jsonify(cells)


def destroy_fort(fort_id):
    """Destroy a fort and update related cells."""
    # Fetch the fort details
    fort = forts_collection.find_one({"fort_id": fort_id})
    if not fort:
        print(f"No fort found with ID: {fort_id}")
        return False
    
    # Get the user ID of the fort owner
    user_id = fort.get("user_id")
    if not user_id:
        print(f"Fort {fort_id} has no owner. Skipping level recalculation.")
        return False

    # Fetch all cells associated with the fort
    affected_cells = list(cells_collection.find({"fort_id": fort_id}))

    # Prepare bulk operations for removing inner cells and updating border cells
    bulk_operations = []

    for cell in affected_cells:
        if cell.get("is_inner", False):
            # Remove inner cells from the collection
            bulk_operations.append(DeleteOne({"coordinates": cell["coordinates"]}))
        else:
            # Update border cells to reset fort-related properties
            bulk_operations.append(
                UpdateOne(
                    {"coordinates": cell["coordinates"]},
                    {
                        "$set": {
                            "is_border": False,
                            "is_inner": False,
                            "is_in_fort": False,
                            "fort_id": None
                        }
                    }
                )
            )

    # Execute bulk operations for cells
    if bulk_operations:
        try:
            result = cells_collection.bulk_write(bulk_operations)
            print(f"Bulk write result: {result.bulk_api_result}")
        except Exception as e:
            print(f"Error executing bulk write: {e}")
            raise

    # Notify clients about deleted cells
    for cell in affected_cells:
        if cell.get("is_inner", False):
            socketio.emit("cell-deleted", {"coordinates": cell["coordinates"]})

    # Remove the fort itself from the forts collection
    forts_collection.delete_one({"fort_id": fort_id})
    print(f"Fort {fort_id} destroyed.")

    new_user_level = calculate_user_level(user_id)

    try:
        socketio.emit(
            "user-level-updated",
            {
                "user_id": user_id,
                "level": new_user_level,
            }
        )
    except Exception as e:
        app.logger.error(f"Error emitting user-level-updated: {e}")

    # Notify clients about the destroyed fort
    socketio.emit(
        "fort-destroyed",
        {"fort_id": fort_id, "affected_cells": [cell["coordinates"] for cell in affected_cells]}
    )

    return True


@app.route("/claim-cell", methods=["POST"])
def claim_cell_with_energy():
    """Handle cell clicks with energy validation."""
    data = request.json
    row, col = data.get("row"), data.get("col")
    user_id = data.get("userId")

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Fetch user energy details
    user = users_collection.find_one({"telegram_user_id": int(user_id)})
    if not user:
        print("❌ Player not found in the database.")
        return jsonify({"error": "Player not initialized: User not found"}), 416

    if "energy" not in user:
        print("❌ Energy data not found for the player.")
        return jsonify({"error": "Player not initialized: Energy data missing"}), 416

    energy = user["energy"]

    # Retrieve current energy details
    clicks_in_charge = energy.get("clicks_in_charge", 0)
    clicks_per_charge = energy.get("clicks_per_charge", MAX_CLICK_PER_CHARGE)

    # Claim the cell logic
    cell_coordinates = f"{row}-{col}"
    cell = cells_collection.find_one({"coordinates": cell_coordinates})

    # Determine the energy_to_use based on cell ownership and level
    if not cell or not cell.get("user_id"):
        # Cell has no owner
        energy_to_use = 1
    else:
        # Cell has an owner; energy_to_use = level of the cell
        energy_to_use = cell.get("level", 1)
    # energy_to_use = 1  # Energy required per cell claim

    now = datetime.utcnow()

    # Check if the user has enough energy to claim the cell
    if clicks_per_charge < energy_to_use:
        print("❌ Not enough energy to claim the cell.")
        return jsonify({"error": "Not enough energy to claim the cell."}), 400

    # Increment clicks_in_charge by the energy used
    clicks_in_charge += energy_to_use
    clicks_per_charge -= energy_to_use

    # Update the user's energy in the database
    users_collection.update_one(
        {"telegram_user_id": int(user_id)},
        {
            "$set": {
                "energy.clicks_in_charge": clicks_in_charge,
                "energy.clicks_per_charge": clicks_per_charge,
                "energy.last_click_timestamp": now,
            }
        }
    )
    print(f"✅ Click registered. Clicks in charge: {clicks_in_charge}, Clicks per charge remaining: {clicks_per_charge}")

    # # Claim the cell logic
    # cell_coordinates = f"{row}-{col}"
    # cell = cells_collection.find_one({"coordinates": cell_coordinates})

    if cell:
        # Ensure 'user_id' exists in the cell document
        cell_user_id = cell.get("user_id")
        if not cell_user_id:
            print(f"❌ Cell at {cell_coordinates} is missing 'user_id'. Skipping.")
            return jsonify({"error": "Cell data is invalid or incomplete"}), 400

        # Determine max level
        max_level = 2  # Default max level for cells not in a fort
        if cell.get("is_in_fort"):
            fort_id = cell.get("fort_id")
            border_cell_count = cells_collection.count_documents({"fort_id": fort_id, "is_border": True})
            max_level = border_cell_count * 2
        if cell_user_id != user_id:
            current_level = cell.get("level", 0)

            if current_level == 1:
                # Check if the cell is part of a fort
                if cell.get("is_in_fort"):
                    fort_id = cell.get("fort_id")
                    destroy_fort(fort_id)  # Destroy the fort as ownership is changing
                    print(f"✅ Fort {fort_id} destroyed due to ownership change.")

                # Change ownership without reducing the level
                cells_collection.update_one(
                    {"coordinates": cell_coordinates},
                    {"$set": {"user_id": user_id, "color": user.get("color"), "level": 1, "is_in_fort": False}}
                )
                updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
                try:
                    socketio.emit("cell-updated", updated_cell)
                except Exception as e:
                    app.logger.error(f"Error emitting cell-updated: {e}")
            else:
                # Reduce the level for cells with a level > 1
                new_level = current_level - 1
                cells_collection.update_one(
                    {"coordinates": cell_coordinates},
                    {"$set": {"level": new_level}}
                )
                updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
                try:
                    socketio.emit("cell-updated", updated_cell)
                except Exception as e:
                    app.logger.error(f"Error emitting cell-updated: {e}")
                

                if cell.get("is_in_fort"):

                    fort_id = cell.get("fort_id")

                    # Get the owner of the fort
                    fort = forts_collection.find_one({"fort_id": fort_id})
                    fort_owner_id = fort.get("user_id") if fort else None

                    if fort_owner_id:
                        updated_fort_level = calculate_fort_level(cell.get("fort_id"))
                        print(f"🚀 ~ updated_fort_level:", updated_fort_level)
                        forts_collection.update_one(
                            {"fort_id": cell.get("fort_id")},
                            {"$set": {"level": updated_fort_level}}
                        )
                        new_user_level = calculate_user_level(fort_owner_id)
                        try:
                            socketio.emit(
                                "user-level-updated",
                                {
                                    "user_id": fort_owner_id,
                                    "level": new_user_level,
                                }
                            )
                            socketio.emit("fort-level-updated", {"fort_id": cell.get("fort_id"), "level": updated_fort_level})
                            print(f"is_in_fort")
                        except Exception as e:
                            app.logger.error(f"Error emitting user-level-updated: {e}")
        else:
            # User owns the cell; increase the level
            current_level = cell.get("level", 0)
            new_level = min(current_level + 1, max_level)  # Ensure it does not exceed max_level
            cells_collection.update_one(
                {"coordinates": cell_coordinates},
                {"$set": {"level": new_level, "color": user.get("color")}}
            )
            updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
            try:
                socketio.emit("cell-updated", updated_cell)
            except Exception as e:
                app.logger.error(f"Error emitting cell-updated: {e}")

            if cell.get("is_in_fort"):
                updated_fort_level = calculate_fort_level(cell.get("fort_id"))
                print(f"🚀 ~ updated_fort_level:", updated_fort_level)
                forts_collection.update_one(
                    {"fort_id": cell.get("fort_id")},
                    {"$set": {"level": updated_fort_level}}
                )
                new_user_level = calculate_user_level(user_id)
                try:
                    socketio.emit(
                        "user-level-updated",
                        {
                            "user_id": user_id,
                            "level": new_user_level,
                        }
                    )
                    socketio.emit("fort-level-updated", {"fort_id": cell.get("fort_id"), "level": updated_fort_level})
                    print(f"is_in_fort")
                except Exception as e:
                    app.logger.error(f"Error emitting user-level-updated: {e}")

    else:
        cells_collection.insert_one({
            "coordinates": cell_coordinates,
            "user_id": user_id,
            "level": 1,
            "is_in_fort": False,
            "color": user.get("color"),
        })
        updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
        try:
            socketio.emit("cell-updated", updated_cell)
        except Exception as e:
            app.logger.error(f"Error emitting cell-updated: {e}")

    detect_and_mark_fort((row, col), user_id)

    return jsonify({
        "success": True,
        "energy_remaining": {
            # "charges": charges,
            "clicks_in_current_charge": clicks_in_charge,
        }
    }), 200



@app.route("/calculate-energy", methods=["POST"])
def calculate_energy_endpoint():
    """
    Endpoint to calculate and update energy recharge for a user.
    """
    data = request.json
    user_id = data.get("userId")

    # Fetch user details
    user = users_collection.find_one({"telegram_user_id": int(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    level = calculate_user_level(user_id)
    energy = user.get("energy", {})
    now = datetime.utcnow()
    clicks_per_charge = energy.get("clicks_per_charge", MAX_CLICK_PER_CHARGE)
    clicks_in_charge = energy.get("clicks_in_charge", 0)
    recharged = energy.get("recharged", 0)
    last_click_timestamp = energy.get("last_click_timestamp")

    # Check if more than 24 hours have passed since the last click
    if last_click_timestamp:
        elapsed_seconds = (now - last_click_timestamp).total_seconds()
        if elapsed_seconds >= 86400:  # 24 hours in seconds
            # Reset energy state for the user
            clicks_per_charge = MAX_CLICK_PER_CHARGE
            clicks_in_charge = 0
            recharged = 0
            users_collection.update_one(
                {"telegram_user_id": int(user_id)},
                {
                    "$set": {
                        "energy.clicks_per_charge": clicks_per_charge,
                        "energy.clicks_in_charge": clicks_in_charge,
                        "energy.recharged": recharged,
                    }
                }
            )
            print(f"✅ Energy reset for user {user_id} after 24 hours of inactivity.")
        else:
            # If less than 24 hours, calculate the recharged clicks
            if clicks_per_charge < MAX_CLICK_PER_CHARGE and recharged < TOTAL_RECHARGABLE_ENERGY:
                recharged_energy = math.floor(elapsed_seconds / RECHARGE_INTERVAL_SECONDS) * ENERGY_RECHARGE_PER_SEC
                if recharged_energy + recharged > TOTAL_RECHARGABLE_ENERGY:
                    new_recharged = TOTAL_RECHARGABLE_ENERGY
                else:
                    new_recharged = recharged_energy + recharged

                if clicks_per_charge + recharged_energy > MAX_CLICK_PER_CHARGE:
                    new_clicks_per_charge = MAX_CLICK_PER_CHARGE
                else: 
                    new_clicks_per_charge = clicks_per_charge + recharged_energy

                users_collection.update_one(
                    {"telegram_user_id": int(user_id)},
                    {
                        "$set": {
                            "energy.clicks_per_charge": new_clicks_per_charge,
                            "energy.recharged": new_recharged,
                        }
                    }
                )
                clicks_per_charge = new_clicks_per_charge
                recharged = new_recharged
                print(f"🔄 Energy updated for user {user_id}: clicks_per_charge={clicks_per_charge}, recharged={recharged}")

    return jsonify({
        "success": True,
        "clicks_per_charge": clicks_per_charge,
        "clicks_in_charge": clicks_in_charge,
        "recharged": recharged,
        "charges": TOTAL_RECHARGABLE_ENERGY / ENERGY_IN_ONE_CHARGE - math.floor(recharged / ENERGY_IN_ONE_CHARGE),
        "level": level
    }), 200




def calculate_user_level(user_id):
    """
    Calculate the level of a user based on their forts.
    Formula: UserLevel = (Average level of all forts * Total area of all forts) / 100
    """
    # Fetch all forts owned by the user
    user_forts = list(forts_collection.find({"user_id": user_id}, {"level": 1, "inner_cells": 1}))

    if not user_forts:
        # If user has no forts, return level 0
        return 0

    # Calculate the total level of all forts and the number of active forts
    total_level = sum(fort["level"] for fort in user_forts)
    print(f"🚀 ~ total_level:", total_level)
    active_fort_count = len(user_forts)

    # Calculate the average level of all forts
    average_fort_level = total_level / active_fort_count
    print(f"🚀 ~ active_fort_count:", active_fort_count)
    print(f"🚀 ~ average_fort_level:", average_fort_level)

    # Calculate the total area of all forts (sum of inner cells)
    total_fort_area = sum(len(fort["inner_cells"]) for fort in user_forts)
    print(f"🚀 ~ total_fort_area:", total_fort_area)

    # Calculate the user level
    user_level = (average_fort_level * total_fort_area) / 100
    rounded_user_level = math.floor(user_level)

    print(f"🚀 ~ user_level:", user_level)

    # Round down to the nearest integer
    return int(rounded_user_level)


# @app.route("/recharge-energy", methods=["POST"])
# def recharge_energy():
#     """Fetch and return user energy details."""
#     data = request.json
#     user_id = data.get("userId")

#     # Fetch user energy details from the database
#     user = users_collection.find_one({"telegram_user_id": int(user_id)})
#     if not user:
#         return jsonify({"error": "User not found"}), 404

#     # Extract energy details
#     energy = user.get("energy", {})
#     clicks_per_charge = energy.get("clicks_per_charge", 0)
#     clicks_in_charge = energy.get("clicks_in_charge", 0)
#     recharged = energy.get("recharged", 0)

#     print(f"🚀 ~ math.floor(new_recharged / ENERGY_IN_ONE_CHARGE):", math.floor(recharged / ENERGY_IN_ONE_CHARGE))
#     return jsonify({
#         "success": True,
#         "clicks_per_charge": clicks_per_charge,
#         "clicks_in_charge": clicks_in_charge,
#         "recharged": recharged,
#         "charges": math.floor(recharged / ENERGY_IN_ONE_CHARGE)
#     }), 200



def calculate_fort_level(fort_id):
    """Calculate the level of a fort based on the minimum level of its border cells."""
    border_cells = cells_collection.find({"fort_id": fort_id, "is_border": True})
    levels = [cell["level"] for cell in border_cells]
    return min(levels, default=1)

def recharge_users():
    """Fetch users from the database and recharge energy."""
    try:
        users = users_collection.find()  # Fetch all users
        for user in users:
            user_id = user["telegram_user_id"]
            energy = user.get("energy", {})
            clicks_per_charge = energy.get("clicks_per_charge", 0)
            recharged = energy.get("recharged", 0)
            last_click_timestamp = energy.get("last_click_timestamp", None)

            # Check if 24 hours have passed since the last click
            if last_click_timestamp:
                # last_click_time = datetime.strptime(last_click_timestamp, "%Y-%m-%dT%H:%M:%S.%f")
                if (datetime.utcnow() - last_click_timestamp).total_seconds() > 86400:
                    if recharged > 0:
                        # Reset energy if 24 hours have passed
                        users_collection.update_one(
                            {"telegram_user_id": user_id},
                            {
                                "$set": {
                                    "energy.clicks_per_charge": MAX_CLICK_PER_CHARGE,
                                    "energy.clicks_in_charge": 0,
                                    "energy.recharged": 0,
                                }
                            }
                        )
                        print(f"Energy reset for user {user_id} as 24 hours have passed since the last click.")
                        continue

            # Check if clicks_per_charge is less than the maximum value
            if clicks_per_charge < MAX_CLICK_PER_CHARGE:
                if recharged < TOTAL_RECHARGABLE_ENERGY:
                    # Increment clicks_per_charge and recharged
                    if clicks_per_charge + ENERGY_RECHARGE_PER_SEC > MAX_CLICK_PER_CHARGE:
                        new_clicks_per_charge = MAX_CLICK_PER_CHARGE
                    else:
                        new_clicks_per_charge = clicks_per_charge + ENERGY_RECHARGE_PER_SEC

                    if recharged + ENERGY_RECHARGE_PER_SEC > TOTAL_RECHARGABLE_ENERGY:
                        new_recharged = TOTAL_RECHARGABLE_ENERGY
                    else:
                        new_recharged = recharged + ENERGY_RECHARGE_PER_SEC

                    # Update the user's energy in the database
                    users_collection.update_one(
                        {"telegram_user_id": user_id},
                        {
                            "$set": {
                                "energy.clicks_per_charge": new_clicks_per_charge,
                                "energy.recharged": new_recharged,
                            }
                        }
                    )

                    # Emit a socket event after recharging
                    socketio.emit(
                        "user-recharged",
                        {
                            "user_id": str(user_id),
                            "clicks_per_charge": new_clicks_per_charge,
                            "recharged": new_recharged,
                            "charges": TOTAL_RECHARGABLE_ENERGY / ENERGY_IN_ONE_CHARGE - math.floor(new_recharged / ENERGY_IN_ONE_CHARGE),
                        }
                    )
                    print(f"🚀 ~ math.floor(new_recharged / ENERGY_IN_ONE_CHARGE):", math.floor(new_recharged / ENERGY_IN_ONE_CHARGE))
                    print(f"Recharged user {user_id}: clicks_per_charge={new_clicks_per_charge}, recharged={new_recharged}")

                else:
                    print(f"User {user_id} has reached the recharge limit (recharged={recharged}).")
    except Exception as e:
        print(f"Error in periodic task: {e}")

def run_periodic_task(interval, func):
    """Run the specified function periodically every interval seconds."""
    while True:
        time.sleep(interval)
        func()

# Run the periodic task every 1 second
threading.Thread(target=lambda: run_periodic_task(RECHARGE_INTERVAL_SECONDS, recharge_users), daemon=True).start()

if __name__ == "__main__":
    from gevent import monkey
    monkey.patch_all()

    print("Starting Flask app with gevent...")
    socketio.run(app, host="0.0.0.0", port=5000)
