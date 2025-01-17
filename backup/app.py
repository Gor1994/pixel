from flask import Flask, request, jsonify, session
from uuid import uuid4
from flask_cors import CORS
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
import certifi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from threading import Thread
import random
import secrets
import logging
import requests
import asyncio
from flask_session import Session


app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "http://localhost:3000"}})

app.secret_key = "aaa"
import os

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
TELEGRAM_BOT_TOKEN = '8076325725:AAHqtb8Z7mJu56NEceWYtLTvD1h-2rI3_Wg'
telegram_bot = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Constants
CODE_VALIDITY_MINUTES = 5  # Code expiration time


# Generate a random 6-digit login code
def generate_login_code():
    return f"{random.randint(100000, 999999)}"


# Send login code to Telegram
async def send_login_code_to_telegram(telegram_user_id, code):
    try:
        message = f"Your login code is: {code}\nIt is valid for {CODE_VALIDITY_MINUTES} minutes."
        await telegram_bot.bot.send_message(chat_id=telegram_user_id, text=message)   

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

        telegram_url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'

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
async def start(update: ContextTypes.DEFAULT_TYPE, context):
    """Handle the /start command to store Telegram user details."""
    telegram_user_id = update.effective_user.id
    telegram_username = update.effective_user.username or "Unknown"

    # Check if the user already exists in the database
    existing_user = users_collection.find_one({"telegram_user_id": telegram_user_id})

    if existing_user:
        await update.message.reply_text(f"Welcome back, {telegram_username}!")
    else:
        user_data = {
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "registered_at": datetime.utcnow().isoformat(),
        }
        users_collection.insert_one(user_data)
        await update.message.reply_text(f"Welcome, {telegram_username}! You have been registered.")

    print(f"User {telegram_username} with ID {telegram_user_id} started the bot.")


# Start the Telegram bot
def start_telegram_bot():
    """Start the Telegram bot."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(telegram_bot.run_polling())


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text("Sorry, I didn't understand that command.")

def telegram_bot():
    """Start the Telegram bot."""
    # Initialize the bot application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))

    print("Starting Telegram bot...")

    # Manually create and set an event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Run the bot in the thread's event loop without signal handlers
    loop.run_until_complete(application.run_polling(allowed_updates=None, stop_signals=None))



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

from uuid import uuid4

def detect_and_mark_fort(start_cell):
    """Detect and mark forts (rectangles) with a minimum size, while handling overlapping or enclosed forts."""
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

    # Start detection from the specified cell
    start_row, start_col = start_cell
    connected_cells = dfs(start_row, start_col)

    # Group cells by rows
    rows = {}
    for r, c in connected_cells:
        if r not in rows:
            rows[r] = []
        rows[r].append(c)

    # Sort rows and their columns
    for r in rows:
        rows[r] = sorted(rows[r])

    # Check for rectangles
    row_indices = sorted(rows.keys())
    for start_row_idx in range(len(row_indices)):
        for end_row_idx in range(start_row_idx + FORT_MIN_SIZE - 1, len(row_indices)):
            start_row = row_indices[start_row_idx]
            end_row = row_indices[end_row_idx]

            # Check if all required rows exist
            if not all(row in rows for row in range(start_row, end_row + 1)):
                continue

            # Determine the column range for the rectangle
            start_col = min(min(rows[row]) for row in range(start_row, end_row + 1))
            end_col = max(max(rows[row]) for row in range(start_row, end_row + 1))

            # Ensure the rectangle meets the minimum size requirements
            if (end_row - start_row + 1) < FORT_MIN_SIZE or (end_col - start_col + 1) < FORT_MIN_SIZE:
                continue

            # Identify border and inner cells
            border_cells = []
            inner_cells = []

            for r in range(start_row, end_row + 1):
                for c in range(start_col, end_col + 1):
                    if r == start_row or r == end_row or c == start_col or c == end_col:
                        border_cells.append(f"{r}-{c}")
                    else:
                        inner_cells.append(f"{r}-{c}")

            # Generate a unique `fort_id` for this fort
            new_fort_id = str(uuid4())

            # Validate the borders of the rectangle
            is_valid_rectangle = True

            # Check top and bottom rows (must be fully filled across start_col to end_col)
            if not all((start_row, col) in connected_cells for col in range(start_col, end_col + 1)):
                is_valid_rectangle = False
            if not all((end_row, col) in connected_cells for col in range(start_col, end_col + 1)):
                is_valid_rectangle = False

            # Check left and right columns (must be fully filled from start_row to end_row)
            if not all((row, start_col) in connected_cells for row in range(start_row, end_row + 1)):
                is_valid_rectangle = False
            if not all((row, end_col) in connected_cells for row in range(start_row, end_row + 1)):
                is_valid_rectangle = False

            if is_valid_rectangle:
                print(f"🏰 Detected valid rectangle from ({start_row}, {start_col}) to ({end_row}, {end_col})")

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
                    "created_at": datetime.utcnow(),
                }

                # Check for existing inner forts
                overlapping_forts = list(forts_collection.find({"border_cells": {"$in": inner_cells}}))
                if overlapping_forts:
                    print(f"❌ Cannot create larger fort from ({start_row}, {start_col}) to ({end_row}, {end_col}) because it encloses another fort.")

                    # Retrieve all existing cells for this larger fort
                    existing_cells = list(cells_collection.find({"coordinates": {"$in": border_cells + inner_cells}}))
                    existing_fort_ids = {cell["coordinates"] for cell in existing_cells if "fort_id" in cell}

                    # Remove only the cells without a valid fort_id in bulk
                    cells_to_remove = [cell for cell in (border_cells + inner_cells) if cell not in existing_fort_ids]
                    if cells_to_remove:
                        cells_collection.delete_many({"coordinates": {"$in": cells_to_remove}})

                    # Do not add the larger fort
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
                return True  # A valid fort has been detected

    return False  # No fort detected



@app.route("/get-grid", methods=["GET"])
def get_grid():
    """Return the current grid state with fort levels included."""
    cells = list(cells_collection.find({}, {"_id": 0}))
    forts = list(forts_collection.find({}, {"_id": 0, "fort_id": 1, "level": 1}))

    # Map fort_id to fort_level
    fort_levels = {fort["fort_id"]: fort["level"] for fort in forts}

    # Add fort_level to each cell if it belongs to a fort
    for cell in cells:
        if "fort_id" in cell and cell["fort_id"] in fort_levels:
            cell["fort_level"] = fort_levels[cell["fort_id"]]

    return jsonify(cells)

@app.route("/claim-cell", methods=["POST"])
def claim_cell():
    """Handle cell clicks."""
    data = request.json
    row, col = data.get("row"), data.get("col")
    user_id = data.get("userId")

    cell_coordinates = f"{row}-{col}"

    # Fetch the current cell
    existing_cell = cells_collection.find_one({"coordinates": cell_coordinates})

    if existing_cell:
        # If the cell is owned by the current user, increment its level
        if existing_cell["user_id"] == user_id:
            new_level = existing_cell.get("level", 0) + 1
            cells_collection.update_one(
                {"coordinates": cell_coordinates},
                {"$set": {"level": new_level}}
            )
            print(f"✅ Cell ({row}, {col}) level updated to {new_level} by user {user_id}")

            # If the cell is part of a fort, recalculate and update the fort level
            if "fort_id" in existing_cell:
                fort_id = existing_cell["fort_id"]
                fort_level = calculate_fort_level(fort_id)
                forts_collection.update_one(
                    {"fort_id": fort_id},
                    {"$set": {"level": fort_level}}
                )
                print(f"🔄 Fort ({fort_id}) level updated to {fort_level}")
        else:
            return jsonify({"error": "Cell is owned by another user"}), 400
    else:
        # If the cell is not owned, claim it for the user
        cell_data = {
            "coordinates": cell_coordinates,
            "is_in_fort": False,
            "user_id": user_id,
            "level": 1,
            "timestamp": datetime.utcnow().isoformat(),
        }
        cells_collection.insert_one(cell_data)
        print(f"✅ Cell ({row}, {col}) claimed by user {user_id}")

    # Detect and mark forts starting from this cell
    detect_and_mark_fort(start_cell=(row, col))

    return jsonify({"success": True})


def calculate_fort_level(fort_id):
    """Calculate the level of a fort based on the minimum level of its border cells."""
    border_cells = cells_collection.find({"fort_id": fort_id, "is_border": True})
    levels = [cell["level"] for cell in border_cells]
    return min(levels, default=1)

if __name__ == "__main__":
    bot_thread = Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    app.run(debug=True, use_reloader=False)
