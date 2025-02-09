from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, jsonify
import joblib,sklearn,numpy
import pandas as pd

app = Flask(__name__)
loaded_model = joblib.load("optimized_customer_payment_model.pkl")  # Ensure this file exists

def init_db():
    # Initialize SQLite database
    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    # Create meter_data table (ensure serial_number is included)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meter_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT NOT NULL,
            balance REAL NOT NULL,
            consumption REAL NOT NULL,
            timestamp TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            owner_contact TEXT NOT NULL
        )
    ''')

    # Create alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    # Create recharges table to store historical recharges
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recharges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT NOT NULL,
            recharge_amount REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, consumption FROM meter_data')
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/api/recharge', methods=['POST'])
def recharge():
    data = request.get_json()
    serial_number = data.get('meter_serial_number')
    amount = data.get('recharge_amount', 0)

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"error": "Invalid recharge amount."}), 400

    if not serial_number or amount <= 0:
        return jsonify({"error": "Invalid serial number or amount."}), 400

    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    cursor.execute('SELECT balance FROM meter_data WHERE serial_number = ?', (serial_number,))
    row = cursor.fetchone()

    if row:
        current_balance = row[0]
        new_balance = current_balance + amount
        cursor.execute('UPDATE meter_data SET balance = ? WHERE serial_number = ?', (new_balance, serial_number))

        # Insert recharge record with timestamp
        cursor.execute('''
            INSERT INTO recharges (serial_number, recharge_amount, timestamp)
            VALUES (?, ?, datetime("now"))
        ''', (serial_number, amount))

        conn.commit()
        conn.close()

        return jsonify({"message": "Recharge successful!", "new_balance": new_balance, "timestamp": "datetime('now')"}), 200
    else:
        conn.close()
        return jsonify({"error": "Meter not found."}), 404

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    serial_number = data.get('serial_number')
    owner_name = data.get('owner_name')
    owner_contact = data.get('owner_contact')

    if not serial_number or not owner_name or not owner_contact:
        return jsonify({"error": "Missing fields."}), 400
    
    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO meter_data (serial_number, balance, consumption, timestamp, owner_name, owner_contact)
        VALUES (?, 0, 0, datetime("now"), ?, ?)
    ''', (serial_number, owner_name, owner_contact))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Meter registered successfully!"}), 200

@app.route('/api/registered_meters', methods=['GET'])
def get_registered_meters():
    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    # Fetch all registered meters
    cursor.execute('SELECT serial_number, owner_name, owner_contact, balance, timestamp FROM meter_data')
    meters = cursor.fetchall()
    conn.close()

    if meters:
        return jsonify(meters), 200
    else:
        return jsonify({"message": "No registered meters found."}), 404

@app.route('/api/recharges', methods=['GET'])
def get_recharge_history():
    serial_number = request.args.get('serial_number')
    
    if not serial_number:
        return jsonify({"error": "Serial number is required."}), 400

    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT recharge_amount, timestamp FROM recharges WHERE serial_number = ?
        ORDER BY timestamp DESC
    ''', (serial_number,))
    recharges = cursor.fetchall()
    conn.close()

    if recharges:
        return jsonify(recharges), 200
    else:
        return jsonify({"message": "No recharge history found for this meter."}), 404
@app.route('/api/get_recharges', methods=['GET'])
def get_recharges():
    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT timestamp, recharge_amount FROM recharges')
    recharges = cursor.fetchall()
    conn.close()

    # Format the data into a JSON-friendly format
    data = [{'timestamp': row[0], 'recharge_amount': row[1]} for row in recharges]
    return jsonify(data)

@app.route('/api/meter_status', methods=['GET'])
def get_meter_status():
    serial_number = request.args.get('serial_number')
    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT balance, consumption FROM meter_data WHERE serial_number = ? ORDER BY timestamp DESC LIMIT 1', (serial_number,))
    data = cursor.fetchone()
    conn.close()
    
    if data:
        balance, consumption = data
        status = "Over" if balance <= 0 else "Normal"
        return jsonify({"balance": balance, "consumption": consumption, "status": status})
    else:
        return jsonify({"error": "Meter not found."}), 404



MODEL_FILENAME = "optimized_customer_payment_model.pkl"
try:
    loaded_model = joblib.load(MODEL_FILENAME)
except ValueError as e:
    raise ValueError("Model version mismatch. Consider retraining or saving with the current sklearn version.") from e

@app.route('/pp')
def predicxt():
    # Render the index.html template
    return render_template('prediction.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        sample_customer_data = pd.DataFrame({
            "Previous Month Payment": [data.get("previous_month_payment", 0)],
            "Two Months Ago Payment": [data.get("two_months_ago_payment", 0)]
        })
        
        predicted_payment = loaded_model.predict(sample_customer_data)[0]
        return jsonify({"predicted_payment": round(predicted_payment, 2)})
    except Exception as e:
        return jsonify({"error": str(e)})
    
    # This will retrieve the total recharge amount for a specific meter, given a serial number
@app.route('/api/recharges/total', methods=['GET'])
def get_total_recharge():
    serial_number = request.args.get('serial_number')

    if not serial_number:
        return jsonify({"error": "Serial number is required."}), 400

    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(recharge_amount) FROM recharges WHERE serial_number = ?
    ''', (serial_number,))
    total_recharge = cursor.fetchone()[0]
    conn.close()

    if total_recharge is not None:
        return jsonify({"total_recharge": total_recharge}), 200
    else:
        return jsonify({"message": "No recharge history found for this meter."}), 404
    
    
    
    import datetime
# Monthly Recharge Amount:

# This will calculate the total recharge for the current month based on the timestamp.


@app.route('/api/recharges/monthly', methods=['GET'])
def get_monthly_recharge():
    serial_number = request.args.get('serial_number')

    if not serial_number:
        return jsonify({"error": "Serial number is required."}), 400

    # Get the current month and year
    current_month = datetime.datetime.now().month
    current_year = datetime.datetime.now().year

    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(recharge_amount) 
        FROM recharges 
        WHERE serial_number = ? 
        AND strftime('%Y', timestamp) = ? 
        AND strftime('%m', timestamp) = ?
    ''', (serial_number, str(current_year), str(current_month).zfill(2)))

    monthly_recharge = cursor.fetchone()[0]
    conn.close()

    if monthly_recharge is not None:
        return jsonify({"monthly_recharge": monthly_recharge}), 200
    else:
        return jsonify({"message": "No recharge history found for this meter this month."}), 404

# This will calculate the total recharge for the current week based on the timestamp.

import datetime

@app.route('/api/recharges/weekly', methods=['GET'])
def get_weekly_recharge():
    serial_number = request.args.get('serial_number')

    if not serial_number:
        return jsonify({"error": "Serial number is required."}), 400

    # Get the current week number and year
    current_week = datetime.datetime.now().isocalendar()[1]
    current_year = datetime.datetime.now().year

    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(recharge_amount) 
        FROM recharges 
        WHERE serial_number = ? 
        AND strftime('%Y', timestamp) = ? 
        AND strftime('%W', timestamp) = ?
    ''', (serial_number, str(current_year), str(current_week).zfill(2)))

    weekly_recharge = cursor.fetchone()[0]
    conn.close()

    if weekly_recharge is not None:
        return jsonify({"weekly_recharge": weekly_recharge}), 200
    else:
        return jsonify({"message": "No recharge history found for this meter this week."}), 404





@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        serial_number = data.get("serial_number")
        
        if not serial_number:
            return jsonify({"error": "Serial number is required."}), 400
        
        # Fetch recharge data for the given serial number
        conn = sqlite3.connect('energy_meter.db')
        cursor = conn.cursor()
        
        # Fetch the last month's recharge for prediction
        cursor.execute('''
            SELECT recharge_amount FROM recharges
            WHERE serial_number = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (serial_number,))
        
        recharge_data = cursor.fetchone()
        conn.close()

        if recharge_data:
            # Return recharge data and allow for prediction
            return jsonify({"monthly_recharge": recharge_data[0]}), 200
        else:
            return jsonify({"error": "No data found for this serial number."}), 404
    except Exception as e:
        return jsonify({"error": str(e)})

# Function to fetch recharge data from the database
# def get_recharge_data(serial_number):
#     conn = sqlite3.connect('energy_meter.db')
#     cursor = conn.cursor()

#     # Query to get recharge data based on serial number
#     cursor.execute('''
#         SELECT recharge_amount, timestamp FROM recharges WHERE serial_number = ?
#         ORDER BY timestamp DESC
#     ''', (serial_number,))
#     recharges = cursor.fetchall()
#     conn.close()

#     return recharges

# API endpoint to get recharge history
# @app.route('/api/recharges', methods=['GET'])
# def get_recharge_history():
#     serial_number = request.args.get('serial_number')
    
#     if not serial_number:
#         return jsonify({"error": "Serial number is required."}), 400

#     recharges = get_recharge_data(serial_number)

#     if recharges:
#         return jsonify(recharges), 200
#     else:
#         return jsonify({"message": "No recharge history found for this meter."}), 404



# def get_recharge_data(serial_number):
#     conn = sqlite3.connect('energy_meter.db')
#     cursor = conn.cursor()
#     cursor.execute('SELECT SUM(recharge_amount) FROM recharges WHERE serial_number = ?', (serial_number,))
#     recharge_sum = cursor.fetchone()[0] or 0  # Default to 0 if no data
#     conn.close()
#     return recharge_sum
# Prediction route to predict based on recharge data
# @app.route('/predictx', methods=['POST'])
# def predictx():
#     try:
#         # Get serial number from request data
#         data = request.get_json()
#         serial_number = data.get('serial_number')

#         if not serial_number:
#             return jsonify({"error": "Serial number is required."}), 400

#         # Get recharge data for the given serial number
#         recharges = get_recharge_data(serial_number)
        
#         if not recharges:
#             return jsonify({"error": "No recharge data found for this serial number."}), 404

#         # Process recharge data (e.g., aggregate it for prediction)
#         # Example: sum the recharge amounts for the last month
#         total_recharge = sum([recharge[0] for recharge in recharges])  # Summing recharge amounts
        
#         # Use the recharge data to make a prediction
#         sample_customer_data = pd.DataFrame({
#             "Previous Month Payment": [total_recharge],  # Use aggregated data
#             "Two Months Ago Payment": [total_recharge]   # Example: Use same for simplicity, modify as needed
#         })

#         predicted_payment = loaded_model.predict(sample_customer_data)[0]
        
#         return jsonify({"predicted_payment": round(predicted_payment, 2)})
    
#     except Exception as e:
#         return jsonify({"error": str(e)})

@app.route('/api/rechargex', methods=['POST'])
def rechargex():
    data = request.get_json()
    serial_number = data.get('meter_serial_number')
    amount = data.get('recharge_amount', 0)

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"error": "Invalid recharge amount."}), 400

    if not serial_number or amount <= 0:
        return jsonify({"error": "Invalid serial number or amount."}), 400

    conn = sqlite3.connect('energy_meter.db')
    cursor = conn.cursor()

    cursor.execute('SELECT balance FROM meter_data WHERE serial_number = ?', (serial_number,))
    row = cursor.fetchone()

    if row:
        current_balance = row[0]
        new_balance = current_balance + amount
        cursor.execute('UPDATE meter_data SET balance = ? WHERE serial_number = ?', (new_balance, serial_number))

        # Insert recharge record with timestamp
        cursor.execute('''
            INSERT INTO recharges (serial_number, recharge_amount, timestamp)
            VALUES (?, ?, datetime("now"))
        ''', (serial_number, amount))

        conn.commit()
        conn.close()

        return jsonify({"message": "Recharge successful!", "new_balance": new_balance}), 200
    else:
        conn.close()
        return jsonify({"error": "Meter not found."}), 404

# --- USSD FUNCTIONALITY ---
@app.route('/ussd', methods=['POST', 'GET'])
def ussd_callback():
    session_id = request.values.get("sessionId", None)
    phone_number = request.values.get("phoneNumber", None)
    text = request.values.get("text", "")

    response = ""

    if text == "":
        response = "CON Welcome to Meter Services\n"
        response += "1. Check Balance\n"
        response += "2. View Consumption\n"
        response += "3. Recharge Meter\n"

    elif text == "1":
        # Fetch balance using phone number (assuming 1 user per meter)
        query = "SELECT balance FROM meter_data WHERE owner_contact = ?"
        meter = execute_query(query, (phone_number,), fetchone=True)
        balance = meter[0] if meter else "N/A"
        response = f"END Your current balance is: KES {balance}"

    elif text == "2":
        # Fetch consumption data
        query = "SELECT consumption FROM meter_data WHERE owner_contact = ?"
        meter = execute_query(query, (phone_number,), fetchone=True)
        consumption = meter[0] if meter else "N/A"
        response = f"END Your consumption is: {consumption} kWh"

    elif text == "3":
        response = "CON Enter recharge amount\n"

    elif text.startswith("3*"):
        recharge_amount = text.split('*')[1]
        query = "INSERT INTO recharges (serial_number, recharge_amount, timestamp) VALUES (?, ?, ?)"
        execute_query(query, (phone_number, recharge_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        response = f"END Recharge of {recharge_amount} KES successful!"

    return response

# --- PAYMENT PREDICTION FUNCTIONALITY ---

def get_recharge_data(serial_number):
    """ Fetch recharge data from the database for a given serial number """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT recharge_amount FROM recharges WHERE serial_number = ?", (serial_number,))
    recharges = cursor.fetchall()
    conn.close()
    
    return recharges  # Returns a list of tuples [(amount,), (amount,)...]

@app.route('/predictx', methods=['POST'])
def predictx():
    try:
        # Get serial number from request data
        data = request.get_json()
        serial_number = data.get('serial_number')

        if not serial_number:
            return jsonify({"error": "Serial number is required."}), 400

        # Get recharge data for the given serial number
        recharges = get_recharge_data(serial_number)
        
        if not recharges:
            return jsonify({"error": "No recharge data found for this serial number."}), 404

        # Aggregate recharge data for prediction
        total_recharge = sum([recharge[0] for recharge in recharges])  # Sum recharge amounts

        # Create input data for the model (ensure column names match the trained model)
        sample_customer_data = pd.DataFrame({
            "Previous Month Payment": [total_recharge],  
            "Two Months Ago Payment": [total_recharge]  
        })

        # Make the prediction
        predicted_payment = loaded_model.predict(sample_customer_data)[0]
        
        return jsonify({"predicted_payment": round(predicted_payment, 2)})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    init_db()
    app.run(debug=False, host="0.0.0.0", port=5000)
