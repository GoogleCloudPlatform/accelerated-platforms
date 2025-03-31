from flask import Flask, request, jsonify
import mlflow.sklearn
from sklearn.datasets import make_regression
import numpy as np

app = Flask(__name__)

mlflow.set_tracking_uri("http://mlflow-tracking-service.ml-team:5000")
model_name = "random-forest"
# Deploying version n. Change the version below for desired version
model_version = "1"

# Load the model from the Model Registry (Do this outside the route so it's only loaded once)
model_uri = f"models:/{model_name}/{model_version}"
model = mlflow.sklearn.load_model(model_uri)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Get data from the request. Expecting a JSON payload like:
        # { "data": [[feature1, feature2, feature3, feature4], [feature1, feature2, feature3, feature4], ...] }
        data = request.get_json()
        if not data or 'data' not in data:
            return jsonify({"error": "Invalid input. Please provide data in the format: {'data': [[feature1, feature2, feature3, feature4], ...]} "}), 400

        X_new = data['data']

        # Ensure X_new is a NumPy array
        X_new = np.array(X_new)

        # Basic validation: Check if each data point has the correct number of features
        for row in X_new:
            if len(row) != 4:
                return jsonify({"error": "Invalid input. Each data point must have 4 features."}), 400

        # Make the prediction
        y_pred_new = model.predict(X_new)

        # Return the prediction as JSON
        return jsonify({"predictions": y_pred_new.tolist()})  # Convert NumPy array to list

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') # Make sure to run on '0.0.0.0' to be accessible externally