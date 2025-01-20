from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from uuid import uuid4
from flask_cors import CORS
from pymongo import MongoClient, UpdateOne
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

socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")

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

# Telegram Bot Handlers
#async def start(update: ContextTypes.DEFAULT_TYPE, context):
#   """Handle the /start command to store Telegram user details and initialize energy."""
#    telegram_user_id = update.effective_user.id
#   telegram_username = update.effective_user.username or "Unknown"
#   print(f"staaaaaaaaaaaaart")
#   # Default energy setup
#   initial_energy = {
#       "charges": 4,
#       "clicks_per_charge": 500,
#       "last_click_timestamp": datetime.utcnow(),
#       "last_recharge_timestamp": datetime.utcnow(),
#   }

    # Generate a random color hex
#    random_color_hex = generate_random_color_hex()

    # Check if the user already exists in the database
#    existing_user = users_collection.find_one({"telegram_user_id": telegram_user_id})

#    if existing_user:
#        await update.message.reply_text(f"Welcome back, {telegram_username}!")
        
        # Check and initialize energy if not already present
#        update_fields = {}
#        if "energy" not in existing_user:
#            print(f"Initializing energy for user {telegram_user_id}.")
#            update_fields["energy"] = initial_energy
        
        # Check and assign color if not already present
#        if "color" not in existing_user:
#            print(f"Assigning random color to user {telegram_user_id}.")
#            update_fields["color"] = random_color_hex
        
        # Update the user document if necessary
#        if update_fields:
#            result = users_collection.update_one(
#                {"telegram_user_id": int(telegram_user_id)},
#                {"$set": update_fields},
#                upsert=True
#            )
#            if result.matched_count > 0 or result.upserted_id:
#                print(f"✅ Updates applied for user {telegram_user_id}: {update_fields}.")
#                await update.message.reply_text("Your profile has been updated!")
#            else:
#                print(f"❌ Failed to update user {telegram_user_id}. Result: {result.raw_result}")
#    else:
        # Create a new user entry with energy and color
#        user_data = {
#            "telegram_user_id": telegram_user_id,
#            "telegram_username": telegram_username,
#            "registered_at": datetime.utcnow().isoformat(),
#            "energy": initial_energy,
#            "color": random_color_hex,
#        }
#        result = users_collection.insert_one(user_data)
#        if result.acknowledged:
#            print(f"✅ User {telegram_user_id} registered with initial energy and color.")
#            await update.message.reply_text(
#                f"Welcome, {telegram_username}! You have been registered, "
#                f"and your energy system and profile color are ready."
#            )
#        else:
#            print(f"❌ Failed to register user {telegram_user_id}.")

#    print(f"User {telegram_username} with ID {telegram_user_id} started the bot.")

#telegram_app.add_handler(CommandHandler("start", start))

# Handle unknown commands
#async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    """Handle unknown commands."""
#    await update.message.reply_text("Sorry, I didn't understand that command.")


#def start_telegram_bot():
#    """Start the Telegram bot."""
#    try:
#        print("Starting Telegram bot...")
        #loop = asyncio.new_event_loop()
        #asyncio.set_event_loop(loop)
#        #loop.run_until_complete(telegram_app.run_polling())
#        asyncio.run(telegram_app.run_polling())
#        print("Telegram bot started successfully.")
#    except telegram.error.Conflict as e:
#        print("Telegram bot conflict error. Ensure no other instance is running.")
#    except Exception as e:
#        print(f"Error starting Telegram bot: {e}")



####################################################################################################


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
                            if not is_valid:
                                break

                        # Check minimum size and at least one inner cell
                        if (not is_valid or 
                            bottom - top + 1 < FORT_MIN_SIZE or 
                            right - left + 1 < FORT_MIN_SIZE or
                            not inner_cells):
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

    # Generate a unique fort_id
    new_fort_id = str(uuid4())

    # Calculate fort level based on the minimum level of border cells
    fort_level = min(
        [grid.get((int(coord.split('-')[0]), int(coord.split('-')[1])), {}).get("level", 1) for coord in border_cells]
    )

    # Generate the fort data
    fort_data = {
        "fort_id": new_fort_id,
        "user_id": grid.get((start_row, start_col), {}).get("user_id"),
        "border_cells": border_cells,
        "inner_cells": inner_cells,
        "level": fort_level,
        "created_at": datetime.utcnow()
    }

    # Check for existing inner forts
    overlapping_forts = list(forts_collection.find({"border_cells": {"$in": inner_cells}}))
    if overlapping_forts:
        print(f"❌ Cannot create fort from ({rectangle['top']}, {rectangle['left']}) to ({rectangle['bottom']}, {rectangle['right']}) because it encloses another fort.")
        
        # Retrieve all existing cells for this fort
        existing_cells = list(cells_collection.find({"coordinates": {"$in": border_cells + inner_cells}}))
        existing_fort_ids = {cell["coordinates"] for cell in existing_cells if "fort_id" in cell}

        # Remove only the cells without a valid fort_id in bulk
        cells_to_remove = [cell for cell in (border_cells + inner_cells) if cell not in existing_fort_ids]
        if cells_to_remove:
            cells_collection.delete_many({"coordinates": {"$in": cells_to_remove}})

        return False

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
            print("Final fort_data to emit:", fort_data)
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
    print(f"🚀 ~ user:", user)
    if not user:
        print("❌ Player not found in the database.")
        return jsonify({"error": "Player not initialized: User not found"}), 416

    if "energy" not in user:
        print("❌ Energy data not found for the player.")
        return jsonify({"error": "Player not initialized: Energy data missing"}), 416

    energy = user["energy"]

    # Retrieve current energy details
    remaining_clicks_in_charge = energy.get("remaining_clicks_in_charge", energy["clicks_per_charge"])
    charges_remaining = energy["charges"]

    # Enforce that no clicks can be made if there is no energy
    if remaining_clicks_in_charge <= 0:
        print("❌ Current charge depleted. Cannot click without recharge.")
        return jsonify({"error": "Current charge depleted. Please recharge."}), 400

    # Enforce click interval
    now = datetime.utcnow()
    last_click = energy.get("last_click_timestamp", now)
    if (now - last_click).total_seconds() < 1:  # Less than 1-second interval
        print("❌ Click interval too short.")
        return jsonify({"error": "You are clicking too fast"}), 429

    # Deduct 1 click from the current charge
    remaining_clicks_in_charge -= 1

    # Update energy and last click timestamp
    users_collection.update_one(
        {"telegram_user_id": int(user_id)},
        {
            "$set": {
                "energy.charges": charges_remaining,
                "energy.remaining_clicks_in_charge": remaining_clicks_in_charge,
                "energy.last_click_timestamp": now,
            }
        }
    )

    # Claim the cell logic
    cell_coordinates = f"{row}-{col}"
    cell = cells_collection.find_one({"coordinates": cell_coordinates})
    if cell:
        if cell["user_id"] == user_id:
            new_level = cell.get("level", 0) + 1
            cells_collection.update_one(
                {"coordinates": cell_coordinates},
                {"$set": {"level": new_level, "color": user.get("color")}}  # Add color field
            )
        else:
            return jsonify({"error": "Cell owned by another user"}), 466
    else:
        cells_collection.insert_one({
            "coordinates": cell_coordinates,
            "user_id": user_id,
            "level": 1,
            "is_in_fort": False,
            "color": user.get("color"),  # Include the user's color
        })

    detect_and_mark_fort((row, col))
    # Broadcast updated cell to all connected clients
    updated_cell = cells_collection.find_one({"coordinates": cell_coordinates}, {"_id": 0})
    print(f"updatedCell", updated_cell)
    socketio.emit("cell-updated", updated_cell)
    return jsonify({
        "success": True,
        "energy_remaining": {
            "charges": charges_remaining,
            "clicks_in_current_charge": remaining_clicks_in_charge,
        }
    }), 200
@app.route("/recharge-energy", methods=["POST"])
def recharge_energy():
    """Recharge energy for the player based on elapsed time."""
    data = request.json
    user_id = data.get("userId")

    # Fetch user energy details
    user = users_collection.find_one({"telegram_user_id": int(user_id)})
    if not user or "energy" not in user:
        return jsonify({"error": "Player not initialized"}), 400

    energy = user["energy"]
    now = datetime.utcnow()
    charges_remaining = energy["charges"]

    # If no charges are remaining, cannot recharge
    if charges_remaining <= 0:
        print("❌ No charges remaining. Cannot recharge.")
        return jsonify({"error": "No charges remaining. Cannot recharge."}), 400

    # Recharge logic: reset clicks and decrease charges by 1
    remaining_clicks_in_charge = energy["clicks_per_charge"]
    charges_remaining -= 1

    # Update user's energy and last recharge timestamp
    users_collection.update_one(
        {"telegram_user_id": int(user_id)},
        {
            "$set": {
                "energy.charges": charges_remaining,
                "energy.remaining_clicks_in_charge": remaining_clicks_in_charge,
                "energy.last_recharge_timestamp": now,
            }
        }
    )

    return jsonify({
        "message": "Energy recharged",
        "charges": charges_remaining,
        "clicks_in_current_charge": remaining_clicks_in_charge,
    }), 200

def calculate_fort_level(fort_id):
    """Calculate the level of a fort based on the minimum level of its border cells."""
    border_cells = cells_collection.find({"fort_id": fort_id, "is_border": True})
    levels = [cell["level"] for cell in border_cells]
    return min(levels, default=1)

@app.route("/get-energy", methods=["POST"])
def get_energy():
    """Fetch the energy details of a user."""
    data = request.json
    user_id = data.get("userId")

    user = users_collection.find_one({"telegram_user_id": int(user_id)}, {"_id": 0, "energy": 1})
    if not user or "energy" not in user:
        return jsonify({"error": "Energy data not found"}), 400

    return jsonify({"energy": user["energy"]}), 200

if __name__ == "__main__":
    from gevent import monkey
    monkey.patch_all()

    print("Starting Flask app with gevent...")
    socketio.run(app, host="0.0.0.0", port=5000)
