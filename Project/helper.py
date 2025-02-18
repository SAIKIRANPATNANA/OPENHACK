import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
from PIL import Image
import cv2
import numpy as np
import io,os
import json
import google.generativeai as genai
genai.configure(api_key='AIzaSyAFTm-mUcFxAakOw_qks3luweKHLmGhNlQ')
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.pydantic_v1 import BaseModel, Field
import warnings as warn
warn.filterwarnings("ignore")
from langchain_core.output_parsers import StrOutputParser
from typing import Optional
from langchain_groq import ChatGroq
os.environ['GROQ_API_KEY'] = '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'
groq_api_key = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model_name='deepseek-r1-distill-llama-70b',groq_api_key = groq_api_key)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
import matplotlib.pyplot as plt
import seaborn as sns
import os
from matplotlib.patches import Rectangle

def preprocess_image(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    image = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY)[1]
    processed_path = "/content/preprocessed.jpg"
    cv2.imwrite(processed_path, image)
    return processed_path

def get_parsed_text_using_tesseract(image_path):
    image = Image.open(image_path)
    extracted_text = pytesseract.image_to_string(image)
    return extracted_text

def get_parsed_text_using_pypdf(file_path):
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    extracted_text = "\n".join([doc.page_content for doc in documents])
    return extracted_text

# def get_parsed_text_using_gemini(file_path):
#     try:
#         # raise Exception("Error")
#         # model = genai.GenerativeModel(model_name="gemini-1.5-flash")
#         # file_id = genai.upload_file(path=file_path)
#         # user_input = """
#         # Extract the text from the uploaded blood report file!
#         # """
#         # response = model.generate_content([file_id, user_input])
#         # return response.text
#         if 'pdf' in file_path:
#             return get_parsed_text_using_pypdf(file_path)
#         else:
#             processed_image = preprocess_image(file_path)
#             extracted_text = get_parsed_text_using_tesseract(processed_image)
#             return extracted_text
#     except Exception as e:
#         print(e)

def get_parsed_text_using_gemini(file_path):
    try:
        if 'pdf' in file_path:
            return get_parsed_text_using_pypdf(file_path)
        else:
            model = genai.GenerativeModel(model_name="gemini-1.5-flash")
            file_id = genai.upload_file(path=file_path)
            user_input = """
            Extract the text from the uploaded blood report file!
            """
            response = model.generate_content([file_id, user_input])
            return response.text
    except Exception as e:
        print(e)
        if 'pdf' not in file_path:
            processed_image = preprocess_image(file_path)
            extracted_text = get_parsed_text_using_tesseract(processed_image)
            return extracted_text
        
class LabTestReport(BaseModel):
    patient_info: dict = Field(..., description="Basic details of the patient.")
    lab_info: dict = Field(..., description="Details about the laboratory.")
    test_name: str = Field(..., description="Name of the test performed.")
    lab_results: dict = Field(..., description="Structured representation of blood test results.")
    medical_personnel: dict = Field(..., description="Details of medical professionals who processed the report.")

# structured_llm = llm.with_structured_output(LabTestReport)

def generate_structured_report(llm,parsed_text: str) -> LabTestReport:
    try: 
        structured_llm = llm.with_structured_output(LabTestReport)
        """
        Converts extracted OCR text from a blood report into a structured JSON format.
        """
        prompt_template = f"""
        Given the following extracted blood report text:
        {parsed_text}

        Your Task:
        - Analyze the text carefully and extract the relevant details in a structured manner.
        - Fill the following JSON format with appropriate values from the extracted text.

        Response Format:
        {{
          "patient_info": {{
            "name": "",  # Extract the patient's name
            "age": "",  # Extract the age
            "gender": "",  # Extract gender
            "patient_id": "",  # Extract patient ID if available
            "sample_collected_at": "",  # Extract sample collection location
            "referred_by": "",  # Doctor who referred the test
            "registered_on": "",  # Registration date
            "collected_on": "",  # Sample collection date
            "reported_on": ""  # Date when report was generated
          }},
          "lab_info": {{
            "lab_name": "",  # Extract lab name
            "lab_contact": {{
              "phone": "",  # Extract lab phone number if available
              "email": ""  # Extract lab email if available
            }},
            "lab_address": "",  # Extract full address of the lab
            "website": "",  # Extract website if available
            "instruments": "",  # Instruments used for testing
            "generated_on": ""  # Report generation date
          }},
          "test_name": "",  # Extract the test name
          "lab_results": {{
              "param_name_1": {{
                "value": "",  # Extract parameter value
                "unit": "",  # Extract unit (e.g., g/dL, cells/cumm)
                "reference_range": "",  # Extract reference range
                "status": ""  # Indicate if value is Normal, High, or Low
              }},
              // Like this, extract all available test parameters in the report
          }},
          "medical_personnel": {{
            "medical_lab_technician": "",  # Extract name of lab technician
            "pathologists": [
              {{
                "name": "",  # Extract name of pathologist
                "qualification": ""  # Extract qualification (e.g., MD Pathology)
              }},
              {{
                "name": "",  # Extract name of additional pathologist if available
                "qualification": ""
              }}
            ]
          }}
        }}
        """
        structured_response = structured_llm.invoke(prompt_template)
        return structured_response
    except Exception as e:
        print(e)
        ehr = parsed_text
        llm = ChatGroq(model_name='llama-3.3-70b-versatile',groq_api_key = groq_api_key)
        parsed_report = generate_structured_report(llm,ehr)
        return parsed_report
        

def get_parsed_report(file_path):
  ehr = get_parsed_text_using_gemini(file_path)
  llm = ChatGroq(model_name='deepseek-r1-distill-llama-70b',groq_api_key = groq_api_key)
  parsed_report = generate_structured_report(llm,ehr)
  return parsed_report
  
COLORS = {
    'high': '#FF6B6B',
    'low': '#4ECDC4',
    'range_fill': '#A8E6CF',
    'range_line': '#3D84A8',
    'text': '#2C3E50',
    'grid': '#DAE1E7'
}

def create_blood_test_plots(parsed_report, output_folder="static/plots"):
    try:
        os.makedirs(output_folder, exist_ok=True)

        # Convert Pydantic model to dictionary
        if hasattr(parsed_report, 'dict'):
            blood_results = parsed_report.dict()['lab_results']
        else:
            blood_results = parsed_report.lab_results

        abnormal_params = {k: v for k, v in blood_results.items() if v['status'] != 'Normal'}

        for param, details in abnormal_params.items():
            try:
                # Clean and convert the value
                value_str = str(details['value']).strip()
                value = float(value_str.replace(',', ''))
                
                # Clean and parse reference range
                ref_range = details['reference_range'].strip()
                # Handle different range formats
                if '-' in ref_range:
                    lower, upper = map(lambda x: float(x.strip().replace(',', '')), ref_range.split('-'))
                elif '–' in ref_range:  # Handle en dash
                    lower, upper = map(lambda x: float(x.strip().replace(',', '')), ref_range.split('–'))
                else:
                    print(f"Skipping {param}: Invalid range format - {ref_range}")
                    continue

                unit = details['unit']

                # Create the plot
                fig, ax = plt.subplots(figsize=(10, 6))
                fig.patch.set_facecolor('white')
                ax.set_facecolor('#F8FBFF')

                rect = Rectangle((0.7, lower), 0.6, upper-lower,
                            facecolor='#A8E6CF',
                            alpha=0.3,
                            label='Reference Range')
                ax.add_patch(rect)

                is_high = value > upper
                point_color = '#FF6B6B' if is_high else '#4ECDC4'

                for alpha in [0.1, 0.2, 0.3]:
                    ax.scatter(1, value,
                             s=300 + (1-alpha)*200,
                             color=point_color,
                             alpha=alpha,
                             zorder=4)

                scatter = ax.scatter(1, value,
                                   s=200,
                                   color=point_color,
                                   marker='o',
                                   edgecolor='white',
                                   linewidth=2,
                                   zorder=5,
                                   label=f"Result: {value} {unit}")

                if is_high:
                    ax.vlines(x=1, ymin=upper, ymax=value,
                            colors=point_color,
                            linestyles='--',
                            alpha=0.6,
                            linewidth=2)
                else:
                    ax.vlines(x=1, ymin=value, ymax=lower,
                            colors=point_color,
                            linestyles='--',
                            alpha=0.6,
                            linewidth=2)

                ax.set_xlim(0.5, 1.5)
                ax.set_ylim(min(lower * 0.9, value * 0.9),
                           max(upper * 1.1, value * 1.1))

                ax.set_xticks([])

                for y in [lower, upper]:
                    ax.axhline(y=y,
                              color='#3D84A8',
                              linestyle='--',
                              alpha=0.4,
                              linewidth=2)

                for y, label in [(lower, 'Lower'), (upper, 'Upper')]:
                    ax.text(0.6, y, f'{label}: {y}',
                            verticalalignment='bottom',
                            horizontalalignment='right',
                            fontsize=10,
                            color='white',
                            bbox=dict(facecolor='#3D84A8',
                                    alpha=0.7,
                                    pad=3,
                                    boxstyle='round,pad=0.5'))

                ax.grid(True, axis='y', linestyle=':', alpha=0.2, color='#DAE1E7')

                plt.title(f"{param} Test Result",
                         pad=20,
                         fontsize=16,
                         fontweight='bold',
                         color='#2C3E50')
                         
                plt.ylabel(f"Value ({unit})",
                          fontsize=12,
                          color='#2C3E50')

                status_color = '#FF6B6B' if is_high else '#4ECDC4'
                status_text = 'HIGH' if is_high else 'LOW'

                bbox_props = dict(boxstyle="round,pad=0.5",
                                fc=status_color,
                                ec="white",
                                alpha=0.8)
                                
                plt.text(0.98, 0.02, status_text,
                        transform=ax.transAxes,
                        color='white',
                        fontsize=12,
                        fontweight='bold',
                        bbox=bbox_props,
                        horizontalalignment='right',
                        verticalalignment='bottom')

                legend = plt.legend(loc="upper right",
                                  fontsize=10,
                                  framealpha=0.95,
                                  shadow=True)
                legend.get_frame().set_facecolor('white')
                legend.get_frame().set_edgecolor('#3D84A8')

                for spine in ax.spines.values():
                    spine.set_edgecolor('#3D84A8')
                    spine.set_linewidth(1.5)

                plt.tight_layout()

                # Save the plot
                save_path = os.path.join(output_folder, f"{param.replace(' ', '_')}.png")
                plt.savefig(save_path,
                           bbox_inches="tight",
                           dpi=300,
                           facecolor='white',
                           edgecolor='none')
                plt.close()
                
                print(f"Successfully created plot for {param}")
                
            except Exception as param_error:
                print(f"Error creating plot for {param}: {str(param_error)}")
                continue

    except Exception as e:
        print(f"Error in create_blood_test_plots: {str(e)}")
        raise Exception(f"Failed to create plots: {str(e)}")

def get_medical_insights_n_recommendataions(parsed_report):
  class ParameterRecommendation(BaseModel):
      parameter: str = Field(..., description="Name of the abnormal blood test parameter.")
      status: str = Field(..., description="Indicates whether the parameter is high or low.")
      possible_disease: list = Field(..., description="Possible health effects.")
      possible_causes: list = Field(..., description="Possible reasons for the abnormality.")
      dietary_suggestions: list = Field(..., description="Recommended foods to normalize levels.")
      lifestyle_changes: list = Field(..., description="Exercise, hydration, and other lifestyle recommendations.")
      medical_advice: str = Field(..., description="When to consult a doctor or take further medical action.")
  class HealthInsights(BaseModel):
      abnormal_parameters: list[ParameterRecommendation] = Field(..., description="List of insights for all abnormal parameters.")
  llm = ChatGroq(model_name='deepseek-r1-distill-llama-70b',groq_api_key = groq_api_key)
  structured_llm = llm.with_structured_output(HealthInsights)
  def generate_health_recommendations_n_insights(abnormal_results: dict):
      """
      Generates insights & recommendations for all abnormal blood parameters in a single call.
      """
      formatted_params = "\n".join([f"- {param}: {status}" for param, status in abnormal_results.items()])
      prompt_template = f"""
      The following blood test parameters are abnormal:
      {formatted_params}
      For each abnormal parameter, generate structured health insights in the following format:
      {{
        "abnormal_parameters": [
          {{
            "parameter": "Parameter Name",
            "status": "High/Low",
            "possible_disease": ["List possible health conditions"],
            "possible_causes": ["List of possible reasons"],
            "dietary_suggestions": ["Foods to normalize levels"],
            "lifestyle_changes": ["Exercise, hydration, sleep recommendations"],
            "medical_advice": "When to consult a doctor?"
          }}
        ]
      }}
      """
      structured_response = structured_llm.invoke(prompt_template)
      return structured_response.dict()
  blood_results = parsed_report.lab_results
  abnormal_results = abnormal_results = {param: details['status'] for param, details in blood_results.items() if details['status'] != "Normal"}
  recommendations_n_insights = generate_health_recommendations_n_insights(abnormal_results)
  # print(json.dumps(recommendations_n_insights, indent=2))
  return recommendations_n_insights

def get_chat_response(message: str, role: str, parsed_report: dict) -> str:
    """
    Generate a chat response based on the user's message, role, and report context.
    """
    try:
        # Initialize the LLM
        llm = ChatGroq(model_name='gemma2-9b-it', groq_api_key=groq_api_key)
        
        # Create a more structured and focused prompt
        system_prompt = """You are a helpful medical assistant analyzing a blood test report. 
        Role: {role}
        Instructions:
        - For patients: Use simple, clear language without medical jargon
        - For doctors: You may use technical medical terminology
        
        Blood Report Summary:
        - Patient Details: {patient_info}
        - Test Name: {test_name}
        - Lab Results: {lab_results}
        
        Please provide relevant, accurate information based on this report and the user's question.
        Focus on explaining:
        1. Abnormal values and their significance
        2. Overall health implications
        3. Any recommended follow-up actions
        
        If you're unsure about something, please say so."""

        # Format the report data for the prompt
        context = {
            'role': role,
            'patient_info': parsed_report.get('patient_info', {}),
            'test_name': parsed_report.get('test_name', 'Blood Test'),
            'lab_results': parsed_report.get('lab_results', {})
        }

        # Create the chat prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", f"Question: {message}")
        ])

        # Generate the response
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke(context)

        return response

    except Exception as e:
        # Provide a more helpful error message
        if 'missing variables' in str(e):
            return "I'm having trouble reading the report data. Please make sure a report has been uploaded and try again."
        return f"I apologize, but I encountered an error: {str(e)}. Please try rephrasing your question."

