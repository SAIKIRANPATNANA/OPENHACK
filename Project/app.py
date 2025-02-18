from flask import Flask, render_template, request, jsonify
import helper
import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
import atexit
os.environ['GROQ_API_KEY'] = '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'
groq_api_key = os.getenv("GROQ_API_KEY")
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Add this after other global variables
message_store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in message_store:
        message_store[session_id] = ChatMessageHistory()
    return message_store[session_id]

@app.route('/')
def index():
    return render_template('index.html')

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 16MB'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error occurred'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file type
        allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
        if not '.' in file.filename or \
           file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed types: PDF, JPG, JPEG, PNG'}), 400

        # Save the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        try:
            file.save(file_path)
        except Exception as e:
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

        try:
            # Process the file using helper functions
            parsed_report = helper.get_parsed_report(file_path)
            
            # Generate plots
            plot_results = helper.create_blood_test_plots(parsed_report, "static/plots")
            
            # Get medical insights
            insights = helper.get_medical_insights_n_recommendataions(parsed_report)

            return jsonify({
                'success': True,
                'report': parsed_report.dict(),
                'insights': insights,
                'plot_results': plot_results
            })

        except helper.ParseError as e:
            return jsonify({'error': f'Failed to parse report: {str(e)}'}), 422
        except helper.BloodReportError as e:
            return jsonify({'error': f'Failed to process report: {str(e)}'}), 422
        except helper.PlotGenerationError as e:
            # Continue with partial results if plots fail
            return jsonify({
                'success': True,
                'report': parsed_report.dict(),
                'insights': insights,
                'plot_error': str(e)
            })
        except Exception as e:
            return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
        finally:
            # Clean up uploaded file
            try:
                os.remove(file_path)
            except:
                pass

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400

        # Validate required fields
        required_fields = ['message', 'role', 'report', 'session_id']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

        message = data['message']
        role = data['role']
        parsed_report = data['report']
        session_id = data['session_id']

        # Validate role
        if role not in ['patient', 'doctor']:
            return jsonify({'error': 'Invalid role. Must be either "patient" or "doctor"'}), 400

        # Validate and parse report data
        try:
            if isinstance(parsed_report, str):
                parsed_report = json.loads(parsed_report)
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Invalid report format: {str(e)}'}), 400

        try:
            response = helper.get_chat_response(message, role, parsed_report)
            if not response:
                return jsonify({'error': 'No response generated'}), 500
                
            return jsonify({'response': response})
            
        except Exception as e:
            print(f"Error generating chat response: {str(e)}")
            return jsonify({'error': f'Failed to generate response: {str(e)}'}), 500

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# Add cleanup on shutdown
def cleanup_uploads():
    """Clean up uploaded files on server shutdown"""
    upload_dir = app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            try:
                file_path = os.path.join(upload_dir, filename)
                os.remove(file_path)
            except Exception as e:
                print(f"Error cleaning up {filename}: {e}")

# Register cleanup function
atexit.register(cleanup_uploads)

if __name__ == '__main__':
    app.run(debug=True) 