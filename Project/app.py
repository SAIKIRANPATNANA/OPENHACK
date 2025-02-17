from flask import Flask, render_template, request, jsonify
import helper
import os
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save the uploaded file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    try:
        # Process the file using helper functions
        parsed_report = helper.get_parsed_report(file_path)
        
        # Generate plots
        helper.create_blood_test_plots(parsed_report, "static/plots")
        
        # Get medical insights
        insights = helper.get_medical_insights_n_recommendataions(parsed_report)

        return jsonify({
            'success': True,
            'report': parsed_report.dict(),
            'insights': insights
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    role = data.get('role')
    parsed_report = data.get('report')
    
    if not all([message, role, parsed_report]):
        return jsonify({'error': 'Please upload a report before starting the chat'}), 400

    try:
        # Convert the report back to the expected format if needed
        if isinstance(parsed_report, str):
            parsed_report = json.loads(parsed_report)
            
        response = helper.get_chat_response(message, role, parsed_report)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 