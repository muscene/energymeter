from flask import Flask, render_template, request, jsonify
import joblib
import pandas as pd

app = Flask(__name__)

# Load the trained model with compatibility check
MODEL_FILENAME = "customer_payment_model.pkl"
try:
    loaded_model = joblib.load(MODEL_FILENAME)
except ValueError as e:
    raise ValueError("Model version mismatch. Consider retraining or saving with the current sklearn version.") from e

@app.route('/predict')
def index():
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

if __name__ == '__main__':
    
    app.run(debug=True, host="0.0.0.0", port=5000)

    
