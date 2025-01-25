from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from uuid import uuid4
from flask_cors import CORS
from pymongo import MongoClient, UpdateOne, DeleteOne
from datetime import datetime, timedelta
import certifi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults
from threading import Thread
import random
import secrets
import logging
import requests
import asyncio
from flask_session import Session
import json
from bson import ObjectId
from multiprocessing import Process

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

def detect_and_mark_fort(start_cell):
    """Detect and mark forts (rectangles) with a minimum size, while handling overlapping or enclosed forts.
    Can detect forts even when there are extra connected cells outside the rectangle."""
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

    def find_largest_rectangle(cells):
        """Find the largest valid rectangle within a set of connected cells."""
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
            for bottom in range(top + FORT_MIN_SIZE - 1, max_row + 1):
                for left in range(min_col, max_col + 1):
                    for right in range(left + FORT_MIN_SIZE - 1, max_col + 1):
                        # Check if this rectangle is valid
                        is_valid = True
                        border_cells = set()
                        inner_cells = set()
                        empty_cells = set()  # Track empty cells

                        # Check all cells in the potential rectangle
                        for r in range(top, bottom + 1):
                            for c in range(left, right + 1):
                                if r == top or r == bottom or c == left or c == right:
                                    if (r, c) not in cells:
                                        is_valid = False
                                        break
                                    border_cells.add((r, c))
                                else:
                                    inner_cells.add((r, c))
                                    # Check for empty cells
                                    cell_data = grid.get((r, c), {})
                                    if "user_id" not in cell_data or cell_data.get("user_id") is None:
                                        empty_cells.add((r, c))
                            if not is_valid:
                                break

                        # Check minimum size, at least one inner cell, and at least one empty cell
                        if (not is_valid or
                                bottom - top + 1 < FORT_MIN_SIZE or
                                right - left + 1 < FORT_MIN_SIZE or
                                not inner_cells or
                                not empty_cells):  # Ensure at least one empty cell
                            continue

                        # Calculate area
                        area = (bottom - top + 1) * (right - left + 1)
                        if area > max_area:
                            max_area = area
                            best_rectangle = {
                                'top': top,
                                'bottom': bottom,
                                'left': left,
                                'right': right,
                                'border_cells': border_cells,
                                'inner_cells': inner_cells
                            }

        return best_rectangle

    # Start detection from the specified cell
    start_row, start_col = start_cell
    connected_cells = dfs(start_row, start_col)

    # Find the largest valid rectangle within connected cells
    rectangle = find_largest_rectangle(connected_cells)
    
    if not rectangle:
        return False

    # Convert coordinate tuples to string format for database
    border_cells = [f"{r}-{c}" for r, c in rectangle['border_cells']]
    inner_cells = [f"{r}-{c}" for r, c in rectangle['inner_cells']]

    # Validate ownership of all cells
    owner_ids = set(
        grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])), {}).get("user_id")
        for coord in border_cells
    )

    if len(owner_ids) > 1 or None in owner_ids:
        print("❌ Cannot create fort: Not all cells belong to the same user.")
        return False

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

    # Remove the fort from the database
    forts_collection.delete_one({"fort_id": fort_id})
    print(f"Fort {fort_id} destroyed.")

    # Fetch all cells associated with the fort
    affected_cells = list(cells_collection.find({"fort_id": fort_id}))

    # Prepare lists for deleted and updated cells
    deleted_cells = []
    remaining_cells = []

    # Prepare bulk operations
    bulk_operations = []

    for cell in affected_cells:
        # Check if the cell's level is 0
        if cell.get("level", 1) == 0:
            # Remove the cell from the collection if its level is 0
            deleted_cells.append(cell["coordinates"])
            bulk_operations.append(DeleteOne({"coordinates": cell["coordinates"]}))
        else:
            # Update the remaining cells to reset fort-related properties to False
            remaining_cells.append(cell["coordinates"])
            bulk_operations.append(
                UpdateOne(
                    {"coordinates": cell["coordinates"]},
                    {"$set": {
                        "is_border": False,
                        "is_inner": False,
                        "is_in_fort": False,
                        "fort_id": None  # Remove the fort association
                    }}
                )
            )

    # Execute bulk operations
    if bulk_operations:
        try:
            result = cells_collection.bulk_write(bulk_operations)
            print(f"Bulk write result: {result.bulk_api_result}")
        except Exception as e:
            print(f"Error executing bulk write: {e}")
            raise

    # Notify clients about the destroyed fort
    socketio.emit(
        "fort-destroyed",
        {
            "fort_id": fort_id,
            "affected_cells": remaining_cells,  # Cells that had their fort properties reset
        }
    )

    # Notify clients about deleted cells
    for coordinates in deleted_cells:
        print(f"🚀 ~ coordinates:", coordinates)
        socketio.emit("cell-deleted", {"coordinates": coordinates})

    return True


@app.route("/claim-cell", methods=["POST"])
def claim_cell_with_energy():
    """Handle cell clicks with energy validation."""
    data = request.json
    row, col = data.get("row"), data.get("col")
    user_id = data.get("userId")
    print(f"🚀 ~ user_id:", user_id)

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
    clicks_per_charge = energy.get("clicks_per_charge", 1000000)
    last_recharge_timestamp = energy.get("last_recharge_timestamp", None)
    charges = energy.get("charges", 0)
    max_charges = 4  # Updated maximum charges
    recharge_duration = 600  # Recharge time in seconds (10 minutes)
    clicks_per_charge_max = 1000000

    now = datetime.utcnow()

    # Check if charges have reached the maximum and 24 hours have passed
    if charges >= max_charges:
        if last_recharge_timestamp:
            elapsed_hours = (now - last_recharge_timestamp).total_seconds() / 3600
            if elapsed_hours >= 24:
                # Reset energy state for the user
                charges = 0
                clicks_in_charge = 0
                clicks_per_charge = 1000000  # Default clicks per charge after reset
                last_recharge_timestamp = None

                users_collection.update_one(
                    {"telegram_user_id": int(user_id)},
                    {
                        "$set": {
                            "energy.charges": charges,
                            "energy.clicks_in_charge": clicks_in_charge,
                            "energy.clicks_per_charge": clicks_per_charge,
                        },
                        "$unset": {"energy.last_recharge_timestamp": ""}
                    }
                )
                print("✅ 24 hours elapsed. Energy reset for the user.")
            else:
                print("❌ Max charges reached. Wait for 24 hours to reset.")
                return jsonify({"error": "Max charges reached. Wait for 24 hours to reset."}), 400
        else:
            print("❌ Max charges reached and last recharge timestamp missing.")
            return jsonify({"error": "Max charges reached. Wait for 24 hours to reset."}), 400

    # Condition 1: If clicks_in_charge >= clicks_per_charge (user exhausted current charge)
    if clicks_in_charge >= clicks_per_charge:
        elapsed_seconds = (now - last_recharge_timestamp).total_seconds() if last_recharge_timestamp else 0
        if elapsed_seconds < recharge_duration:
            print("❌ Recharge ongoing. Please wait.")
            return jsonify({"error": "Recharging... Please wait before claiming more cells."}), 400

        if elapsed_seconds >= recharge_duration:
            if charges < max_charges:
                charges += 1
                clicks_in_charge = 0
                clicks_per_charge = 0
                last_recharge_timestamp = now

                users_collection.update_one(
                    {"telegram_user_id": int(user_id)},
                    {
                        "$set": {
                            "energy.charges": charges,
                            "energy.clicks_in_charge": clicks_in_charge,
                            "energy.clicks_per_charge": clicks_per_charge,
                            "energy.last_recharge_timestamp": last_recharge_timestamp,
                        }
                    }
                )
                print("Charge increased. Please wait for recharge to complete.")
                return jsonify({"error": "Max clicks reached. Please wait for energy recharge."}), 400

    # Increment clicks_in_charge for valid cases
    clicks_in_charge += 1
    if clicks_in_charge >= clicks_per_charge_max:
        if charges < max_charges:
            charges += 1
            clicks_in_charge = 0
            clicks_per_charge = 0
            last_recharge_timestamp = now

            users_collection.update_one(
                {"telegram_user_id": int(user_id)},
                {
                    "$set": {
                        "energy.charges": charges,
                        "energy.clicks_in_charge": clicks_in_charge,
                        "energy.clicks_per_charge": clicks_per_charge,
                        "energy.last_recharge_timestamp": last_recharge_timestamp,
                    }
                }
            )
            print(f"Charge increased to {charges}. Reset clicks_in_charge and clicks_per_charge.")

    users_collection.update_one(
        {"telegram_user_id": int(user_id)},
        {
            "$set": {
                "energy.clicks_in_charge": clicks_in_charge,
                "energy.last_click_timestamp": now,
            }
        }
    )
    print(f"Click registered. Clicks in charge: {clicks_in_charge}")

    # Claim the cell logic
    cell_coordinates = f"{row}-{col}"
    cell = cells_collection.find_one({"coordinates": cell_coordinates})
    if cell:
        # Determine max level
        max_level = 2  # Default max level for cells not in a fort
        if cell.get("is_in_fort"):
            fort_id = cell.get("fort_id")
            border_cell_count = cells_collection.count_documents({"fort_id": fort_id, "is_border": True})
            max_level = border_cell_count * 2

        if cell["user_id"] != user_id:
            new_level = max(cell.get("level", 0) - 1, 0)
            if new_level <= 0:
                cells_collection.delete_one({"coordinates": cell_coordinates})
                socketio.emit("cell-deleted", {"coordinates": cell_coordinates})
                if cell.get("is_in_fort"):
                    destroy_fort(cell.get("fort_id"))
            else:
                cells_collection.update_one(
                    {"coordinates": cell_coordinates},
                    {"$set": {"level": new_level}}
                )
                updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
                try:
                    socketio.emit("cell-updated", updated_cell)
                    socketio.emit("test-event", {"message": "Test message from server"})

                    print(f"emiting event")
                except Exception as e:
                    print(f"faild", e)
                    app.logger.error(f"Error emitting cell-updated: {e}")
        else:
            current_level = cell.get("level", 0)
            new_level = min(current_level + 1, max_level)
            cells_collection.update_one(
                {"coordinates": cell_coordinates},
                {"$set": {"level": new_level, "color": user.get("color")}}
            )
            updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
            
            try:
                socketio.emit("cell-updated", updated_cell)
                socketio.emit("test-event", {"message": "Test message from server"})

                print(f"emiting event")
            except Exception as e:
                print(f"faild", e)
                app.logger.error(f"Error emitting cell-updated: {e}")

            if cell.get("is_in_fort"):
                updated_fort_level = calculate_fort_level(cell.get("fort_id"))
                forts_collection.update_one(
                    {"fort_id": cell.get("fort_id")},
                    {"$set": {"level": updated_fort_level}}
                )
                socketio.emit("fort-level-updated", {"fort_id": cell.get("fort_id"), "level": updated_fort_level})
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
            socketio.emit("test-event", {"message": "Test message from server"})

            print(f"emiting event")
        except Exception as e:
            print(f"faild", e)
            app.logger.error(f"Error emitting cell-updated: {e}")

    detect_and_mark_fort((row, col))

    return jsonify({
        "success": True,
        "energy_remaining": {
            "charges": charges,
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

    energy = user.get("energy", {})
    now = datetime.utcnow()
    clicks_per_charge = energy.get("clicks_per_charge", 1000000)
    clicks_per_charge_max = 1000000  # Maximum clicks per charge
    clicks_in_charge = energy.get("clicks_in_charge", 0)
    charges = energy.get("charges", 0)
    last_recharge_timestamp = energy.get("last_recharge_timestamp", None)

    # Check if charges are 4 and 24 hours have passed
    if charges >= 4:
        if last_recharge_timestamp:
            elapsed_hours = (now - last_recharge_timestamp).total_seconds() / 3600
            if elapsed_hours >= 24:
                # Reset energy state for the user
                charges = 0
                clicks_in_charge = 0
                clicks_per_charge = 1000000  # Default clicks per charge after reset
                last_recharge_timestamp = None

                users_collection.update_one(
                    {"telegram_user_id": int(user_id)},
                    {
                        "$set": {
                            "energy.charges": charges,
                            "energy.clicks_in_charge": clicks_in_charge,
                            "energy.clicks_per_charge": clicks_per_charge,
                        },
                        "$unset": {"energy.last_recharge_timestamp": ""}
                    }
                )
                print("✅ 24 hours elapsed. Energy reset for the user.")

    # Calculate remaining clicks if charges are not maxed out
    if charges == 0:
        # If no charges, calculate remaining clicks
        remaining_clicks = clicks_per_charge - clicks_in_charge
    else:
        # Handle clicks per charge recharge logic
        remaining_clicks = clicks_per_charge - clicks_in_charge
        if clicks_per_charge < clicks_per_charge_max:
            elapsed_seconds = (now - last_recharge_timestamp).total_seconds() if last_recharge_timestamp else 0

            if elapsed_seconds >= 600:  # If 10 minutes have passed
                clicks_per_charge = clicks_per_charge_max
                users_collection.update_one(
                    {"telegram_user_id": int(user_id)},
                    {"$set": {"energy.clicks_per_charge": clicks_per_charge}}
                )
            else:
                # Calculate recharged clicks
                recharge_rate = clicks_per_charge_max / 600  # 10 clicks in 10 minutes
                recharged_clicks = int(elapsed_seconds * recharge_rate)
                clicks_per_charge = min(clicks_per_charge_max, recharged_clicks)

                # Update the recharged clicks in the database
                users_collection.update_one(
                    {"telegram_user_id": int(user_id)},
                    {"$set": {"energy.clicks_per_charge": clicks_per_charge}}
                )

    # Calculate remaining clicks again in case of any updates
    remaining_clicks = clicks_per_charge - clicks_in_charge

    return jsonify({
        "remaining_clicks": remaining_clicks,
        "charges": charges
    }), 200



def calculate_user_level(user_id):
    """
    Calculate the level of a user based on their forts.
    Formula: (Count of user's forts * Maximum level fort) / 10
    """
    # Fetch all forts owned by the user
    user_forts = list(forts_collection.find({"user_id": user_id}, {"level": 1}))

    if not user_forts:
        # If user has no forts, return level 0
        return 0

    # Calculate the maximum fort level and count of forts
    max_fort_level = max(fort["level"] for fort in user_forts)
    fort_count = len(user_forts)

    # Calculate the user's level
    user_level = (fort_count * max_fort_level) / 10

    # Return the integer level
    return int(user_level)

@app.route("/recharge-energy", methods=["POST"])
def recharge_energy():
    """Recharge energy for the player based on elapsed time."""
    data = request.json
    user_id = data.get("userId")

    # Fetch user energy details
    user = users_collection.find_one({"telegram_user_id": int(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    energy = user.get("energy", {})
    now = datetime.utcnow()
    clicks_per_charge = energy.get("clicks_per_charge", 1000000)
    clicks_in_charge = energy.get("clicks_in_charge", 0)
    charges = energy.get("charges", 0)
    last_recharge_timestamp = energy.get("last_recharge_timestamp")

    # Energy calculation
    available_clicks = clicks_per_charge - clicks_in_charge
    if charges > 0 and last_recharge_timestamp:
        elapsed_seconds = (now - last_recharge_timestamp).total_seconds()
        if elapsed_seconds < 600:  # Only calculate if within recharge duration
            recharge_rate = clicks_per_charge / 600  # 500 clicks in 10 minutes
            recharged_clicks = int(elapsed_seconds * recharge_rate)
            available_clicks = min(clicks_per_charge, clicks_in_charge + recharged_clicks) - clicks_in_charge

    # Update energy in the database
    users_collection.update_one(
        {"telegram_user_id": int(user_id)},
        {
            "$set": {
                "energy.last_recharge_timestamp": now if charges > 0 else None,
            }
        }
    )

    return jsonify({
        "success": True,
        "available_clicks": available_clicks,
        "charges": charges,
    }), 200


def calculate_fort_level(fort_id):
    """Calculate the level of a fort based on the minimum level of its border cells."""
    border_cells = cells_collection.find({"fort_id": fort_id, "is_border": True})
    levels = [cell["level"] for cell in border_cells]
    return min(levels, default=1)

if __name__ == "__main__":
    from gevent import monkey
    monkey.patch_all()

    print("Starting Flask app with gevent...")
    socketio.run(app, host="0.0.0.0", port=5000)
