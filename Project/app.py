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

# Add these custom exceptions at the top of the file
class ParseError(Exception):
    pass

class BloodReportError(Exception):
    pass

class PlotGenerationError(Exception):
    pass

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

# Create the chat chain at module level
system_prompt = """
You are a friendly and concise medical assistant that helps explain blood reports.
Keep your responses brief and conversational, like a natural chat.

For doctors: Provide focused technical insights using medical terminology.
For patients: Use simple language and brief, easy-to-understand explanations.

Blood Report Context:
{blood_report}

Remember:
- Keep responses short and focused (2-3 sentences when possible)
- Be conversational and friendly
- Avoid lengthy explanations unless specifically asked
- If unsure, admit it and suggest consulting a doctor

User Role: {role}
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
])

model = ChatGroq(model_name="gemma2-9b-it", groq_api_key=groq_api_key)

chain = (
    RunnablePassthrough.assign(blood_report=lambda x: x["blood_report"])
    | prompt
    | model
)

with_message_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="messages",
)

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
            print(f"File saved successfully: {file_path}")
        except Exception as e:
            print(f"File save error: {str(e)}")
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

        try:
            # Process the file using helper functions
            print(f"Processing file: {file_path}")
            parsed_report = helper.get_parsed_report(file_path)
            print("Report parsed successfully")

            # Convert Pydantic model to dict for JSON serialization
            report_dict = parsed_report.dict() if hasattr(parsed_report, 'dict') else parsed_report
            
            try:
                print("Generating plots...")
                helper.create_blood_test_plots(parsed_report, "static/plots")
                print("Plots generated successfully")
            except Exception as e:
                print(f"Warning: Plot generation failed: {str(e)}")
            
            print("Getting medical insights...")
            insights = helper.get_medical_insights_n_recommendataions(parsed_report)
            print("Medical insights generated successfully")

            response_data = {
                'success': True,
                'report': report_dict,
                'insights': insights,
            }
            return jsonify(response_data)

        except Exception as e:
            print(f"Error in upload endpoint: {str(e)}")
            return jsonify({'error': f'Failed to process report: {str(e)}'}), 422
        finally:
            # Clean up uploaded file
            try:
                os.remove(file_path)
                print(f"Cleaned up file: {file_path}")
            except Exception as e:
                print(f"Cleanup error: {str(e)}")

    except Exception as e:
        print(f"Server error: {str(e)}")
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

        # Create the user message
        user_message = HumanMessage(content=message)

        try:
            # Generate response using the chain with message history
            response = with_message_history.invoke(
                {
                    "blood_report": parsed_report,
                    "messages": [user_message],
                    "role": role,
                },
                config={"configurable": {"session_id": session_id}},
            )

            if not response:
                return jsonify({'error': 'No response generated'}), 500

            return jsonify({'response': response.content})

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

# Add cleanup for message store on shutdown
def cleanup_message_store():
    """Clean up message store on server shutdown"""
    global message_store
    message_store.clear()

# Register both cleanup functions
atexit.register(cleanup_uploads)
atexit.register(cleanup_message_store)

if __name__ == '__main__':
    app.run(debug=True) 